import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Ensure the root project directory is in the path for module importing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ingestion.db_connection import test_connection
from ingestion.fetch_weather import fetch_weather_json, transform_weather_with_spark

@patch('ingestion.db_connection.get_psycopg2_connection')
def test_db_connection_returns_true(mock_get_conn):
    """Test that the database connection checker returns True on success."""
    mock_conn = MagicMock()
    mock_get_conn.return_value = mock_conn
    
    assert test_connection() is True

@patch('ingestion.fetch_weather.requests.get')
def test_fetch_weather_returns_dict(mock_get):
    """Test the fetch operation retrieves dictionary structured JSON payload."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'hourly': {
            'time': ['2023-01-01T00:00'] * 10,
            'temperature_2m': [10.5] * 10,
            'relative_humidity_2m': [50.0] * 10,
            'windspeed_10m': [5.0] * 10,
            'precipitation': [0.0] * 10
        }
    }
    mock_get.return_value = mock_response
    
    result = fetch_weather_json()
    
    assert isinstance(result, dict)
    assert 'hourly' in result
    assert len(result['hourly']['time']) == 10

@pytest.fixture
def sample_weather_data():
    """Provides standard mock API json formatted payload."""
    return {
        'hourly': {
            'time': ['2023-01-01T00:00', '2023-01-01T01:00'],
            'temperature_2m': [15.5, 16.0],
            'relative_humidity_2m': [60.5, 62.1],
            'windspeed_10m': [10.2, 11.5],
            'precipitation': [0.0, 1.2]
        }
    }

def test_weather_dataframe_has_correct_columns(sample_weather_data):
    """Test that Spark processes correct dataframe headers including 'city'."""
    df = transform_weather_with_spark(sample_weather_data)
    expected_columns = ['timestamp', 'temperature', 'humidity', 'windspeed', 'precipitation', 'city']
    
    assert all(col in df.columns for col in expected_columns)
    assert df.count() > 0

def test_weather_dataframe_no_null_temperature(sample_weather_data):
    """Test that the transform automatically filters out rows with Null temperatures."""
    # Append a row with a null temperature to test filtering behavior
    sample_weather_data['hourly']['time'].append('2023-01-01T02:00')
    sample_weather_data['hourly']['temperature_2m'].append(None)
    sample_weather_data['hourly']['relative_humidity_2m'].append(50.0)
    sample_weather_data['hourly']['windspeed_10m'].append(5.0)
    sample_weather_data['hourly']['precipitation'].append(0.0)
    
    df = transform_weather_with_spark(sample_weather_data)
    
    null_temps = df.filter(df.temperature.isNull()).count()
    assert null_temps == 0
