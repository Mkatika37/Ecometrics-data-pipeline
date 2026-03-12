import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def verify_data():
    tables_to_check = [
        ("raw.weather_hourly", 1),
        ("raw.air_quality", 1),
        ("public_staging.stg_weather", 0),
        ("public_staging.stg_air_quality", 0),
        ("public_marts.mart_daily_weather", 0),
        ("public_marts.mart_daily_aqi", 0),
        ("public_marts.mart_combined_daily", 0),
    ]

    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            dbname=os.getenv("DB_NAME", "weather_db"),
            user=os.getenv("DB_USER", "de_user"),
            password=os.getenv("DB_PASSWORD", "de_password")
        )
        cursor = conn.cursor()

        print("\n--- Data Verification Results ---")
        for table, _ in tables_to_check:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table};")
                count = cursor.fetchone()[0]
                
                if count > 0:
                    print(f"✅ {table:<30} → {count} rows")
                else:
                    print(f"❌ {table:<30} → 0 rows (warn if empty)")
            except psycopg2.Error as e:
                # Rollback transaction block on error (e.g., table doesn't exist)
                conn.rollback()
                print(f"❌ {table:<30} → ERROR: {str(e).strip()}")

    except psycopg2.Error as e:
        print(f"Database connection failed: {e}")
    finally:
        if 'conn' in locals() and conn is not None:
            cursor.close()
            conn.close()

if __name__ == "__main__":
    verify_data()
