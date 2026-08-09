"""Profile lifecycle: start runs, stream progress (SSE), and query status."""

from __future__ import annotations

import asyncio
import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlmodel import select

from app import config
from app.capture import sidecar
from app.db import SessionDep, new_session
from app.engine.graph import Edge
from app.models import FlowEdge, Profile
from app.service import run_profile
from app.templating import templates

router = APIRouter()


class StartRequest(BaseModel):
    project: str = "env"
    duration: int = 45


def _append_event(profile_id: int, stage: str, message: str) -> None:
    with new_session() as session:
        p = session.get(Profile, profile_id)
        if p is None:
            return
        events = json.loads(p.events)
        events.append(
            {
                "stage": stage,
                "msg": message,
                "ts": datetime.now(UTC).isoformat(),
            }
        )
        p.events = json.dumps(events)
        if stage == "done":
            p.status = "done"
            p.finished_at = datetime.now(UTC)
        elif stage == "error":
            p.status = "failed"
            p.error = message
        else:
            p.status = "running"
        session.add(p)
        session.commit()


def _persist_edges(profile_id: int, edges: list[Edge]) -> None:
    with new_session() as session:
        session.add_all(
            [
                FlowEdge(
                    profile_id=profile_id,
                    src=e.src,
                    dst=e.dst,
                    proto=e.proto,
                    dport=e.dport,
                    packets=e.packets,
                    bytes=e.bytes,
                    first_ts=e.first_ts,
                    last_ts=e.last_ts,
                )
                for e in edges
            ]
        )
        session.commit()


def _worker(profile_id: int, project: str, duration: int) -> None:
    try:
        edges = run_profile(
            project,
            duration=duration,
            on_event=lambda s, m: _append_event(profile_id, s, m),
        )
        _persist_edges(profile_id, edges)
    except BaseException as exc:  # noqa: BLE001 - background-forever guard
        _append_event(profile_id, "error", f"{type(exc).__name__}: {exc}")


@router.post("/api/profiles")
def start(request: StartRequest) -> dict[str, Any]:
    project = config.WORKSPACE / request.project
    if not sidecar.compose_files(project):
        raise HTTPException(400, f"no compose files under {project}")

    with new_session() as session:
        p = Profile(project=str(project), status="running")
        session.add(p)
        session.commit()
        session.refresh(p)
        profile_id = p.id

    threading.Thread(
        target=_worker, args=(profile_id, str(project), request.duration), daemon=True
    ).start()
    return {"profile_id": profile_id}


@router.get("/profiles/{profile_id}", response_class=HTMLResponse)
def profile_page(
    profile_id: int, request: Request, session: SessionDep
) -> HTMLResponse:
    p = session.get(Profile, profile_id)
    if p is None:
        raise HTTPException(404, "profile not found")
    return templates.TemplateResponse(request, "profile.html", {"profile": p})


@router.get("/api/profiles")
def list_profiles(session: SessionDep) -> list[dict[str, Any]]:
    rows = session.exec(select(Profile).order_by(Profile.id.desc())).all()
    return [_profile_view(p) for p in rows]


@router.get("/api/profiles/{profile_id}")
def profile_api(profile_id: int, session: SessionDep) -> dict[str, Any]:
    p = session.get(Profile, profile_id)
    if p is None:
        raise HTTPException(404, "profile not found")
    return _profile_view(p)


def _profile_view(p: Profile) -> dict[str, Any]:
    return {
        "id": p.id,
        "project": Path(p.project).name if p.project else p.project,
        "status": p.status,
        "started_at": p.started_at.isoformat(),
        "events": json.loads(p.events),
        "error": p.error,
    }


@router.get("/api/profiles/{profile_id}/events")
async def profile_events(profile_id: int):
    """Server-sent events: a JSON blob whenever the profile state changes."""
    last: tuple | None = None
    while True:
        with new_session() as session:
            p = session.get(Profile, profile_id)
            if p is None:
                yield 'data: {"error": "profile not found"}\n\n'
                break
            state = (p.status, p.events, p.error)
        if state != last:
            last = state
            yield f"data: {json.dumps({'status': p.status, 'events': json.loads(p.events), 'error': p.error})}\n\n"
        await asyncio.sleep(1)
