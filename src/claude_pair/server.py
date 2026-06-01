import json
import os
import socket
import threading
import time
from mcp.server.fastmcp import FastMCP
from claude_pair import discovery, transport
from claude_pair.constants import DEFAULT_PORT, DISCOVERY_TIMEOUT, EXCHANGE_GATE_THRESHOLD, HUMAN_GATE_TIMEOUT
from claude_pair.utils import gen_code

fastmcp = FastMCP("ccpair")

_lock = threading.Lock()
_state: dict = {
    "connected": False,
    "my_name": None,
    "peer_name": None,
    "role": None,
    "code": None,
    "inbox": None,
    "exchange_count": 0,
    "interrupted": False,
    "peer_replied": False,
    "last_peer_action": None,
}
_conn: socket.socket | None = None
_peer_event = threading.Event()
_zc_handle: tuple | None = None


def _update(**kwargs) -> None:
    with _lock:
        _state.update(kwargs)


def _relay_loop() -> None:
    global _conn
    while True:
        msg = transport.recv(_conn)
        if msg is None:
            _update(connected=False)
            return
        with _lock:
            _state["inbox"] = msg
            _state["peer_replied"] = True
            _state["last_peer_action"] = msg.get("type")


def _accept_peer(server_sock: socket.socket, name: str) -> None:
    global _conn, _zc_handle
    conn, _ = server_sock.accept()
    server_sock.close()
    msg = transport.recv(conn)
    peer_name = msg["name"] if msg else "guest"
    transport.send(conn, {"name": name})
    _conn = conn
    _update(connected=True, peer_name=peer_name)
    if _zc_handle:
        zc, info = _zc_handle
        zc.unregister_service(info)
        zc.close()
        _zc_handle = None
    _peer_event.set()
    threading.Thread(target=_relay_loop, daemon=True).start()


def _watchdog(parent_pid: int) -> None:
    while True:
        try:
            os.kill(parent_pid, 0)
        except OSError:
            os._exit(0)
        time.sleep(2)


@fastmcp.tool()
def host_session(name: str) -> str:
    """Start a pair session as host. Returns the session code to share with the peer."""
    global _zc_handle
    code = gen_code()
    _update(my_name=name, role="host", code=code, connected=False)
    _peer_event.clear()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", DEFAULT_PORT))
    server.listen(1)

    zc, info = discovery.advertise(code, DEFAULT_PORT)
    _zc_handle = (zc, info)
    threading.Thread(target=_accept_peer, args=(server, name), daemon=True).start()
    return f"code: {code}"


@fastmcp.tool()
def wait_for_peer(timeout: int = 90) -> str:
    """Wait for the peer to join after host_session. Returns 'connected: <peer>' or 'timeout'."""
    if _peer_event.wait(timeout):
        return f"connected: {_state['peer_name']}"
    return "timeout"


@fastmcp.tool()
def join_session(code: str, name: str) -> str:
    """Join a peer's session by code. Returns 'connected: <host>' or an error."""
    global _conn
    _update(my_name=name, role="join", connected=False)

    result = discovery.find(code, DISCOVERY_TIMEOUT)
    if not result:
        return f"error: session '{code}' not found on this network"

    ip, port = result
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((ip, port))
    transport.send(sock, {"name": name})
    msg = transport.recv(sock)
    host_name = msg["name"] if msg else "host"
    _conn = sock
    _update(connected=True, peer_name=host_name)
    threading.Thread(target=_relay_loop, daemon=True).start()
    return f"connected: {host_name}"


@fastmcp.tool()
def stop_session() -> str:
    """Stop the active pair session."""
    global _conn
    if _conn:
        try:
            _conn.close()
        except Exception:
            pass
        _conn = None
    _update(connected=False, peer_name=None, role=None, code=None)
    return "stopped"


@fastmcp.tool()
def session_status() -> str:
    """Return current session status."""
    if not _state.get("connected"):
        return "no active session"
    return f"connected to {_state['peer_name']} as {_state['role']}"


def _send(msg: dict) -> str:
    if _conn is None:
        return "error: no active session"
    transport.send(_conn, msg)
    return "sent"


@fastmcp.tool()
def propose_task(task: str, context: str) -> str:
    """Propose a task to the peer agent."""
    return _send({"type": "propose_task", "task": task, "context": context})


@fastmcp.tool()
def share_context(summary: str, files: list[str] = []) -> str:
    """Share context or findings with the peer agent."""
    return _send({"type": "share_context", "summary": summary, "files": files})


@fastmcp.tool()
def request_review(diff: str, question: str) -> str:
    """Ask the peer agent to review a diff or answer a question."""
    return _send({"type": "request_review", "diff": diff, "question": question})


@fastmcp.tool()
def unblock(message: str) -> str:
    """Unblock the peer agent with a clarification or answer."""
    return _send({"type": "unblock", "message": message})


@fastmcp.tool()
def read_inbox() -> str:
    """Read and clear the latest message from the peer. Returns JSON or 'empty'."""
    with _lock:
        inbox = _state.get("inbox")
        if not inbox:
            return "empty"
        _state["inbox"] = None
        _state["peer_replied"] = False
        return json.dumps(inbox)


@fastmcp.tool()
def await_peer(timeout: int = HUMAN_GATE_TIMEOUT) -> str:
    """
    Yield control and wait for peer to respond or human to interject.
    Returns 'peer_replied: <type>', 'human_interjected', or 'timeout'.
    If 'peer_replied', call read_inbox() next.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        with _lock:
            if _state.get("interrupted"):
                return "human_interjected"
            if _state.get("peer_replied"):
                return f"peer_replied: {_state.get('last_peer_action', 'message')}"
        time.sleep(0.5)
    return "timeout"


@fastmcp.tool()
def human_gate() -> str:
    """Mandatory pause after several consecutive agent exchanges. Blocks until human input."""
    with _lock:
        count = _state.get("exchange_count", 0)
    if count < EXCHANGE_GATE_THRESHOLD:
        return f"below threshold ({count}/{EXCHANGE_GATE_THRESHOLD}), continue"
    deadline = time.time() + 120
    while time.time() < deadline:
        with _lock:
            if _state.get("interrupted"):
                return "human_resumed"
        time.sleep(0.5)
    return "timeout — proceeding"


def run() -> None:
    ppid = int(os.environ.get("CCPAIR_PARENT_PID", "") or 0)
    if ppid:
        threading.Thread(target=_watchdog, args=(ppid,), daemon=True).start()
    fastmcp.run()
