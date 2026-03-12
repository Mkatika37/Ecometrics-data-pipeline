-- Mart: daily air quality aggregations per pollutant

SELECT
    DATE_TRUNC('day', measured_at) AS date,
    city_name,
    pollutant_type,
    ROUND(AVG(measurement_value), 2) AS avg_value,
    ROUND(MAX(measurement_value), 2) AS max_value,
    ROUND(MIN(measurement_value), 2) AS min_value,
    COUNT(*) AS reading_count
FROM "weather_db"."public_staging"."stg_air_quality"
GROUP BY DATE_TRUNC('day', measured_at), city_name, pollutant_type
ORDER BY date DESC, pollutant_type