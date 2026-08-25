#!/usr/bin/env bash
# Wait for a specific harvester PID to exit, then name every subreddit.
# Takes a PID rather than grepping for a name: `pgrep -f harvest_all.py` also
# matches any monitoring command that merely mentions the script, so the wait
# can deadlock against its own watcher instead of the job it cares about.
set -u
cd "$(dirname "$0")/.."
pid="${1:?usage: run_after_harvest.sh <harvester-pid>}"
while kill -0 "$pid" 2>/dev/null; do sleep 20; done
echo "harvester $pid exited at $(date -Is); starting analysis"
exec python3 scripts/analyze_all.py
