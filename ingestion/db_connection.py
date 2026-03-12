import os
import psycopg2
from sqlalchemy import create_engine
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_psycopg2_connection():
    """Returns a psycopg2 database connection object."""
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD")
        )
        return conn
    except Exception as e:
        raise Exception(f"Failed to connect to the database via psycopg2: {str(e)}")

def get_sqlalchemy_engine():
    """Returns a SQLAlchemy engine."""
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    dbname = os.getenv("DB_NAME")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    
    # Format the connection string
    connection_string = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"
    return create_engine(connection_string)

def create_raw_schema():
    """Creates the 'raw' schema if it does not already exist."""
    conn = None
    try:
        conn = get_psycopg2_connection()
        cursor = conn.cursor()
        cursor.execute("CREATE SCHEMA IF NOT EXISTS raw")
        conn.commit()
        cursor.close()
        print("Schema 'raw' created or already exists")
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Failed to create schema: {str(e)}")
    finally:
        if conn:
            conn.close()

def test_connection():
    """Tests the database connection using psycopg2."""
    conn = None
    try:
        conn = get_psycopg2_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        print("Connection successful!")
        return True
    except Exception as e:
        print(f"Connection failed: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    test_connection()
