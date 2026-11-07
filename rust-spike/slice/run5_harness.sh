#!/bin/bash
# run5_harness.sh WORK: plan run 5's harness presets on both backends, one after the other. WORK/run5-harness-{rust,python}.txt
# hold the output; each one's last line counts the solvers made. WORK/run5-harness-finished.txt is written last.
. ~/sa-rust-ids-work/env.sh
export PYTHONPATH SA_EVAL_DATA PYTHONHASHSEED
cd ~/dev/sa-rust
for b in rust python; do
  timeout 7200 "$PY" rust-spike/slice/harness_rust.py $b "$1/run5-harness-$b.txt" fuzz --seeds 0-3 --config all \
    --out "$1/run5-harness-out-$b" > "$1/run5-harness-$b.log" 2>&1
  echo "$b rc=$? $(date -u +%T)" >> "$1/run5-harness-finished.tmp"
done
mv "$1/run5-harness-finished.tmp" "$1/run5-harness-finished.txt"
