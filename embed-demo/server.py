#!/usr/bin/env python3
"""Small local demo page for the commit analytics dashboard.

The page is intentionally dependency-light: it serves a Chart.js frontend and
reads only the dashboard_reader view from PostgreSQL.
"""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
from psycopg2.extras import RealDictCursor

ROOT = Path(__file__).parent


def db():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "resident_analytics"),
        user=os.getenv("DASHBOARD_DB_USER", "dashboard_reader"),
        password=os.environ["DASHBOARD_DB_PASSWORD"],
    )


class Handler(BaseHTTPRequestHandler):
    def send_json(self, value):
        raw = json.dumps(value, default=str).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/activity":
            with db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    select commit_date, repository, author_key, author_name,
                           commit_count, merge_commit_count,
                           verified_commit_count, verified_commit_rate
                    from mart.agg_commit_activity_daily
                    order by commit_date, author_key
                    """
                )
                self.send_json(cur.fetchall())
            return
        if path == "/":
            path = "/index.html"
        file = (ROOT / path.lstrip("/")).resolve()
        if ROOT not in file.parents or not file.is_file():
            self.send_error(404)
            return
        content = file.read_bytes()
        self.send_response(200)
        self.send_header(
            "Content-Type",
            "text/html; charset=utf-8" if file.suffix == ".html"
            else "text/css; charset=utf-8" if file.suffix == ".css"
            else "application/javascript; charset=utf-8",
        )
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", int(os.getenv("DEMO_PORT", "8090"))), Handler).serve_forever()
