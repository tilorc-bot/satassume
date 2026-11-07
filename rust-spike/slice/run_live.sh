#!/bin/sh
# run_live.sh WORK [CHECK]: full dev and fuzz on both backends, separate processes, same seed; Python twice as a control.
# Results land in WORK as they finish; `summary.txt` is the last thing written.
W2=$1; CHECK=${2:-entry}; mkdir -p "$W2"
# The tree under test is the one holding this script, not the path env.sh names; tree.txt records what imported.
T=$(cd "$(dirname "$0")/../.." && pwd)
. "$HOME/sa-rust-ids-work/env.sh"; PYTHONPATH=$T:$W/sympy:$W/shim; export PYTHONPATH SA_EVAL_DATA PYTHONHASHSEED
cd "$(dirname "$0")"
$PY -c 'import satassume; print(satassume.__file__)' >"$W2/tree.txt"
for wl in dev fuzz; do
  $PY live.py $wl py "$W2/$wl-py.jsonl" --check $CHECK >"$W2/$wl-py.tot" 2>"$W2/$wl-py.err" &
  $PY live.py $wl py "$W2/$wl-py2.jsonl" --check $CHECK >"$W2/$wl-py2.tot" 2>"$W2/$wl-py2.err" &
  $PY live.py $wl rust "$W2/$wl-rust.jsonl" --check $CHECK >"$W2/$wl-rust.tot" 2>"$W2/$wl-rust.err" &
  # No subclass and no hook wrappers on these: end states and answers only, from what a user would run.
  $PY live.py $wl rust "$W2/$wl-rust-raw.jsonl" --check raw >"$W2/$wl-rust-raw.tot" 2>"$W2/$wl-rust-raw.err" &
  $PY live.py $wl py "$W2/$wl-py-raw.jsonl" --check raw >"$W2/$wl-py-raw.tot" 2>"$W2/$wl-py-raw.err" &
  wait
  { echo "== $wl py vs py (control)"; $PY livecmp.py "$W2/$wl-py.jsonl" "$W2/$wl-py2.jsonl"
    echo "== $wl py vs rust"; $PY livecmp.py "$W2/$wl-py.jsonl" "$W2/$wl-rust.jsonl"
    echo "== $wl py traced vs py untraced, end states"; $PY livecmp.py "$W2/$wl-py.jsonl" "$W2/$wl-py-raw.jsonl" --end-only
    echo "== $wl py traced vs rust untraced, end states"; $PY livecmp.py "$W2/$wl-py.jsonl" "$W2/$wl-rust-raw.jsonl" --end-only; } >>"$W2/summary.part" 2>&1
done
mv "$W2/summary.part" "$W2/summary.txt"
date -u >>"$W2/summary.txt"
