#!/bin/bash
# Time the refine-identities battery (tools/refine_identity_scoreboard.py, 1,736 cases)
# once per backend, interleaved.  Run from a checkout that has satrefine/ (main merged
# with refine-identities).  Usage: refine_battery_time.sh SYMPY_DIR OUTDIR ROUND [BACKENDS...]
sympy=$1; out=$2; round=$3; shift 3
backends=${*:-sympy satassume combined}
mkdir -p "$out"
for b in $backends; do
  s=$(date +%s%N)
  SATREFINE_BACKEND=$b PYTHONHASHSEED=0 PYTHONPATH=.:$sympy timeout 250 \
    /home/tilo/satassume/.venv/bin/python tools/refine_identity_scoreboard.py > "$out/battery-$b-$round.txt" 2>&1
  e=$?
  ms=$(( ($(date +%s%N) - s) / 1000000 ))
  echo "round $round $b exit $e wall ${ms} ms" | tee -a "$out/battery-times.txt"
done
