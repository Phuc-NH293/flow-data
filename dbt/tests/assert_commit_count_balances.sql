-- Every commit is either a merge commit or a non-merge commit.
select *
from {{ ref('agg_commit_activity_daily') }}
where merge_commit_count < 0
   or merge_commit_count > commit_count
   or verified_commit_count < 0
   or verified_commit_count > commit_count

