#!/usr/bin/env python3
"""Provision a Metabase dashboard, cards, filters, and guest-embed config."""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def request(method, path, token=None, payload=None):
    base = os.getenv("METABASE_API_URL", "http://metabase:3000")
    url = f"{base}{path}"
    body = None if payload is None else json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Metabase-Session"] = token
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else None


def login() -> str:
    data = {
        "username": os.environ["METABASE_ADMIN_EMAIL"],
        "password": os.environ["METABASE_ADMIN_PASSWORD"],
    }
    return request("POST", "/api/session/", payload=data)["id"]


def get_or_set_setting(token: str, key: str, value):
    request("PUT", f"/api/setting/{urllib.parse.quote(key, safe='')}", token=token, payload={"value": value})


def create_card(token: str, name: str, sql: str, template_tags: dict, display: str, collection_id: int):
    payload = {
        "name": name,
        "display": display,
        "collection_id": collection_id,
        "dataset_query": {
            "database": 2,
            "type": "native",
            "native": {"query": sql, "template-tags": template_tags},
            "parameters": [],
        },
        "visualization_settings": {},
    }
    return request("POST", "/api/card/", token=token, payload=payload)


def create_dashboard(token: str, name: str, collection_id: int):
    return request(
        "POST",
        "/api/dashboard/",
        token=token,
        payload={"name": name, "collection_id": collection_id},
    )


def place_cards(token: str, dashboard_id: int, cards: list[dict]):
    request("PUT", f"/api/dashboard/{dashboard_id}/cards", token=token, payload={"cards": cards})


def main():
    token = login()

    secret = os.environ["MB_EMBEDDING_SECRET_KEY"]
    get_or_set_setting(token, "enable-embedding", True)
    get_or_set_setting(token, "embedding-secret-key", secret)

    collection_id = 4
    dashboard = create_dashboard(token, "Commit Analytics Embed", collection_id)

    tags = {
        "commit_date": {
            "id": "commit_date",
            "name": "commit_date",
            "display-name": "Commit date",
            "type": "date",
            "dimension": ["field", 75, None],
        },
        "repository": {
            "id": "repository",
            "name": "repository",
            "display-name": "Repository",
            "type": "category",
            "dimension": ["field", 72, None],
        },
        "author_name": {
            "id": "author_name",
            "name": "author_name",
            "display-name": "Author",
            "type": "category",
            "dimension": ["field", 74, None],
        },
    }

    common_where = "WHERE 1=1 [[AND {{commit_date}}]] [[AND {{repository}}]] [[AND {{author_name}}]]"

    cards = [
        create_card(
            token,
            "Commits over time",
            f"""
SELECT commit_date, sum(commit_count) AS commits
FROM mart.agg_commit_activity_daily
{common_where}
GROUP BY 1
ORDER BY 1
""".strip(),
            tags,
            "line",
            collection_id,
        ),
        create_card(
            token,
            "Top authors",
            """
SELECT author_name, sum(commit_count) AS commits
FROM mart.agg_commit_activity_daily
WHERE 1=1 [[AND {{commit_date}}]] [[AND {{repository}}]]
GROUP BY 1
ORDER BY 2 DESC
LIMIT 10
""".strip(),
            tags,
            "bar",
            collection_id,
        ),
        create_card(
            token,
            "Merge vs verified",
            f"""
SELECT commit_date,
       sum(merge_commit_count) AS merge_commits,
       sum(verified_commit_count) AS verified_commits
FROM mart.agg_commit_activity_daily
{common_where}
GROUP BY 1
ORDER BY 1
""".strip(),
            tags,
            "bar",
            collection_id,
        ),
        create_card(
            token,
            "Activity table",
            f"""
SELECT commit_date, repository, author_name,
       commit_count, merge_commit_count, verified_commit_count, verified_commit_rate
FROM mart.agg_commit_activity_daily
{common_where}
ORDER BY 1 DESC, 4 DESC
LIMIT 200
""".strip(),
            tags,
            "table",
            collection_id,
        ),
    ]

    now = 0
    layout = []
    for card in cards:
        layout.append(
            {
                "id": card["id"],
                "row": now,
                "col": 0,
                "size_x": 16,
                "size_y": 8 if card["display"] != "table" else 10,
            }
        )
        now += 8 if card["display"] != "table" else 10

    place_cards(token, dashboard["id"], layout)

    parameters = [
        {
            "id": "commit_date",
            "name": "Commit date",
            "slug": "commit_date",
            "sectionId": "date",
            "type": "date/all-options",
        },
        {
            "id": "repository",
            "name": "Repository",
            "slug": "repository",
            "sectionId": "string",
            "type": "string/=",
        },
        {
            "id": "author_name",
            "name": "Author",
            "slug": "author_name",
            "sectionId": "string",
            "type": "string/=",
        },
    ]

    dashcards = []
    for card in cards:
        mappings = [
            {
                "card_id": card["id"],
                "parameter_id": "commit_date",
                "target": ["dimension", ["field", 75, {"base-type": "type/DateTime"}], {"stage-number": 0}],
            },
            {
                "card_id": card["id"],
                "parameter_id": "repository",
                "target": ["dimension", ["field", 72, {"base-type": "type/Text"}], {"stage-number": 0}],
            },
            {
                "card_id": card["id"],
                "parameter_id": "author_name",
                "target": ["dimension", ["field", 74, {"base-type": "type/Text"}], {"stage-number": 0}],
            },
        ]
        dashcards.append(
            {
                "id": card["id"],
                "row": next(item["row"] for item in layout if item["id"] == card["id"]),
                "col": 0,
                "size_x": 16,
                "size_y": 8 if card["display"] != "table" else 10,
                "parameter_mappings": mappings,
            }
        )

    request(
        "PUT",
        f"/api/dashboard/{dashboard['id']}",
        token=token,
        payload={
            "name": dashboard["name"],
            "collection_id": collection_id,
            "parameters": parameters,
            "dashcards": dashcards,
        },
    )

    print(json.dumps({"dashboard_id": dashboard["id"], "cards": [card["id"] for card in cards]}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as exc:
        print(exc.read().decode())
        raise
