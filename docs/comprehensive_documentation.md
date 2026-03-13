# EcoMetrics: Comprehensive Project Documentation & Architecture Report

This document serves as an exhaustive technical deep-dive into the **EcoMetrics: End-to-End Weather & AQI Pipeline**. It is designed for Staff Engineers, Technical Recruiters, and Data Architecture Stakeholders to thoroughly evaluate the system's design patterns, data handling mechanisms, code logic, and automated CI/CD processes.

---

## 1. Executive Summary & End-to-End Workflow

The primary objective of EcoMetrics is to autonomously ingest disparate environmental data sources, structurally normalize them using distributed big-data processing paradigms, and surface low-latency analytical dashboards. These dashboards track critical daily operational metrics, specifically correlating meteorological phenomena with Air Quality Index (AQI) thresholds.

**Detailed Step-by-Step Execution Flow:**
1.  **Schedule Trigger & Orchestration:** Apache Airflow operates as the central control plane. Utilizing a CRON-based scheduler (`0 8 * * *`), the `weather_aqi_pipeline` Directed Acyclic Graph (DAG) is initialized daily at 08:00 UTC. The DAG uses `catchup=False` to prevent execution flooding during prolonged offline periods.
2.  **Pre-flight Health Checks:** Before allocating compute resources, Airflow executes a `PythonOperator` to ping the Open-Meteo and OpenAQ (WAQI) REST APIs. If an endpoint returns a non-200 HTTP status, the pipeline gracefully halts, logging the failure without triggering downstream processing errors.
3.  **Data Extraction & Distributed Processing (PySpark):** Upon successful health checks, parallel tasks (`fetch_weather.py` and `fetch_aqi.py`) are triggered.
    *   **Extraction:** Python's `requests` library retrieves live, deeply nested JSON payloads.
    *   **Transformation Engine:** The JSON arrays are loaded into an **Apache Spark (PySpark)** in-memory cluster. Spark enforces strict schema validation via `StructType` definitions (e.g., Temperature explicitly cast as `DoubleType()`, Timestamps as `TimestampType()`). Missing values and nulls are sanitized via `.dropna()` and `.filter()` operations to ensure categorical integrity before disk writing.
4.  **Database Loading (Idempotent Upserts):** The sanitized PySpark DataFrames write localized batches into a containerized **PostgreSQL** instance (`raw` schema). 
    *   *Engineering Choice:* Instead of standard `INSERT` statements, the JDBC driver executes `ON CONFLICT (timestamp, city) DO UPDATE SET`. This guarantees **Idempotency**—ensuring that multiple pipeline executions on the same day result in accurate data convergence rather than duplicated row anomalies.
5.  **Analytics Transformation (dbt Core):** Post-ingestion, Airflow triggers a sequence of `BashOperator` commands invoking **Data Build Tool (dbt)** to execute declarative SQL transformations.
    *   **Staging Tier (Silver):** Normalizes inputs, standardizes timezone formatting, and prepares base views (`stg_weather`, `stg_air_quality`).
    *   **Marts Tier (Gold):** Executes complex analytical aggregations. Hourly constraints are rolled up utilizing `GROUP BY DATE()`, calculating maximums, minimums, and averages. The final operation materializes a broad fact table (`mart_combined_daily`) performing a composite join across the weather and AQI dimensional models.
6.  **Data Quality Assurance (dbt test):** Airflow issues a `dbt test` command. This evaluates the materialized tables against assertions defined in `schema.yml` (e.g., verifying `avg_humidity` remains within the `0-100` bounds, and primary keys remain `unique` and `not_null`).
7.  **Dashboard Visualization:** The finalized, optimized `public_marts` tier is queried directly by a highly-available **Metabase** instance, rendering interactive, zero-latency visualizations indicating environmental standard deviations.

---

## 2. Advanced Data Handling & Storage Mechanics

### Data Collection & Payload Volume
The system interacts with two high-frequency public REST APIs:
*   **Open-Meteo:** Retrieves a rolling 7-day window of hourly meteorological forecasts for major metropolitan areas. (1 city × 7 days × 24 hours = **~168 discrete payload constraints** per execution).
*   **World Air Quality Index (WAQI):** Extracts real-time telemetry across 3 target cities (New York, Los Angeles, Chicago) for 4 primary particulate pollutants (PM2.5, PM10, O3, NO2). This yields **12 distinct rows** of pollution constraints per run.

*Scalability Note:* While configured locally for demonstration, the integration of PySpark's DataFrame API ensures the ingestion layer is horizontally scalable. It is natively capable of partitioning and processing terabytes of historical parquet data across a distributed cluster without modifying the codebase.

### Storage Architecture (The Medallion Approach)
Data persistence is structured hierarchically within **PostgreSQL**, mirroring a modern Data Lakehouse paradigm:
*   `raw` **(Bronze):** The raw landing zone. Highly granular, untransformed telemetry data matching the origin JSON layout.
*   `public_staging` **(Silver):** Cleansed, filtered, and typed views.
*   `public_marts` **(Gold):** Highly aggregated, business-ready dimensional tables explicitly optimized for heavy read-query loads by BI visualization tools.

---

## 3. Comprehensive Project Structure Breakdown

