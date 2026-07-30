with parsed as (
    select
        raw_id,
        source_repository as repository,
        _ingested_at,
        _raw ->> 'sha' as commit_sha,
        _raw -> 'author' ->> 'login' as github_login,
        _raw -> 'commit' -> 'author' ->> 'name' as author_name,
        _raw -> 'commit' -> 'author' ->> 'email' as author_email,
        (_raw -> 'commit' -> 'committer' ->> 'date')::timestamptz as committed_at_utc,
        _raw -> 'commit' ->> 'message' as commit_message,
        coalesce((_raw -> 'commit' -> 'verification' ->> 'verified')::boolean, false)
            as is_verified,
        jsonb_array_length(coalesce(_raw -> 'parents', '[]'::jsonb)) > 1 as is_merge
    from {{ source('raw', 'github_commits') }}
),
deduplicated as (
    select *,
        row_number() over (
            partition by commit_sha
            order by _ingested_at desc, raw_id desc
        ) as duplicate_rank
    from parsed
)
select
    commit_sha,
    repository,
    github_login,
    author_name,
    author_email,
    coalesce(github_login, author_email, author_name, 'unknown') as author_key,
    committed_at_utc,
    commit_message,
    is_verified,
    is_merge,
    github_login is null as is_github_user_missing,
    _ingested_at
from deduplicated
where duplicate_rank = 1
