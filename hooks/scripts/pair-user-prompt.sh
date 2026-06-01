#!/bin/bash
DIR="${CLAUDE_PAIR_DIR:-$HOME/.claude-pair}"
STATE="$DIR/state.json"
[[ ! -f "$STATE" ]] && exit 0

active=$(jq -r '.active // false' "$STATE" 2>/dev/null)
[[ "$active" != "true" ]] && exit 0

tmp=$(mktemp "$DIR/.state.XXXXXX.tmp")
jq '.phase = "human_active" | .interrupted = true | .exchange_count = 0 | .human_deadline = null' \
   "$STATE" > "$tmp" && mv "$tmp" "$STATE"
