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
