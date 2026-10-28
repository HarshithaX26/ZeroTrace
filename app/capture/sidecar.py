"""Compose override injection: add one tcpdump sidecar per target service.

The sidecar uses ``network_mode: service:<name>`` to share the service's
network namespace. This is what makes passive capture portable: it works on
Docker Desktop (macOS/Windows), where a second container cannot sniff the
host-side bridge, because the capture happens inside the service's own
network stack and only ever sees that service's traffic.

The generated override is written to ``<data>/capture-override.yml`` and is
applied alongside the target project's own compose file::

    docker compose -f env/docker-compose.yml \
                   -f .zero-trace/capture-override.yml up -d
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import yaml

from app.config import DATA_DIR

CAPTURE_IMAGE = os.environ.get("ZERO_TRACE_CAPTURE_IMAGE", "zero-trace/capture:latest")
OVERRIDE_FILE = DATA_DIR / "capture-override.yml"
CAPTURE_DIR = DATA_DIR / "capture"


def compose_files(project_dir: str | Path) -> list[Path]:
    """Return the compose file(s) found in a project directory, if any."""
    root = Path(project_dir)
    default = next(
        (
            root / name
            for name in (
                "docker-compose.yml",
                "docker-compose.yaml",
                "compose.yml",
                "compose.yaml",
            )
            if (root / name).exists()
        ),
        None,
    )
    if default is not None:
        return [default]
    files = sorted(root.glob("*.yml")) + sorted(root.glob("*.yaml"))
    if not files:
        raise FileNotFoundError(f"No docker-compose file found in {root}")
    return files


def _resolve_via_compose(
    compose_files: list[Path | str],
) -> dict[str, Any] | None:
    """Try ``docker compose config`` first; it is authoritative when available.

    Returns ``None`` when the daemon is unreachable so callers can fall back.
    """
    cmd = ["docker", "compose"]
    for f in compose_files:
        cmd += ["-f", str(f)]
    cmd += ["config", "--format", "json"]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        return None
    return json.loads(proc.stdout)


def _resolve_via_yaml(compose_files: list[Path | str]) -> dict[str, Any]:
    """Daemon-free fallback: merge ``services`` maps across compose files."""
    services: dict[str, Any] = {}
    name: str | None = None
    for f in compose_files:
        raw = yaml.safe_load(Path(f).read_text(encoding="utf-8")) or {}
        if raw.get("name"):
            name = raw["name"]
        for svc_name, svc in (raw.get("services") or {}).items():
            services[svc_name] = (services.get(svc_name) or {}) | (svc or {})
    if not services:
        raise ValueError(f"No services declared in {compose_files}")
    if name is None:
        name = Path(compose_files[0]).resolve().parent.name
    return {"name": name, "services": services}


def resolve_compose(compose_files: list[Path | str]) -> dict[str, Any]:
    """Return the resolved project model, preferring the Docker engine."""
    return _resolve_via_compose(compose_files) or _resolve_via_yaml(compose_files)


def build_override(compose_files: list[Path | str]) -> dict[str, Any]:
    """Construct the override mapping (name -> sidecar service definition)."""
    spec = resolve_compose(compose_files)
    services = spec["services"]

    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    override: dict[str, Any] = {"services": {}}

    for name in services:
        out_dir = CAPTURE_DIR / name
        out_dir.mkdir(exist_ok=True)
        override["services"][f"zt-{name}-cap"] = {
            "image": CAPTURE_IMAGE,
            "network_mode": f"service:{name}",
            "cap_add": ["NET_RAW", "NET_ADMIN"],
            "depends_on": {name: {"condition": "service_started"}},
            "volumes": [
                {
                    "type": "bind",
                    "source": str(out_dir),
                    "target": "/capture",
                }
            ],
            # -U flushes each packet so files stay useful even mid-capture.
            "command": ["-U", "-i", "eth0", "-n", "-w", "/capture/eth0.pcap"],
        }

    return override


def write_override(override: dict[str, Any]) -> Path:
    """Persist a rendered override next to the target compose file."""
    import yaml

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OVERRIDE_FILE.write_text(
        yaml.safe_dump(override, sort_keys=False), encoding="utf-8"
    )
    return OVERRIDE_FILE
