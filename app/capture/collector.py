"""Pcap collection: locate and parse the per-service capture files."""

from __future__ import annotations

from pathlib import Path

from app.engine import parser
from app.engine.graph import Edge, build_edges
from app.engine.parser import Flow


def capture_files(capture_dir: Path) -> list[tuple[str, Path]]:
    """Return ``(service_name, pcap path)`` for every capture written so far.

    Per-service captures live in ``<service>/*.pcap`` (echoing the compose
    service that each sidecar watches).
    """
    found: list[tuple[str, Path]] = []
    if not capture_dir.exists():
        return found
    for svc_dir in sorted(capture_dir.iterdir()):
        if not svc_dir.is_dir():
            continue
        for pcap in sorted(svc_dir.glob("*.pcap")):
            found.append((svc_dir.name, pcap))
    return found


def load_flows(capture_dir: Path) -> list[Flow]:
    """Parse every pcap under ``capture_dir`` into one list of flows."""
    flows: list[Flow] = []
    for _svc, path in capture_files(capture_dir):
        flows.extend(parser.parse_pcap(path).values())
    return flows


def load_edges(capture_dir: Path, ip_to_service: dict[str, str]) -> list[Edge]:
    """Parse all captures and resolve them to service-level edges."""
    return sorted(
        build_edges(load_flows(capture_dir), ip_to_service).values(),
        key=lambda e: (e.src, e.dst, e.proto, e.dport),
    )
