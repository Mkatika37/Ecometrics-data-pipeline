-- Staging model: cleans raw weather data from Open-Meteo API

SELECT
    id,
    CAST(timestamp AS TIMESTAMP) AS measured_at,
    UPPER(TRIM(city)) AS city_name,
    ROUND(CAST(temperature AS NUMERIC), 2) AS temperature_celsius,
    ROUND(CAST(humidity AS NUMERIC), 2) AS humidity_pct,
    ROUND(CAST(windspeed AS NUMERIC), 2) AS windspeed_kmh,
    ROUND(CAST(precipitation AS NUMERIC), 2) AS precipitation_mm,
    CURRENT_TIMESTAMP AS loaded_at
FROM {{ source('raw', 'weather_hourly') }}
WHERE temperature IS NOT NULL
  AND timestamp IS NOT NULL
