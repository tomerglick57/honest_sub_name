#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."
echo $$ > data/out/.batch2.pid
DEADLINE=$(( $(date +%s) + 6*3600 + 20*60 ))
echo "batch2 start $(date -Is), GPU deadline $(date -d @$DEADLINE -Is)"

# M3 is API-only: run it concurrently with the GPU work
rm -f data/out/.m3.marker
( python3 scripts/m3_attrition.py > logs/m3.log 2>&1; touch data/out/.m3.marker ) &

rm -f data/out/.g1x.lock data/out/.m4.lock
python3 scripts/g1_expand.py --deadline "$DEADLINE" --limit 4600
python3 scripts/m4_run.py --deadline "$DEADLINE"

# wait (bounded) for m3 before the final analysis
for i in $(seq 1 60); do [ -f data/out/.m3.marker ] && break; sleep 60; done
python3 scripts/batch2_analysis.py
echo "freeing VRAM"
/mnt/c/Users/User/.lmstudio/bin/lms.exe unload --all || true
echo "batch2 done $(date -Is)"
