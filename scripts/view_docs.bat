@echo off
echo Starting dbt Docs server on http://localhost:8081...
cd ..\dbt_project\target
start http://localhost:8081
python -m http.server 8081
