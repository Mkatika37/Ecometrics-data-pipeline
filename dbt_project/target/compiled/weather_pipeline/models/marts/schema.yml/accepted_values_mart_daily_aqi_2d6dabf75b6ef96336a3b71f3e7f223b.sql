
    
    

with all_values as (

    select
        pollutant_type as value_field,
        count(*) as n_records

    from "weather_db"."public_marts"."mart_daily_aqi"
    group by pollutant_type

)

select *
from all_values
where value_field not in (
    'PM25','PM10','O3','NO2','CO','SO2'
)


