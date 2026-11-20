#!/bin/bash
# rep349.sh ROOT OUT (sa-port-349, pareto0, shared lease, HOME=~/sp19): a28c548's method (tools347/pre347.sh:36-45) for
# the planted-history test under plant 759 skip-work, because the bar's suite-witness:skip-work row passed it. On
# sa-port-348's frozen tree of 82d4ddf (ROOT/s1/bench-82d4ddf/tree), rust backend, switch on, one fresh process a run,
# 20 runs a cell: the test (orig) and sa-port-185's keep-alive variant (keep), with the plant and, side by side,
# without it. End marker: OUT/rep-end.txt, the last line here.
export HOME=/home/tilo/sp19
T=$1/s1/bench-82d4ddf/tree; S=$T/rust-spike/slice; PLUG=$1/s1/plug; X=$2
. ~/sa-rust-ids-work/env.sh; export PY W SA_EVAL_DATA PYTHONHASHSEED T S X PLUG
unset SLICE_WITNESS SLICE_WITNESS_CAP SLICE_WITNESS_WORK SLICE_WITNESS_PLANT SLICE_CONVERT SLICE_TERM_FRAMES SLICE_SUITE_OUT
mkdir -p $X/logs
{ cat $T/../SHA; sha256sum $S/sa_solver.so $T/satassume/witness.py $PLUG/test_keepalive185.py; } > $X/rep-source.txt
for pl in skip-work none; do for k in orig keep; do for i in $(seq 20); do echo "$pl $k $i"; done; done; done > $X/todo.txt
xargs -P 8 -L 1 bash -c 'pl=$0; k=$1; i=$2; out=$X/logs/$pl-$k-$i.log
  case $k in keep) TGT=$PLUG/test_keepalive185.py ;; *) TGT=tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence ;; esac
  case $pl in none) unset SLICE_WITNESS_PLANT ;; *) export SLICE_WITNESS_PLANT=$pl ;; esac
  cd $T
  SLICE_WITNESS=1 SLICE_SUITE_BACKEND=rust PYTHONPATH=$T:$W/sympy:$W/shim:$S:$PLUG $PY -m pytest -p rust_plugin -q -s --tb=line -p no:cacheprovider --rootdir=$T $TGT > $out 2>&1
  echo "EXIT $?" >> $out
  SLICE_WITNESS=1 SLICE_SUITE_BACKEND=rust PYTHONPATH=$T:$W/sympy:$W/shim:$S $PY -c "import satassume, sa_solver; from satassume import witness; print(\"TREE\", satassume.__file__, sa_solver.__file__, \"WITNESS\", witness.ENABLED[0], \"PLANT\", witness.PLANT[0])" >> $out 2>&1' < $X/todo.txt
for pl in skip-work none; do for k in orig keep; do
  echo "rust plant=$pl $k sw=1 passed $(grep -l "^EXIT 0" $X/logs/$pl-$k-*.log 2>/dev/null | wc -l) of $(ls $X/logs/$pl-$k-*.log | wc -l); asserts: $(grep -h "assert" $X/logs/$pl-$k-*.log | sed 's/.*py:\([0-9]*\): /\1 /' | sort | uniq -c | tr '\n' ';') last: $(grep -h " passed\| failed" $X/logs/$pl-$k-*.log | sed 's/ in .*//' | sort | uniq -c | tr '\n' ';')"
done; done > $X/rep-sum.txt
grep -h "^TREE" $X/logs/*.log | sort | uniq -c > $X/trees.txt
echo "END $(date -u +%FT%TZ)" > $X/rep-end.txt
