"""Dashboard: list recorded profiles and kick off new ones."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlmodel import select

from app.db import SessionDep
from app.models import Profile
from app.templating import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, session: SessionDep) -> HTMLResponse:
    profiles = session.exec(select(Profile).order_by(Profile.id.desc())).all()
    stats = {
        "count": len(profiles),
        "done": sum(1 for p in profiles if p.status == "done"),
    }
    return templates.TemplateResponse(
        request,
        "index.html",
        {"profiles": profiles, "stats": stats},
    )
