#!/usr/bin/env bash
# Screen big non-political subs with the r/pics front-page method, 2023 on:
# census each sub, label every day's top 10, write data/out/screen/<sub>.json.
# LABELER=hybrid (default) sends titles to TypeSafe Jev first and only the
# low-confidence fifth to the LAN model (2 concurrent: the host is shared);
# LABELER=gemma is the all-LAN path. Subs run one after another; each sub's
# census overlaps its own labeling (--follow). Resumable: rerun to continue.
set -u
cd "$(dirname "$0")/.."
SUBS=${SUBS:-"funny interestingasfuck Damnthatsinteresting facepalm MadeMeSmile OldSchoolCool aww"}
LABELER=${LABELER:-hybrid}
GEMMA_CONC=${GEMMA_CONC:-2}  # set to 1 when running two lanes side by side
for sub in $SUBS; do
  echo "== r/$sub $(date +%H:%M) ($LABELER)"
  rm -f "data/census/$sub/_done.json"
  python3 scripts/census.py "$sub" --since 2023-01 --workers 2 > "logs/census_$sub.log" 2>&1 &
  cpid=$!
  # wait for the counts file; if the census dies first (bad archive reply), skip the sub
  until [ -f "data/census/$sub/_counts.json" ] || ! kill -0 $cpid 2>/dev/null; do sleep 5; done
  if [ ! -f "data/census/$sub/_counts.json" ]; then echo "   !! census r/$sub died before writing counts; skipped"; continue; fi
  python3 scripts/frontpage_label.py "$sub" --n 10 --sample 0 --concurrency "$GEMMA_CONC" --labeler "$LABELER" --follow > "logs/frontpage_label_$sub.log" 2>&1
  wait $cpid
  python3 scripts/control_series.py "$sub" > "logs/screen_$sub.log" 2>&1
  echo "   $(tail -1 "logs/frontpage_label_$sub.log") | $(tail -1 "logs/census_$sub.log") | $(grep -c CHECK "logs/census_$sub.log") months flagged"
done
echo "screen_subs done $(date +%H:%M)"
