# System Architecture & Technical Workflow (TDD)

This technical design document (TDD) details the system architecture, foundational data engineering paradigms, data flow mappings, and structural modeling behind the **EcoMetrics Pipeline**.

---

## 1. System High-Level Design (HLD)

EcoMetrics is constructed utilizing a modern Data Lakehouse and decoupled container methodology. The architecture isolates the compute layer (Airflow, Spark, dbt) from the storage layer (PostgreSQL) and the presentation layer (Metabase).

This guarantees fault isolation: if the Airflow scheduler crashes, the analytical dashboards remain fully online and queries continue to route seamlessly to the optimized data warehouse.

```mermaid
graph LR
    %% Data Sources
    A[☁️ Open-Meteo REST]
    B[🏭 WAQI Air Quality REST]

    %% Compute & Orchestration Layer
    H((🕰️ Apache Airflow Scheduler))
    
    subgraph Compute & Processing
        C[🐍 PySpark Ingestion Engine]
        E[🔨 dbt Core (Data Build Tool)]
    end

    %% Distributed Storage Layer
    subgraph Relational Data Warehouse
        D[(PostgreSQL: Bronze / Raw)]
        F[(PostgreSQL: Silver & Gold / Marts)]
    end

    %% Visualization
    G[📊 Metabase BI Instance]

    %% Data Flow Pathways
    A -->|JSON Payloads| C
    B -->|JSON Payloads| C
    C -->|JDBC Upserts| D
    D -->|Aggregates| E
    E -->|Materializes Views & Facts| F
    F -->|Hosts BI Dashboard Constraints| G

    %% Scheduling Logic
    H -.->|Triggers PythonOperator| C
    H -.->|Triggers BashOperator| E

    %% Theming
    classDef storage fill:#e1f5fe,stroke:#0288d1,stroke-width:2px;
    classDef compute fill:#f3e5f5,stroke:#8e24aa,stroke-width:2px;
    classDef dash fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px;
    classDef source fill:#fff3e0,stroke:#f57c00,stroke-width:2px;
    classDef orchestrator fill:#eceff1,stroke:#607d8b,stroke-width:4px;
    
    class A,B source;
    class C,E compute;
    class D,F storage;
    class G dash;
    class H orchestrator;
```

---

## 2. Component Design & Technical Specifications

### 2.1 The Data Extraction & Computing Layer (PySpark)
**Why PySpark?**
While simple Python `pandas` DataFrames are suitable for small API responses, **Apache Spark (PySpark)** is implemented to simulate enterprise-grade, distributed big data capabilities capable of handling thousands of highly nested meteorological JSON responses simultaneously.
*   **Arrow Acceleration:** PySpark configurations optimize in-memory execution speeds when casting arrays.
*   **Strict Typing Contextualization:** Raw API responses frequently lack standard typing (e.g., returning numeric variables indiscriminately as text). The PySpark layer maps incoming lists recursively into `StructType([StructField("temperature", DoubleType(), True)])`. A failure to conform automatically rejects the specific faulty record.
*   **Localized Filtering:** Data is scrubbed (`.filter()`, `.dropna()`) in the compute layer (RAM) prior to ever taxing the Database CPU cycle.

### 2.2 Relational Modeling Strategy (dbt Core)
The project deliberately segregates raw ingestion from highly formatted dashboard data utilizing **Data Build Tool (dbt)**. This adheres strictly to the Medallion Data Architecture (Bronze, Silver, Gold).

1.  **Bronze (Raw Ingestion):** The PySpark load. Idempotent insertion logic maps constraints exactly as retrieved.
2.  **Silver (Staging Models):** Dbt constructs dynamic SQL Views. Columns like `timestamp` are parsed to standard categorical `DATE()` formats. Null bounds are asserted utilizing external libraries like `dbt_utils`.
3.  **Gold (Data Marts):** Complex dimensional modeling occurs. The `mart_combined_daily` table integrates metrics from disjoint domains (Weather arrays vs Air Quality readings), flattening highly normalized datasets into wide, denormalized records specifically tailored to return query results to Metabase in under `500ms`.

### 2.3 Workflow Orchestration (Apache Airflow)
Apache Airflow governs the daily lifecycle. The DAG is functionally constructed using modular operators:
*   **Parallel Execution Trees:** The weather dataset and AQI dataset share no dependencies. Therefore, Airflow natively executes the `fetch_weather_task` and `fetch_aqi_task` in parallel utilizing Docker container threading to drastically reduce pipeline runtime.
*   **Dependency Management:** The data transformation tasks (`run_dbt_staging`) explicitly block and wait (`>>`) until both upstream extractions are validated.
*   **Operational Monitoring Hooks:** Airflow utilizes an `on_failure_callback`. The pipeline runtime monitors internal tracebacks. If a Spark Out-Of-Memory (OOM) error or a database timeout occurs, a custom Python function synthesizes the specific `Task_Id`, context exception string, and runtime date, posting an automated REST request to a Slack integrated Webhook to page the on-call engineer.

### 2.4 CI/CD Infrastructure Pipeline (GitHub Actions)
Continuous Testing is critical in Data Engineering. Code merges must be verified mechanically to prevent schema degradations on production servers.

**The Action Strategy (`.github/workflows/ci.yml`):**
1. Automatically instantiated when a developer issues a `git commit`.
2. Checks out the repository into an isolated Ubuntu VM runner dynamically generated by GitHub.
3. Explicitly bypasses package conflict behaviors (often native to Apache Airflow and SQLAlchemy bindings) by utilizing strict installation constraint maps pulled directly from the Apache master repository.
4. Executes the localized `pytest` testing suite and tracks test coverage.
5. If the `fetch_weather` PySpark logic modifications fail the nested API JSON interpretation checks, the pipeline halts with an `Exit code: 1`, turning the GitHub Pull Request red and blocking the deployment.

---

## 3. Infrastructure and Deployment (Docker)

The physical operation of EcoMetrics relies entirely on **Docker Compose**, an Infrastructure-as-Code (IaC) methodology ensuring absolute environment parity between a developer's local laptop, testing servers, and the final cloud production runtime.

*   `weather_postgres`: The central analytical instance.
*   `airflow_postgres`: Airflow's internal metadata tracking database (maintaining run history).
*   `airflow-init`: A transient container executing baseline user creation and Airflow migrations.
*   `airflow-webserver` & `airflow-scheduler`: The core orchestration engines.
*   `metabase`: The container hosting the BI JVM processing logic.

**State Persistence:**
To ensure pipeline runs, Airflow logic modifications, and highly configured Metabase dashboard visuals survive server reboots, Docker mounts multiple Native Volumes (`weather_postgres_data`, `./dags:/opt/airflow/dags`).

*For localized system bootstrapping, refer to the operations outlined in `comprehensive_documentation.md`.*
