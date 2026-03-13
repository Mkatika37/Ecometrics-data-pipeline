# EcoMetrics: In-Depth System Architecture & Workflow

This document provides a comprehensive, highly detailed technical breakdown of the EcoMetrics data pipeline. Use this document to understand the underlying code structures, automation logic, and relational modeling of the complete end-to-end framework.

---

## 1. Project Directory Structure & Purpose

The codebase is organized following standard Data Engineering best practices:

```text
Ecometrics-data-pipeline/
├── .github/workflows/
│   └── ci.yml                   # The GitHub Actions configuration. Automates building an Ubuntu environment to run pytest testing suite on every commit.
├── dags/
│   ├── utils/
│   │   └── pipeline_monitor.py  # Utility functions: HTTP status checks for the APIs, Data validations (row counting), and Slack alerting webhooks.
│   └── weather_pipeline_dag.py  # The primary Apache Airflow configuration file mapping the Directed Acyclic Graph dependencies using Python logic.
├── dbt_project/                 # The Data Build Tool (dbt) environment.
│   ├── models/
│   │   ├── marts/               # Final Fact/Aggregation tables (e.g., mart_combined_daily.sql) and strict schema quality constraints (schema.yml).
│   │   └── staging/             # First-pass cleaned view models (e.g., stg_weather.sql).
│   ├── dbt_project.yml          # Global settings for dbt dictating where models compile.
│   └── packages.yml             # External dbt plugin management (like downloading dbt-utils).
├── docs/                        # Project documentation (this file).
├── ingestion/                   # The Python and PySpark engine layer.
│   ├── fetch_aqi.py             # Script to pull JSON from WAQI API and structure it via Spark into Postgres.
│   └── fetch_weather.py         # Script to pull JSON from Open-Meteo API and structure via Spark.
├── lib/
│   └── postgresql-42.7.1.jar    # The Java JDBC driver required for PySpark to securely establish a connection loop with PostgreSQL.
├── scripts/
│   ├── run_pipeline.sh          # A localized bootstrap script executing PySpark & dbt to populate the database on Day 1.
│   └── view_docs.bat            # Windows executable to launch a localhost server rendering the dbt data lineage graphs.
├── tests/
│   ├── test_dag.py              # Pytests ensuring the Airflow DAG loads correctly with the exact amount of expected tasks.
│   └── test_ingestion.py        # Pytests implementing mocking to simulate API responses for testing DataFrame logic without hitting the internet.
├── .env.example                 # Template for secret variables (Passwords, Slack Tokens) which are ignored by Git.
├── docker-compose.yml           # The Docker networking map that defines and connects PostgreSQL, Airflow, and Metabase containers.
├── requirements.txt             # Python pip package definitions.
└── README.md                    # The front-page portfolio and high-level architectural overview.
```

---

## 2. In-Depth Code Explanation

### 2a. Ingestion Layer (`ingestion/fetch_weather.py`)
This script acts as the Extraction & Load (EL) engine.
1.  **Extraction (`fetch_weather_json`)**: Uses `requests.get` to target the free public endpoint `api.open-meteo.com/v1/forecast`. It requests a dense JSON block of the past 7 days of historical weather for coordinates mapping to New York City.
2.  **Transformation (`transform_weather_with_spark`)**: Initiates `SparkSession.builder`. The script navigates the nested JSON tree and extracts targeted values like temperature and windspeed into native Python Arrays.
    *   **Spark Schemas**: Creating a strict struct (`StructType` and `StructField`) forces the dynamic arrays into a strict in-memory database configuration, immediately casting fields with functions like `Float()` and `.withColumn()`.
    *   **Cleaning**: Uses `.dropna(subset=["temperature"])` to ensure missing data doesn't corrupt downstream logic. Adds a hardcoded column `.withColumn("city", lit("NEW YORK"))` to standardize join keys later on.
3.  **Loading (`load_weather_to_postgres`)**: Transforms the in-memory Spark cluster down to raw SQL using `psycopg2`. Defines `INSERT INTO raw.weather_hourly` but appends an `ON CONFLICT (timestamp, city) DO UPDATE SET` logic to execute **Idempotent Upserts** (meaning rows update rather than duplicate if run multiple times).

