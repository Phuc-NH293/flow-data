FROM apache/airflow:2.10.5-python3.11

USER airflow
RUN pip install --no-cache-dir \
    dbt-postgres==1.9.0 \
    psycopg2-binary==2.9.10

WORKDIR /opt/flow-data

