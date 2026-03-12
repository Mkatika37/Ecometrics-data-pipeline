# 🌤️ EcoMetrics: End-to-End Weather & AQI Pipeline

![Python](https://img.shields.io/badge/Python-3.10-blue?style=for-the-badge&logo=python&logoColor=white)
![Apache Airflow](https://img.shields.io/badge/Apache%20Airflow-017CEE?style=for-the-badge&logo=Apache%20Airflow&logoColor=white)
![Apache Spark](https://img.shields.io/badge/PySpark-E25A1C?style=for-the-badge&logo=Apache%20Spark&logoColor=white)
![dbt](https://img.shields.io/badge/dbt-FF694B?style=for-the-badge&logo=dbt&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)

> End-to-end data engineering pipeline ingesting real-time weather and air quality data using PySpark, Airflow, dbt, and PostgreSQL.

---

## 🏗️ Architecture

```text
Open-Meteo API   OpenAQ API
      ↓               ↓
   PySpark Ingestion Scripts
           ↓
    PostgreSQL (Raw Layer)
           ↓
      Apache Airflow
           ↓
       dbt Core
    (Staging → Marts)
           ↓
   Metabase Dashboard
```

---

## 🛠️ Tech Stack

| Tool | Purpose | Free/Open Source |
| :--- | :--- | :---: |
| **Python 3.10** | Core programming language for API requests and logic | ✅ |
| **PySpark** | In-memory distributed data transformation and DataFrame manipulation | ✅ |
| **PostgreSQL** | Relational Database acting as Data Warehouse | ✅ |
| **dbt Core** | SQL-first data transformation, testing, and modeling | ✅ |
| **Apache Airflow** | Workflow orchestration and dependency management | ✅ |
| **Docker Compose** | Containerization of services (Postgres, Airflow, Metabase) | ✅ |
| **Metabase** | BI Dashboard for data visualization | ✅ |
| **Pytest** | Unit testing for ingestion and DAG components | ✅ |

---

## 📂 Project Structure

```text
.
├── dags/
│   ├── utils/
│   │   └── pipeline_monitor.py
│   └── weather_pipeline_dag.py
├── dbt_project/
│   ├── models/
│   │   ├── marts/
│   │   │   ├── mart_combined_daily.sql
│   │   │   ├── mart_daily_aqi.sql
│   │   │   ├── mart_daily_weather.sql
│   │   │   └── schema.yml
│   │   └── staging/
│   │       ├── schema.yml
│   │       ├── sources.yml
│   │       ├── stg_air_quality.sql
│   │       └── stg_weather.sql
│   ├── dbt_project.yml
│   └── profiles.yml
├── ingestion/
│   ├── create_tables.py
│   ├── db_connection.py
│   ├── fetch_aqi.py
│   └── fetch_weather.py
├── tests/
│   ├── test_dag.py
│   └── test_ingestion.py
├── .env.example
├── .gitignore
├── docker-compose.yml
└── requirements.txt
```

---

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.10+
- Git

### Installation & Execution

1. Clone the repository
```bash
git clone <your-repo-url>
cd <repo-name>
```

2. Establish Configuration
```bash
cp .env.example .env
# Edit .env and supply your credentials if needed
```

3. Spin up the infrastructure
```bash
docker-compose up -d
```

4. Initialize the database schemas
```bash
python ingestion/create_tables.py
```

5. Fetch raw data locally using PySpark
```bash
python ingestion/fetch_weather.py
python ingestion/fetch_aqi.py
```

6. Run dbt transformations
```bash
cd dbt_project
dbt run
```

7. Access UIs
- **Apache Airflow**: Open [http://localhost:8080](http://localhost:8080)
- **Metabase**: Open [http://localhost:3000](http://localhost:3000)

---

## 🧠 What I Built & Learned

Throughout this project, my main goal was to simulate a professional data engineering ecosystem on a small scale:
- **API Ingestion**: I built fault-tolerant Python fetchers pointing to OpenAQ and Open-Meteo endpoints.
- **PySpark Processing**: Utilized Spark DataFrames to enforce schema types, cast appropriately with Arrow optimizations, and logically format data before dumping it down to raw tiers via JDBC.
- **dbt Modeling**: Structured data cleanly into a staging (`view`) and marts (`table`) architecture. I applied DRY principles and configured crucial assertions (`not_null`, `accepted_values`) inside `schema.yml`.
- **Airflow Orchestration**: Set up a robust, dependency-mapped DAG leveraging custom Python and Bash operators, tied together with native health checking hooks.
- **Testing Mastery**: Leveraged PyTest and `unittest.mock` to validate my business logic securely detached from live infrastructure.

## 🔭 Future Improvements

- Migrate storage layer from local PostgreSQL to a cloud-native equivalent e.g., Snowflake, BigQuery, or Amazon Redshift.
- Fully containerize the Python `fetch` ingestion logic.
- Replace Airflow `LocalExecutor` with `CeleryExecutor` or equivalent for horizontal scalability.
- Automate dashboard creation in Metabase using predefined configuration exports.
- Configure CI/CD pipelines (GitHub Actions) to run dbt tests and `pytest` automatically on PRs.