### 2b. Orchestration Layer (`dags/weather_pipeline_dag.py`)
This file controls *when* and *in what order* code executes.
1.  **DAG Definition**: Instantiates the workflow using a cron schedule `0 8 * * *` (run daily at 8:00 AM) and disables `catchup` to prevent the system from accidentally firing dozens of runs if it was turned off for a week.
2.  **Health Verification (`PythonOperator`)**: Calls `check_api_health` before running any code. By checking if the endpoints return HTTP 200, it safely avoids executing Spark code if the data source is down.
3.  **Data Extraction mapping**: Defines nodes for `fetch_weather_task` and `fetch_aqi_task`, executing them in parallel for speed.
4.  **Transformation execution (`BashOperator`)**: Triggers command-line operations natively inside the Airflow Docker environment to execute `dbt run --select staging` followed by `dbt run --select marts` followed by `dbt test`.
5.  **Failure hooks (`pipeline_monitor.py`)**: Utilizes `on_failure_callback`. If any script errors out, Airflow automatically captures the execution context (Task ID, Date, Exception) and fires a JSON payload to a Slack webhook to instantly alert software engineers on their phones.

### 2c. Transformation Layer (`dbt_project/`)
While PySpark structures the data, Data Build Tool (dbt) cleans and models it using modular SQL.
1.  **Raw → Staging (`stg_weather.sql`)**: Reads `raw.weather_hourly` and isolates the business logic required to format raw strings, standardizing them for deeper analytics.
2.  **Staging → Marts (`mart_daily_weather.sql` & `mart_combined_daily.sql`)**: Executes massive data aggregations. It shrinks 168 rows of hourly data down into a daily summary grouping by `DATE()`, utilizing aggregation functions like `AVG(temperature)` and `MAX(windspeed)`. The Combined mart joins pollution levels side-by-side with weather constraints cleanly ON `city_name` and `date`.
3.  **Quality Engine (`schema.yml`)**: An automated testing suite asserting data assertions like `tests: [not_null, unique]`. When Airflow runs `dbt test`, the system queries the entire database verifying nothing slipped through validation.

---

## 3. Storage, Analytics, and Data Handling

### Postgres Architecture
Data lives in a PostgreSQL container hosted on port `5432`. It is broken into three physical schemas mirroring the medallion (Bronze/Silver/Gold) framework.
*   `raw`: **Bronze tier**. Raw inputs heavily matching the input JSON structures. (Table volume: ~383 rows of historical weather).
*   `public_staging`: **Silver tier**. Minor formatting upgrades acting as clean views rather than physical tables.
*   `public_marts`: **Gold tier**. Heavy aggregation and logical mappings. Clean reporting tables designed solely for Business Intelligence (BI) read queries.

### Visualization (Metabase)
Hosted natively in a Docker container mapped to port `3000`. Metabase points *only* to the Gold tier (`public_marts`). Complex graphing and UI dashboards were designed to expose temperature variations mapped against critical PM2.5 environmental pollution standards.

---

## 4. Automation and DevOps (CI/CD)

The project leverages massive DevOps engineering to ensure local development never breaks the production environment:
1.  **GitHub Actions (`ci.yml`)**: Whenever developers push code to the `master` repository branch:
    *   GitHub summons a clean Ubuntu VM server.
    *   It clones the repository and installs Python 3.10.
    *   **Dependency Constraint Resolution**: Installs Airflow binaries strictly referencing constraint maps to prevent `pip` dependency collisions with older SQLAlchemy structures.
2.  **Pytest (`tests/`)**: A fast, logic unit-testing framework execution. 
    *   `pytest-mock` safely isolates `requests.get` functions, allowing the test to verify DataFrame formatting logic entirely inside the cloud server without executing heavy network queries against the live APIs.

---

## 5. System Operations Guide

### Bootstrapping Day 1
To stand up the application on a new engineering machine:
```bash
docker-compose up -d
bash scripts/run_pipeline.sh
```
The localized Bash script automatically triggers PySpark and builds the baseline schema/marts into an empty database so the BI tools can immediately render data.

### Day 2+ (Normal Operation)
Airflow handles daily extractions entirely autonomously in the background. Engineers execute changes via `git commit` to test logic updates continuously on GitHub branch pipelines.

### Teardown
To cleanly exit the environment processing logic:
```bash
docker-compose down
```
Because the system maps database states to localized named Docker volumes (`volumes: weather_postgres_data`), no pipeline data is lost if the environment is paused or the laptop is shut down.
