select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
    



select date
from "weather_db"."public_marts"."mart_combined_daily"
where date is null



      
    ) dbt_internal_test