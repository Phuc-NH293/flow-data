"""Daily, catchup-enabled resident application quality pipeline."""

from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator


with DAG(
    dag_id="github_commit_pipeline",
    description="Extract GitHub commits, transform with dbt, then test.",
    start_date=datetime(2026, 7, 1),
    schedule="@daily",
    catchup=True,
    max_active_runs=1,
    default_args={"owner": "data-team", "retries": 1},
    tags=["github", "analytics"],
) as dag:
    extract = BashOperator(
        task_id="extract_window",
        bash_command=(
            "python /opt/flow-data/extractor/extract_github.py "
            "--start '{{ data_interval_start.isoformat() }}' "
            "--end '{{ data_interval_end.isoformat() }}'"
        ),
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=(
            "dbt run --project-dir /opt/flow-data/dbt "
            "--profiles-dir /opt/flow-data/dbt"
        ),
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=(
            "dbt test --project-dir /opt/flow-data/dbt "
            "--profiles-dir /opt/flow-data/dbt"
        ),
    )

    extract >> dbt_run >> dbt_test
