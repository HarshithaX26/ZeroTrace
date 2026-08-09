"""Policy review: render the generated hardening artifacts for a profile."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from sqlmodel import select

from app import config
from app.db import SessionDep, new_session
from app.engine.graph import Edge
from app.generators import generate_all
from app.models import FlowEdge, Profile
from app.templating import templates

router = APIRouter()

POLICY = "zero-trace.policy.yaml"
COMPOSE = "compose.hardened.yml"
IPTABLES = "iptables.hardened.sh"
ARTIFACTS = (POLICY, COMPOSE, IPTABLES)


def _out_dir(profile_id: int) -> Path:
    return config.DATA_DIR / "policies" / f"profile-{profile_id}"


def _generate(profile: Profile) -> Path:
    with new_session() as session:
        rows = session.exec(
            select(FlowEdge).where(FlowEdge.profile_id == profile.id)
        ).all()
    edges = [Edge(src=r.src, dst=r.dst, proto=r.proto, dport=r.dport) for r in rows]
    out = _out_dir(profile.id)
    generate_all(
        profile.project,
        edges,
        out_dir=out,
        profile_id=profile.id,
    )
    return out


@router.get("/policies/{profile_id}", response_class=HTMLResponse)
def policies_page(
    profile_id: int, request: Request, session: SessionDep
) -> HTMLResponse:
    p = session.get(Profile, profile_id)
    if p is None:
        raise HTTPException(404, "profile not found")
    out = _generate(p)
    return templates.TemplateResponse(
        request,
        "policies.html",
        {
            "profile": p,
            "policy": (out / POLICY).read_text(),
            "compose": (out / COMPOSE).read_text(),
            "iptables": (out / IPTABLES).read_text(),
        },
    )


@router.get("/api/policies/{profile_id}/{artifact}")
def policy_artifact(
    profile_id: int, artifact: str, session: SessionDep
) -> PlainTextResponse:
    p = session.get(Profile, profile_id)
    if p is None:
        raise HTTPException(404, "profile not found")
    if artifact not in ARTIFACTS:
        raise HTTPException(400, "unknown artifact")
    out = _out_dir(profile_id)
    path = out / artifact
    if not path.exists():
        _generate(p)
    return PlainTextResponse(path.read_text())
