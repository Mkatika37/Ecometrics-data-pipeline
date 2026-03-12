import os
import platform
if platform.system() == "Windows":
    os.environ['JAVA_HOME'] = "C:/Program Files/Eclipse Adoptium/jdk-17.0.18.8-hotspot"
    os.environ['HADOOP_HOME'] = "C:/hadoop"
    os.environ['PYSPARK_PYTHON'] = "python"

import logging
import requests
from dotenv import load_dotenv
from datetime import datetime, timedelta
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, DoubleType
from pyspark.sql.functions import col, to_timestamp, upper, trim, round

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fetch_aqi_json():
    """Fetches air quality data from WAQI API."""
    token = os.getenv("WAQI_TOKEN", "")
    if not token:
        logger.warning("WAQI_TOKEN not set in .env file")
        return {}

    cities = ["new york", "los-angeles", "chicago"]
    all_results = []

    for city in cities:
        url = f"https://api.waqi.info/feed/{city}/?token={token}"
        try:
            response = requests.get(url, timeout=30)
            if response.status_code != 200:
                logger.warning(f"Failed for {city}: {response.status_code}")
                continue

            data = response.json()
            if data.get("status") != "ok":
                logger.warning(f"Bad status for {city}: {data.get('status')}")
                continue

            d = data["data"]
            time_str = d["time"]["s"]
            city_name = city.upper().replace("-", " ")
            iaqi = d.get("iaqi", {})

            pollutants = {
                "PM25": iaqi.get("pm25", {}).get("v"),
                "PM10": iaqi.get("pm10", {}).get("v"),
                "O3":   iaqi.get("o3",   {}).get("v"),
                "NO2":  iaqi.get("no2",  {}).get("v"),
            }

            for pollutant, value in pollutants.items():
                if value is not None:
                    all_results.append({
                        "timestamp": time_str,
                        "value": float(value),
                        "pollutant_type": pollutant,
                        "city_name": city_name,
                        "station_name": d.get("city", {}).get("name", city_name),
                        "unit": "µg/m³"
                    })

        except Exception as e:
            logger.warning(f"Error fetching {city}: {e}")
            continue

    logger.info(f"Total AQI records fetched: {len(all_results)}")
    return {"results": all_results}

def transform_aqi_with_spark(json_data: dict):
    """Transforms raw JSON AQI data into a cleaned PySpark DataFrame."""
    # 1. Creates SparkSession with appName: AQIPipeline
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
    
    schema = StructType([
        StructField("timestamp", StringType(), True),
        StructField("value", DoubleType(), True),
        StructField("pollutant_type", StringType(), True),
        StructField("city_name", StringType(), True),
        StructField("station_name", StringType(), True),
        StructField("unit", StringType(), True)
    ])
    
    # 2. If json_data is empty or has no results, return empty DataFrame with schema and log a warning
    if not json_data or "results" not in json_data or not json_data["results"]:
        logger.warning("Empty JSON data provided or no results. Returning empty DataFrame.")
        return spark.createDataFrame([], schema)
        
    # 3. Extracts results list from json_data['results']
    results = json_data["results"]
    
    rows = []
    for r in results:
        try:
            rows.append((
                str(r["timestamp"]),
                float(r["value"]),
                str(r["pollutant_type"]).upper(),
                str(r["city_name"]).upper().strip(),
                str(r["station_name"]).strip(),
                str(r["unit"])
            ))
        except (KeyError, TypeError):
            continue
    
    # 4. Converts list of tuples to PySpark DataFrame
    df = spark.createDataFrame(rows, schema)
    
    # 5. Native PySpark transformations with explicit timestamp casting
    clean_df = df.withColumn("timestamp", to_timestamp(col("timestamp"), "yyyy-MM-dd HH:mm:ss")) \
           .withColumn("pollutant_type", upper(trim(col("pollutant_type")))) \
           .withColumn("city_name", upper(trim(col("city_name")))) \
           .withColumn("station_name", trim(col("station_name"))) \
           .filter(col("value").isNotNull()) \
           .filter(col("value") >= 0) \
           .filter(col("timestamp").isNotNull()) \
           .withColumnRenamed("city_name", "city") \
           .withColumnRenamed("pollutant_type", "parameter") \
           .withColumnRenamed("station_name", "location")
    
    # 7. Returns cleaned DataFrame
    return clean_df

def load_aqi_to_postgres(df):
    from ingestion.db_connection import get_psycopg2_connection
    import logging

    if df is None or df.count() == 0:
        logging.warning("No AQI data to load")
        return

    # Convert Spark DataFrame to Python list of tuples
    rows = df.collect()

    conn = get_psycopg2_connection()
    cursor = conn.cursor()

    upsert_sql = """
        INSERT INTO raw.air_quality 
            (timestamp, city, location, parameter, value, unit)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (timestamp, city, parameter, location)
        DO UPDATE SET
            value = EXCLUDED.value,
            unit = EXCLUDED.unit
    """

    success_count = 0
    for row in rows:
        try:
            cursor.execute(upsert_sql, (
                row["timestamp"],
                row["city"],
                row["location"],
                row["parameter"],
                row["value"],
                row["unit"]
            ))
            success_count += 1
        except Exception as e:
            logging.warning(f"Skipping row due to error: {e}")
            conn.rollback()
            continue

    conn.commit()
    cursor.close()
    conn.close()
    logging.info(f"Successfully upserted {success_count} rows to raw.air_quality")

def main():
    """Main execution pipeline."""
    try:
        # Calls fetch_aqi_json()
        raw_data = fetch_aqi_json()
        
        # Calls transform_aqi_with_spark()
        transformed_df = transform_aqi_with_spark(raw_data)
        
        # Calls load_aqi_to_postgres()
        load_aqi_to_postgres(transformed_df)
        
        # Logs success or failure clearly
        logger.info("AQI Pipeline completed successfully!")
    except Exception as e:
        logger.error(f"AQI Pipeline failed: {str(e)}")

if __name__ == "__main__":
    main()
