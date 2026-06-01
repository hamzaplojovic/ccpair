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
_CP_STATUS="${CLAUDE_PAIR_DIR:-$HOME/.claude-pair}/status.json"
if [[ -f "$_CP_STATUS" ]]; then
    cp_status=$(jq -r '.status // ""' "$_CP_STATUS" 2>/dev/null)
    if [[ "$cp_status" == "waiting" ]]; then
        cp_code=$(jq -r '.code // ""' "$_CP_STATUS" 2>/dev/null)
        pair_str="${sep}${yellow}⇄ ${cp_code}${reset}${sep}${muted}waiting...${reset}"
    elif [[ "$cp_status" == "connected" ]]; then
        cp_peer=$(jq -r '.peer // "peer"' "$_CP_STATUS" 2>/dev/null)
        pair_str="${sep}${cyan}⇄ ${cp_peer}${reset}"
    fi
fi
# end ccpair overlay
"""

_STOP_HOOK = """\
#!/bin/bash
# No-op: session state lives in-memory in the MCP server process
exit 0
"""

_PROMPT_HOOK = """\
#!/bin/bash
DIR="${CLAUDE_PAIR_DIR:-$HOME/.claude-pair}"
touch "$DIR/interrupted" 2>/dev/null || true
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
