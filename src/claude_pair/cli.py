import click
from pathlib import Path
from claude_pair.constants import DEFAULT_PORT, DISCOVERY_TIMEOUT
from claude_pair.server import run as run_mcp
from claude_pair.session import host_session, join_session


@click.group()
def cli(): pass


@cli.command()
@click.option("--port", default=DEFAULT_PORT, show_default=True)
@click.option("--name", default="host", show_default=True)
def host(port: int, name: str) -> None:
    host_session(name, port)


@cli.command()
@click.argument("code")
@click.option("--name", default="guest", show_default=True)
@click.option("--timeout", default=DISCOVERY_TIMEOUT, show_default=True)
def join(code: str, name: str, timeout: float) -> None:
    join_session(code, name, timeout)


@cli.command()
def mcp() -> None:
    run_mcp()


@cli.command()
@click.option("--project-dir", default=".", show_default=True,
              help="Project directory to write .mcp.json into.")
def install(project_dir: str) -> None:
    """Wire claude-pair into Claude Code (hooks, statusline, MCP, skills)."""
    from claude_pair.installer import install as do_install
    do_install(Path(project_dir).resolve())
