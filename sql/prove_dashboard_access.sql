-- Run as dashboard_reader.
-- This query must succeed.
select count(*) as mart_rows
from mart.agg_commit_activity_daily;

-- These queries must fail with "permission denied for schema".
select count(*) from raw.github_commits;
select count(*) from staging.stg_github_commits;
