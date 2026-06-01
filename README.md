# ccpair

Peer-to-peer agent sessions over your local network.

Two developers. Two agents (Claude Code, opencode, Cursor — anything with bash). One shared session, with humans always in the loop.

## How it works

- mDNS discovery — no config, just be on the same WiFi
- Long-lived `ccpair daemon` per session — owns the TCP port, mDNS, peer connection
- Agents talk to peer through bash commands: `host`, `join`, `wait`, `say`, `recv`
- No MCP server, no harness-specific plumbing — works anywhere bash works
- Hooks inject `ccpair interrupt` on user input, so `recv` exits the moment a human types

```
agent A (any bash harness)             agent B
   │ ccpair host / join / wait           │ same commands
   │ ccpair say "..."                    │
   │ ccpair recv --wait 60               │
   ↓                                     ↓
ccpair daemon  ←─── mDNS + TCP/LAN ────→ ccpair daemon
```

## Install

```sh
uv tool install ccpair
ccpair install              # installs skills, hooks, statusline overlay
# OR for two windows on the same machine pairing each other:
ccpair install --isolated   # per-project state dir, run in each project
```

Restart your harness. In Claude Code, type `/pair` to host, or `/pair join <CODE>` to join.

## CLI

| Command | Description |
|---|---|
| `ccpair host [--name X]` | Start hosting. Prints the 6-char code on stdout. |
| `ccpair join CODE [--name X]` | Join a peer's session. |
| `ccpair wait [--timeout N]` | Block until peer joins. Prints `connected: <peer>`. |
| `ccpair say "<text>"` | Send a message to peer. |
| `ccpair recv [--wait N]` | Block for next peer message. Stdout = JSON. Exit codes: 0=message, 1=timeout, 2=human interjected, 3=session ended. |
| `ccpair status` | Show session state. |
| `ccpair stop` | End session (daemon keeps running). |
| `ccpair daemon start/stop/status` | Daemon lifecycle. |
| `ccpair interrupt` | Signal human interjection (used by hooks). |
| `ccpair logs` | Tail the daemon log. |
| `ccpair --version` | Print version. |

## Manual two-terminal demo

```sh
# Terminal A
$ ccpair host --name alice
ab3x9k
$ ccpair wait --timeout 60
connected: bob
$ ccpair recv --wait 60
{"type": "text", "text": "what is 17 plus 25?"}
$ ccpair say "42"

# Terminal B (separate CLAUDE_PAIR_DIR if same machine)
$ ccpair join ab3x9k --name bob
connected: alice
$ ccpair say "what is 17 plus 25?"
$ ccpair recv --wait 60
{"type": "text", "text": "42"}
```

## Agent loop (what the peer-session skill tells your agent to run)

```sh
while true; do
  msg=$(ccpair recv --wait 60) || break
  # parse $msg JSON, act on it, then reply:
  ccpair say "your response here"
done
```

Exit code 2 (human interjected) breaks the loop and yields to the human.

## Verified harnesses

- **Claude Code** — via the `/pair` skill installed by `ccpair install`
- **opencode** — same skills work; agents call bash directly
- **anything else** — if your agent can run bash, it can pair

End-to-end test: two MiniMax-M2.7 agents in opencode, autonomous, math Q→A round-trip, first try.

## Same-machine pairing

Two windows on the same machine need separate state dirs so the two daemons don't collide:

```sh
# In project A
CLAUDE_PAIR_DIR=~/.ccpair-A ccpair install --isolated

# In project B
CLAUDE_PAIR_DIR=~/.ccpair-B ccpair install --isolated
```

Or use `--isolated` and ccpair auto-derives a path from each project directory hash.

## Requirements

- Python 3.12+
- Same LAN (mDNS / TCP port 52001)
- `jq` in PATH (for statusline overlay)
- Your harness needs a `Bash` tool (Claude Code, opencode, Cursor all qualify)

## Architecture notes

Earlier versions (≤0.4.x) exposed P2P through an MCP server. That worked in Claude Code but tripped on opencode's `run` mode tool-result handling and added a layer for no benefit — the protocol between two collaborating agents is fundamentally duplex, not request/response. v0.5+ drops MCP entirely. Agents use bash; the daemon owns the wire.

## License

MIT
