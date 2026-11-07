#!/bin/bash
# run6_counts.sh WORK: plan run 6's count: dev and fuzz on Rust under --check raw, one after the other. WORK/{dev,fuzz}.tot hold the totals,
# with backend_created and backend_dropped; WORK/finished.txt comes last.
. ~/sa-rust-ids-work/env.sh
export PYTHONPATH SA_EVAL_DATA PYTHONHASHSEED
cd "$(dirname "$0")"
for wl in dev fuzz; do
  "$PY" live.py $wl rust "$1/$wl.jsonl" --check raw > "$1/$wl.tot" 2> "$1/$wl.err"
done
date -u > "$1/finished.txt"
