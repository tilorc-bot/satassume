#!/bin/bash
# run325.sh OUT_DIR [CAP] (sa-port-325, issue 323; orion): the pure-Python None-certify pass of dev and fuzz (cap325.py) and
# the tables (sum325.py). Offline scratch check; reads the worktree's package, changes nothing in it. End marker: OUT/end.txt.
W=~/sa-rust-ids-work; O=$1; CAP=${2:-2000}
T=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$T/../../../.." && pwd)
mkdir -p $O; cd $ROOT
export PYTHONHASHSEED=0 SA_EVAL_DATA=$W/data PYTHONPATH=$ROOT:$W/sympy:$W/shim:$T
{ date -u; hostname; git -C $ROOT rev-parse HEAD; git -C $ROOT status --porcelain -- satassume | wc -l; $W/venv/bin/python -VV; sha256sum $T/*.py; uptime; } > $O/env.txt 2>&1
for wl in dev fuzz; do
  $W/venv/bin/python $T/cap325.py $wl $O/$wl.jsonl $CAP > $O/$wl.out 2> $O/$wl.err &
done
wait
python3 $T/sum325.py $O $W/sa-port-322/run-count $W/sa-port-323/timing-r1/time.jsonl $O/lists.txt > $O/sum.txt 2> $O/sum.err
echo "END rc=$? $(date -u +%FT%TZ) $(wc -c < $O/dev.err) $(wc -c < $O/fuzz.err) $(wc -c < $O/sum.err)" > $O/end.txt
