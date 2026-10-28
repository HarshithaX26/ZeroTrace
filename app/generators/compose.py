"""Hardened compose: one private bridge network per allowed peer pair.

Every service joins only the networks that carry an allowed flow (plus a
single non-internal ``zt_ingress`` network for services that publish ports).
Docker's own DNS then *enforces* the least-privilege graph: a service simply
cannot resolve peers that share no network with it.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from app.capture import sidecar
from app.generators.common import Rule, to_rules

INGRESS_NET = "zt_ingress"


def unique_pairs(rules: list[Rule]) -> list[tuple[str, str]]:
    """Undirected service pairs with an allowed relationship."""
    seen: set[str] = set()
    pairs: list[tuple[str, str]] = []
    for r in rules:
        a, b = sorted((r.src, r.dst))
        if (a, b) not in seen:
            seen.add((a, b))
            pairs.append((a, b))
    return pairs


def network_name(a: str, b: str) -> str:
    return f"ztnet_{a}__{b}"


def compose_project_name(project_dir: str | Path) -> str:
    """The compose project name (``name:`` key) or the directory name."""
    spec = _raw_compose_spec(project_dir)
    return spec.get("name") or Path(project_dir).name


def _raw_compose_spec(project_dir: str | Path) -> dict[str, Any]:
    """Load the target project's own compose YAML (deep, single-file merge)."""
    files = sidecar.compose_files(project_dir)
    merged: dict[str, Any] = {}
    for f in files:
        raw = yaml.safe_load(Path(f).read_text(encoding="utf-8")) or {}
        for key, value in raw.items():
            if isinstance(value, dict):
                merged.setdefault(key, {})
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value
    return merged


def build_compose(
    project_dir: str | Path, edges, *, internal: bool = True
) -> dict[str, Any]:
    """Build a hardened compose spec from the project's own services."""
    rules = to_rules(edges)
    base = _raw_compose_spec(project_dir)
    services_raw = base.get("services") or {}

    published: set[str] = {
        name
        for name, svc in services_raw.items()
        if isinstance(svc, dict) and svc.get("ports")
    }
    pairs = unique_pairs(rules)

    hardened: dict[str, Any] = {"services": {}, "networks": {}}
    for svc_name, svc in services_raw.items():
        out = copy.deepcopy(svc)
        out.pop("networks", None)
        nets = {network_name(a, b) for a, b in pairs if svc_name in (a, b)}
        if svc_name in published:
            nets.add(INGRESS_NET)
        out["networks"] = sorted(nets)
        hardened["services"][svc_name] = out

    for a, b in pairs:
        name = network_name(a, b)
        hardened["networks"][name] = (
            {"driver": "bridge", "internal": True} if internal else {"driver": "bridge"}
        )
    if published:
        hardened["networks"][INGRESS_NET] = {"driver": "bridge"}

    # Preserve volumes/other top-level keys for a drop-in replacement.
    for key in ("volumes", "configs", "secrets"):
        if key in base:
            hardened[key] = base[key]

    return hardened


def render(hardened: dict[str, Any]) -> str:
    return yaml.safe_dump(hardened, sort_keys=False, default_flow_style=False)


def render_for_project(project_dir: str | Path, edges) -> dict[str, Any]:
    """Shorthand: build a hardened compose from the project's own services."""
    return build_compose(project_dir, edges)


def write(project_dir: str | Path, edges, *, out_dir: Path) -> Path:
    spec = render_for_project(project_dir, edges)
    target = out_dir / "compose.hardened.yml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(spec), encoding="utf-8")
    return target
