"""Shared application service used by both the ``auth`` and ``orders`` roles.

Every operation touches the shared Postgres database so profiling captures
real cross-service traffic (app tier -> db).
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import time
import uuid

import psycopg2
from fastapi import FastAPI

DB_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@db:5432/shop"
)
ROLE = os.environ.get("SERVICE_ROLE", "unknown")


def connect() -> psycopg2.extensions.connection:
    return psycopg2.connect(DB_URL, connect_timeout=5)


def _init_db() -> None:
    for _ in range(30):
        try:
            with connect() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS events (
                        id TEXT PRIMARY KEY,
                        role TEXT NOT NULL,
                        ts REAL NOT NULL
                    )
                    """
                )
            return
        except psycopg2.Error:
            time.sleep(2)


async def _heartbeat() -> None:
    # Steady, unsolicited app->db traffic so captures show the baseline even
    # when nothing external is driving the stack.
    while True:
        with contextlib.suppress(Exception):
            with connect() as conn, conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO events (id, role, ts) VALUES (%s, %s, %s)",
                    (str(uuid.uuid4()), ROLE, time.time()),
                )
        await asyncio.sleep(10)


@contextlib.asynccontextmanager
async def lifespan(_: FastAPI):
    _init_db()
    task = asyncio.create_task(_heartbeat())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)


@app.get("/api/{role}/health")
def health(role: str) -> dict:
    return {"ok": True, "role": role, "svc": ROLE}


@app.post("/api/{role}/ping")
def ping(role: str) -> dict:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO events (id, role, ts) VALUES (%s, %s, %s)",
            (str(uuid.uuid4()), role, time.time()),
        )
    return {"pong": True, "role": role, "svc": ROLE}


@app.get("/api/{role}/events")
def events(role: str) -> dict:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, role, ts FROM events ORDER BY ts DESC LIMIT 20")
        rows = [{"id": r[0], "role": r[1], "ts": r[2]} for r in cur.fetchall()]
    return {"role": role, "svc": ROLE, "events": rows}