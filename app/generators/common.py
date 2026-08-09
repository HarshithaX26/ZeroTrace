"""Python helpers shared by the policy generators."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

EXTERNAL_PREFIX = "ext:"


@dataclass(frozen=True)
class Rule:
    """One directional, least-privilege allow: ``src`` -> ``dst:port``."""

    src: str
    dst: str
    proto: str
    port: int


def is_external(name: str) -> bool:
    return name.startswith(EXTERNAL_PREFIX)


def to_rules(edges) -> list[Rule]:
    """Project service-level edges into allow/deny rules, dropping externals.

    External peers (the host, the internet) are out of scope for the
    container firewall artifacts; they fall back to ``iptables`` defaults.
    """
    rules: list[Rule] = []
    for e in edges:
        if is_external(e.src) or is_external(e.dst):
            continue
        rules.append(Rule(src=e.src, dst=e.dst, proto=e.proto, port=e.dport))
    return sorted({r for r in rules}, key=lambda r: (r.src, r.dst, r.proto, r.port))


def services_used(rules: list[Rule]) -> list[str]:
    names = {r.src for r in rules} | {r.dst for r in rules}
    return sorted(names)


def utcnow_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
