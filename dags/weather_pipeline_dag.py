from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from dags.utils.pipeline_monitor import check_api_health, validate_table_has_data
from dags.utils.pipeline_monitor import log_pipeline_summary, handle_pipeline_failure

default_args = {
    'owner': 'de_student',
    'depends_on_past': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'email_on_failure': False,
    'email_on_retry': False,
}

def run_fetch_weather():
    from ingestion.fetch_weather import main
    main()

def run_fetch_aqi():
    from ingestion.fetch_aqi import main
    main()

with DAG(
    dag_id='weather_aqi_pipeline',
    default_args=default_args,
    schedule_interval='0 8 * * *',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['weather', 'aqi', 'pyspark', 'portfolio'],
    on_success_callback=log_pipeline_summary,
    on_failure_callback=handle_pipeline_failure,
    description='Daily weather and AQI data pipeline'
) as dag:

    check_api_health_task = PythonOperator(
        task_id='check_api_health',
        python_callable=lambda: check_api_health([
            "https://api.open-meteo.com/v1/forecast?latitude=40.71&longitude=-74.00&hourly=temperature_2m",
            "https://api.waqi.info/feed/new%20york/?token=demo"
        ])
    )

    fetch_weather_task = PythonOperator(
        task_id='fetch_weather_data',
        python_callable=run_fetch_weather
    )

    fetch_aqi_task = PythonOperator(
        task_id='fetch_aqi_data',
        python_callable=run_fetch_aqi
    )

    validate_data_task = PythonOperator(
        task_id='validate_raw_data',
        python_callable=lambda: validate_table_has_data("raw.weather_hourly", 1) and validate_table_has_data("raw.air_quality", 1)
    )

    run_dbt_staging_task = BashOperator(
        task_id='run_dbt_staging',
        bash_command='cd /opt/airflow/dbt_project && dbt run --select staging'
    )

    run_dbt_marts_task = BashOperator(
        task_id='run_dbt_marts',
        bash_command='cd /opt/airflow/dbt_project && dbt run --select marts'
    )

    run_dbt_tests_task = BashOperator(
        task_id='run_dbt_tests',
        bash_command='cd /opt/airflow/dbt_project && dbt test'
    )

    # Setup dependencies
    check_api_health_task >> fetch_weather_task
    check_api_health_task >> fetch_aqi_task
    fetch_weather_task >> validate_data_task
    fetch_aqi_task >> validate_data_task
    validate_data_task >> run_dbt_staging_task
    run_dbt_staging_task >> run_dbt_marts_task
    run_dbt_marts_task >> run_dbt_tests_task
