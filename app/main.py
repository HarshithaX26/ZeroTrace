"""FastAPI entry point for the zero-trace web dashboard."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import config
from app.db import init_db

ROOT = config.project_root()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="zero-trace", lifespan=lifespan)
app.mount(
    "/static",
    StaticFiles(directory=str(ROOT / "app" / "static")),
    name="static",
)

from app.routers import dashboard, flows, graph, policies, profile

app.include_router(dashboard.router)
app.include_router(profile.router)
app.include_router(flows.router)
app.include_router(graph.router)
app.include_router(policies.router)
