import json
import os
import socket
import sys
import tempfile
import threading
import time
import click
from claude_pair import approval, discovery, transport
from claude_pair.constants import (
    DEFAULT_PORT,
    DISCOVERY_TIMEOUT,
    EXCHANGE_GATE_THRESHOLD,
    HOST_IPC_PORT,
    HUMAN_GATE_TIMEOUT,
    JOIN_IPC_PORT,
    PID_FILE,
    SESSION_FILE,
    STATE_FILE,
)
from claude_pair.messages import format_incoming
from claude_pair.utils import gen_code

write_lock = threading.Lock()
state_lock = threading.Lock()


def write_session(my_name: str, peer_name: str, role: str) -> None:
    ipc_port = HOST_IPC_PORT if role == "host" else JOIN_IPC_PORT
    SESSION_FILE.parent.mkdir(exist_ok=True)
    SESSION_FILE.write_text(json.dumps({
        "my_name": my_name,
        "peer_name": peer_name,
        "my_ipc_port": ipc_port,
        "role": role,
    }))


def write_state(my_name: str, peer_name: str, role: str,
                session_code: str | None = None, waiting: bool = False) -> None:
    state = {
        "active": not waiting,
        "waiting": waiting,
        "session_code": session_code,
        "role": role,
        "my_name": my_name,
        "peer_name": peer_name,
        "phase": "idle",
        "exchange_count": 0,
        "human_deadline": None,
        "last_peer_action": None,
        "peer_replied": False,
        "interrupted": False,
        "inbox": None,
    }
    atomic_write_state(state)


def atomic_write_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=STATE_FILE.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f)
        os.replace(tmp, STATE_FILE)
    except Exception:
        os.unlink(tmp)
        raise


def read_state() -> dict | None:
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return None


def update_state(**kwargs) -> None:
    with state_lock:
        state = read_state()
        if state is None:
            return
        state.update(kwargs)
        atomic_write_state(state)


def clear_state() -> None:
    try:
        STATE_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def write_pid() -> None:
    PID_FILE.parent.mkdir(exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))


def relay_loop(sock: socket.socket, peer_name: str) -> None:
    while True:
        msg = transport.recv(sock)
        if msg is None:
            clear_state()
            click.echo(f"\n[{peer_name} disconnected]")
            sys.exit(0)
        update_state(
            peer_replied=True,
            last_peer_action=msg.get("type"),
            phase="awaiting_human",
            human_deadline=int(time.time()) + HUMAN_GATE_TIMEOUT,
            interrupted=False,
            inbox=msg,
        )
        if msg.get("type") == "text":
            click.echo(f"\n[{peer_name}] {msg['text']}")
        else:
            click.echo(f"\n{format_incoming(peer_name, msg)}")


def input_loop(sock: socket.socket, my_name: str) -> None:
    while True:
        try:
            text = input(f"[{my_name}] ")
        except (EOFError, KeyboardInterrupt):
            clear_state()
            click.echo("\n[disconnected]")
            sys.exit(0)
        if text.strip():
            update_state(phase="human_active", interrupted=True, exchange_count=0)
            with write_lock:
                transport.send(sock, {"type": "text", "text": text})


def ipc_listener(peer_sock: socket.socket, ipc_port: int) -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    server.bind(("127.0.0.1", ipc_port))
    server.listen(1)
    conn, _ = server.accept()
    server.close()
    while True:
        msg = transport.recv(conn)
        if msg is None:
            break
        if approval.prompt(msg):
            state = read_state()
            exchange_count = (state or {}).get("exchange_count", 0) + 1
            update_state(exchange_count=exchange_count, phase="agent_active")
            with write_lock:
                transport.send(peer_sock, msg)


def _parent_watchdog(parent_pid: int) -> None:
    while True:
        try:
            os.kill(parent_pid, 0)
        except OSError:
            os._exit(0)
        time.sleep(2)


def start_session(sock: socket.socket, my_name: str, peer_name: str, role: str, parent_pid: int | None = None) -> None:
    ipc_port = HOST_IPC_PORT if role == "host" else JOIN_IPC_PORT
    write_session(my_name, peer_name, role)
    write_state(my_name, peer_name, role)
    click.echo(f"[MCP ready — run: ccpair mcp]\n")
    if parent_pid:
        threading.Thread(target=_parent_watchdog, args=(parent_pid,), daemon=True).start()
    threading.Thread(target=relay_loop, args=(sock, peer_name), daemon=True).start()
    threading.Thread(target=ipc_listener, args=(sock, ipc_port), daemon=True).start()
    input_loop(sock, my_name)


def host_session(name: str, port: int, parent_pid: int | None = None) -> None:
    code = gen_code()
    write_pid()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    server.bind(("0.0.0.0", port))
    server.listen(1)

    write_state(name, "", "host", session_code=code, waiting=True)
    click.echo(f"Session code: {click.style(code, fg='green', bold=True)}")
    click.echo("Waiting for peer to join...")

    zc, info = discovery.advertise(code, port)

    conn, addr = server.accept()
    server.close()
    zc.unregister_service(info)
    zc.close()

    msg = transport.recv(conn)
    peer_name = msg["name"] if msg else "guest"
    transport.send(conn, {"name": name})

    update_state(active=True, waiting=False, session_code=None, peer_name=peer_name)
    click.echo(f"[connected: {peer_name}@{addr[0]}]")
    start_session(conn, name, peer_name, "host", parent_pid=parent_pid)


def join_session(code: str, name: str, timeout: float, parent_pid: int | None = None) -> None:
    write_pid()
    write_state(name, "", "join", waiting=True)
    click.echo(f"Looking for session {click.style(code, fg='yellow')}...")

    result = discovery.find(code, timeout)
    if not result:
        clear_state()
        click.echo(f"Session '{code}' not found on this network.", err=True)
        sys.exit(1)

    ip, port = result
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((ip, port))

    transport.send(sock, {"name": name})
    msg = transport.recv(sock)
    host_name = msg["name"] if msg else "host"

    update_state(active=True, waiting=False, peer_name=host_name)
    click.echo(f"[connected: {host_name}@{ip}]")
    start_session(sock, name, host_name, "join", parent_pid=parent_pid)
