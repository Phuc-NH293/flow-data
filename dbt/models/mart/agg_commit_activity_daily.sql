select
    (committed_at_utc at time zone 'UTC')::date as commit_date,
    repository,
    author_key,
    max(author_name) as author_name,
    count(*) as commit_count,
    count(*) filter (where is_merge) as merge_commit_count,
    count(*) filter (where is_verified) as verified_commit_count,
    round(
        count(*) filter (where is_verified)::numeric / nullif(count(*), 0),
        4
    ) as verified_commit_rate
from {{ ref('stg_github_commits') }}
group by 1, 2, 3

