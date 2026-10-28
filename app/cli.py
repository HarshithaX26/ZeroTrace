"""zero-trace command-line interface.

Commands are stubs wired into ``app.capture``, ``app.engine`` and
``app.generators`` as they are implemented (build steps 2-4).
"""

from __future__ import annotations

from pathlib import Path

import typer

from app import __version__
from app.config import DATA_DIR

app = typer.Typer(
    name="zero-trace",
    help="Profile a Docker Compose project and emit least-privilege network policies.",
    no_args_is_help=True,
)

# Re-export the Typer app under a conventional name so ``projects.scripts``
# can point at it.
main = app


@app.command()
def version() -> None:
    """Print the installed zero-trace version."""
    typer.echo(f"zero-trace {__version__}")


@app.callback()
def _prepare(ctx: typer.Context) -> None:
    """Ensure the per-project working directory exists before any command runs."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ctx.ensure_object(dict)


@app.command()
def profile(
    project: str = typer.Option(
        "env",
        "--project",
        "-p",
        help="Path to the target Docker Compose project directory.",
    ),
    duration: int = typer.Option(
        60,
        "--duration",
        "-d",
        help="Capture window in seconds.",
    ),
) -> None:
    """Run a passive capture against a running compose stack and ingest flows."""
    from app.capture import sidecar
    from app.engine.graph import graph_edges
    from app.service import run_profile

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    def report(stage: str, message: str) -> None:
        typer.echo(f"[{stage:<9}] {message}", err=True)

    if not sidecar.compose_files(project):
        raise typer.BadParameter(f"No compose file in project: {project}")

    edges = run_profile(project, duration=duration, on_event=report)

    typer.echo("\nDetected reachability:")
    for e in graph_edges(edges):
        typer.echo(f"  {e.src} -> {e.dst}  tcp/{e.dport:<5} {e.packets:>6} pkts")
    typer.echo(f"\n{len(edges)} edge(s) detected.")


@app.command()
def generate(
    profile_id: int | None = typer.Option(
        None,
        "--profile",
        help="Profile id to generate policies from (default: latest done).",
    ),
    out: str = typer.Option(
        None,
        "--out",
        help="Output directory (default: <data>/policies/<project>).",
    ),
) -> None:
    """Generate policy artifacts from a previously captured profile."""
    from sqlmodel import select

    from app.db import new_session
    from app.engine.graph import Edge
    from app.generators import generate_all
    from app.models import FlowEdge, Profile

    with new_session() as session:
        if profile_id is not None:
            profile = session.get(Profile, int(profile_id))
            if profile is None:
                raise typer.BadParameter(f"no profile #{profile_id}")
        else:
            profile = session.exec(
                select(Profile)
                .where(Profile.status == "done")
                .order_by(Profile.id.desc())
            ).first()
        if profile is None:
            typer.echo(
                "No completed profile found; run 'zero-trace profile' first.", err=True
            )
            raise typer.Exit(1)

        rows = session.exec(
            select(FlowEdge)
            .where(FlowEdge.profile_id == profile.id)
            .order_by(FlowEdge.id)
        ).all()
        edges = [Edge(src=r.src, dst=r.dst, proto=r.proto, dport=r.dport) for r in rows]
        if not edges:
            typer.echo(f"Profile #{profile.id} has no edges.", err=True)
            raise typer.Exit(1)

    out_dir = Path(out) if out else DATA_DIR / "policies" / Path(profile.project).name
    paths = generate_all(
        profile.project,
        edges,
        out_dir=out_dir,
        profile_id=profile.id,
        project_compose=None,
    )

    typer.echo(f"Profile #{profile.id} -> {len(edges)} edge(s)")
    for artifact, path in paths.items():
        typer.echo(f"  {artifact:<8} {path}")


@app.command()
def serve_web(
    host: str = typer.Option("127.0.0.1", help="Bind address."),
    port: int = typer.Option(8000, help="Bind port."),
) -> None:
    """Start the FastAPI web dashboard."""
    import uvicorn

    uvicorn.run("app.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
