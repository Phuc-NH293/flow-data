"""Near-real-time GitHub commit pipeline."""

from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator


with DAG(
    dag_id="github_commit_pipeline",
    description="Extract GitHub commits, transform with dbt, then test.",
    start_date=datetime(2026, 7, 1),
    schedule="*/1 * * * *",
    catchup=False,
    max_active_runs=1,
    default_args={"owner": "data-team", "retries": 1},
    tags=["github", "analytics"],
) as dag:
    extract = BashOperator(
        task_id="extract_window",
        bash_command=(
            "start=$(date -u -d '1 day ago' --iso-8601=seconds); "
            "end=$(date -u --iso-8601=seconds); "
            "python /opt/flow-data/extractor/extract_github.py "
            "--start \"$start\" "
            "--end \"$end\""
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
