-- DEMO ONLY. This intentionally breaks the mart invariant.
-- Run dbt run afterward to restore the mart from staging.
update mart.agg_commit_activity_daily
set merge_commit_count = commit_count + 1
where (commit_date, repository, author_key) = (
    select commit_date, repository, author_key
    from mart.agg_commit_activity_daily
    limit 1
);
