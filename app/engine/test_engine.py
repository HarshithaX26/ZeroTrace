"""Engine unit tests using synthetic pcaps generated with scapy."""

from __future__ import annotations

from pathlib import Path

import pytest
from scapy.all import ICMP, IP, TCP, UDP, Ether, wrpcap

from app.capture import collector
from app.engine import parser
from app.engine.resolver import StaticResolver


def _pkt(proto: str, src: str, dst: str, sport: int, dport: int, flags: str = "S"):
    base = Ether() / IP(src=src, dst=dst)
    if proto == "tcp":
        return base / TCP(sport=sport, dport=dport, flags=flags)
    return base / UDP(sport=sport, dport=dport)


@pytest.fixture()
def captures(tmp_path: Path) -> Path:
    frontend, auth, db, orders = "172.18.0.2", "172.18.0.3", "172.18.0.4", "172.18.0.5"

    # frontend's own capture: HTTP to auth and orders.
    (tmp_path / "frontend").mkdir()
    wrpcap(
        str(tmp_path / "frontend" / "eth0.pcap"),
        [_pkt("tcp", frontend, auth, 51000, 8000)] * 3
        + [_pkt("tcp", frontend, orders, 52000, 8000)] * 2,
    )
    # auth's capture: same HTTP tuples + its own postgres traffic to db.
    (tmp_path / "auth").mkdir()
    wrpcap(
        str(tmp_path / "auth" / "eth0.pcap"),
        [_pkt("tcp", frontend, auth, 51000, 8000)] * 3
        + [_pkt("tcp", auth, db, 34000, 5432)] * 5,
    )
    return tmp_path


def test_parse_pcap_counts_and_aggregates(tmp_path: Path) -> None:
    pcap = tmp_path / "single.pcap"
    wrpcap(str(pcap), [_pkt("tcp", "10.0.0.1", "10.0.0.2", 1234, 8080)] * 4)
    flows = parser.parse_pcap(pcap)
    assert len(flows) == 1
    (flow,) = flows.values()
    assert flow.packets == 4
    assert flow.key.proto == "tcp"
    assert flow.key.dport == 8080


def test_icmp_has_zero_dport(tmp_path: Path) -> None:
    pcap = tmp_path / "icmp.pcap"
    wrpcap(str(pcap), [Ether() / IP(src="1.1.1.1", dst="2.2.2.2") / ICMP()])
    (flow,) = parser.parse_pcap(pcap).values()
    assert flow.key.proto == "icmp"
    assert flow.key.dport == 0


def test_load_edges_dedupes_and_resolves(captures: Path) -> None:
    ip_map = {
        "172.18.0.2": "frontend",
        "172.18.0.3": "auth",
        "172.18.0.4": "db",
        "172.18.0.5": "orders",
    }
    edges = collector.load_edges(captures, ip_map)
    by_id = {e.id: e for e in edges}

    # frontend->auth http appears in BOTH frontend and auth pcaps -> merged.
    fe_auth = by_id["frontend->auth:tcp/8000"]
    assert fe_auth.packets == 6
    # auth->db is only in auth's pcap.
    assert by_id["auth->db:tcp/5432"].packets == 5
    assert by_id["frontend->orders:tcp/8000"].packets == 2


def test_unknown_ip_becomes_external(captures: Path) -> None:
    # Only resolve frontend; everything else is external.
    edges = collector.load_edges(captures, {"172.18.0.2": "frontend"})
    ids = {e.id for e in edges}
    assert "frontend->ext:172.18.0.3:tcp/8000" in ids


def test_reverse_ack_folded_into_listening_edge(tmp_path: Path) -> None:
    """Reverse traffic toward an ephemeral port must merge into the connection."""
    fe, auth = "172.18.0.2", "172.18.0.3"
    (tmp_path / "frontend").mkdir()
    # 3 SYNs/requests frontend->auth:8000 ...
    wrpcap(
        str(tmp_path / "frontend" / "eth0.pcap"),
        [_pkt("tcp", fe, auth, 51000, 8000)] * 3,
    )
    # ... and the ACK/return side auth->frontend:51000 (ephemeral, no SYN).
    (tmp_path / "auth").mkdir()
    wrpcap(
        str(tmp_path / "auth" / "eth0.pcap"),
        [_pkt("tcp", auth, fe, 8000, 51000, flags="A")] * 3,
    )

    ip_map = {fe: "frontend", auth: "auth"}
    edges = collector.load_edges(tmp_path, ip_map)
    by_id = {e.id: e for e in edges}

    # Only the well-known edge remains, with both directions' packets summed.
    assert list(by_id) == ["frontend->auth:tcp/8000"]
    assert by_id["frontend->auth:tcp/8000"].packets == 6


def test_static_resolver() -> None:
    r = StaticResolver({"10.0.0.1": "api"})
    assert r.service_for("10.0.0.1") == "api"
    assert r.service_for("9.9.9.9") is None
