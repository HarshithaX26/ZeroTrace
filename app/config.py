"""Configuration for the zero-trace application."""

from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    """Absolute path to the repository root (parent of the ``app`` package)."""
    return Path(__file__).resolve().parent.parent


# Can be overridden via ZERO_TRACE_WORKSPACE so the app can operate on any
# project directory (the "swappable" property).
WORKSPACE = Path(os.environ.get("ZERO_TRACE_WORKSPACE", project_root()))

# Per-project working directory for captures, overrides, and generated output.
DATA_DIR = WORKSPACE / ".zero-trace"

# Sqlite database with profiles, flows, and policies.
DB_PATH = DATA_DIR / "zero-trace.db"

# Docker daemon Unix socket used for IP -> service resolution.
DOCKER_SOCKET = os.environ.get("DOCKER_HOST", "unix:///var/run/docker.sock")
