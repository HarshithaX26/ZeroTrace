"""Shared Jinja2 template loader."""

from __future__ import annotations

from fastapi.templating import Jinja2Templates

from app import config

templates = Jinja2Templates(directory=str(config.project_root() / "app" / "templates"))
