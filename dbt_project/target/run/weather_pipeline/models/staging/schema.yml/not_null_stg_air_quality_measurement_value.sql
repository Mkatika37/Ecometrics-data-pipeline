select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
    



select measurement_value
from "weather_db"."public_staging"."stg_air_quality"
where measurement_value is null



      
    ) dbt_internal_test