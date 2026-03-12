-- Mart: combined weather + PM2.5 for main dashboard

SELECT
    w.date,
    w.city_name,
    w.avg_temperature,
    w.max_temperature,
    w.min_temperature,
    w.total_precipitation,
    w.avg_humidity,
    w.avg_windspeed,
    a.avg_value AS avg_pm25,
    a.max_value AS max_pm25
FROM {{ ref('mart_daily_weather') }} w
LEFT JOIN {{ ref('mart_daily_aqi') }} a
  ON w.date = a.date
  AND w.city_name = a.city_name
  AND a.pollutant_type = 'PM25'
ORDER BY w.date DESC
