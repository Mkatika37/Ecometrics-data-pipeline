select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
    



select humidity_pct
from "weather_db"."public_staging"."stg_weather"
where humidity_pct is null



      
    ) dbt_internal_test