#!/usr/bin/env bash
# Double-click this file from Finder to start the Content Hub.
# Terminal opens, the server starts, and your browser opens automatically.
set -e
cd "$(dirname "$0")"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt
export IG_USERNAME="${IG_USERNAME:-fabiometa_}"
# Give the server a second, then open the dashboard in the default browser.
(sleep 1 && open "http://127.0.0.1:5000") &
echo ""
echo "  Content Hub running at http://127.0.0.1:5000"
echo "  Close this window (or press Ctrl+C) to stop the server."
echo ""
python app.py
