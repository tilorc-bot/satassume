#!/bin/bash
# passes.sh: item 3's three passes of the six kept files under run_suite.sh (the suite plugin and handler_count), -n 4:
#   k-py    head, SLICE_CONVERT=py      k-rust  head, SLICE_CONVERT=rust      k-base  de88d9b9, SLICE_CONVERT=rust
# DEEP, test_a_deep_formula_is_pythons[700-too-deep], is deselected from each pass and run by itself under `timeout`
# into k-X-deep: under handler_count (any sys.monitoring EXCEPTION_HANDLED callback) CPython 3.12.14 never returns from
# Python's `formula` at the recursion limit, on the head and on de88d9b9 alike (tools/repro.py, deep-first.txt).
# Each pass writes exit.txt last; the job's end marker is the last line of this script: $O/passes-end.txt.
O=~/sa-rust-ids-work/sa-port-358
HEAD=~/sa-rust-ids-work/sa-port-356/wt
BASE=~/sa-rust-ids-work/sa-port-357/base
DEEP='rust-spike/slice/test_convert_walk.py::test_a_deep_formula_is_pythons[700-too-deep]'
F=""; for f in test_lazy_reads test_convert_once test_term_live test_term_ids test_knowledge_lazy test_convert_walk; do F="$F rust-spike/slice/$f.py"; done
rm -f $O/passes-end.txt
pass() {  # NAME TREE MODE
  rm -rf $O/k-$1 $O/k-$1-deep
  sha256sum $2/rust-spike/slice/sa_solver.so > $O/k-$1.so.txt; git -C $2 rev-parse HEAD >> $O/k-$1.so.txt
  SLICE_CONVERT=$3 SLICE_TERM_FRAMES=rust PYTEST_N="-n 4" sh $2/rust-spike/slice/run_suite.sh $O/k-$1 rust $F -W ignore --deselect "$DEEP" > /dev/null 2>&1
  SLICE_CONVERT=$3 SLICE_TERM_FRAMES=rust PYTEST_N="" timeout 120 sh $2/rust-spike/slice/run_suite.sh $O/k-$1-deep rust "$DEEP" -W ignore > /dev/null 2>&1
  echo "$1 deep rc=$? (124: killed by the timeout)" > $O/k-$1-deep.rc
}
pass py $HEAD py
pass rust $HEAD rust
pass base $BASE rust
echo "END $(date -u +%FT%TZ)" > $O/passes-end.txt
