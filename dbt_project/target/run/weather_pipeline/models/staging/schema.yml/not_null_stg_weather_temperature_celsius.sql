select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
    



select temperature_celsius
from "weather_db"."public_staging"."stg_weather"
where temperature_celsius is null



      
    ) dbt_internal_test