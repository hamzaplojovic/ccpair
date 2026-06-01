import click
import json
import os
from pathlib import Path
from claude_pair.constants import DEFAULT_PORT, DISCOVERY_TIMEOUT
from claude_pair.server import run as run_mcp
from claude_pair.session import host_session, join_session

_PAIR_DIR = Path(os.environ.get("CLAUDE_PAIR_DIR", str(Path.home() / ".claude-pair")))


def _version():
    from importlib.metadata import version
    return version("ccpair")


@click.group()
@click.version_option(_version(), prog_name="ccpair")
def cli(): pass


@cli.command()
@click.option("--port", default=DEFAULT_PORT, show_default=True)
@click.option("--name", default="host", show_default=True)
@click.option("--parent-pid", default=None, type=int, hidden=True)
def host(port: int, name: str, parent_pid: int | None) -> None:
    """Start a pair session as host."""
    host_session(name, port, parent_pid=parent_pid)


@cli.command()
@click.argument("code")
@click.option("--name", default="guest", show_default=True)
@click.option("--timeout", default=DISCOVERY_TIMEOUT, show_default=True)
@click.option("--parent-pid", default=None, type=int, hidden=True)
def join(code: str, name: str, timeout: float, parent_pid: int | None) -> None:
    """Join an existing pair session by code."""
    join_session(code, name, timeout, parent_pid=parent_pid)


@cli.command()
def mcp() -> None:
    """Start the MCP server (used by Claude Code)."""
    run_mcp()


@cli.command()
@click.option("--project-dir", default=".", show_default=True,
              help="Project directory to write .mcp.json into.")
def install(project_dir: str) -> None:
    """Wire ccpair into Claude Code (hooks, statusline, MCP, skills)."""
    from claude_pair.installer import install as do_install
    do_install(Path(project_dir).resolve())


@cli.command()
def status() -> None:
    """Show current session status."""
    status_file = _PAIR_DIR / "status.json"
    if not status_file.exists():
        click.echo("no active session")
        return
    try:
        data = json.loads(status_file.read_text())
        s = data.get("status", "unknown")
        if s == "waiting":
            click.echo(f"waiting  code={data.get('code', '?')}")
        elif s == "connected":
            click.echo(f"connected  peer={data.get('peer', '?')}  role={data.get('role', '?')}")
        else:
            click.echo(s)
    except Exception as e:
        click.echo(f"error reading status: {e}", err=True)


@cli.command()
@click.option("-n", default=50, show_default=True, help="Number of lines to show.")
def logs(n: int) -> None:
    """Tail the session log."""
    log_file = _PAIR_DIR / "session.log"
    if not log_file.exists():
        click.echo("no log file found")
        return
    lines = log_file.read_text().splitlines()
    click.echo("\n".join(lines[-n:]))
