#!/usr/bin/env python3
"""Extract one half-open GitHub commit window with pagination."""

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import psycopg2
from psycopg2.extras import Json


def timestamp(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timestamp requires timezone")
    return result.astimezone(timezone.utc)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=timestamp, required=True)
    parser.add_argument("--end", type=timestamp, required=True)
    parser.add_argument("--end-next-day", action="store_true")
    return parser.parse_args()


def request_page(repository: str, start: datetime, end: datetime, page: int) -> list:
    query = urllib.parse.urlencode({
        "since": start.isoformat().replace("+00:00", "Z"),
        "until": end.isoformat().replace("+00:00", "Z"),
        "per_page": 100,
        "page": page,
    })
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/commits?{query}",
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "flow-data-course-project",
        },
    )
    token = os.getenv("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")

    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code not in (403, 429) or attempt == 3:
                raise
            time.sleep(2 ** attempt)
    return []


def main() -> None:
    args = arguments()
    end = args.end + timedelta(days=1) if args.end_next_day else args.end
    repository = os.environ["GITHUB_REPOSITORY"]
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "resident_analytics"),
        user=os.getenv("POSTGRES_USER", "pipeline_user"),
        password=os.environ["POSTGRES_PASSWORD"],
    )
    accepted = rejected = page = 0
    with conn, conn.cursor() as cursor:
        while True:
            page += 1
            payloads = request_page(repository, args.start, end, page)
            if not payloads:
                break
            for payload in payloads:
                try:
                    commit_time = timestamp(payload["commit"]["committer"]["date"])
                    if not payload.get("sha"):
                        raise ValueError("missing natural key")
                    # GitHub's `until` boundary is inclusive; enforce [start, end).
                    if not args.start <= commit_time < end:
                        continue
                    cursor.execute(
                        "insert into raw.github_commits (_raw) values (%s)",
                        (Json(payload),),
                    )
                    accepted += 1
                except (KeyError, TypeError, ValueError) as exc:
                    cursor.execute(
                        """
                        insert into raw.rejected_github_commits
                          (source_repository, page_number, raw_text, error_message)
                        values (%s, %s, %s, %s)
                        """,
                        (repository, page, json.dumps(payload), str(exc)),
                    )
                    rejected += 1
            if len(payloads) < 100:
                break
    print(f"repository={repository} window=[{args.start}, {end}) pages={page} accepted={accepted} rejected={rejected}")


if __name__ == "__main__":
    main()
