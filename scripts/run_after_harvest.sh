#!/usr/bin/env bash
# Wait for the harvester to exit, then name every subreddit.
set -u
cd "$(dirname "$0")/.."
while pgrep -f "harvest_all.py" >/dev/null; do sleep 20; done
echo "harvest finished at $(date -Is); starting analysis"
exec python3 scripts/analyze_all.py
