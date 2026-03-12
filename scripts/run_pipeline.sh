#!/bin/bash

# Function to handle error reporting
handle_error() {
    echo "❌ ERROR: Pipeline failed at step: $1"
    exit 1
}

echo "Starting Weather & AQI Pipeline..."

echo "Step 1: Starting Docker containers..."
if ! docker-compose up -d; then
    handle_error "docker-compose up"
fi
echo "Waiting 15 seconds for containers to initialize..."
sleep 15
echo "Containers started"

echo "Step 2: Creating database tables..."
if ! python ingestion/create_tables.py; then
    handle_error "create tables"
fi
echo "Tables created"

echo "Step 3: Fetching and loading weather data..."
if ! python ingestion/fetch_weather.py; then
    handle_error "fetch weather"
fi
echo "Weather data loaded"

echo "Step 4: Fetching and loading AQI data..."
if ! python ingestion/fetch_aqi.py; then
    handle_error "fetch AQI"
fi
echo "AQI data loaded"

echo "Step 5: Running dbt models and tests..."
if ! (cd dbt_project && dbt run && dbt test); then
    handle_error "dbt run and test"
fi
echo "dbt models built and tested"

echo "Pipeline complete! Open http://localhost:3000 for dashboard"
