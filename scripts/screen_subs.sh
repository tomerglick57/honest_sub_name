#!/usr/bin/env bash
# Screen big non-political subs with the r/pics front-page method, 2023 on:
# census each sub, label every day's top 10 (2 concurrent: the LAN host is
# shared), write data/out/screen/<sub>.json. Subs run one after another so
# the model never sees more than 2 requests; each sub's census overlaps its
# own labeling (--follow). Resumable: rerun to continue.
set -u
cd "$(dirname "$0")/.."
SUBS=${SUBS:-"funny interestingasfuck Damnthatsinteresting facepalm MadeMeSmile OldSchoolCool aww"}
for sub in $SUBS; do
  echo "== r/$sub $(date +%H:%M)"
  python3 scripts/census.py "$sub" --since 2023-01 --workers 2 > "logs/census_$sub.log" 2>&1 &
  cpid=$!
  until [ -f "data/census/$sub/_counts.json" ]; do sleep 5; done
  python3 scripts/frontpage_label.py "$sub" --n 10 --sample 0 --concurrency 2 --follow > "logs/frontpage_label_$sub.log" 2>&1
  wait $cpid
  python3 scripts/control_series.py "$sub" > "logs/screen_$sub.log" 2>&1
  echo "   $(tail -1 "logs/frontpage_label_$sub.log") | census: $(grep -c CHECK "logs/census_$sub.log") months flagged"
done
echo "screen_subs done $(date +%H:%M)"
