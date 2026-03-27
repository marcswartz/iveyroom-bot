#!/bin/zsh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

cp "config_5pm_6pm.json" "config.json"
echo "Applied config preset: 5pm + 6pm"

"$SCRIPT_DIR/setup_for_friend.command"
