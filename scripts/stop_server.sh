#!/usr/bin/env bash
# Stops the background Content Hub server started by the .app bundle.
set -e
cd "$(dirname "$0")/.."
if [ -f data/server.pid ]; then
  pid=$(cat data/server.pid)
  if kill "$pid" 2>/dev/null; then
    echo "Stopped Content Hub (pid $pid)."
  else
    echo "No live process for pid $pid — cleaning up."
  fi
  rm -f data/server.pid
else
  echo "No server.pid file. Nothing to stop."
fi
