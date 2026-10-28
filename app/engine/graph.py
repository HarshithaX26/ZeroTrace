"""Reachability model: service-level edges aggregated from raw flows."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.engine.parser import Flow, FlowKey


@dataclass(frozen=True)
class Edge:
    """One least-privilege candidate: ``src`` may talk to ``dst`` on a port."""

    src: str
    dst: str
    proto: str
    dport: int
    packets: int = 0
    bytes: int = 0
    first_ts: float = 0.0
    last_ts: float = 0.0

    @property
    def id(self) -> str:
        return f"{self.src}->{self.dst}:{self.proto}/{self.dport}"


def _merge(a: Edge, b: Edge) -> Edge:
    return Edge(
        src=a.src,
        dst=a.dst,
        proto=a.proto,
        dport=a.dport,
        packets=a.packets + b.packets,
        bytes=a.bytes + b.bytes,
        first_ts=min(a.first_ts, b.first_ts),
        last_ts=max(a.last_ts, b.last_ts),
    )


# TCP/UDP ephemeral source-port threshold (RFC 6335 high range).
EPHEMERAL_PORT = 32768


def _display_name(ip: str, service: str | None) -> str:
    if service:
        return service
    # Unknown host: keep the ip visible so unexpected peers stand out.
    return f"ext:{ip}"


def build_edges(
    flows: Iterable[Flow],
    ip_to_service: dict[str, str],
) -> dict[str, Edge]:
    """Resolve raw flows to service-level edges and merge duplicates.

    Every connection is witnessed twice (once per endpoint). Worse, the ACK
    return-traffic looks like an independent flow aimed at an ephemeral port,
    fragmenting one real relationship into a pile of near-duplicate edges.
    Two rules collapse the noise:

    1. The TCP SYN establishes ground truth for "who is the server": its
       destination port is the listening port. Directions carrying zero SYN
       packets are return-traffic and fold back into the reverse listening
       edge.
    2. UDP / ICMP (no SYN) fall back to a port-range heuristic for the same
       purpose.
    """
    raw: dict[str, Edge] = {}
    # (proto, src, dst) -> (edge_id, port) of the listening edge that SYNs
    # into whatever. Keeping the smallest port across a direction.
    prim: dict[tuple[str, str, str], tuple[str, int]] = {}

    for flow in flows:
        key: FlowKey = flow.key
        src = _display_name(key.src_ip, ip_to_service.get(key.src_ip))
        dst = _display_name(key.dst_ip, ip_to_service.get(key.dst_ip))
        edge_id = f"{src}->{dst}:{key.proto}/{key.dport}"

        base = Edge(
            src=src,
            dst=dst,
            proto=key.proto,
            dport=key.dport,
            packets=flow.packets,
            bytes=flow.bytes,
            first_ts=flow.first_ts,
            last_ts=flow.last_ts,
        )
        if prev_edge := raw.get(edge_id):
            raw[edge_id] = _merge(prev_edge, base)
        else:
            raw[edge_id] = base

        is_listener = flow.syn > 0 or (
            key.proto != "tcp" and key.dport < EPHEMERAL_PORT
        )
        if is_listener:
            pk = (key.proto, src, dst)
            current = prim.get(pk)
            if current is None or key.dport < current[1]:
                prim[pk] = (edge_id, key.dport)

    return _fold_return_traffic(raw, prim)


def _fold_return_traffic(
    raw: dict[str, Edge],
    prim: dict[tuple[str, str, str], tuple[str, int]],
) -> dict[str, Edge]:
    """Merge zero-SYN reverse traffic into the paired listening edge."""
    out: dict[str, Edge] = {}

    for edge_id, edge in raw.items():
        out.setdefault(edge_id, edge)

    for edge_id, edge in raw.items():
        pk = (edge.proto, edge.src, edge.dst)
        if edge_id == (prim.get(pk) or (None, None))[0]:
            continue  # a listener; keep as-is
        rev = prim.get((edge.proto, edge.dst, edge.src))
        if rev is None:
            continue
        host_id = rev[0]
        out[host_id] = _merge(out.get(host_id, raw[host_id]), edge)
        out.pop(edge_id, None)

    return out


def graph_edges(edges: Iterable[Edge]) -> list[Edge]:
    """Return edges in a stable display order (service pair, then port)."""
    return sorted(
        edges,
        key=lambda e: (e.src, e.dst, e.proto, e.dport),
    )
