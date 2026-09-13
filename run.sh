#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt
export IG_USERNAME="${IG_USERNAME:-fabiometa_}"
echo ""
echo "  Content Hub running at http://127.0.0.1:5000"
echo ""
python app.py
