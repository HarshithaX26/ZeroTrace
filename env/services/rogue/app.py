"""Unauthorized worker: reads the shared database directly, bypassing the app
tier. This is the cross-service flow zero-trace should flag and block."""

from __future__ import annotations

import os
import time

import psycopg2

DB_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@db:5432/shop"
)

while True:
    try:
        with psycopg2.connect(DB_URL, connect_timeout=3) as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM events")
            (n,) = cur.fetchone()
        print(f"rogue: read {n} events", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"rogue: error {exc}", flush=True)
    time.sleep(15)