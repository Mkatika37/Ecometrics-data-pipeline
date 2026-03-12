select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
    



select avg_temperature
from "weather_db"."public_marts"."mart_daily_weather"
where avg_temperature is null



      
    ) dbt_internal_test