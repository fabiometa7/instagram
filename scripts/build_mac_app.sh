#!/usr/bin/env bash
# Build a "Content Hub.app" bundle you can drag into /Applications and pin
# to the Dock. Double-clicking it runs the server in the background and
# opens the dashboard in your browser — no visible Terminal window.
#
# Usage:
#   ./scripts/build_mac_app.sh          # builds to ./Content\ Hub.app
#   ./scripts/build_mac_app.sh install  # also moves it to /Applications
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="Content Hub.app"

read -r -d '' SRC <<APPLESCRIPT || true
on run
  set projectDir to "$ROOT"
  set logPath to projectDir & "/data/server.log"
  set pidPath to projectDir & "/data/server.pid"

  do shell script "mkdir -p " & quoted form of (projectDir & "/data")

  -- If already running (pid file points to a live process), just open the browser.
  try
    set existingPid to do shell script "cat " & quoted form of pidPath & " 2>/dev/null"
    set alive to do shell script "ps -p " & existingPid & " >/dev/null 2>&1 && echo yes || echo no"
    if alive is "yes" then
      delay 0
      do shell script "open http://127.0.0.1:5000"
      return
    end if
  end try

  -- Otherwise install deps if needed, then launch the server detached.
  do shell script "cd " & quoted form of projectDir & " && \\
    { [ -d .venv ] || /usr/bin/env python3 -m venv .venv; } && \\
    ./.venv/bin/pip install -q -r requirements.txt && \\
    nohup ./.venv/bin/python app.py >> " & quoted form of logPath & " 2>&1 & echo \$! > " & quoted form of pidPath

  -- Wait for the port to be up, then open the browser.
  do shell script "for i in 1 2 3 4 5 6 7 8 9 10; do \\
    curl -s -o /dev/null http://127.0.0.1:5000 && break; sleep 0.5; done"
  do shell script "open http://127.0.0.1:5000"
end run
APPLESCRIPT

cd "$ROOT"
rm -rf "$APP"
osacompile -o "$APP" -e "$SRC"
echo "Built: $ROOT/$APP"

if [ "${1:-}" = "install" ]; then
  rm -rf "/Applications/$APP"
  mv "$APP" "/Applications/"
  echo "Installed to /Applications/$APP"
  echo "Open Finder → Applications → 'Content Hub' → right-click → Options → Keep in Dock."
fi
