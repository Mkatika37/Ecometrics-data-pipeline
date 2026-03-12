select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
    



select city_name
from "weather_db"."public_staging"."stg_air_quality"
where city_name is null



      
    ) dbt_internal_test