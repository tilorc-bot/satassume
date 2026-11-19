#!/bin/sh
# run1.sh TREE BACKEND(rust|python) KIND(orig|keep) MODE(plain|walk|both) OUTFILE: one fresh pytest process.
# a28c548's method (sa-port-185's run1.sh, as 282, 310 and 318 ran it), on sa-port-327's worktree. MODE walk sets
# SLICE_CONVERT=rust, both adds SLICE_TERM_FRAMES=rust.
T=$1; B=$2; K=$3; F=$4; OUT=$5
. ~/sa-rust-ids-work/env.sh
O=$HOME/sa-rust-ids-work/sa-port-327
export PYTHONPATH=$T:$W/sympy:$W/shim:$T/rust-spike/slice:$O/plug SLICE_SUITE_BACKEND=$B
unset SLICE_SUITE_OUT SLICE_TERM_FRAMES SLICE_CONVERT SLICE_TERM_PLANT SLICE_SESSION_PLANT SLICE_CONVERT_PLANT
case $F in walk) export SLICE_CONVERT=rust;; both) export SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust;; esac
cd $T
case $K in
  keep) TGT=$O/plug/test_keepalive185.py ;;
  *) TGT=tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence ;;
esac
$PY -m pytest -p rust_plugin -q -s --tb=line -p no:cacheprovider --rootdir=$T $TGT > $OUT 2>&1
echo "EXIT $?" >> $OUT
$PY -c 'import satassume,sys,os; import sa_solver, convert; convert.from_env(); print("TREE", satassume.__file__, sa_solver.__file__, "FRAMES", os.environ.get("SLICE_TERM_FRAMES"), "CONVERT", os.environ.get("SLICE_CONVERT"), "WALK", repr(convert.WALK[0])[:40])' >> $OUT 2>&1
exit 0
