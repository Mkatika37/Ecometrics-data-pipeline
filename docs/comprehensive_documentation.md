# EcoMetrics: Comprehensive Project Documentation & Architecture Report

This document serves as a deep-dive technical explanation of the **EcoMetrics: End-to-End Weather & AQI Pipeline**. It is designed to act as a complete guide for engineers, recruiters, or stakeholders to fully understand the project's architecture, data handling, code logic, and automated CI/CD processes.

---

## 1. End-to-End Workflow

The primary goal of EcoMetrics is to autonomously ingest distinct environmental data sources, structurally merge them using big-data processing tools, and surface analytical dashboards that track daily operational metrics (Weather vs Air Quality).

**Step-by-Step Execution Flow:**
1.  **Schedule Trigger:** Apache Airflow acts as the orchestrator. Every day at 08:00 UTC, the cron scheduler turns on and initiates the `weather_aqi_pipeline` Directed Acyclic Graph (DAG).
2.  **Health Check:** Airflow first fires an HTTP ping to the Open-Meteo and OpenAQ (WAQI) APIs to ensure their servers are online. If offline, the pipeline halts to save compute resources.
3.  **Data Ingestion & Spark Processing:** If APIs are healthy, Airflow triggers two separate Python tasks (`fetch_weather.py` and `fetch_aqi.py`). 
    *   These scripts pull live JSON payloads via HTTP Requests.
    *   The scripts load that JSON into **Apache Spark (PySpark)** in-memory. Spark strictly enforces data types (e.g., Temperature must be a Float, Date must be a Timestamp) and cleans out any null or malformed data.
4.  **Database Loading (Upsert):** The cleaned Spark DataFrames push data into a containerized **PostgreSQL** database into the `raw` schema. It uses an `ON CONFLICT DO UPDATE` strategy to ensure that if a script runs twice, data isn't duplicated—it's only updated (Idempotency).
5.  **Analytics Transformation:** After validating the raw table row counts, Airflow commands **dbt Core** to execute SQL transformations.
    *   **Staging Tier:** Minor formatting/cleaning (e.g., standardizing capitalization).
    *   **Marts Tier:** Advanced SQL `GROUP BY` operations that aggregate 24 hours of hourly data into single Daily Averages for Weather and Air Quality, and finally joins the two sources together into a master reporting table.
6.  **Data Quality Testing:** Airflow runs `dbt test`, applying strict assertions on the database (e.g., ensuring Humidity is never below 0% or above 100%).
7.  **Dashboarding:** The final processed metrics are queried by a connected **Metabase** container. The pre-computed data populates interactive charts without putting heavy analytical load on the database.

---

## 2. Data Handling

### Data Collection & Volume
The system interacts with two public APIs:
*   **Open-Meteo:** A 7-day rolling window of hourly forecasts for New York City. At 1 city × 7 days × 24 hours, this represents approximately **168 rows of weather constraints** per run.
*   **World Air Quality Index (WAQI):** Live readings for 3 cities (New York, LA, Chicago) measuring 4 separate pollutants (PM2.5, PM10, O3, NO2). This yields **12 distinct rows** of pollution constraints per run.

While this project is configured as a small-scale portfolio prototype, the utilization of PySpark means the ingestion layer is horizontally scalable. It could easily process millions of rows if pointed at a larger historical data bucket.

### Storage Mechanisms
Data is structured hierarchically within **PostgreSQL**:
*   `raw.weather_hourly` and `raw.air_quality`: The landing zone. Highly granular, untransformed data matching the API layout.
*   `public_staging`: Filtered subsets of the raw schema.
*   `public_marts`: The highest-value data. Aggregated daily facts and deeply joined dimensional tables optimized entirely for read-heavy visualization tools.

---

## 3. Project Structure Breakdown

```text
Ecometrics-data-pipeline/
├── .github/workflows/
│   └── ci.yml                   # The GitHub Actions file defining cloud CI/CD logic.
├── dags/
│   ├── utils/
│   │   └── pipeline_monitor.py  # Helper functions: API pings, Data validations, Slack alerts.
│   └── weather_pipeline_dag.py  # The Airflow DAG defining task dependencies.
├── dbt_project/
│   ├── models/
│   │   ├── marts/               # Final Fact/Agg tables (.sql) & data quality tests (.yml).
│   │   └── staging/             # Cleaned view models & schema tests.
│   ├── dbt_project.yml          # dbt global configuration.
│   └── packages.yml             # External dbt dependencies (like dbt-utils).
├── ingestion/
│   ├── fetch_aqi.py             # PySpark script to download and structure pollution data.
│   └── fetch_weather.py         # PySpark script to download and structure weather data.
├── lib/                         # Holds the PostgreSQL JDBC driver (.jar) for Spark connections.
├── scripts/                     # Shell/Batch scripts to automate local deployments.
├── tests/                       # Pytest unit tests for the ingestion scripts and DAG integrity.
├── docker-compose.yml           # The Docker mapping creating Postgres, Airflow, and Metabase.
└── requirements.txt             # Virtual environment Python package dependencies.
```

---

## 4. Code Explanation Deep-Dive

### A. The Ingestion Engine: `fetch_weather.py`
This script connects to the external API, models the data in PySpark, and writes to Postgres.
*   **Line 20 (`fetch_weather_json()`):** Uses the `requests` library to execute a standard HTTP GET request to the Open-Meteo endpoint. Passes parameters for coordinates and fields. Raises an exception if the status code isn't 200 (OK).
*   **Line 48 (`transform_weather_with_spark()`):** Initializes a local `SparkSession`. Parses the nested JSON payload into lists. It forces float conversions locally, zips them into tuples, and defines a strict PySpark `StructType` schema. The Spark DataFrame is then created, and native `.withColumn()` commands are used to explicitly cast timestamps, round decimal places, and hardcode the city name to "NEW YORK".
*   **Line 115 (`load_weather_to_postgres()`):** Uses `psycopg2` to open a Postgres connection. Iterates over the PySpark DataFrame rows to execute the SQL `INSERT ... ON CONFLICT DO UPDATE SET ...` command.

