import hashlib
import json
import os
import stat
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

_PROMPT_HOOK = """\
#!/bin/bash
ccpair interrupt 2>/dev/null || true
"""


def _write_hooks(hooks_dir: Path) -> Path:
    hooks_dir.mkdir(parents=True, exist_ok=True)
    prompt = hooks_dir / "pair-user-prompt.sh"
    prompt.write_text(_PROMPT_HOOK)
    prompt.chmod(prompt.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return prompt


def _patch_settings(prompt: Path, isolated_dir: Path | None) -> None:
    settings_path = CLAUDE_DIR / "settings.json"
    data = json.loads(settings_path.read_text()) if settings_path.exists() else {}

    def _ensure_hook(event: str, cmd: str) -> None:
        hooks = data.setdefault("hooks", {})
        entries = hooks.setdefault(event, [])
        for entry in entries:
            for h in entry.get("hooks", []):
                if h.get("command") == cmd:
                    return
        entries.append({"matcher": "", "hooks": [{"type": "command", "command": cmd, "timeout": 5}]})

    cmd = f"bash {prompt}"
    if isolated_dir:
        cmd = f"CLAUDE_PAIR_DIR={isolated_dir} bash {prompt}"
    _ensure_hook("UserPromptSubmit", cmd)

    # Clean up stale claude-pair MCP entries from earlier versions
    mcp_servers = data.get("mcpServers", {})
    if isinstance(mcp_servers, dict):
        for stale in ("claude-pair", "ccpair"):
            mcp_servers.pop(stale, None)

    CLAUDE_DIR.mkdir(exist_ok=True)
    settings_path.write_text(json.dumps(data, indent=2))


def _patch_statusline() -> None:
    sl = CLAUDE_DIR / "statusline-command.sh"
    if not sl.exists():
        return
    content = sl.read_text()
    if "# ccpair overlay" in content:
        return
    insert_before = "\nleft=$("
    idx = content.rfind(insert_before)
    if idx == -1:
        return
    content = content[:idx] + _STATUSLINE_PAIR_BLOCK + content[idx:]
    sl.write_text(content)


def _clean_legacy_mcp_in_project() -> None:
    """Remove old .mcp.json ccpair entries from previous MCP-based versions."""
    for mcp_path in Path.cwd().rglob(".mcp.json"):
        try:
            data = json.loads(mcp_path.read_text())
            servers = data.get("mcpServers", {})
            removed = False
            for stale in ("ccpair", "claude-pair"):
                if servers.pop(stale, None) is not None:
                    removed = True
            if removed:
                mcp_path.write_text(json.dumps(data, indent=2))
                print(f"  ✓ removed legacy MCP entry from {mcp_path}")
        except Exception:
            continue


def _write_skills() -> None:
    from claude_pair.skills import PAIR_SKILL, PEER_SESSION_SKILL
    skills_dir = CLAUDE_DIR / "skills"
    for name, content in (("peer-session", PEER_SESSION_SKILL), ("pair", PAIR_SKILL)):
        d = skills_dir / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(content)


def install(isolated: bool = False) -> None:
    isolated_dir: Path | None = None
    if isolated:
        proj_hash = hashlib.sha1(str(Path.cwd().resolve()).encode()).hexdigest()[:8]
        isolated_dir = Path.home() / ".claude-pair" / f"proj-{proj_hash}"
        isolated_dir.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ isolated state dir → {isolated_dir}")
        print(f"    (set CLAUDE_PAIR_DIR={isolated_dir} in your shell for this project)")

    hooks_dir = PAIR_DIR / "hooks"
    prompt = _write_hooks(hooks_dir)
    print(f"  ✓ interrupt hook → {prompt}")

    _patch_settings(prompt, isolated_dir)
    print(f"  ✓ hook registered in {CLAUDE_DIR / 'settings.json'}")

    _patch_statusline()
    print("  ✓ statusline overlay installed")

    _write_skills()
    print(f"  ✓ skills installed to {CLAUDE_DIR / 'skills'}/(pair|peer-session)")

    _clean_legacy_mcp_in_project()

    PAIR_DIR.mkdir(exist_ok=True)
    print()
    print("Done. Architecture:")
    print("  - Agents call bash commands (ccpair host/join/wait/say/recv)")
    print("  - Daemon runs in background, owns TCP port + mDNS")
    print("  - No MCP server — works in any harness with bash")
    print()
    print("Restart Claude Code to load the new skills.")
