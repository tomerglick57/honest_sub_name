#!/usr/bin/env bash
# One deadline-bounded batch: Q-pass validation + classification, Conservative
# expansion while time allows, advocacy-only analysis, then free the GPU.
set -u
cd "$(dirname "$0")/.."
DEADLINE=$(( $(date +%s) + 6*3600 + 15*60 ))
echo "batch start $(date -Is), GPU deadline $(date -d @$DEADLINE -Is)"

python3 scripts/qpass_run.py --deadline "$DEADLINE"
rc=$?
if [ $rc -ne 0 ]; then echo "Q-PASS GATE FAILED (rc=$rc) -- stopping batch"; exit $rc; fi

# grow r/Conservative's left-survivor sample while >75 min of GPU time remain
while [ "$(date +%s)" -lt $(( DEADLINE - 4500 )) ]; do
  rm -f data/out/.slant.lock
  python3 scripts/slant_run.py --limit 500 --alloc "Conservative:500" || break
done

# q-label whatever the expansion added
rm -f data/out/.qpass.lock
python3 scripts/qpass_run.py --deadline "$DEADLINE"

python3 scripts/audience_run2.py | tee data/out/audience2_report.txt
echo "freeing VRAM"
/mnt/c/Users/User/.lmstudio/bin/lms.exe unload --all || true
echo "batch done $(date -Is)"
