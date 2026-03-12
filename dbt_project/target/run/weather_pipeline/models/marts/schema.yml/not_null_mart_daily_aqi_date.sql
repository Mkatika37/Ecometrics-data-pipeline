select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
    



select date
from "weather_db"."public_marts"."mart_daily_aqi"
where date is null



      
    ) dbt_internal_test