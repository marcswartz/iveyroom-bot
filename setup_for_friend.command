#!/bin/zsh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "== Ivey Bot setup =="
echo "Working directory: $SCRIPT_DIR"

python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium

echo ""
echo "Now login once to Canvas to create session.json..."
python3 save_session.py

echo ""
echo "Installing scheduler from config.json..."
python3 install_scheduler.py

echo ""
echo "Setup complete."
echo "You can edit config.json to change slots/room ranking, then re-run:"
echo "python3 install_scheduler.py"
