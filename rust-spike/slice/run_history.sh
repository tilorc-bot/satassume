#!/bin/bash
# run_history.sh WORK [JOBS]: plan section 3's runs 1 to 4, each on both backends, traced with `--check entry`.
#   WORK/recorded-{dev,fuzz}-{py,rust}.jsonl     recorded order, seed 0 (the base of the compares)
#   shuffle1-*, shuffle2-*                       run 1: two shuffles, seed 0
#   fork-*                                       run 2: a child per query, forked after import
#   twice-*                                      run 3: each query twice in a row in one process
#   seed1-*, seed2-*                             run 4: other hash seeds, recorded order
# Each run leaves .jsonl, .tot, .err and a line in done.txt. historycmp.py reads them. Skips a run that finished.
# The tree under test is the one holding this script, not the path env.sh names; tree.txt records what imported.
T=$(cd "$(dirname "$0")/../.." && pwd)
. ~/sa-rust-ids-work/env.sh
PYTHONPATH=$T:$W/sympy:$W/shim
export SA_EVAL_DATA PYTHONPATH
W2=$(mkdir -p "$1" && cd "$1" && pwd); J=${2:-4}
cd "$(dirname "$0")"
$PY -c 'import satassume; print(satassume.__file__)' >"$W2/tree.txt"
one() { # name seed backend wl flags...
  n=$1; seed=$2; b=$3; wl=$4; shift 4
  f="$W2/$n-$wl-$b"
  grep -q '"total"' "$f.jsonl" 2>/dev/null && return
  PYTHONHASHSEED=$seed $PY live.py $wl $b "$f.jsonl" --check entry "$@" >"$f.tot" 2>"$f.err"
  echo "$n-$wl-$b rc=$? $(date -u +%T)" >>"$W2/done.txt"
}
export -f one; export W2 PY
for wl in dev fuzz; do for b in py rust; do
  echo "recorded 0 $b $wl"
  echo "shuffle1 0 $b $wl --shuffle 1"
  echo "shuffle2 0 $b $wl --shuffle 2"
  echo "fork 0 $b $wl --fork"
  echo "twice 0 $b $wl --twice"
  echo "seed1 1 $b $wl"
  echo "seed2 2 $b $wl"
done; done | xargs -P "$J" -L1 bash -c 'one "$@"' _
date -u >"$W2/finished.txt"
