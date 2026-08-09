"""Service topology graph for a profile."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import select

from app.db import SessionDep
from app.models import FlowEdge, Profile
from app.templating import templates

router = APIRouter()


@router.get("/graph/{profile_id}", response_class=HTMLResponse)
def graph_page(profile_id: int, request: Request, session: SessionDep) -> HTMLResponse:
    p = session.get(Profile, profile_id)
    if p is None:
        raise HTTPException(404, "profile not found")
    return templates.TemplateResponse(request, "graph.html", {"profile": p})


@router.get("/api/graph/{profile_id}")
def graph_api(profile_id: int, session: SessionDep) -> dict[str, Any]:
    rows = session.exec(select(FlowEdge).where(FlowEdge.profile_id == profile_id)).all()
    nodes: dict[str, dict[str, Any]] = {}
    for r in rows:
        for name in (r.src, r.dst):
            nodes.setdefault(
                name,
                {
                    "id": name,
                    "label": name.split(":")[-1],
                    "external": name.startswith("ext:"),
                },
            )
    edges = [
        {
            "data": {
                "id": f"{r.src}-{r.dst}-{r.proto}-{r.dport}",
                "source": r.src,
                "target": r.dst,
                "label": f"{r.proto}/{r.dport}",
                "packets": r.packets,
            }
        }
        for r in rows
    ]
    return {"nodes": [{"data": v} for v in nodes.values()], "edges": edges}
