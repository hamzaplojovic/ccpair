#!/bin/bash
set -e

PLUGIN_NAME="claude-pair"
VERSION="0.2.0"
PLUGIN_DIR="$HOME/.claude/plugins/local/${PLUGIN_NAME}/${VERSION}"
INSTALLED_PLUGINS="$HOME/.claude/plugins/installed_plugins.json"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Installing ${PLUGIN_NAME} plugin locally..."

# symlink repo into plugins/local so edits are live
mkdir -p "$(dirname "$PLUGIN_DIR")"
ln -sfn "$REPO_DIR" "$PLUGIN_DIR"
echo "  ✓ linked $REPO_DIR → $PLUGIN_DIR"

# update installed_plugins.json
if [[ ! -f "$INSTALLED_PLUGINS" ]]; then
    echo '{"version":2,"plugins":{}}' > "$INSTALLED_PLUGINS"
fi

now=$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")
python3 - <<PYEOF
import json, sys
path = "$INSTALLED_PLUGINS"
data = json.loads(open(path).read())
data.setdefault("plugins", {})["${PLUGIN_NAME}@local"] = [{
    "scope": "user",
    "installPath": "$PLUGIN_DIR",
    "version": "$VERSION",
    "installedAt": "$now",
    "lastUpdated": "$now"
}]
open(path, "w").write(json.dumps(data, indent=4))
print("  ✓ registered in installed_plugins.json")
PYEOF

# make hook scripts executable
chmod +x "$REPO_DIR/hooks/scripts/"*.sh
echo "  ✓ hook scripts executable"

# write config.json so the /pair skill can find the project dir
mkdir -p "$HOME/.claude-pair"
python3 - <<PYEOF
import json, os
path = os.path.expanduser("~/.claude-pair/config.json")
data = {"project_dir": "$REPO_DIR"}
open(path, "w").write(json.dumps(data, indent=2))
print("  ✓ wrote ~/.claude-pair/config.json")
PYEOF

# install claude-pair wrapper to ~/.local/bin so skills can call it directly
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/claude-pair" <<WRAPPER
#!/bin/bash
exec uv --directory "$REPO_DIR" run claude-pair "\$@"
WRAPPER
chmod +x "$HOME/.local/bin/claude-pair"
echo "  ✓ installed ~/.local/bin/claude-pair"

echo ""
echo "Done. Restart Claude Code, then enable the plugin:"
echo "  /plugin enable claude-pair"
