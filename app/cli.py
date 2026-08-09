"""zero-trace command-line interface.

Commands are stubs wired into ``app.capture``, ``app.engine`` and
``app.generators`` as they are implemented (build steps 2-4).
"""

from __future__ import annotations

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
    """Run a passive capture against a running compose stack and ingest flows.

    Delegates to ``app.capture.sidecar`` (compose override injection),
    ``app.capture.collector`` and ``app.engine``.
    """
    # TODO(build step 2/3): sidecar override + collect + parse + resolve.
    raise typer.Exit("profile: capture pipeline not implemented yet")


@app.command()
def generate(
    profile_id: str = typer.Option(
        ...,
        "--profile",
        help="Profile id to generate policies from.",
    ),
) -> None:
    """Generate policy artifacts (zero-trace.policy.yaml, hardened compose, iptables).

    Delegates to the ``app.generators`` package.
    """
    # TODO(build step 4): emit policy/compose/iptables.
    raise typer.Exit("generate: policy generators not implemented yet")


@app.command()
def serve_web(
    host: str = typer.Option("127.0.0.1", help="Bind address."),
    port: int = typer.Option(8000, help="Bind port."),
) -> None:
    """Start the FastAPI web dashboard."""
    # TODO(build step 5): uvicorn.run("app.main:app", ...)
    raise typer.Exit("serve: web dashboard not implemented yet")


if __name__ == "__main__":
    main()
