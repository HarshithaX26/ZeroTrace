"""Flow table: list discovered service->service edges for a profile."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import select

from app.db import SessionDep
from app.models import FlowEdge, Profile
from app.templating import templates

router = APIRouter()


@router.get("/flows", response_class=HTMLResponse)
def flows_page(profile_id: int, request: Request, session: SessionDep) -> HTMLResponse:
    p = session.get(Profile, profile_id)
    if p is None:
        raise HTTPException(404, "profile not found")
    rows = session.exec(
        select(FlowEdge)
        .where(FlowEdge.profile_id == profile_id)
        .order_by(FlowEdge.packets.desc())
    ).all()
    return templates.TemplateResponse(
        request, "flows.html", {"profile": p, "edges": rows}
    )


@router.get("/api/flows")
def flows_api(profile_id: int, session: SessionDep) -> list[dict[str, Any]]:
    rows = session.exec(
        select(FlowEdge)
        .where(FlowEdge.profile_id == profile_id)
        .order_by(FlowEdge.packets.desc())
    ).all()
    return [
        {
            "src": r.src,
            "dst": r.dst,
            "proto": r.proto,
            "dport": r.dport,
            "packets": r.packets,
            "bytes": r.bytes,
        }
        for r in rows
    ]
