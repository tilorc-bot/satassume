#!/bin/bash
# rep362.sh TREE PLUG OUT (sa-port-362, pareto0, shared lease, HOME=~/sp19): a28c548's method (tools355/rep355.sh with
# this step's cells) for the planted-history test, because the bar on 5b20d1f2 shows it (FAILED at :204 in each of its
# eight suite rows, as on base; planner [137e]: the check runs each time it shows). On the bar's own tree of 5b20d1f2
# (TREE, ~/sp19/dev/sa-port-361, the pareto venv .so), one fresh process a run, 20 runs a cell: the test (orig) and
# sa-port-185's keep-alive variant (keep), in four cells: rust with every switch off, rust with SLICE_CONVERT=rust (this
# step's path), rust with wnative:on's environment (a bar row), and python with every switch off (its base rate).
# End marker: OUT/rep-end.txt, the last line here.
export HOME=/home/tilo/sp19
T=$1; S=$T/rust-spike/slice; PLUG=$2; X=$3
. ~/sa-rust-ids-work/env.sh; export PY W SA_EVAL_DATA PYTHONHASHSEED T S X PLUG
for v in $(env | grep -o '^SLICE_[A-Z_0-9]*'); do unset $v; done
mkdir -p $X/logs
{ git -C $T rev-parse --short HEAD; sha256sum $S/sa_solver.so $S/convert.py $PLUG/test_keepalive185.py; } > $X/rep-source.txt
CELLS="rust:off rust:conv rust:nat python:off"
for c in $CELLS; do for k in orig keep; do for i in $(seq 20); do echo "${c%%:*} ${c#*:} $k $i"; done; done; done > $X/todo.txt
xargs -P 8 -L 1 bash -c 'be=$0; cell=$1; k=$2; i=$3; out=$X/logs/$be-$cell-$k-$i.log
  case $k in keep) TGT=$PLUG/test_keepalive185.py ;; *) TGT=tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence ;; esac
  case $cell in off) ;; conv) export SLICE_CONVERT=rust ;; nat) export SLICE_WITNESS=1 SLICE_CONVERT=rust SLICE_WITNESS_RUST=1 ;; esac
  cd $T
  SLICE_SUITE_BACKEND=$be PYTHONPATH=$T:$W/sympy:$W/shim:$S:$PLUG $PY -m pytest -p rust_plugin -q -s --tb=line -p no:cacheprovider --rootdir=$T $TGT > $out 2>&1
  echo "EXIT $?" >> $out
  SLICE_SUITE_BACKEND=$be PYTHONPATH=$T:$W/sympy:$W/shim:$S $PY -c "import os, satassume, sa_solver, convert; convert.from_env(); print(\"TREE\", satassume.__file__, sa_solver.__file__, \"SLICE_CONVERT\", os.environ.get(\"SLICE_CONVERT\"), \"RUST WALKER\", convert.WALK[0] is not None, \"BACKEND\", os.environ[\"SLICE_SUITE_BACKEND\"])" >> $out 2>&1' < $X/todo.txt
for c in $CELLS; do for k in orig keep; do p=${c%%:*}-${c#*:}-$k
  echo "$c $k passed $(grep -l "^EXIT 0" $X/logs/$p-*.log 2>/dev/null | wc -l) of $(ls $X/logs/$p-*.log | wc -l); asserts: $(grep -h "^E .*assert" $X/logs/$p-*.log | sort | uniq -c | tr '\n' ';') at: $(grep -ho "test_public_incremental.py:[0-9]*: Assert" $X/logs/$p-*.log | sort | uniq -c | tr '\n' ';') last: $(grep -ho "[0-9]* \(passed\|failed\)" $X/logs/$p-*.log | sort | uniq -c | tr '\n' ';')"
done; done > $X/rep-sum.txt
grep -h "^TREE" $X/logs/*.log | sort | uniq -c > $X/trees.txt
echo "END $(date -u +%FT%TZ)" > $X/rep-end.txt
