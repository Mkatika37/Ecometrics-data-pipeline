import os
import sys
import pytest

# Ensure the root project directory is in the path for module importing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.fixture
def dag():
    """Imports and returns the weather pipeline DAG object."""
    from dags.weather_pipeline_dag import dag as weather_dag
    return weather_dag

def test_dag_loaded(dag):
    """Test that the DAG was successfully loaded and has the correct ID."""
    assert dag is not None
    assert dag.dag_id == 'weather_aqi_pipeline'

def test_dag_has_correct_task_count(dag):
    """Test that the DAG has exactly 7 tasks."""
    assert len(dag.tasks) == 7

def test_no_catchup(dag):
    """Test that DAG catchup is set to False."""
    assert dag.catchup is False

def test_schedule_interval(dag):
    """Test that the DAG schedule interval is set to daily at 8 AM."""
    assert dag.schedule_interval == '0 8 * * *'

def test_check_health_runs_before_fetch(dag):
    """Test that check_api_health has downward dependencies to both fetch operations."""
    health_task = dag.get_task('check_api_health')
    downstream_ids = health_task.downstream_task_ids
    
    assert 'fetch_weather_data' in downstream_ids
    assert 'fetch_aqi_data' in downstream_ids

def test_validate_runs_after_both_fetches(dag):
    """Test that validate_raw_data waits for both upstream fetch tasks."""
    validate_task = dag.get_task('validate_raw_data')
    upstream_ids = validate_task.upstream_task_ids
    
    assert 'fetch_weather_data' in upstream_ids
    assert 'fetch_aqi_data' in upstream_ids
