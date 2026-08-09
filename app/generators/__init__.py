"""Generators: emit the three hardening artifacts from the observed edges."""

from __future__ import annotations

from pathlib import Path

from app.generators import compose, iptables, policy

POLICY = "zero-trace.policy.yaml"
COMPOSE = "compose.hardened.yml"
IPTABLES = "iptables.hardened.sh"
ARTIFACTS = (POLICY, COMPOSE, IPTABLES)


def generate_all(
    project_dir: str | Path,
    edges,
    *,
    out_dir: Path,
    profile_id: int | None = None,
    project_compose: str | None = None,
) -> dict[str, Path]:
    """Emit policy yaml, hardened compose, and the iptables script.

    ``project_compose`` is the compose *project name* used for iptables IP
    resolution at apply time; it defaults to the project's own ``name:`` or
    its directory name.
    """
    project = Path(project_dir).name
    compose_name = project_compose or compose.compose_project_name(project_dir)

    out_dir.mkdir(parents=True, exist_ok=True)

    policy.write(
        policy.build_policy(edges, project=project, profile_id=profile_id),
        out_dir / POLICY,
    )
    compose.write(project_dir, edges, out_dir=out_dir)
    iptables.write(compose_name, edges, out_dir=out_dir)

    return {
        "policy": out_dir / POLICY,
        "compose": out_dir / COMPOSE,
        "iptables": out_dir / IPTABLES,
    }
