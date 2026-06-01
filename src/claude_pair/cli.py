import json
import os
import signal
from pathlib import Path

import click

from claude_pair.client import _daemon_alive, _pair_dir, call, ensure_daemon
from claude_pair.daemon import run_daemon
from claude_pair.server import run as run_mcp


def _version():
    from importlib.metadata import version
    return version("ccpair")


@click.group()
@click.version_option(_version(), prog_name="ccpair")
def cli(): pass


@cli.command()
def mcp() -> None:
    """Start the MCP server (used by Claude Code / opencode / any MCP client)."""
    run_mcp()


@cli.group()
def daemon() -> None:
    """Manage the ccpair daemon (long-lived P2P connection process)."""
    pass


@daemon.command("start")
def daemon_start() -> None:
    """Run the daemon in the foreground."""
    run_daemon(_pair_dir())


@daemon.command("stop")
def daemon_stop() -> None:
    """Stop the daemon."""
    pair_dir = _pair_dir()
    pid_path = pair_dir / "daemon.pid"
    if not pid_path.exists():
        click.echo("no daemon running")
        return
    try:
        pid = int(pid_path.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        click.echo(f"sent SIGTERM to pid {pid}")
    except (ValueError, ProcessLookupError) as e:
        click.echo(f"stale pid file: {e}")
    pid_path.unlink(missing_ok=True)
    (pair_dir / "daemon.sock").unlink(missing_ok=True)


@daemon.command("status")
def daemon_status() -> None:
    """Check daemon status."""
    pair_dir = _pair_dir()
    if _daemon_alive(pair_dir):
        pid = (pair_dir / "daemon.pid").read_text().strip()
        click.echo(f"running  pid={pid}  dir={pair_dir}")
    else:
        click.echo("not running")


@cli.command()
@click.option("--name", default="host", show_default=True)
def host(name: str) -> None:
    """Start hosting a pair session (via daemon)."""
    r = call({"cmd": "host", "name": name})
    if "error" in r:
        click.echo(f"error: {r['error']}", err=True)
        raise SystemExit(1)
    click.echo(f"code: {r['code']}")
    click.echo("waiting for peer...")
    r = call({"cmd": "wait_peer", "timeout": 300})
    if r.get("connected"):
        click.echo(f"connected: {r['connected']}")
    else:
        click.echo("timeout")


@cli.command()
@click.argument("code")
@click.option("--name", default="guest", show_default=True)
def join(code: str, name: str) -> None:
    """Join a pair session by code (via daemon)."""
    r = call({"cmd": "join", "code": code, "name": name})
    if "error" in r:
        click.echo(f"error: {r['error']}", err=True)
        raise SystemExit(1)
    click.echo(f"connected: {r['connected']}")


@cli.command()
def stop() -> None:
    """Stop the current pair session (keep daemon running)."""
    r = call({"cmd": "stop"}, autostart=False) if _daemon_alive(_pair_dir()) else {}
    click.echo("stopped" if r.get("stopped") else "no active session")


@cli.command()
def status() -> None:
    """Show current session status."""
    pair_dir = _pair_dir()
    if not _daemon_alive(pair_dir):
        click.echo("daemon: not running")
        return
    r = call({"cmd": "status"}, autostart=False)
    if r.get("connected"):
        click.echo(f"connected  peer={r['peer']}  role={r['role']}")
    elif r.get("code"):
        click.echo(f"waiting    code={r['code']}")
    else:
        click.echo("idle")


@cli.command()
def interrupt() -> None:
    """Signal the daemon that a human interjected (used by hooks)."""
    pair_dir = _pair_dir()
    if not _daemon_alive(pair_dir):
        return
    try:
        call({"cmd": "interrupt"}, autostart=False)
    except Exception:
        pass


@cli.command()
@click.option("-n", default=50, show_default=True, help="Number of lines to show.")
def logs(n: int) -> None:
    """Tail the daemon log."""
    log_file = _pair_dir() / "daemon.log"
    if not log_file.exists():
        click.echo("no log file found")
        return
    lines = log_file.read_text().splitlines()
    click.echo("\n".join(lines[-n:]))


@cli.command()
@click.option("--project-dir", default=".", show_default=True,
              help="Project directory to write .mcp.json into.")
@click.option("--isolated", is_flag=True,
              help="Use a per-project CLAUDE_PAIR_DIR — needed for same-machine pairing across two Claude Code windows.")
def install(project_dir: str, isolated: bool) -> None:
    """Wire ccpair into Claude Code (hooks, statusline, MCP, skills)."""
    from claude_pair.installer import install as do_install
    do_install(Path(project_dir).resolve(), isolated=isolated)
