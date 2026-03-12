select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
    



select measured_at
from "weather_db"."public_staging"."stg_weather"
where measured_at is null



      
    ) dbt_internal_test