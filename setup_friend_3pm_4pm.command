#!/bin/zsh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

cp "config_3pm_4pm.json" "config.json"
echo "Applied config preset: 3pm + 4pm"

"$SCRIPT_DIR/setup_for_friend.command"
