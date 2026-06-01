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
