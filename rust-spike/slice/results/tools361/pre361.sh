#!/bin/bash
# pre361.sh NEW BASE (sa-port-361, pareto0, under ONE shared lease): the planner's two checks before the bar.
#  cond3  tests/test_noncommutative.py::test_scalar_valued_matrix_functions_stay_in_scope (the id at :546, the suite's
#         Q.commutative(Trace(M*N))) alone under p1/bar.sh suite()'s exact invocation (-p rust_plugin -p handler_count
#         -p plant_count -p hyp_profile --hypothesis-profile=bar -n 6), SLICE_CONVERT=py and =rust, on NEW and on BASE,
#         each under `timeout 300`: does a cell hang on NEW where BASE returns (OWED [157])?  -> OUT/cond3.txt, one line
#         per cell (rc 124 = timed out), and the same four cells with -n 0 (the main process, another call depth) as
#         information -> OUT/cond3-n0.txt
#  cond4  p1/convert_diff.sh of NEW as it stands (no -p handler_count in its suite pass): the differential on every
#         input of the 20 workloads and the suite, then the answers  -> OUT/convdiff/total.txt
# End marker: OUT/end.txt, the last line here.
export HOME=/home/tilo/sp19
R=/home/tilo/sp19/sa-rust-ids-work; G=$R/sa-port-361/s1; NEW=$1; BASE=$2; OUT=$R/sa-port-361/pre-$NEW
ID=tests/test_noncommutative.py::test_scalar_valued_matrix_functions_stay_in_scope
rm -rf $OUT; mkdir -p $OUT
. ~/sa-rust-ids-work/env.sh; export PY W SA_EVAL_DATA PYTHONHASHSEED
for v in $(env | grep -o '^SLICE_[A-Z_0-9]*'); do unset $v; done
for n in 6 0; do
  for sha in $NEW $BASE; do for cv in py rust; do
    T=$G/bench-$sha/tree; S=$T/rust-spike/slice; O=$OUT/c3-n$n-$sha-$cv; mkdir -p $O
    ( export SLICE_CONVERT=$cv SLICE_SUITE_OUT=$O SLICE_SUITE_BACKEND=rust PYTHONPATH=$T:$W/sympy:$W/shim:$S HYPOTHESIS_STORAGE_DIRECTORY=$O/hyp
      cd $T; $PY -c 'import satassume, sa_solver; print(satassume.__file__, sa_solver.__file__)' > $O/tree.txt; sha256sum $S/sa_solver.so >> $O/tree.txt
      t0=$(date +%s.%N)
      timeout 300 $PY -m pytest -p rust_plugin -p handler_count -p plant_count -p hyp_profile --hypothesis-profile=bar -n $n -q --tb=short -p no:cacheprovider "$ID" > $O/pytest.log 2>&1; rc=$?
      echo "$sha SLICE_CONVERT=$cv -n $n: rc $rc | $(tail -n 1 $O/pytest.log) | wall $(echo "$(date +%s.%N) - $t0" | bc | cut -c1-6) s | handler rows $(cat $O/handlers.*.jsonl 2>/dev/null | wc -l) | rows $(cat $O/rows.*.jsonl 2>/dev/null | wc -l)" )
  done; done > $OUT/cond3$([ $n = 0 ] && echo -n0).txt
done
T=$G/bench-$NEW/tree; S=$T/rust-spike/slice
export PYTHONPATH=$T:$W/sympy:$W/shim
{ cat $G/bench-$NEW/SHA; sha256sum $S/sa_solver.so; grep -c -- '-p handler_count' $S/p1/convert_diff.sh; } > $OUT/source.txt 2>&1
N=6 P=7 bash $S/p1/convert_diff.sh $OUT/convdiff > $OUT/convdiff.log 2>&1
echo "END $(date -u +%FT%TZ) load $(cut -d' ' -f1-3 /proc/loadavg) | cond3 rc0 $(grep -c ': rc 0 ' $OUT/cond3.txt)/4 | convdiff $(tail -n 2 $OUT/convdiff/total.txt | tr '\n' ' ')" > $OUT/end.txt
