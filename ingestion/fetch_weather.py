import os
import platform
if platform.system() == "Windows":
    os.environ['JAVA_HOME'] = "C:/Program Files/Eclipse Adoptium/jdk-17.0.18.8-hotspot"
    os.environ['HADOOP_HOME'] = "C:/hadoop"
    os.environ['PYSPARK_PYTHON'] = "python"

import requests
import logging
from dotenv import load_dotenv
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, TimestampType
from pyspark.sql.functions import col, lit, round

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fetch_weather_json():
    """Fetches hourly weather data from Open-Meteo API."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": 40.7128,
        "longitude": -74.0060,
        "hourly": "temperature_2m,relative_humidity_2m,windspeed_10m,precipitation",
        "timezone": "America/New_York",
        "past_days": 7
    }
    
    logger.info(f"Fetching weather data from: {url}")
    
    try:
        response = requests.get(url, params=params, timeout=30)
        logger.info(f"Response status code: {response.status_code}")
        
        response.raise_for_status()  # Raises HttpError if status code != 200
        
        return response.json()
        
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        raise
    except Exception as err:
        logger.error(f"Other error occurred: {err}")
        raise

def transform_weather_with_spark(json_data: dict):
    """Transforms raw JSON weather data into a PySpark DataFrame."""
    app_name = os.getenv("SPARK_APP_NAME", "WeatherPipeline")
    master = os.getenv("SPARK_MASTER", "local[*]")
    
    hadoop_home = "C:/hadoop" if platform.system() == "Windows" else "/opt/hadoop"
    jdbc_jar = "lib/postgresql-42.7.1.jar" if platform.system() == "Windows" else ""
    
    builder = SparkSession.builder \
        .appName("WeatherPipeline") \
        .master("local[*]") \
        .config("spark.driver.host", "localhost") \
        .config("spark.driver.bindAddress", "127.0.0.1") \
        .config("spark.sql.shuffle.partitions", "2") \
        .config("spark.driver.memory", "1g") \
        .config("spark.hadoop.hadoop.home.dir", hadoop_home) \
        .config("spark.sql.execution.arrow.pyspark.enabled", "false")
    
    if jdbc_jar:
        builder = builder.config("spark.jars", jdbc_jar)
    
    spark = builder.getOrCreate()
        
    spark.sparkContext.setLogLevel("ERROR")
        
    hourly = json_data.get('hourly', {})
    times = hourly.get('time', [])
    temps = hourly.get('temperature_2m', [])
    humidity = hourly.get('relative_humidity_2m', [])
    windspeed = hourly.get('windspeed_10m', [])
    precipitation = hourly.get('precipitation', [])
    
    # Zip all lists into a list of tuples and cast variables to explicit float types beforehand
    rows = [
        (
            str(t),
            float(temp) if temp is not None else None,
            float(hum) if hum is not None else None,
            float(wind) if wind is not None else None,
            float(precip) if precip is not None else None,
        )
        for t, temp, hum, wind, precip in zip(times, temps, humidity, windspeed, precipitation)
    ]
    
    # Define schema
    schema = StructType([
        StructField("timestamp", StringType(), True),
        StructField("temperature", DoubleType(), True),
        StructField("humidity", DoubleType(), True),
        StructField("windspeed", DoubleType(), True),
        StructField("precipitation", DoubleType(), True)
    ])
    
    # Create DataFrame
    df = spark.createDataFrame(rows, schema)
    
    # Apply transformations
    df = df.withColumn("timestamp", col("timestamp").cast(TimestampType())) \
           .withColumn("temperature", round(col("temperature"), 2)) \
           .withColumn("humidity", round(col("humidity"), 2)) \
           .withColumn("windspeed", round(col("windspeed"), 2)) \
           .withColumn("precipitation", round(col("precipitation"), 2)) \
           .withColumn("city", lit("NEW YORK")) \
           .dropna(subset=["temperature"])
           
    return df

def load_weather_to_postgres(df):
    from ingestion.db_connection import get_psycopg2_connection
    import logging

    rows = df.collect()

    conn = get_psycopg2_connection()
    cursor = conn.cursor()

    upsert_sql = """
        INSERT INTO raw.weather_hourly
            (timestamp, city, temperature, humidity, windspeed, precipitation)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (timestamp, city)
        DO UPDATE SET
            temperature = EXCLUDED.temperature,
            humidity = EXCLUDED.humidity,
            windspeed = EXCLUDED.windspeed,
            precipitation = EXCLUDED.precipitation
    """

    success_count = 0
    for row in rows:
        try:
            cursor.execute(upsert_sql, (
                row["timestamp"],
                row["city"],
                row["temperature"],
                row["humidity"],
                row["windspeed"],
                row["precipitation"]
            ))
            success_count += 1
        except Exception as e:
            logging.warning(f"Skipping row: {e}")
            conn.rollback()
            continue

    conn.commit()
    cursor.close()
    conn.close()
    logging.info(f"Successfully upserted {success_count} rows to raw.weather_hourly")

def main():
    """Main execution pipeline."""
    try:
        # 1. Fetch
        raw_data = fetch_weather_json()
        
        # 2. Transform
        transformed_df = transform_weather_with_spark(raw_data)
        
        # 3. Load
        load_weather_to_postgres(transformed_df)
        
        logger.info("Pipeline completed successfully!")
    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}")

if __name__ == "__main__":
    main()