```text
Ecometrics-data-pipeline/
├── .github/workflows/
│   └── ci.yml                   # GitHub Actions pipeline logic orchestrating cloud-based Ubuntu environments for CI/CD.
├── dags/
│   ├── utils/
│   │   └── pipeline_monitor.py  # Utility module housing API pings, row-count validation logic, and the Slack Webhook integration.
│   └── weather_pipeline_dag.py  # The core Apache Airflow DAG defining task execution order, retries, and failure hooks.
├── dbt_project/
│   ├── models/
│   │   ├── marts/               # Final Fact/Aggregation tables (.sql) & data quality tests (.yml).
│   │   └── staging/             # Cleaned view models & schema tests.
│   ├── dbt_project.yml          # dbt global configuration (naming conventions, target paths).
│   └── packages.yml             # External dbt dependencies (imports dbt-labs/dbt_utils).
├── docs/                        # Project documentation, architectural diagrams, and presentation materials.
├── ingestion/
│   ├── fetch_aqi.py             # PySpark script to download, deserialize, and structure WAQI pollution data.
│   ├── fetch_weather.py         # PySpark script for Open-Meteo extraction and schema enforcement.
│   ├── create_tables.py         # DDL execution script for bootstrapping Postgres schemas.
│   └── db_connection.py         # Standardized psycopg2 PostgreSQL connection pooling.
├── lib/                         # External binaries (PostgreSQL 42.7.1 JDBC driver).
├── scripts/                     # Shell deployment scripts (run_pipeline.sh for local bootstrap initialization).
├── tests/                       # Pytest directory featuring mock-driven unit testing for Spark logic and Airflow DAG integrity.
├── .env.example                 # Template for environment topography (Passwords, Slack Tokens, API Keys).
├── docker-compose.yml           # Infrastructure-as-Code (IaC) defining the PostgreSQL, Airflow, and Metabase container networking mesh.
└── requirements.txt             # Python pip package dependencies with strict version pinning.
```

---

## 4. Automation and CI/CD (DevOps)

To guarantee enterprise-grade software reliability and prevent regressions, the pipeline implements **GitHub Actions** for Continuous Integration (CI).

1.  **Trigger Mechanism:** CI is initiated upon any `git push` or Pull Request (PR) targeting the `main` branch.
2.  **Headless Environment Setup:** GitHub Actions provisions an isolated Ubuntu Linux runner, configures Python 3.10, and installs `requirements.txt`. 
    *   *Crucial Engineering Component:* Airflow historically conflicts with modern SQLAlchemy versions. The CI pipeline resolves this by dynamically fetching Apache's official `--constraint` URL matrix, guaranteeing seamless dependency resolution in the cloud.
3.  **Automated Unit Testing:** The workflow invokes `pytest`. 
    *   Utilizing `unittest.mock`, the pipeline simulates API JSON payload returns. This enables PySpark parsing validation to occur rapidly inside the CI runner without requiring live network calls to external APIs or a running Database instance.
4.  **Deployment Confidence:** This architecture ensures that faulty Python syntax, broken Spark schemas, or cyclical DAG errors are caught *before* they can be merged into the production branch.

---

## 5. System Operations & Local Bootstrapping

### Initializing the Environment (Day 1)
The entire infrastructure is containerized via Docker for seamless replication across operating systems.
1. Define environment variables in `.env`.
2. Initialize the containerized network: `docker-compose up -d`.
3. Bootstrap the database schemas and perform the first historical data load: `bash scripts/run_pipeline.sh`.

### Lifecycle Management
*   **Routine Operation:** Apache Airflow manages ongoing extraction scheduling without manual intervention.
*   **Environment Teardown:** `docker-compose down` gracefully terminates processes and releases CPU/RAM.
*   **State Persistence:** Due to localized Docker named volumes (`postgres-data`), all database records, Metabase dashboards, and Airflow user states are structurally persisted locally and seamlessly resume upon the next initialization.

---

## 6. Technical Obstacles & Engineering Solutions

**Challenge 1: Airflow CI/CD Dependency Conflicts**
*   *Issue:* Standard continuous integration installations failed because Airflow 2.8 strictly requires `sqlalchemy < 2.0.0`, whereas newer internal components default to SQLAlchemy 2+.
*   *Resolution:* Engineered the GitHub Actions `ci.yml` file to parse Apache's exact release constraints list (`constraints-3.10.txt`) during installation, establishing a pristine Python virtual environment entirely circumventing version clashes.

**Challenge 2: Incomplete Telemetry Data Structures**
*   *Issue:* Public environmental APIs frequently return sparse JSON arrays due to station downtime (e.g., missing PM2.5 readings for specific hours), causing database `NOT NULL` constraints to fail.
*   *Resolution:* PySpark was strategically positioned to act as a data validation firewall. Native PySpark commands (`.dropna()`, implicit `.cast()`) aggressively sanitize the JSON stream in memory. If data relies on critical analytics fields, corrupted records are cleanly quarantined before reaching the PostgreSQL warehouse.

**Challenge 3: Real-Time Operational Monitoring**
*   *Issue:* Silent pipeline failures result in stale dashboard data, degrading stakeholder trust.
*   *Resolution:* Integrated Airflow's native `on_failure_callback` hooks. If any task exceptions occur (e.g., API timeout out, Spark memory overflow), a custom Python utility captures the exact Stack Trace, Task ID, and Execution timestamp, immediately formatting and broadcasting a POST request to a dedicated Slack webhook for immediate engineer notification.
