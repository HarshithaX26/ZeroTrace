"""The profiling pipeline: bring up a target stack with capture sidecars,
exercise it, capture to pcap, then parse into service-level edges.

Web workers and the CLI both call :func:`run_profile`; only persistence differs.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from collections.abc import Callable, Sequence
from pathlib import Path

import httpx

from app.capture import collector, sidecar
from app.engine.graph import Edge
from app.engine.resolver import DockerResolver

log = logging.getLogger(__name__)

DEFAULT_FRONTEND = "http://localhost:8080"

EventCB = Callable[[str, str], None]


def _noop(_event: str, _message: str) -> None:
    pass


def compose_command(files: Sequence[Path], *args: str) -> list[str]:
    cmd = ["docker", "compose"]
    for f in files:
        cmd += ["-f", str(f)]
    cmd += list(args)
    return cmd


def _run(
    cmd: Sequence[str], on_event: EventCB, timeout: int = 120
) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        list(cmd), capture_output=True, text=True, timeout=timeout, check=False
    )
    if proc.returncode != 0:
        on_event(
            "error",
            f"{' '.join(cmd[2:])} exited {proc.returncode}: {proc.stderr.strip()[:300]}",
        )
    return proc


def _clear_captures() -> None:
    sidecar.CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    for pcap in sidecar.CAPTURE_DIR.glob("**/*.pcap"):
        pcap.unlink(missing_ok=True)


def _wait_for_frontend(on_event: EventCB, timeout: float = 90.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if httpx.get(DEFAULT_FRONTEND, timeout=2).status_code < 500:
                return True
        except httpx.HTTPError:
            pass
        time.sleep(2)
    return False


def _drive_traffic() -> int:
    """Send a handful of requests through the frontend; return requests sent."""
    endpoints = [
        ("GET", "/api/auth/health"),
        ("POST", "/api/auth/ping"),
        ("GET", "/api/orders/events"),
        ("GET", "/api/orders/health"),
    ]
    hit = 0
    with httpx.Client(timeout=3) as client:
        for _ in range(6):
            for method, path in endpoints:
                try:
                    client.request(method, DEFAULT_FRONTEND + path)
                    hit += 1
                except httpx.HTTPError:
                    pass
            time.sleep(1)
    return hit


def run_profile(
    project: str | Path,
    *,
    duration: int = 60,
    on_event: EventCB = _noop,
) -> list[Edge]:
    """Run one full capture profile against ``project`` and return edges.

    Starts the target stack (with injected capture sidecars), waits for it to
    come up, snapshots container IPs, drives traffic through the frontend,
    captures for ``duration`` seconds, then tears the stack down and resolves
    the pcaps into service-level edges. Progress is streamed via ``on_event``.
    """
    root = Path(project)
    on_event("resolve", f"Reading compose project {root.name}")
    files = sidecar.compose_files(root)

    on_event("override", "Rendering capture override")
    override = sidecar.build_override(files)
    override_file = sidecar.write_override(override)

    _clear_captures()
    on_event("start", "Starting stack with capture sidecars")
    _run(
        compose_command(
            files, "-f", str(override_file), "up", "-d", "--remove-orphans"
        ),
        on_event,
    )

    ip_map: dict[str, str] = {}
    try:
        if _wait_for_frontend(on_event):
            on_event("ready", "Reset ready")
        else:
            on_event(
                "warning",
                f"Frontend not reachable on {DEFAULT_FRONTEND}; capturing anyway",
            )

        on_event("index", "Indexing container IPs -> services")
        ip_map = DockerResolver().snapshot()
        (sidecar.CAPTURE_DIR / "ip_map.json").write_text(
            json.dumps(ip_map), encoding="utf-8"
        )

        on_event("capture", f"Exercising stack and capturing for {duration}s")
        hit = _drive_traffic()
        on_event("exercise", f"Drove {hit} requests through the frontend")
        time.sleep(max(0, duration - 6))
    finally:
        on_event("stop", "Stopping capture stack")
        _run(
            compose_command(
                files, "-f", str(override_file), "down", "--remove-orphans"
            ),
            on_event,
        )

    on_event("parse", "Parsing pcaps into a service graph")
    edges = collector.load_edges(sidecar.CAPTURE_DIR, ip_map)
    on_event("done", f"Completed: {len(edges)} allowed edge(s)")
    return edges
