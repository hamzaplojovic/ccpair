---
name: pair
description: Start, join, or stop a ccpair p2p session from inside Claude Code. Use when the user types /pair.
version: 0.3.0
triggers:
  - /pair
---

# /pair — P2P Session Manager

When the user types `/pair`, manage the ccpair session lifecycle using the ccpair MCP tools.

## Step 1 — Determine intent

- `/pair` or `/pair start` → host a new session
- `/pair join <CODE>` → join an existing session
- `/pair stop` → stop the session
- `/pair status` → check session status

---

## Starting a session (host)

1. Call `host_session(name="<YOUR_NAME>")` → returns `code: <CODE>`
2. Tell the user: **"Session code: `<CODE>` — run `/pair join <CODE>` in your second Claude Code window."**
3. Call `wait_for_peer(timeout=120)` — this blocks until peer connects or times out
4. On `connected: <peer>`: **"Connected to `<peer>`. The ccpair session is live."**
5. On `timeout`: **"Still waiting — run `/pair join <CODE>` in your second window."**

---

## Joining a session

1. Call `join_session(code="<CODE>", name="<YOUR_NAME>")` → returns `connected: <host>` or `error: ...`
2. On success: **"Connected to `<host>`. Session is live."**
3. On error: report the error message.

---

## Stopping a session

1. Call `stop_session()` → returns `stopped`
2. Confirm: **"Session stopped."**

---

## Status check

Call `session_status()` and report the result.

---

## Error handling

- If ccpair tools are missing: `uv tool install ccpair`, then restart Claude Code
- If `join_session` returns `not found`: verify the code and that both machines are on the same network
