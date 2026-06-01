import json
import os
import shutil
import stat
import sys
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude"
PAIR_DIR = Path(os.environ.get("CLAUDE_PAIR_DIR", str(Path.home() / ".claude-pair")))

_STATUSLINE_PAIR_BLOCK = r"""
# ccpair overlay — managed by ccpair install
pair_str=""
_CP_STATE="${CLAUDE_PAIR_DIR:-$HOME/.claude-pair}/state.json"
if [[ -f "$_CP_STATE" ]]; then
    pair_waiting=$(jq -r '.waiting // false' "$_CP_STATE" 2>/dev/null)
    if [[ "$pair_waiting" == "true" ]]; then
        session_code=$(jq -r '.session_code // ""' "$_CP_STATE" 2>/dev/null)
        if [[ -n "$session_code" && "$session_code" != "null" ]]; then
            pair_str="${sep}${yellow}⇄ ${session_code}${reset}${sep}${muted}waiting...${reset}"
        else
            pair_str="${sep}${muted}⇄ discovering...${reset}"
        fi
    fi
    pair_active=$(jq -r '.active // false' "$_CP_STATE" 2>/dev/null)
    if [[ "$pair_active" == "true" ]]; then
        peer_name=$(jq -r '.peer_name // "peer"' "$_CP_STATE" 2>/dev/null)
        phase=$(jq -r '.phase // "idle"' "$_CP_STATE" 2>/dev/null)
        exchange=$(jq -r '.exchange_count // 0' "$_CP_STATE" 2>/dev/null)
        deadline=$(jq -r '.human_deadline // 0' "$_CP_STATE" 2>/dev/null)
        last_action=$(jq -r '.last_peer_action // ""' "$_CP_STATE" 2>/dev/null)
        case "$phase" in
            awaiting_human)  phase_color="$yellow";  phase_icon="⏳" ;;
            human_active)    phase_color="$green";   phase_icon="✍"  ;;
            agent_active)    phase_color="$cyan";    phase_icon="⚡"  ;;
            awaiting_peer)   phase_color="$orange";  phase_icon="⇄"  ;;
            *)               phase_color="$muted";   phase_icon="○"  ;;
        esac
        pair_str="${sep}${cyan}⇄${peer_name}${reset}${sep}${phase_color}${phase_icon}${phase}${reset}"
        if [[ "$phase" == "awaiting_human" && "$deadline" != "0" && "$deadline" != "null" ]]; then
            now=$(date +%s)
            secs_left=$(( deadline - now ))
            if (( secs_left > 0 )); then
                cd_color="$yellow"
                (( secs_left <= 10 )) && cd_color="$pink"
                pair_str="${pair_str}${sep}${cd_color}${secs_left}s${reset}"
            fi
        fi
        if (( exchange > 0 )); then
            ex_color="$muted"
            (( exchange >= 3 )) && ex_color="$orange"
            (( exchange >= 4 )) && ex_color="$pink"
            pair_str="${pair_str}${sep}${ex_color}ex:${exchange}${reset}"
        fi
        if [[ -n "$last_action" && "$last_action" != "null" && "$last_action" != "text" ]]; then
            pair_str="${pair_str}${sep}${muted}${last_action}${reset}"
        fi
    fi
fi
# end ccpair overlay
"""

_STOP_HOOK = """\
#!/bin/bash
DIR="${CLAUDE_PAIR_DIR:-$HOME/.claude-pair}"
STATE="$DIR/state.json"
[[ ! -f "$STATE" ]] && exit 0
active=$(jq -r '.active // false' "$STATE" 2>/dev/null)
[[ "$active" != "true" ]] && exit 0
deadline=$(date -v +120S +%s 2>/dev/null || date -d '+120 seconds' +%s 2>/dev/null)
tmp=$(mktemp "$DIR/.state.XXXXXX.tmp")
jq --argjson dl "$deadline" \
   '.phase = "awaiting_human" | .human_deadline = $dl | .interrupted = false | .peer_replied = false' \
   "$STATE" > "$tmp" && mv "$tmp" "$STATE"
"""

