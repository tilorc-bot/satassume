#!/bin/bash
# nohandler360.sh (sa-port-360, pareto0, under ONE shared lease, detached): the differential's suite pass exactly as
# p1/convert_diff.sh:19-21 runs it on the staged tree of 00535462 (sa-port-359/s1/bench-00535462/tree, venv .so), but
# WITHOUT -p handler_count (no sys.monitoring EXCEPTION_HANDLED tool): does the one difference of 359's job
# (Q.commutative(Trace(M*N)): OWED [157]'s hang at one walker's call depth and not the other's) go, with nothing else
# appearing? Then depth360.py on this x86-64 build. End marker: OUT/end.txt, the last line here.
export HOME=/home/tilo/sp19
R=/home/tilo/sp19/sa-rust-ids-work; G=$R/sa-port-359/s1; NEW=00535462; T=$G/bench-$NEW/tree; S=$T/rust-spike/slice; O=$R/sa-port-360/nohandler
mkdir -p $O/suite-rows
. ~/sa-rust-ids-work/env.sh; export PY W SA_EVAL_DATA PYTHONHASHSEED; export PYTHONPATH=$T:$W/sympy:$W/shim SLICE_DIR=$S
for v in $(env | grep -o '^SLICE_[A-Z_0-9]*' | grep -v '^SLICE_DIR$'); do unset $v; done
{ cat $G/bench-$NEW/SHA; sha256sum $S/sa_solver.so; cd $S && $PY -c 'import satassume, convert, sa_solver; print(satassume.__file__, convert.__file__, sa_solver.__file__)'; } > $O/source.txt 2>&1
( export SLICE_CONVERT=py SLICE_CONVERT_DIFF=$O/suite SLICE_SUITE_OUT=$O/suite-rows SLICE_SUITE_BACKEND=rust PYTHONPATH=$PYTHONPATH:$S HYPOTHESIS_STORAGE_DIRECTORY=$O/hyp
  cd $T && $PY -m pytest -p rust_plugin -p plant_count -n 6 -q --tb=short -p no:cacheprovider tests > $O/suite-pytest.log 2>&1; echo "$? $(tail -n 1 $O/suite-pytest.log)" > $O/suite-exit.txt )
( cd $S && $PY convert_diff.py $O/suite > $O/total.txt 2>&1; echo "exit $?" >> $O/total.txt )
( cd $S && $PY $R/sa-port-360/tools/depth360.py 5 8 > $O/depth360-x86.txt 2>&1 )
echo "END $(date -u +%FT%TZ) load $(cut -d' ' -f1-3 /proc/loadavg)" > $O/end.txt
