-- Staging model: cleans raw air quality data from OpenAQ API

SELECT
    id,
    CAST(timestamp AS TIMESTAMP) AS measured_at,
    UPPER(TRIM(city)) AS city_name,
    UPPER(parameter) AS pollutant_type,
    ROUND(CAST(value AS NUMERIC), 2) AS measurement_value,
    unit,
    TRIM(location) AS station_name,
    CURRENT_TIMESTAMP AS loaded_at
FROM {{ source('raw', 'air_quality') }}
WHERE value IS NOT NULL
  AND value >= 0
  AND timestamp IS NOT NULL
