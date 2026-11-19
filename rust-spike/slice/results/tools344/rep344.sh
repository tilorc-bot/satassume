#!/bin/bash
# rep344.sh ROOT343 OUT NEW BASE (sa-port-344, pareto0, shared lease, HOME=~/sp19): the gate's patch row
# (tools342/pre342.sh:32-33: test_history's two tests that patch Engine.ask, then tests/test_public_incremental.py, one
# process, python backend) repeated on the staged frozen trees of NEW and BASE, switch off and on, 12 runs a cell:
#   plain  the row as pre342.sh runs it
#   keep   the same row with the planted-history test deselected and sa-port-185's keep-alive variant run after it
# a28c548's method on the row where 01e8ca74's gate showed the planted-history test failing on Python (assert 0 == 2).
# End marker: OUT/rep-end.txt, the last line here.
export HOME=/home/tilo/sp19
G=$1/s1; X=$2; NEW=$3; BASE=$4
. ~/sa-rust-ids-work/env.sh; export PY W SA_EVAL_DATA PYTHONHASHSEED G X
unset SLICE_WITNESS SLICE_WITNESS_CAP SLICE_WITNESS_PLANT SLICE_CONVERT SLICE_TERM_FRAMES SLICE_SUITE_OUT
mkdir -p $X/logs $X/out
for sha in $NEW $BASE; do for k in plain keep; do for sw in 0 1; do for i in $(seq 12); do echo "$sha $k $sw $i"; done; done; done; done > $X/todo.txt
xargs -P 8 -L 1 bash -c 'sha=$0; k=$1; sw=$2; i=$3; T=$G/bench-$sha/tree; S=$T/rust-spike/slice; log=$X/logs/$sha-$k-$sw-$i.log
  ID=tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence
  PATCH="tests/test_history.py::test_ddmin_shrinks_to_the_responsible_query tests/test_history.py::test_checker_catches_a_planted_history_dependence tests/test_public_incremental.py"
  case $k in keep) EXTRA="--deselect $ID $G/plug/test_keepalive185.py" ;; *) EXTRA= ;; esac
  mkdir -p $X/out/$sha-$k-$sw-$i; cd $T
  SLICE_WITNESS=$sw SLICE_SUITE_OUT=$X/out/$sha-$k-$sw-$i SLICE_SUITE_BACKEND=python PYTHONPATH=$T:$W/sympy:$W/shim:$S:$G/plug $PY -m pytest -p rust_plugin -p handler_count -p hyp_profile --hypothesis-profile=bar -n 0 -q -rf --tb=line -p no:cacheprovider --rootdir=$T $PATCH $EXTRA > $log 2>&1
  echo "EXIT $?" >> $log
  SLICE_WITNESS=$sw SLICE_SUITE_BACKEND=python PYTHONPATH=$T:$W/sympy:$W/shim:$S $PY -c "import satassume; from satassume import witness; print(\"TREE\", satassume.__file__, \"WITNESS\", witness.ENABLED[0])" >> $log 2>&1' < $X/todo.txt
for sha in $NEW $BASE; do for k in plain keep; do for sw in 0 1; do
  echo "$sha python $k sw=$sw exit 0 in $(grep -l "^EXIT 0" $X/logs/$sha-$k-$sw-*.log 2>/dev/null | wc -l) of $(ls $X/logs/$sha-$k-$sw-*.log | wc -l); failed ids: $(grep -h "^FAILED" $X/logs/$sha-$k-$sw-*.log | cut -d" " -f2 | sort | uniq -c | tr '\n' ';') asserts: $(grep -h "^E .*assert\|py:[0-9]*: Assert" $X/logs/$sha-$k-$sw-*.log | sed 's/.*py:\([0-9]*\): /\1 /' | sort | uniq -c | tr '\n' ';') last: $(tail -qn 3 $X/logs/$sha-$k-$sw-*.log | grep -h "passed\|failed" | sed 's/ in .*//' | sort | uniq -c | tr '\n' ';')"
done; done; done > $X/rep-sum.txt
grep -h "^TREE" $X/logs/*.log | sort | uniq -c > $X/trees.txt
echo "END $(date -u +%FT%TZ)" > $X/rep-end.txt
