#!/usr/bin/env bash
# Install a launchd agent so Content Hub starts automatically at login and
# keeps itself running. Reboot-proof.
#
# Usage:
#   ./scripts/install_autostart.sh     # install and start
#   ./scripts/install_autostart.sh off # uninstall
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.fabiometa.contenthub"
PLIST_SRC="$ROOT/scripts/com.fabiometa.contenthub.plist.template"
PLIST_DST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ "${1:-}" = "off" ]; then
  launchctl unload "$PLIST_DST" 2>/dev/null || true
  rm -f "$PLIST_DST"
  echo "Autostart uninstalled."
  exit 0
fi

# Make sure venv exists so launchd doesn't launch nothing.
if [ ! -d "$ROOT/.venv" ]; then
  python3 -m venv "$ROOT/.venv"
  "$ROOT/.venv/bin/pip" install -q -r "$ROOT/requirements.txt"
fi

mkdir -p "$HOME/Library/LaunchAgents"
sed "s|__PROJECT_DIR__|$ROOT|g" "$PLIST_SRC" > "$PLIST_DST"

launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"

echo "Autostart installed."
echo "Content Hub will now start at login and auto-restart if it crashes."
echo "Open: http://127.0.0.1:5000"
echo "Uninstall later with: ./scripts/install_autostart.sh off"
