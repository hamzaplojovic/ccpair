PEER_SESSION_SKILL = """\
---
name: peer-session
description: Active peer-programming session protocol. Use whenever `ccpair status` reports a connected session — you are one of two agents collaborating with a peer over the local network.
version: 0.5.0
---

# Peer Session Protocol

When `ccpair status` reports `connected`, a p2p session is live. You are one of two agents.
You communicate with your peer through these bash commands. There is no MCP — just CLI.

## After every response that involved the peer

Run this exact command and process its output:

```bash
ccpair recv --wait 60
```

Exit codes:
- **0** → stdout contains a JSON message from your peer. Parse it, act on it, respond with `ccpair say "..."`, then call `ccpair recv` again.
- **1** → timeout. Peer didn't respond. Proceed independently or ask the human for direction.
- **2** → human interjected (they typed in the terminal). Stop. Let the human lead.
- **3** → session ended.

## Sending to your peer

```bash
ccpair say "your message text"
```

Send concise, structured messages. Examples:
- `ccpair say "I'll handle auth.py. You take routes.py. Reply when done."`
- `ccpair say "Done with auth.py — pushed e3f9a12. Anything blocking on your side?"`
- `ccpair say "Need a decision: rename ctx → context everywhere, or keep ctx? Your call."`

## Hierarchy

- **Humans always preempt agents.** Exit code 2 means stop and yield.
- **Don't exceed 4 consecutive agent exchanges** without human input. After 4, send `ccpair say "checking in — human, any direction?"` and wait.
- **Don't poll in a tight loop.** Always do meaningful work between `ccpair recv` calls.

## Status check at any time

```bash
ccpair status
```

## Proactive posture

After completing a piece of work, share it. Don't wait to be asked:
```bash
ccpair say "I refactored the daemon. Tests pass. Reviewing your auth change next."
ccpair recv --wait 60
```
"""

PAIR_SKILL = """\
---
name: pair
description: Start, join, or stop a ccpair p2p session. Use when the user types /pair.
version: 0.5.0
triggers:
  - /pair
---

# /pair — P2P Session Manager

When the user types `/pair`, run bash commands.

## Intent

- `/pair` or `/pair start` → host
- `/pair join <CODE>` → join
- `/pair stop` → stop session
- `/pair status` → status

## Host

```bash
ccpair host --name "<YOUR_NAME>"
```

This prints the 6-char session code. Tell the user:
**"Session code: `<CODE>` — run `/pair join <CODE>` in your second window."**

Then wait for peer:
```bash
ccpair wait --timeout 120
```

On success it prints `connected: <peer>`. Tell the user: **"Connected to `<peer>`. Session live."**
Then immediately enter the peer-session loop:
```bash
ccpair recv --wait 60
```
(See the peer-session skill for the full loop.)

## Join

```bash
ccpair join <CODE> --name "<YOUR_NAME>"
```

On success it prints `connected: <host>`. Tell the user, then enter the peer-session loop with `ccpair recv --wait 60`.

## Stop

```bash
ccpair stop
```

## Status

```bash
ccpair status
```

## Errors

- "command not found: ccpair" → `uv tool install ccpair`
- "session 'XXX' not found on this network" → check the code, verify both machines on same LAN
- "bind :52001 failed" → another ccpair daemon owns the port; run `ccpair stop` then `ccpair daemon stop`
"""
