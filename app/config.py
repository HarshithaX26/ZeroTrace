"""Configuration for the zero-trace application."""

from __future__ import annotations

import os
import platform
from pathlib import Path


def project_root() -> Path:
    """Absolute path to the repository root (parent of the ``app`` package)."""
    return Path(__file__).resolve().parent.parent


def docker_base_url() -> str:
    """Docker engine endpoint, honouring ``DOCKER_HOST`` and per-platform defaults.

    - Windows: the Docker Desktop named pipe.
    - macOS: a running Docker Desktop user socket (``~/.docker/run/docker.sock``),
      falling back to the legacy ``/var/run/docker.sock``.
    - Linux/other: the standard ``/var/run/docker.sock``.
    """
    env = os.environ.get("DOCKER_HOST")
    if env:
        return env

    system = platform.system()
    if system == "Windows":
        return "npipe:////./pipe/docker_engine"

    if system == "Darwin":
        candidates = [
            Path.home() / ".docker" / "run" / "docker.sock",
            Path("/var/run/docker.sock"),
        ]
        for sock in candidates:
            if sock.exists():
                return f"unix://{sock}"
        return f"unix://{candidates[0]}"

    return "unix:///var/run/docker.sock"


# Can be overridden via ZERO_TRACE_WORKSPACE so the app can operate on any
# project directory (the "swappable" property).
WORKSPACE = Path(os.environ.get("ZERO_TRACE_WORKSPACE", project_root()))

# Per-project working directory for captures, overrides, and generated output.
DATA_DIR = WORKSPACE / ".zero-trace"

# Sqlite database with profiles, flows, and policies.
DB_PATH = DATA_DIR / "zero-trace.db"

# Docker engine endpoint for IP -> service resolution (see docker_base_url).
DOCKER_SOCKET = docker_base_url()
