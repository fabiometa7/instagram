#!/usr/bin/env bash
# Build a "Content Hub.app" bundle you can drag into /Applications and pin
# to the Dock. Double-clicking it starts the server in the background and
# opens the dashboard — no visible Terminal, and the launcher itself is
# instant because the venv + pip install happen HERE at build time.
#
# Usage:
#   ./scripts/build_mac_app.sh          # builds to ./Content\ Hub.app
#   ./scripts/build_mac_app.sh install  # also moves it to /Applications
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="Content Hub.app"

echo "→ Preparing Python environment (one-time)…"
if [ ! -d "$ROOT/.venv" ]; then
  /usr/bin/env python3 -m venv "$ROOT/.venv"
fi
"$ROOT/.venv/bin/pip" install -q --upgrade pip
"$ROOT/.venv/bin/pip" install -q -r "$ROOT/requirements.txt"
mkdir -p "$ROOT/data"

echo "→ Compiling AppleScript bundle…"
read -r -d '' SRC <<'APPLESCRIPT' || true
on run
  set projectDir to "__PROJECT_DIR__"
  set logPath to projectDir & "/data/server.log"
  set pidPath to projectDir & "/data/server.pid"
  set venvPy to projectDir & "/.venv/bin/python"

  -- If the venv vanished (project moved, cleaned), tell the user how to fix.
  try
    do shell script "test -x " & quoted form of venvPy
  on error
    display dialog "Content Hub isn't set up yet.

Run this once in Terminal:

    cd " & projectDir & "
    ./scripts/build_mac_app.sh install" buttons {"OK"} default button 1 with icon caution
    return
  end try

  -- If already running, just open the browser.
  try
    set existingPid to do shell script "cat " & quoted form of pidPath & " 2>/dev/null"
    set alive to do shell script "ps -p " & existingPid & " >/dev/null 2>&1 && echo yes || echo no"
    if alive is "yes" then
      do shell script "open http://127.0.0.1:5000"
      return
    end if
  end try

  -- Start the server detached. This returns immediately.
  do shell script "cd " & quoted form of projectDir & " && nohup " & quoted form of venvPy & " app.py >> " & quoted form of logPath & " 2>&1 & echo $! > " & quoted form of pidPath

  -- Wait up to ~5 seconds for the port to come up, then open the browser.
  do shell script "for i in 1 2 3 4 5 6 7 8 9 10; do /usr/bin/curl -s -o /dev/null http://127.0.0.1:5000 && break; sleep 0.5; done"
  do shell script "open http://127.0.0.1:5000"
end run
APPLESCRIPT

# Inject the absolute project path into the script source.
SRC="${SRC//__PROJECT_DIR__/$ROOT}"

cd "$ROOT"
rm -rf "$APP"
osacompile -o "$APP" -e "$SRC"
echo "✓ Built: $ROOT/$APP"

if [ "${1:-}" = "install" ]; then
  rm -rf "/Applications/$APP"
  mv "$APP" "/Applications/"
  echo "✓ Installed to /Applications/$APP"
  echo ""
  echo "Next: open Finder → Applications → 'Content Hub' (right-click → Open"
  echo "the first time to accept the unidentified-developer warning), then"
  echo "right-click its Dock icon → Options → Keep in Dock."
fi
