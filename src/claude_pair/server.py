import json
import os
import socket
import tempfile
import time
from mcp.server.fastmcp import FastMCP
from claude_pair import transport
from claude_pair.constants import EXCHANGE_GATE_THRESHOLD, HUMAN_GATE_TIMEOUT, SESSION_FILE, STATE_FILE

fastmcp = FastMCP("claude-pair")
ipc_sock: socket.socket | None = None


def connect_ipc() -> None:
    global ipc_sock
    data = json.loads(SESSION_FILE.read_text())
    ipc_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ipc_sock.connect(("127.0.0.1", data["my_ipc_port"]))


def send(msg: dict) -> str:
    transport.send(ipc_sock, msg)
    return "sent"


def read_state() -> dict | None:
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return None


def _atomic_write_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=STATE_FILE.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f)
        os.replace(tmp, STATE_FILE)
    except Exception:
        os.unlink(tmp)
        raise


@fastmcp.tool()
def propose_task(task: str, context: str) -> str:
    """Propose a task to the peer agent."""
    return send({"type": "propose_task", "task": task, "context": context})


@fastmcp.tool()
def share_context(summary: str, files: list[str] = []) -> str:
    """Share context or findings with the peer agent."""
    return send({"type": "share_context", "summary": summary, "files": files})


@fastmcp.tool()
def request_review(diff: str, question: str) -> str:
    """Ask peer agent to review a diff or answer a question."""
    return send({"type": "request_review", "diff": diff, "question": question})


@fastmcp.tool()
def unblock(message: str) -> str:
    """Unblock peer agent with a clarification or answer."""
    return send({"type": "unblock", "message": message})


@fastmcp.tool()
def read_inbox() -> str:
    """
    Read and clear the latest message from the peer agent.
    Call immediately after await_peer returns 'peer_replied' to get the full message content.
    Returns JSON string of the message, or 'empty' if nothing is waiting.
    """
    state = read_state()
    if state is None:
        return "no session"
    inbox = state.get("inbox")
    if not inbox:
        return "empty"
    state["inbox"] = None
    state["peer_replied"] = False
    _atomic_write_state(state)
    return json.dumps(inbox)


@fastmcp.tool()
def await_peer(timeout: int = HUMAN_GATE_TIMEOUT) -> str:
    """
    Yield control and wait for peer agent to respond or human to interject.
    Blocks until peer replies, human interrupts, or timeout expires.
    If returns 'peer_replied: <type>', call read_inbox() next to get the full message.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = read_state()
        if state is None:
            return "session ended"
        if state.get("interrupted"):
            return "human_interjected"
        if state.get("peer_replied"):
            action = state.get("last_peer_action", "message")
            return f"peer_replied: {action}"
        time.sleep(0.5)
    return "timeout"


@fastmcp.tool()
def human_gate() -> str:
    """
    Mandatory pause after several consecutive agent exchanges.
    Blocks until a human submits a message. Call periodically to keep humans in the loop.
    Auto-returns immediately if exchange count is below threshold.
    """
    state = read_state()
    if state is None:
        return "no session"
    if state.get("exchange_count", 0) < EXCHANGE_GATE_THRESHOLD:
        return f"below threshold ({state.get('exchange_count', 0)}/{EXCHANGE_GATE_THRESHOLD}), continue"
    deadline = time.time() + 120
    while time.time() < deadline:
        state = read_state()
        if state is None:
            return "session ended"
        if state.get("interrupted") or state.get("phase") == "human_active":
            return "human_resumed"
        time.sleep(0.5)
    return "timeout — proceeding"


def run() -> None:
    connect_ipc()
    fastmcp.run()
