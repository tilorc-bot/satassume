#!/bin/bash
# gocnt367.sh OUT CELL "WL..." FILE... (sa-port-367, orion, counts only, no timing; tools364/gocnt364.sh's environment):
# cnt367.py on the workloads named, in one cell:
#   default   the package alone, no SLICE_ switch (what SymPy runs)
#   rust-nat  the slice with SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust SLICE_WITNESS=1 SLICE_WITNESS_CAP=32 SLICE_WITNESS_RUST=1
# The tree is this worktree (its sa_solver.so as built by build_solver.sh). End marker: OUT/end-CELL.txt, the last line.
WT=$(cd "$(dirname "$0")/../../../.." && pwd); S=$WT/rust-spike/slice; T=$S/results/tools367; OUT=$1; CELL=$2; WLS=$3; shift 3
mkdir -p $OUT
. ~/sa-rust-ids-work/env.sh; export SA_EVAL_DATA PYTHONHASHSEED
for v in $(env | grep -o '^SLICE_[A-Z_0-9]*'); do unset $v; done
export PYTHONPATH=$WT:$W/sympy:$W/shim SLICE_DIR=$S
{ git -C $WT rev-parse HEAD; sha256sum $S/sa_solver.so; $PY -c 'import satassume, sympy, sys; print(satassume.__file__, sympy.__file__, sys.version.split()[0])'; } > $OUT/tree-$CELL.txt 2>&1
rc=0
for wl in $WLS; do
  if [ $CELL = default ]; then
    $PY $T/cnt367.py $wl py $OUT/$wl-$CELL.json "$@" > $OUT/$wl-$CELL.line 2> $OUT/$wl-$CELL.err || rc="$rc $wl"
  else
    SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust SLICE_WITNESS=1 SLICE_WITNESS_CAP=32 SLICE_WITNESS_RUST=1 $PY $T/cnt367.py $wl rust $OUT/$wl-$CELL.json "$@" > $OUT/$wl-$CELL.line 2> $OUT/$wl-$CELL.err || rc="$rc $wl"
  fi
done
echo "END $rc $(date -u +%FT%TZ)" > $OUT/end-$CELL.txt
