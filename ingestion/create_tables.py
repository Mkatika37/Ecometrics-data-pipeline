import psycopg2
from db_connection import get_psycopg2_connection

def create_tables():
    """Create schemas and tables in the database."""
    conn = None
    cursor = None
    try:
        # 1. Connects using get_psycopg2_connection() from db_connection.py
        conn = get_psycopg2_connection()
        cursor = conn.cursor()

        # 2. Creates schema raw if not exists
        cursor.execute("CREATE SCHEMA IF NOT EXISTS raw;")
        conn.commit()

        # 3. Creates table raw.weather_hourly if not exists
        create_weather_hourly_query = """
            CREATE TABLE IF NOT EXISTS raw.weather_hourly (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                city VARCHAR(100) NOT NULL,
                temperature FLOAT,
                humidity FLOAT,
                windspeed FLOAT,
                precipitation FLOAT,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE (timestamp, city)
            );
        """
        cursor.execute(create_weather_hourly_query)
        conn.commit()
        print("Tables created successfully") # 5. Prints after each table

        # 4. Creates table raw.air_quality if not exists
        create_air_quality_query = """
            CREATE TABLE IF NOT EXISTS raw.air_quality (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                city VARCHAR(100) NOT NULL,
                location VARCHAR(200),
                parameter VARCHAR(50),
                value FLOAT,
                unit VARCHAR(20),
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE (timestamp, city, parameter, location)
            );
        """
        cursor.execute(create_air_quality_query)
        conn.commit()
        print("Tables created successfully") # 5. Prints after each table

    except Exception as e:
        print(f"Failed to create schema or tables: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    create_tables()
