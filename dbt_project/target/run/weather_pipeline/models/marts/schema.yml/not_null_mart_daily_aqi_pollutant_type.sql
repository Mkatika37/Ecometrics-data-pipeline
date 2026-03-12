select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
    



select pollutant_type
from "weather_db"."public_marts"."mart_daily_aqi"
where pollutant_type is null



      
    ) dbt_internal_test