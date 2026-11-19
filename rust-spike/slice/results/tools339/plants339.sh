#!/bin/bash
# plants339.sh TREE OUT "BACKENDS" [KEEPALIVE_PLUG_DIR] (sa-port-339, issue 323; the planner's addition (1) to the
# land-only step; pre336.sh's pt() and rep, on a frozen tree of 81e6561e; reads TREE, writes only under OUT):
#  tw/   tests/test_witness.py alone, one process, SLICE_WITNESS=1: no plant (and switch 0), then under each of
#        SLICE_WITNESS_PLANT=integer-half single skip-own skip-patched skip-users (plants 749 750 751 752 754);
#        and, separately, the tests that patch Engine.ask (pre336.sh's PATCH) under the same rows
#  rep/  only with KEEPALIVE_PLUG_DIR: the planted-history test and sa-port-185's keep-alive variant, a28c548's
#        method, one fresh process a run, 20 runs a cell, each backend, switch off and on
# End marker: OUT/end.txt, the last line here. On a pareto, run under HOME=~/sp19.
T=$(cd "$1" && pwd); mkdir -p "$2"; X=$(cd "$2" && pwd); BES=$3; KP=$4; S=$T/rust-spike/slice
. ~/sa-rust-ids-work/env.sh; export PY W T S X KP
unset SLICE_WITNESS SLICE_WITNESS_CAP SLICE_WITNESS_PLANT SLICE_CONVERT SLICE_TERM_FRAMES SLICE_SUITE_OUT
mkdir -p $X/tw $X/rep
{ echo "start $(date -u +%FT%TZ) host $(hostname) tree $T"; cat $T/../SHA 2>/dev/null; sha256sum $S/sa_solver.so $T/satassume/witness.py $T/tests/test_witness.py 2>&1; } > $X/source.txt
cd $T
pt() { # pt LOG BACKEND SWITCH PLANT TARGETS...
  local log=$1 be=$2 sw=$3 pl=$4; shift 4; mkdir -p $X/tw/out-$log
  ( [ $pl != - ] && export SLICE_WITNESS_PLANT=$pl
    export SLICE_WITNESS=$sw SLICE_SUITE_OUT=$X/tw/out-$log SLICE_SUITE_BACKEND=$be PYTHONPATH=$T:$W/sympy:$W/shim:$S
    $PY -c "import satassume, os; from satassume import witness; print('TREE', satassume.__file__, 'WITNESS', witness.ENABLED[0], 'PLANT', os.environ.get('SLICE_WITNESS_PLANT'))" > $X/tw/$log.tree 2>&1
    $PY -m pytest -p rust_plugin -p handler_count -p hyp_profile --hypothesis-profile=bar -n 0 -q -rf --tb=line -p no:cacheprovider "$@" > $X/tw/$log.log 2>&1
    echo "EXIT $?" >> $X/tw/$log.log )
}
PATCH="tests/test_history.py::test_ddmin_shrinks_to_the_responsible_query tests/test_history.py::test_checker_catches_a_planted_history_dependence tests/test_public_incremental.py"
for be in $BES; do
  pt tw-$be-sw0 $be 0 - tests/test_witness.py; pt tw-$be-sw1 $be 1 - tests/test_witness.py
  pt patch-$be-sw0 $be 0 - $PATCH; pt patch-$be-sw1 $be 1 - $PATCH
  for pl in integer-half single skip-own skip-patched skip-users; do
    pt plant-$pl-$be $be 1 $pl tests/test_witness.py; pt plantpatch-$pl-$be $be 1 $pl $PATCH
  done
done
for f in $X/tw/*.log; do n=$(basename $f .log)
  echo "$n | $(grep ^EXIT $f) | $(grep -E ' (passed|failed)' $f | tail -1) | $(cat $X/tw/$n.tree)"
  grep -h "^FAILED" $f | sed 's/ - .*//; s/^/    /'
done > $X/tw-sum.txt
if [ -n "$KP" ]; then
  for be in $BES; do for k in orig keep; do for sw in 0 1; do for i in $(seq 20); do echo "$be $k $sw $i"; done; done; done; done > $X/rep/todo.txt
  xargs -P 8 -L 1 bash -c 'be=$0; k=$1; sw=$2; i=$3; out=$X/rep/$be-$k-$sw-$i.log
    case $k in keep) TGT=$KP/test_keepalive185.py ;; *) TGT=tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence ;; esac
    SLICE_WITNESS=$sw SLICE_SUITE_BACKEND=$be PYTHONPATH=$T:$W/sympy:$W/shim:$S:$KP $PY -m pytest -p rust_plugin -q -s --tb=line -p no:cacheprovider --rootdir=$T $TGT > $out 2>&1
    echo "EXIT $?" >> $out
    SLICE_WITNESS=$sw SLICE_SUITE_BACKEND=$be PYTHONPATH=$T:$W/sympy:$W/shim:$S $PY -c "import satassume, sa_solver; from satassume import witness; print(\"TREE\", satassume.__file__, sa_solver.__file__, \"WITNESS\", witness.ENABLED[0])" >> $out 2>&1' < $X/rep/todo.txt
  for be in $BES; do for k in orig keep; do for sw in 0 1; do
    echo "$be $k sw=$sw passed $(grep -l "^EXIT 0" $X/rep/$be-$k-$sw-*.log 2>/dev/null | wc -l) of $(ls $X/rep/$be-$k-$sw-*.log | wc -l); asserts: $(grep -h "assert" $X/rep/$be-$k-$sw-*.log | sed 's/.*py:\([0-9]*\): /\1 /' | sort | uniq -c | tr '\n' ';')"
  done; done; done > $X/rep/rep-sum.txt
  grep -h "^TREE" $X/rep/*.log | sort | uniq -c > $X/rep/trees.txt
fi
echo "END $(date -u +%FT%TZ) load $(cut -d' ' -f1-3 /proc/loadavg)" > $X/end.txt
