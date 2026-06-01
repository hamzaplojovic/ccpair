import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from claude_pair import transport


def _pair_dir() -> Path:
    return Path(os.environ.get("CLAUDE_PAIR_DIR", str(Path.home() / ".claude-pair")))


def _daemon_alive(pair_dir: Path) -> bool:
    pid_path = pair_dir / "daemon.pid"
    sock_path = pair_dir / "daemon.sock"
    if not pid_path.exists() or not sock_path.exists():
        return False
    try:
        pid = int(pid_path.read_text().strip())
        os.kill(pid, 0)
        return True
    except (ValueError, ProcessLookupError, PermissionError, OSError):
        return False


def ensure_daemon(pair_dir: Path | None = None, timeout: float = 5.0) -> Path:
    pair_dir = pair_dir or _pair_dir()
    sock_path = pair_dir / "daemon.sock"
    if _daemon_alive(pair_dir):
        return sock_path
    pair_dir.mkdir(exist_ok=True)
    pair_dir.joinpath("daemon.pid").unlink(missing_ok=True)
    pair_dir.joinpath("daemon.sock").unlink(missing_ok=True)
    log = open(pair_dir / "daemon.log", "ab")
    env = {**os.environ, "CLAUDE_PAIR_DIR": str(pair_dir)}
    subprocess.Popen(
        [sys.executable, "-m", "claude_pair", "daemon", "start"],
        stdout=log, stderr=log,
        env=env,
        start_new_session=True,
        close_fds=True,
    )
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _daemon_alive(pair_dir):
            return sock_path
        time.sleep(0.1)
    raise RuntimeError(f"daemon failed to start within {timeout}s — check {pair_dir / 'daemon.log'}")


def call(cmd: dict, pair_dir: Path | None = None, autostart: bool = True) -> dict:
    pair_dir = pair_dir or _pair_dir()
    sock_path = pair_dir / "daemon.sock"
    if autostart:
        ensure_daemon(pair_dir)
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(5.0)
    try:
        s.connect(str(sock_path))
        s.settimeout(None)
        transport.send(s, cmd)
        return transport.recv(s) or {"error": "no response from daemon"}
    finally:
        try:
            s.close()
        except Exception:
            pass