### B. The Orchestrator: `weather_pipeline_dag.py`
This is an Airflow DAG file using Python definitions to map dependencies using the `>>` bitshift operator.
*   **`check_api_health_task`**: Defers execution to a custom utility evaluating if URLs return an HTTP 200 status.
*   **`fetch_weather_task` / `fetch_aqi_task`**: Executes the ingestion scripts inside heavily shielded `PythonOperator` tasks.
*   **`run_dbt_staging_task` / `run_dbt_marts_task` / `run_dbt_tests_task`**: Uses `BashOperator` to execute command-line `dbt` operations logically ordered from Staging -> Marts -> Tests.

### C. Analytical Modeling: `dbt_project/models/marts/mart_daily_weather.sql`
*(Example of dbt code structure)*
```sql
SELECT 
    DATE(measured_at) as date,
    city_name,
    AVG(temperature_celsius) as avg_temperature,
    MAX(temperature_celsius) as max_temperature
FROM {{ ref('stg_weather') }}
GROUP BY 1, 2
```
*   `{{ ref('stg_weather') }}`: Instead of hardcoding table names, dbt uses Jinja interpolation references. This dynamically builds a DAG so dbt knows it must build `stg_weather` before it is allowed to build `mart_daily_weather`.

---

## 5. Automation and CI/CD

To ensure enterprise-grade software reliability, the pipeline uses **GitHub Actions** for Continuous Integration.

1.  **Trigger:** Every time code is pushed or a Pull Request is opened on GitHub, the `.github/workflows/ci.yml` file is activated.
2.  **Environment Setup:** GitHub automatically spawns an Ubuntu Linux cloud server, installs Python 3.10, and runs `pip install -r requirements.txt`. It uses constraints to perfectly align Airflow dependencies with SQLAlchemy.
3.  **Unit Testing:** The CI pipeline runs `pytest`. It executes the mock environments inside `tests/` to guarantee that edits to the PySpark code logic haven't broken the JSON-to-DataFrame transformations.
4.  **Why it matters:** In a real production environment, this prevents broken code from ever being deployed to the live Airflow servers, saving thousands of dollars in potentially bad data processing.

---

## 6. Libraries and Dependencies

*   **`apache-airflow==2.8.0`**: The primary scheduler and orchestrator monitoring task health.
*   **`pyspark==3.5.0`**: Distributed computing engine utilized for its capacity to enforce schema typing and handle big-data transformations in memory.
*   **`dbt-core & dbt-postgres`**: Compiles SQL select statements into data warehouse table creation scripts.
*   **`pytest-mock`**: Allows isolated testing of the python logic by "mocking" (faking) the API responses so tests can run without needing Internet or Database access.
*   **`psycopg2-binary`**: The foundational PostgreSQL database adapter for Python.
*   **`dbt_utils`**: An external dbt package imported to run advanced bounds testing (like min/max threshold tracking).

---

## 7. Operational Details

### Starting the Pipeline
The infrastructure is containerized in Docker, preventing local environment conflicts.
1.  Run `docker-compose up -d` in the root folder. This downloads and starts PostgreSQL, Airflow, and Metabase in detached mode.
2.  Run `bash scripts/run_pipeline.sh` to initialize the postgres schemas locally.
3.  Open `http://localhost:8080`, log in to Airflow, and toggle the `weather_aqi_pipeline` to **ON**. The pipeline typically takes about **45 seconds** to ingest, process, and test the full workflow.

### Shutting Down & Restarting
*   To halt the system and save RAM/CPU, navigate to the folder and run `docker-compose down`. This safely downs the servers.
*   Because Docker is configured with named volumes (`postgres-data`), all your data, Airflow logs, and Metabase dashboards are structurally saved to your hard drive and instantly resume when you type `docker-compose up -d` again.

---

## 8. Technical Challenges & Considerations

**Challenge 1: Airflow CI/CD Dependency Conflicts**
*   *Issue:* Attempting to install Airflow via basic `pip install` on GitHub Actions resulted in immediate crashing. Airflow requires strict SQLAlchemy dependencies which conflicted with standard package requests.
*   *Solution:* Implemented Apache's official `--constraint` URL resolution inside the `ci.yml`. This forced pip to evaluate the exact package hashes used by modern Airflow distributions, allowing PySpark and Airflow to coexist peacefully.

**Challenge 2: Incomplete JSON API Formats**
*   *Issue:* Environmental APIs often have missing time blocks or null values for specific pollutants based on machine downtime at the collection station.
*   *Solution:* Integrated PySpark to pre-process the data in memory before it ever touched the database. Standard `.dropna()` methods and explicit structural typing were utilized to sanitize unpredictable data inputs, preventing database ingestion errors downstream.

**Challenge 3: Idempotent Execution**
*   *Issue:* If Airflow executes the data pipeline twice in one day, simple `INSERT` statements would duplicate the raw payload.
*   *Solution:* Engineered Postgres schemas with Primary Keys and engineered psycopg2 scripts using `INSERT INTO ... ON CONFLICT (timestamp, city) DO UPDATE SET ...` logic. This ensures data is seamlessly overwritten to the latest accurate values without duplicating row counts.
