---
name: pair
description: Start, join, or stop a claude-pair p2p session from inside Claude Code. Use when the user types /pair.
version: 0.2.0
triggers:
  - /pair
---

# /pair — P2P Session Manager

When the user types `/pair`, manage the claude-pair session lifecycle using the Bash tool.

## Step 1 — Determine intent

Ask the user (or infer from args):
- `/pair` or `/pair start` → start a new session as host
- `/pair join <CODE>` → join an existing session
- `/pair stop` → kill the running session

---

## Starting a session (host)

```bash
# 1. Launch session in background
nohup ~/.local/bin/claude-pair host --name "<YOUR_NAME>" >> ~/.claude-pair/session.log 2>&1 &
echo $!
```

Use the user's name or ask for one. Then poll for the session code:

```bash
# 2. Poll until session_code appears (up to 10s)
for i in $(seq 1 20); do
  code=$(jq -r '.session_code // empty' ~/.claude-pair/state.json 2>/dev/null)
  [[ -n "$code" ]] && echo "$code" && break
  sleep 0.5
done
```

Tell the user: **"Session code: `<CODE>` — visible in your statusline. Share it with your colleague."**

Then poll for peer connection:

```bash
# 3. Poll until active=true (peer joined)
for i in $(seq 1 60); do
  active=$(jq -r '.active // false' ~/.claude-pair/state.json 2>/dev/null)
  peer=$(jq -r '.peer_name // ""' ~/.claude-pair/state.json 2>/dev/null)
  [[ "$active" == "true" && -n "$peer" ]] && echo "connected: $peer" && break
  sleep 1
done
```

Once connected, say: **"Connected to `<peer_name>`. Session is live — the `claude-pair` MCP tools are now available."**

---

## Joining a session

```bash
# 1. Launch join in background
nohup ~/.local/bin/claude-pair join <CODE> --name "<YOUR_NAME>" >> ~/.claude-pair/session.log 2>&1 &
echo $!
```

Then poll for connection:

```bash
# 2. Poll until active=true
for i in $(seq 1 60); do
  active=$(jq -r '.active // false' ~/.claude-pair/state.json 2>/dev/null)
  peer=$(jq -r '.peer_name // ""' ~/.claude-pair/state.json 2>/dev/null)
  [[ "$active" == "true" && -n "$peer" ]] && echo "connected: $peer" && break
  sleep 1
done
```

Once connected, say: **"Connected to `<peer_name>`. The `claude-pair` MCP tools are now available."**

---

## Stopping a session

```bash
pid=$(cat ~/.claude-pair/session.pid 2>/dev/null)
[[ -n "$pid" ]] && kill "$pid" && echo "stopped" || echo "no session running"
```

Also clean up state:

```bash
rm -f ~/.claude-pair/state.json ~/.claude-pair/session.json ~/.claude-pair/session.pid
```

Confirm: **"Session stopped."**

---

## Error handling

- If `~/.local/bin/claude-pair` not found: tell the user to run `bash install.sh` from the claude-pair repo dir.
- If state.json never appears after 10s: check `~/.claude-pair/session.log` for errors.
- If poll times out waiting for peer: say "Still waiting for peer to join. Share code `<CODE>`."

---

## Notes

- The session process runs as a background daemon — it persists after Claude Code exits.
- The statusline shows the session code while waiting and peer stats when connected.
- After connecting, the `claude-pair` MCP server must be running in this Claude Code instance (started via `.mcp.json` at project root, or `claude-pair mcp` manually).
