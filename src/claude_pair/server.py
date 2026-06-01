import json
from mcp.server.fastmcp import FastMCP

from claude_pair.client import call

fastmcp = FastMCP("ccpair")


def _send_msg(msg: dict) -> str:
    r = call({"cmd": "send", "msg": msg})
    if r.get("sent"):
        return "sent"
    return f"error: {r.get('error', 'unknown')}"


@fastmcp.tool()
def host_session(name: str) -> str:
    """Start a pair session as host. Returns the session code to share with the peer."""
    r = call({"cmd": "host", "name": name})
    if "error" in r:
        return f"error: {r['error']}"
    return f"code: {r['code']}"


@fastmcp.tool()
def wait_for_peer(timeout: int = 90) -> str:
    """Wait for peer to join after host_session. Returns 'connected: <peer>' or 'timeout'."""
    r = call({"cmd": "wait_peer", "timeout": timeout})
    if r.get("timeout"):
        return "timeout"
    if "error" in r:
        return f"error: {r['error']}"
    return f"connected: {r['connected']}"


@fastmcp.tool()
def join_session(code: str, name: str) -> str:
    """Join a peer's session by code. Returns 'connected: <host>' or an error."""
    r = call({"cmd": "join", "code": code, "name": name})
    if "error" in r:
        return f"error: {r['error']}"
    return f"connected: {r['connected']}"


@fastmcp.tool()
def stop_session() -> str:
    """Stop the active pair session."""
    r = call({"cmd": "stop"})
    return "stopped" if r.get("stopped") else f"error: {r.get('error', 'unknown')}"


@fastmcp.tool()
def session_status() -> str:
    """Return current session status."""
    r = call({"cmd": "status"})
    if "error" in r:
        return f"error: {r['error']}"
    if not r.get("connected"):
        if r.get("code"):
            return f"waiting for peer (code: {r['code']})"
        return "no active session"
    return f"connected to {r['peer']} as {r['role']}"


@fastmcp.tool()
def propose_task(task: str, context: str) -> str:
    """Propose a task to the peer agent."""
    return _send_msg({"type": "propose_task", "task": task, "context": context})


@fastmcp.tool()
def share_context(summary: str, files: list[str] = []) -> str:
    """Share context or findings with the peer agent."""
    return _send_msg({"type": "share_context", "summary": summary, "files": files})


@fastmcp.tool()
def request_review(diff: str, question: str) -> str:
    """Ask the peer agent to review a diff or answer a question."""
    return _send_msg({"type": "request_review", "diff": diff, "question": question})


@fastmcp.tool()
def unblock(message: str) -> str:
    """Unblock the peer agent with a clarification or answer."""
    return _send_msg({"type": "unblock", "message": message})


@fastmcp.tool()
def read_inbox() -> str:
    """Read and clear the latest message from the peer. Returns JSON or 'empty'."""
    r = call({"cmd": "read_inbox"})
    if r.get("empty"):
        return "empty"
    if "error" in r:
        return f"error: {r['error']}"
    return json.dumps(r.get("inbox", {}))


@fastmcp.tool()
def await_peer(timeout: int = 120) -> str:
    """
    Yield control and wait for peer to respond or human to interject.
    Returns 'peer_replied: <type>', 'human_interjected', or 'timeout'.
    If 'peer_replied', call read_inbox() next.
    """
    r = call({"cmd": "await_peer", "timeout": timeout})
    if r.get("interrupted"):
        return "human_interjected"
    if r.get("timeout"):
        return "timeout"
    if "error" in r:
        return f"error: {r['error']}"
    return f"peer_replied: {r.get('peer_replied', 'message')}"


@fastmcp.tool()
def human_gate() -> str:
    """Mandatory pause after several consecutive agent exchanges."""
    return await_peer(120)


def run() -> None:
    fastmcp.run()
