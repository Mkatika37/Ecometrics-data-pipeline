
  
    

  create  table "weather_db"."public_marts"."mart_daily_weather__dbt_tmp"
  
  
    as
  
  (
    -- Mart: daily weather aggregations for dashboard

SELECT
    DATE_TRUNC('day', measured_at) AS date,
    city_name,
    ROUND(AVG(temperature_celsius), 2) AS avg_temperature,
    ROUND(MAX(temperature_celsius), 2) AS max_temperature,
    ROUND(MIN(temperature_celsius), 2) AS min_temperature,
    ROUND(AVG(humidity_pct), 2) AS avg_humidity,
    ROUND(AVG(windspeed_kmh), 2) AS avg_windspeed,
    ROUND(SUM(precipitation_mm), 2) AS total_precipitation,
    COUNT(*) AS hourly_readings
FROM "weather_db"."public_staging"."stg_weather"
GROUP BY DATE_TRUNC('day', measured_at), city_name
ORDER BY date DESC
  );
  