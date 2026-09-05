#!/usr/bin/env bash
# Full four-gate run for r/PublicFreakout, GPU-bounded.
set -u
cd "$(dirname "$0")/.."
echo $$ > data/out/.pf.pid
DEADLINE=$(( $(date +%s) + 6*3600 + 30*60 ))
echo "pf batch start $(date -Is), GPU deadline $(date -d @$DEADLINE -Is)"

# 1. ledger entry: rescore cohort (now 101 subs), then name the new sub
python3 scripts/score_gaps.py > logs/pf_gaps.log 2>&1
rm -f data/out/.analyze.lock
python3 scripts/analyze_all.py >> logs/pf_gaps.log 2>&1

# 2. stance labels, case-control (other subs skipped via --alloc)
rm -f data/out/.slant.lock
python3 scripts/slant_run.py --limit 4200 --alloc "PublicFreakout:4200"

# 3. advocacy-vs-quotation pass over the new sided titles
rm -f data/out/.qpass.lock
python3 scripts/qpass_run.py --deadline "$DEADLINE"

# 4. M3 (API) runs concurrently with M4 (GPU)
rm -f data/out/.m3pf.marker
( python3 scripts/m3_attrition.py > logs/m3_pf.log 2>&1
  python3 scripts/m3_prior.py > logs/m3prior_pf.log 2>&1
  touch data/out/.m3pf.marker ) &
rm -f data/out/.m4.lock
python3 scripts/m4_run.py --deadline "$DEADLINE"

for i in $(seq 1 90); do [ -f data/out/.m3pf.marker ] && break; sleep 60; done

# 5. analysis
python3 scripts/audience_run2.py > data/out/pf_audience.txt 2>&1
python3 scripts/batch2_analysis.py > /dev/null 2>&1
echo "freeing VRAM"
/mnt/c/Users/User/.lmstudio/bin/lms.exe unload --all || true
echo "pf batch done $(date -Is)"
