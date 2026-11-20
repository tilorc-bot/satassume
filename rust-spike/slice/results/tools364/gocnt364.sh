#!/bin/bash
# gocnt364.sh OUT (sa-port-364, orion, counts only, no timing): cnt364.py on dev, fuzz, budget, wiring in three cells:
#   py        the package alone (the default path)
#   rust-py   the slice with S1's rust-nat switches and SLICE_CONVERT=py (Python's walker)
#   rust-nat  the slice with S1's rust-nat switches (SLICE_CONVERT=rust, Rust's walker)
# The tree is this worktree (its sa_solver.so as built by build_solver.sh). End marker: OUT/end.txt, the last line.
WT=$(cd "$(dirname "$0")/../../../.." && pwd); S=$WT/rust-spike/slice; T=$S/results/tools364; OUT=$1
mkdir -p $OUT
. ~/sa-rust-ids-work/env.sh; export SA_EVAL_DATA PYTHONHASHSEED
for v in $(env | grep -o '^SLICE_[A-Z_0-9]*'); do unset $v; done
export PYTHONPATH=$WT:$W/sympy:$W/shim SLICE_DIR=$S
{ git -C $WT rev-parse HEAD; sha256sum $S/sa_solver.so; $PY -c 'import satassume, sympy, sys; print(satassume.__file__, sympy.__file__, sys.version.split()[0])'; } > $OUT/tree.txt 2>&1
rc=0
for wl in dev budget wiring fuzz; do
  SLICE_WITNESS=1 $PY $T/cnt364.py $wl py $OUT/$wl-py.json > $OUT/$wl-py.line 2> $OUT/$wl-py.err || rc="$rc $wl-py"
  for cv in py rust; do
    c=rust-$([ $cv = rust ] && echo nat || echo py)
    SLICE_CONVERT=$cv SLICE_TERM_FRAMES=rust SLICE_WITNESS=1 SLICE_WITNESS_RUST=1 $PY $T/cnt364.py $wl rust $OUT/$wl-$c.json > $OUT/$wl-$c.line 2> $OUT/$wl-$c.err || rc="$rc $wl-$c"
  done
done
echo "END $rc $(date -u +%FT%TZ)" > $OUT/end.txt
