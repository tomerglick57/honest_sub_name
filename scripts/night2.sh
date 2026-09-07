#!/usr/bin/env bash
# Night run: finish r/PublicFreakout, full 2025-26 funnel for r/pics.
set -u
cd "$(dirname "$0")/.."
echo $$ > data/out/.night2.pid
DEADLINE=$(( $(date +%s) + 8*3600 + 30*60 ))
echo "night2 start $(date -Is), GPU deadline $(date -d @$DEADLINE -Is)"

# stance: PublicFreakout resumes at 0/4200; pics fresh 3800
rm -f data/out/.slant.lock
python3 scripts/slant_run.py --limit 3800 --alloc "PublicFreakout:3800"
rm -f data/out/.slant.lock
python3 scripts/slant_run.py --limit 3800 --alloc "pics:3800"

# advocacy pass over all new sided titles (both subs)
rm -f data/out/.qpass.lock
python3 scripts/qpass_run.py --deadline "$DEADLINE"

# M3 (API) concurrent with M4 (GPU)
rm -f data/out/.m3n2.marker
( python3 scripts/m3_attrition.py > logs/m3_n2.log 2>&1
  python3 scripts/m3_prior.py > logs/m3prior_n2.log 2>&1
  touch data/out/.m3n2.marker ) &
rm -f data/out/.m4.lock
python3 scripts/m4_run.py --deadline "$DEADLINE"

for i in $(seq 1 120); do [ -f data/out/.m3n2.marker ] && break; sleep 60; done

python3 scripts/audience_run2.py > data/out/night2_audience.txt 2>&1
python3 scripts/batch2_analysis.py > /dev/null 2>&1
echo "freeing VRAM"
/mnt/c/Users/User/.lmstudio/bin/lms.exe unload --all || true
echo "night2 done $(date -Is)"
