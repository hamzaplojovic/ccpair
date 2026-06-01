PEER_SESSION_SKILL = """\
---
name: peer-session
description: Active peer programming session protocol. Use when the ccpair MCP server is available — you are one of two Claude agents in a 4-person team (2 humans + 2 agents) collaborating over a local network session.
version: 0.2.0
---

# Peer Session Protocol

When the `ccpair` MCP server is available in your tool list, a p2p session is active.
You are one of two Claude agents in a 4-person team: 2 humans + 2 agents.

## Mandatory behavior

**After every response that involves the peer agent:**
1. Call `await_peer(timeout=120)` — yield control so the peer can respond or a human can interject
2. Check the return value:
   - `human_interjected` — stop, let the human lead
   - `peer_replied: <action>` — immediately call `read_inbox()` to get the full message, then narrate its content in your response
   - `timeout` — proceed independently, note the peer was unresponsive

**Periodically (every 4 agent exchanges):**
- Call `human_gate()` — mandatory pause until a human submits a message
- This keeps humans in the hierarchy loop

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
| `read_inbox` | Immediately after `await_peer` returns `peer_replied` — get full message content |
| `human_gate` | Every N exchanges — pause for mandatory human input |

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
version: 0.2.0
triggers:
  - /pair
---

# /pair — P2P Session Manager

When the user types `/pair`, manage the ccpair session lifecycle using the Bash tool.

## Step 1 — Determine intent

Ask the user (or infer from args):
- `/pair` or `/pair start` → start a new session as host
- `/pair join <CODE>` → join an existing session
- `/pair stop` → kill the running session

---

## Starting a session (host)

```bash
nohup ccpair host --name "<YOUR_NAME>" --parent-pid $PPID >> ~/.claude-pair/session.log 2>&1 &
```

Poll for the session code (up to 10s):

```bash
for i in $(seq 1 20); do
  code=$(jq -r '.session_code // empty' "${CLAUDE_PAIR_DIR:-$HOME/.claude-pair}/state.json" 2>/dev/null)
  [[ -n "$code" ]] && echo "$code" && break
  sleep 0.5
done
```

Tell the user: **"Session code: `<CODE>` — visible in your statusline. Share it with your colleague."**

Poll for peer connection (up to 60s):

```bash
for i in $(seq 1 60); do
  active=$(jq -r '.active // false' "${CLAUDE_PAIR_DIR:-$HOME/.claude-pair}/state.json" 2>/dev/null)
  peer=$(jq -r '.peer_name // ""' "${CLAUDE_PAIR_DIR:-$HOME/.claude-pair}/state.json" 2>/dev/null)
  [[ "$active" == "true" && -n "$peer" ]] && echo "connected: $peer" && break
  sleep 1
done
```

Once connected, say: **"Connected to `<peer_name>`. Session is live — the `ccpair` MCP tools are now available."**

---

## Joining a session

```bash
nohup ccpair join <CODE> --name "<YOUR_NAME>" --parent-pid $PPID >> ~/.claude-pair/session.log 2>&1 &
```

Poll for connection (up to 60s):

```bash
for i in $(seq 1 60); do
  active=$(jq -r '.active // false' "${CLAUDE_PAIR_DIR:-$HOME/.claude-pair}/state.json" 2>/dev/null)
  peer=$(jq -r '.peer_name // ""' "${CLAUDE_PAIR_DIR:-$HOME/.claude-pair}/state.json" 2>/dev/null)
  [[ "$active" == "true" && -n "$peer" ]] && echo "connected: $peer" && break
  sleep 1
done
```

Once connected, say: **"Connected to `<peer_name>`. The `ccpair` MCP tools are now available."**

---

## Stopping a session

```bash
pid=$(cat "${CLAUDE_PAIR_DIR:-$HOME/.claude-pair}/session.pid" 2>/dev/null)
[[ -n "$pid" ]] && kill "$pid" && echo "stopped" || echo "no session running"
rm -f "${CLAUDE_PAIR_DIR:-$HOME/.claude-pair}"/{state.json,session.json,session.pid}
```

Confirm: **"Session stopped."**

---

## Error handling

- If `ccpair` not found: `uv tool install ccpair`
- If state.json never appears after 10s: check `~/.claude-pair/session.log`
- If poll times out waiting for peer: "Still waiting — share code `<CODE>`"
"""
