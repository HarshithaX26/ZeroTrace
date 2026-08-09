"""The human-editable source of truth: ``zero-trace.policy.yaml``.

The generator emits exactly the observed reachability as an *allowlist*.
Editors can delete rules (e.g. a rogue service's DB access) and re-render
the hardened compose + iptables from the edited file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.generators.common import Rule, to_rules, utcnow_iso


def build_policy(edges, *, project: str, profile_id: int | None) -> dict[str, Any]:
    rules = to_rules(edges)
    return {
        "metadata": {
            "project": project,
            "profile_id": profile_id,
            "generated_at": utcnow_iso(),
            "description": (
                "Least-privilege allowlist. Delete any rule to revoke a "
                "relationship, then re-generate."
            ),
        },
        "allow": [
            {"from": r.src, "to": r.dst, "proto": r.proto, "port": r.port}
            for r in rules
        ],
    }


def dump(policy: dict[str, Any]) -> str:
    return yaml.safe_dump(policy, sort_keys=False, default_flow_style=False)


def write(policy: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump(policy), encoding="utf-8")
    return path


def load(path: str | Path) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def rules_from_policy(policy: dict[str, Any]) -> list[Rule]:
    return sorted(
        (
            Rule(src=r["from"], dst=r["to"], proto=r["proto"], port=int(r["port"]))
            for r in policy["allow"]
        ),
        key=lambda r: (r.src, r.dst, r.proto, r.port),
    )