_PROMPT_HOOK = """\
#!/bin/bash
DIR="${CLAUDE_PAIR_DIR:-$HOME/.claude-pair}"
STATE="$DIR/state.json"
[[ ! -f "$STATE" ]] && exit 0
active=$(jq -r '.active // false' "$STATE" 2>/dev/null)
[[ "$active" != "true" ]] && exit 0
tmp=$(mktemp "$DIR/.state.XXXXXX.tmp")
jq '.phase = "human_active" | .interrupted = true | .exchange_count = 0 | .human_deadline = null' \
   "$STATE" > "$tmp" && mv "$tmp" "$STATE"
"""


def _write_hooks(hooks_dir: Path) -> tuple[Path, Path]:
    hooks_dir.mkdir(parents=True, exist_ok=True)
    stop = hooks_dir / "pair-stop.sh"
    prompt = hooks_dir / "pair-user-prompt.sh"
    stop.write_text(_STOP_HOOK)
    prompt.write_text(_PROMPT_HOOK)
    for p in (stop, prompt):
        p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return stop, prompt


def _patch_settings(stop: Path, prompt: Path) -> None:
    settings_path = CLAUDE_DIR / "settings.json"
    if settings_path.exists():
        data = json.loads(settings_path.read_text())
    else:
        data = {}

    def _hook_entry(cmd: str) -> dict:
        return {"type": "command", "command": cmd, "timeout": 5}

    def _ensure_hook(event: str, cmd: str) -> None:
        hooks = data.setdefault("hooks", {})
        entries = hooks.setdefault(event, [])
        for entry in entries:
            for h in entry.get("hooks", []):
                if h.get("command") == cmd:
                    return
        entries.append({"matcher": "", "hooks": [_hook_entry(cmd)]})

    _ensure_hook("Stop", f"bash {stop}")
    _ensure_hook("UserPromptSubmit", f"bash {prompt}")

    CLAUDE_DIR.mkdir(exist_ok=True)
    settings_path.write_text(json.dumps(data, indent=2))


def _patch_statusline() -> None:
    sl = CLAUDE_DIR / "statusline-command.sh"
    if not sl.exists():
        return
    content = sl.read_text()
    marker = "# ccpair overlay"
    if marker in content:
        return
    # inject before the final left= line
    insert_before = "\nleft=$("
    idx = content.rfind(insert_before)
    if idx == -1:
        return
    content = content[:idx] + _STATUSLINE_PAIR_BLOCK + content[idx:]
    sl.write_text(content)


def _write_mcp(project_dir: Path) -> None:
    mcp = project_dir / ".mcp.json"
    if mcp.exists():
        data = json.loads(mcp.read_text())
    else:
        data = {"mcpServers": {}}
    data.setdefault("mcpServers", {})["ccpair"] = {
        "type": "stdio",
        "command": "ccpair",
        "args": ["mcp"],
    }
    mcp.write_text(json.dumps(data, indent=2))


def _write_skills() -> None:
    from claude_pair.skills import PEER_SESSION_SKILL, PAIR_SKILL
    skills_dir = CLAUDE_DIR / "skills"
    for name, content in (("peer-session", PEER_SESSION_SKILL), ("pair", PAIR_SKILL)):
        d = skills_dir / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(content)


def install(project_dir: Path) -> None:
    hooks_dir = PAIR_DIR / "hooks"
    stop, prompt = _write_hooks(hooks_dir)
    print(f"  ✓ hook scripts → {hooks_dir}")

    _patch_settings(stop, prompt)
    print(f"  ✓ hooks registered in {CLAUDE_DIR / 'settings.json'}")

    _patch_statusline()
    print(f"  ✓ statusline patched")

    _write_mcp(project_dir)
    print(f"  ✓ .mcp.json written to {project_dir}")

    _write_skills()
    print(f"  ✓ skills installed to {CLAUDE_DIR / 'skills'}")

    PAIR_DIR.mkdir(exist_ok=True)
    print(f"\nDone. Restart Claude Code to pick up the changes.")
