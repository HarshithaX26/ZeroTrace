"""Unit tests for the hardening generators."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.engine.graph import Edge
from app.generators import common, compose, generate_all, iptables, policy

BASE_COMPOSE = """
name: zt-env
services:
  frontend:
    build: ./services/frontend
    ports: ["8080:80"]
  auth:
    build: ./services/api
  orders:
    build: ./services/api
  db:
    image: postgres:16-alpine
  rogue:
    build: ./services/rogue
"""


def _edges() -> list[Edge]:
    return [
        Edge(src="frontend", dst="auth", proto="tcp", dport=8000),
        Edge(src="frontend", dst="orders", proto="tcp", dport=8000),
        Edge(src="auth", dst="db", proto="tcp", dport=5432),
        Edge(src="orders", dst="db", proto="tcp", dport=5432),
        Edge(src="rogue", dst="db", proto="tcp", dport=5432),
        Edge(src="ext:192.168.65.1", dst="frontend", proto="tcp", dport=80),
    ]


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    (tmp_path / "docker-compose.yml").write_text(BASE_COMPOSE, encoding="utf-8")
    return tmp_path


def test_to_rules_drops_external() -> None:
    rules = common.to_rules(_edges())
    assert len(rules) == 5
    assert all((r.src, r.dst) != ("ext:192.168.65.1", "frontend") for r in rules)


def test_policy_round_trip(tmp_path: Path) -> None:
    p = policy.build_policy(_edges(), project="env", profile_id=7)
    path = policy.write(p, tmp_path / "p.yaml")
    loaded = policy.load(path)
    assert loaded["metadata"]["profile_id"] == 7
    rules = policy.rules_from_policy(loaded)
    assert len(rules) == 5
    assert {r.port for r in rules} == {8000, 5432}


def test_compose_segments_into_one_network_per_pair(project: Path) -> None:
    spec = compose.build_compose(project, _edges(), internal=True)
    nets = spec["networks"]
    assert "ztnet_auth__db" in nets
    assert nets["ztnet_auth__db"] == {"driver": "bridge", "internal": True}

    frontend_nets = set(spec["services"]["frontend"]["networks"])
    assert "ztnet_auth__db" not in frontend_nets
    assert "ztnet_auth__frontend" in frontend_nets
    assert compose.INGRESS_NET in frontend_nets  # publishes a port

    assert set(spec["services"]["db"]["networks"]) == {
        "ztnet_auth__db",
        "ztnet_db__orders",
        "ztnet_db__rogue",
    }
    assert set(spec["services"]["rogue"]["networks"]) == {"ztnet_db__rogue"}


def test_compose_preserves_published_ports(project: Path) -> None:
    spec = compose.build_compose(project, _edges())
    assert spec["services"]["frontend"]["ports"] == ["8080:80"]
    # Ingress net is external; pair nets are internal by default.
    assert spec["networks"][compose.INGRESS_NET] == {"driver": "bridge"}


def test_compose_render_is_valid_yaml() -> None:
    rendered = compose.render({"services": {}, "networks": {}})
    assert yaml.safe_load(rendered) == {"services": {}, "networks": {}}


def test_iptables_script_contains_allow_and_default_drop() -> None:
    script = iptables.build_script("zt-env", _edges())
    assert (
        "iptables -A DOCKER-USER -s $IP_AUTH -d $IP_DB -p tcp --dport 5432 -j ACCEPT"
        in script
    )
    assert "iptables -A DOCKER-USER -s 172.18.0.0/16 -d 172.18.0.0/16 -j DROP" in script
    assert "svc_ip()" in script
    assert "IP_ROGUE=$(svc_ip rogue)" in script
    assert "ext:192.168.65.1" not in script


def test_generate_all_writes_three_artifacts(project: Path) -> None:
    dest = project / "out"
    paths = generate_all(project, _edges(), out_dir=dest, profile_id=1)
    assert set(paths) == {"policy", "compose", "iptables"}
    assert all(p.exists() for p in paths.values())
    assert (dest / "iptables.hardened.sh").stat().st_mode & 0o111
