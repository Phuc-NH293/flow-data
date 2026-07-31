#!/usr/bin/env python3
"""Small local demo page for the commit analytics dashboard.

It serves two surfaces:
1. a lightweight Chart.js preview built directly from the mart table; and
2. a guest-embedded Metabase dashboard if the embed has been provisioned.
"""

import base64
import hashlib
import hmac
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
from psycopg2.extras import RealDictCursor

ROOT = Path(__file__).parent
EMBED_META = ROOT / "metabase_embed.json"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def sign_guest_jwt(resource_type: str, resource_id: int, params: dict | None = None) -> str:
    secret = os.environ["MB_EMBEDDING_SECRET_KEY"].encode()
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "resource": {resource_type: resource_id},
        "params": params or {},
        "exp": int(time.time()) + 600,
    }
    signing_input = f"{_b64url(json.dumps(header, separators=(',', ':')).encode())}.{_b64url(json.dumps(payload, separators=(',', ':')).encode())}"
    signature = hmac.new(secret, signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url(signature)}"


def load_embed_meta() -> dict | None:
    if not EMBED_META.exists():
        return None
    return json.loads(EMBED_META.read_text())


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
        if path == "/api/embed-config":
            meta = load_embed_meta()
            if not meta:
                self.send_error(404)
                return
            self.send_json(
                {
                    "dashboard_id": meta["dashboard_id"],
                    "metabase_url": os.getenv("METABASE_PUBLIC_URL", "http://localhost:3001"),
                }
            )
            return
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

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/metabase-guest-token":
            meta = load_embed_meta()
            if not meta:
                self.send_error(404, "Metabase dashboard is not provisioned yet")
                return
            length = int(self.headers.get("Content-Length", "0") or "0")
            body = json.loads(self.rfile.read(length) or b"{}")
            entity_type = body.get("entityType", "dashboard")
            entity_id = int(body.get("entityId") or meta["dashboard_id"])
            params = body.get("params") or {}
            self.send_json({"jwt": sign_guest_jwt(entity_type, entity_id, params)})
            return
        self.send_error(404)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", int(os.getenv("DEMO_PORT", "8090"))), Handler).serve_forever()
