"""Persisted tables for profiles and the flows they discovered."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Profile(SQLModel, table=True):
    """One capture run against a compose project."""

    id: int | None = Field(default=None, primary_key=True)
    project: str
    status: str = "queued"  # queued | running | done | failed
    started_at: datetime = Field(default_factory=_utcnow)
    finished_at: datetime | None = None
    error: str | None = None
    # JSON array of {"stage": str, "msg": str, "ts": iso} progress events.
    events: str = "[]"

    @property
    def events_parsed(self) -> list[dict]:
        """Decoded ``events`` for templates and the API."""
        try:
            return json.loads(self.events)
        except (TypeError, json.JSONDecodeError):
            return []


class FlowEdge(SQLModel, table=True):
    """One observed service->service flow, at service granularity."""

    id: int | None = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="profile.id", index=True)
    src: str
    dst: str
    proto: str
    dport: int
    packets: int = 0
    bytes: int = 0
    first_ts: float = 0.0
    last_ts: float = 0.0
