import os
import requests
import psycopg2
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_api_health(urls: list) -> bool:
    """Checks the health of the given API URLs."""
    all_passed = True
    for url in urls:
        try:
            response = requests.get(url, timeout=10)
            logger.info(f"Health check for {url}: Status {response.status_code}")
            if response.status_code != 200:
                logger.warning(f"URL {url} returned non-200 status: {response.status_code}")
                all_passed = False
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to check health for {url}: {str(e)}")
            all_passed = False
    return all_passed

def validate_table_has_data(table_name: str, min_rows: int = 1) -> int:
    """Validates that a PostgreSQL table has at least the specified number of rows."""
    conn = None
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            dbname=os.getenv("DB_NAME", "weather_db"),
            user=os.getenv("DB_USER", "de_user"),
            password=os.getenv("DB_PASSWORD", "de_password")
        )
        cursor = conn.cursor()
        
        # Safe string formatting assuming table_name is statically supplied by pipeline author
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        
        if count < min_rows:
            raise ValueError(f"Table validation failed for {table_name}: Found {count} rows, expected at least {min_rows}.")
            
        logger.info(f"Table {table_name} validation passed with {count} rows.")
        return count
    except psycopg2.Error as e:
        logger.error(f"Database error during validation: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()

def log_pipeline_summary(context):
    """Airflow on_success_callback to log pipeline summary."""
    dag_run = context.get('dag_run')
    if dag_run:
        execution_date = dag_run.execution_date
        dag_id = dag_run.dag_id
        duration = dag_run.end_date - dag_run.start_date if dag_run.end_date and dag_run.start_date else None
        
        logger.info("="*40)
        logger.info("PIPELINE SUCCESS SUMMARY")
        logger.info("="*40)
        logger.info(f"DAG ID: {dag_id}")
        logger.info(f"Execution Date: {execution_date}")
        logger.info(f"Run Duration: {duration}")
        logger.info("="*40)

def handle_pipeline_failure(context):
    """Airflow on_failure_callback to log pipeline failure details and alert Slack."""
    task_instance = context.get('task_instance')
    exception = context.get('exception')
    execution_date = context.get('execution_date')
    
    task_id = task_instance.task_id if task_instance else 'Unknown'
    
    # 1. Log locally
    logger.error("!"*40)
    logger.error("PIPELINE FAILURE NOTIFICATION")
    logger.error("!"*40)
    logger.error(f"Failed Task ID: {task_id}")
    logger.error(f"Execution Date: {execution_date}")
    logger.error(f"Exception: {str(exception)}")
    logger.error("!"*40)
    
    # 2. Send Slack Alert (if configured)
    slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if slack_webhook_url:
        slack_msg = {
            "text": f"🚨 *Airflow Pipeline Failure* 🚨\n"
                    f"*Task*: `{task_id}`\n"
                    f"*Date*: {execution_date}\n"
                    f"*Error*: {str(exception)}"
        }
        try:
            requests.post(slack_webhook_url, json=slack_msg, timeout=10)
            logger.info("Slack alert sent successfully.")
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
