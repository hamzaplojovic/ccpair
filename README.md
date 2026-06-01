# ccpair

Peer-to-peer Claude Code sessions over your local network.

Two developers. Two Claude Code instances. One shared session — with humans always in the loop.

## How it works

- mDNS discovery — no config, just be on the same WiFi
- Each Claude can propose tasks, share context, and request reviews via MCP tools
- After every Claude response a 2-minute human gate opens — either human can type and take over
- Stats (phase, countdown, exchange count) live in the statusline

## Install

```sh
uvx tool install ccpair
ccpair install               # wire up hooks, statusline, MCP, and skills
```

Restart Claude Code, then in any project:

```
/pair
```

## Usage

**Start a session (host):**
```sh
ccpair host --name alice
# prints: Session code: ab3x9k
```

**Join a session:**
```sh
ccpair join ab3x9k --name bob
```

Or use `/pair` inside Claude Code — it handles both flows interactively.

## Requirements

- Python 3.12+
- Same LAN (mDNS / port 52001)
- Claude Code with statusline configured
- `jq` in PATH (for hooks/statusline)

## MCP tools

| Tool | Description |
|------|-------------|
| `propose_task` | Hand off a scoped subtask to the peer agent |
| `share_context` | Broadcast findings and file paths |
| `request_review` | Ask peer to review a diff |
| `unblock` | Reply to a stuck peer |
| `await_peer` | Yield and wait for peer reply or human interject |
| `read_inbox` | Get the full message after `await_peer` returns |
| `human_gate` | Mandatory pause every N exchanges |
