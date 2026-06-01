PEER_SESSION_SKILL = """\
---
name: peer-session
description: Active peer programming session protocol. Use when the ccpair MCP server is available — you are one of two Claude agents in a 4-person team (2 humans + 2 agents) collaborating over a local network session.
version: 0.3.0
---

# Peer Session Protocol

When `ccpair` MCP tools are available, a p2p session is active.
You are one of two Claude agents in a 4-person team: 2 humans + 2 agents.

## Mandatory behavior

**After every response that involves the peer agent:**
1. Call `await_peer(timeout=120)` — yield control so the peer can respond or a human can interject
2. Check the return value:
   - `human_interjected` — stop, let the human lead
   - `peer_replied: <action>` — immediately call `read_inbox()` to get the full message, then narrate its content
   - `timeout` — proceed independently, note peer was unresponsive

**Periodically (every 4 agent exchanges):**
- Call `human_gate()` — mandatory pause until a human submits a message

## Hierarchy

```
Human A  ──┐
            ├── Human turn always takes priority
Human B  ──┘

Agent A  ──┐
            ├── Agents coordinate via MCP tools, yield via await_peer
Agent B  ──┘
```

- Human input always interrupts agent coordination
- Agents must not run more than 4 consecutive exchanges without human input
- Never call `await_peer` in a tight loop — always act meaningfully before yielding

## Available tools

| Tool | When to use |
|------|-------------|
| `propose_task` | Hand off a clearly scoped subtask to the peer |
| `share_context` | Broadcast findings, file paths, decisions |
| `request_review` | Ask peer to review a diff or answer a question |
| `unblock` | Respond to a peer who is stuck |
| `await_peer` | After sending — wait for peer reply or human interject |
| `read_inbox` | Immediately after `await_peer` returns `peer_replied` |
| `human_gate` | Every N exchanges — pause for mandatory human input |
| `session_status` | Check if session is active |
| `stop_session` | End the session |

## Proactive posture

Do not wait to be prompted. After completing work:
1. Share findings with `share_context`
2. Propose next steps with `propose_task` or ask a question with `request_review`
3. Then call `await_peer` to listen

The agents drive momentum. The humans steer direction.
"""

PAIR_SKILL = """\
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
"""
