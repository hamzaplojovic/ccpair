import json
import os
import signal
import sys
from pathlib import Path

import click

from claude_pair.client import _daemon_alive, _pair_dir, call
from claude_pair.daemon import run_daemon


def _version():
    from importlib.metadata import version
    return version("ccpair")


@click.group()
@click.version_option(_version(), prog_name="ccpair")
def cli(): pass


# ---- session lifecycle ----

@cli.command()
@click.option("--name", default=lambda: os.environ.get("USER", "host"), show_default="$USER")
def host(name: str) -> None:
    """Host a pair session. Prints the session code; returns immediately."""
    r = call({"cmd": "host", "name": name})
    if "error" in r:
        click.echo(f"error: {r['error']}", err=True)
        sys.exit(1)
    click.echo(r["code"])


@cli.command()
@click.argument("code")
@click.option("--name", default=lambda: os.environ.get("USER", "guest"), show_default="$USER")
def join(code: str, name: str) -> None:
    """Join a pair session by code."""
    r = call({"cmd": "join", "code": code, "name": name})
    if "error" in r:
        click.echo(f"error: {r['error']}", err=True)
        sys.exit(1)
    click.echo(f"connected: {r['connected']}")


@cli.command()
@click.option("--timeout", default=120, show_default=True, help="Seconds to wait for peer.")
def wait(timeout: int) -> None:
    """Block until peer joins. Prints 'connected: <peer>' or exits 1 on timeout."""
    r = call({"cmd": "wait_peer", "timeout": timeout})
    if r.get("connected"):
        click.echo(f"connected: {r['connected']}")
        return
    click.echo("timeout", err=True)
    sys.exit(1)


@cli.command()
@click.argument("text")
def say(text: str) -> None:
    """Send a text message to the peer."""
    r = call({"cmd": "send", "msg": {"type": "text", "text": text}})
    if not r.get("sent"):
        click.echo(f"error: {r.get('error', 'unknown')}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--wait", "wait_sec", default=60, show_default=True, help="Seconds to block.")
def recv(wait_sec: int) -> None:
    """
    Block for an incoming peer message.
    Exit codes: 0=message (JSON on stdout), 1=timeout, 2=human interjection, 3=session ended.
    """
    r = call({"cmd": "recv", "timeout": wait_sec})
    if "message" in r:
        msg = dict(r["message"])
        msg.pop("v", None)
        click.echo(json.dumps(msg))
        return
    if r.get("interrupted"):
        click.echo("human_interjected", err=True)
        sys.exit(2)
    if r.get("timeout"):
        click.echo("timeout", err=True)
        sys.exit(1)
    click.echo(f"session ended: {r.get('error', '')}", err=True)
    sys.exit(3)


@cli.command()
def stop() -> None:
    """Stop the current pair session (daemon keeps running)."""
    if not _daemon_alive(_pair_dir()):
        click.echo("no daemon running")
        return
    r = call({"cmd": "stop"}, autostart=False)
    click.echo("stopped" if r.get("stopped") else f"error: {r.get('error', 'unknown')}")


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
    """Signal the daemon that a human interjected (used by harness hooks)."""
    if not _daemon_alive(_pair_dir()):
        return
    try:
        call({"cmd": "interrupt"}, autostart=False)
    except Exception:
        pass


@cli.command()
@click.option("-n", default=50, show_default=True)
def logs(n: int) -> None:
    """Tail the daemon log."""
    log_file = _pair_dir() / "daemon.log"
    if not log_file.exists():
        click.echo("no log file found")
        return
    click.echo("\n".join(log_file.read_text().splitlines()[-n:]))


# ---- daemon lifecycle ----

@cli.group()
def daemon() -> None:
    """Manage the ccpair daemon process."""
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


# ---- install (skills + hooks only; no MCP) ----

@cli.command()
@click.option("--isolated", is_flag=True,
              help="Per-project state dir (needed for same-machine pairing across two harness windows).")
def install(isolated: bool) -> None:
    """Install ccpair skills + statusline overlay + interrupt hook into Claude Code."""
    from claude_pair.installer import install as do_install
    do_install(isolated=isolated)
