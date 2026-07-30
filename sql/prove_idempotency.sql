-- Raw may grow on rerun; staging and mart business counts must not.
select 'raw' as layer, count(*) as row_count
from raw.github_commits
union all
select 'staging', count(*) from staging.stg_github_commits
union all
select 'mart_commits', sum(commit_count) from mart.agg_commit_activity_daily;

select count(*) = count(distinct commit_sha) as staging_is_idempotent
from staging.stg_github_commits;
