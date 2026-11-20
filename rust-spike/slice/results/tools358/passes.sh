#!/bin/bash
# passes.sh: item 3's three passes of the six kept files under run_suite.sh (the suite plugin and handler_count), -n 4:
#   k-py    head, SLICE_CONVERT=py      k-rust  head, SLICE_CONVERT=rust      k-base  de88d9b9, SLICE_CONVERT=rust
# test_a_deep_formula_is_pythons[700-too-deep] skips itself in these passes (sa-port-359, the planner's ruling): its
# skipif reads sys.monitoring for an EXCEPTION_HANDLED tool, which handler_count is (OWED [157], tools358/repro.py).
# The per-job deselect and the `timeout` run of that id (358) are gone; the id runs in plain pytest (the bar's tests phase).
# Each pass writes exit.txt last; the job's end marker is the last line of this script: $O/passes-end.txt.
O=${O:-~/sa-rust-ids-work/sa-port-358}
HEAD=~/sa-rust-ids-work/sa-port-356/wt
BASE=~/sa-rust-ids-work/sa-port-357/base
F=""; for f in test_lazy_reads test_convert_once test_term_live test_term_ids test_knowledge_lazy test_convert_walk; do F="$F rust-spike/slice/$f.py"; done
rm -f $O/passes-end.txt
pass() {  # NAME TREE MODE
  rm -rf $O/k-$1
  sha256sum $2/rust-spike/slice/sa_solver.so > $O/k-$1.so.txt; git -C $2 rev-parse HEAD >> $O/k-$1.so.txt
  SLICE_CONVERT=$3 SLICE_TERM_FRAMES=rust PYTEST_N="-n 4" sh $2/rust-spike/slice/run_suite.sh $O/k-$1 rust $F -W ignore > /dev/null 2>&1
}
pass py $HEAD py
pass rust $HEAD rust
pass base $BASE rust
echo "END $(date -u +%FT%TZ)" > $O/passes-end.txt
