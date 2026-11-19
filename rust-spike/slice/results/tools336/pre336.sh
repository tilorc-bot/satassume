#!/bin/bash
# pre336.sh TREE OUT PLUG (sa-port-336, pareto0 under HOME=~/sp19, inside job336.sh; tools328/pre330.sh with the plugin
# directory as an argument, plant 754 skip-users added and 8 at a time): on a frozen copy of the tested SHA:
#  dig/   dev and fuzz answer digests (wit328.py), py and rust, switch off and on; and py with each plant, switch on
#  tw/    tests/test_witness.py, python and rust backend, switch off and on; and, per plant (python, switch on),
#         test_witness.py plus the tests that patch Engine.ask (test_history's two, test_public_incremental.py)
#  rep/   the planted-history test and sa-port-185's keep-alive variant, a28c548's method (tools318/run1.sh): one fresh
#         process a run, 20 runs a cell, backend rust and python, switch off and on
# End marker: OUT/pre-end.txt, the last line here.
T=$1; S=$T/rust-spike/slice; X=$2; TOOLS=$T/rust-spike/slice/results/tools328
. ~/sa-rust-ids-work/env.sh; export PY W SA_EVAL_DATA PYTHONHASHSEED T S X TOOLS
unset SLICE_WITNESS SLICE_WITNESS_CAP SLICE_WITNESS_PLANT SLICE_CONVERT SLICE_TERM_FRAMES SLICE_SUITE_OUT
mkdir -p $X/dig $X/tw $X/rep $X/plug; cp $3/test_keepalive185.py $X/plug/
{ cat $T/../SHA; sha256sum $S/sa_solver.so $T/satassume/witness.py; } > $X/pre-source.txt
cd $S
for wl in dev fuzz; do for m in py rust; do for sw in 0 1; do echo "$wl $m $sw -"; done; done
  for pl in integer-half single skip-own skip-patched skip-users; do echo "$wl py 1 $pl"; done; done > $X/dig/todo.txt
xargs -P 8 -L 1 bash -c 'wl=$0; m=$1; sw=$2; pl=$3
  [ $m = rust ] && export SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust
  [ $pl != - ] && export SLICE_WITNESS_PLANT=$pl
  SLICE_WITNESS=$sw SLICE_DIR=$S PYTHONPATH=$T:$W/sympy:$W/shim $PY $TOOLS/wit328.py $wl $m 2>> $X/dig/err.txt | $PY -c "
import json,sys
d=json.loads(sys.stdin.read()); print(json.dumps(dict(wl=d[\"wl\"], mode=d[\"mode\"], sw=$sw, plant=\"$pl\", digest=d[\"digest\"], n=d[\"n\"], fires=d[\"fires\"], certified=d[\"certified\"], so=d[\"so\"])))" >> $X/dig/dig.jsonl' < $X/dig/todo.txt
echo "DIG $(date -u +%T)" > $X/progress.txt
cd $T
pt() { # pt LOG BACKEND SWITCH PLANT TARGETS...
  local log=$1 be=$2 sw=$3 pl=$4; shift 4; mkdir -p $X/tw/out-$log
  ( [ $pl != - ] && export SLICE_WITNESS_PLANT=$pl
    SLICE_WITNESS=$sw SLICE_SUITE_OUT=$X/tw/out-$log SLICE_SUITE_BACKEND=$be PYTHONPATH=$T:$W/sympy:$W/shim:$S $PY -m pytest -p rust_plugin -p handler_count -p hyp_profile --hypothesis-profile=bar -n 0 -q -rf --tb=line -p no:cacheprovider "$@" > $X/tw/$log.log 2>&1 )
}
for be in python rust; do for sw in 0 1; do pt tw-$be-$sw $be $sw - tests/test_witness.py; done; done
PATCH="tests/test_history.py::test_ddmin_shrinks_to_the_responsible_query tests/test_history.py::test_checker_catches_a_planted_history_dependence tests/test_public_incremental.py"
pt patch-python-0 python 0 - $PATCH; pt patch-python-1 python 1 - $PATCH
for pl in integer-half single skip-own skip-patched skip-users; do pt plant-$pl python 1 $pl tests/test_witness.py $PATCH; done
echo "TW $(date -u +%T)" >> $X/progress.txt
for be in rust python; do for k in orig keep; do for sw in 0 1; do for i in $(seq 20); do echo "$be $k $sw $i"; done; done; done; done > $X/rep/todo.txt
xargs -P 8 -L 1 bash -c 'be=$0; k=$1; sw=$2; i=$3; out=$X/rep/$be-$k-$sw-$i.log
  case $k in keep) TGT=$X/plug/test_keepalive185.py ;; *) TGT=tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence ;; esac
  SLICE_WITNESS=$sw SLICE_SUITE_BACKEND=$be PYTHONPATH=$T:$W/sympy:$W/shim:$S:$X/plug $PY -m pytest -p rust_plugin -q -s --tb=line -p no:cacheprovider --rootdir=$T $TGT > $out 2>&1
  echo "EXIT $?" >> $out
  SLICE_WITNESS=$sw SLICE_SUITE_BACKEND=$be PYTHONPATH=$T:$W/sympy:$W/shim:$S $PY -c "import satassume, sa_solver; from satassume import witness; print(\"TREE\", satassume.__file__, sa_solver.__file__, \"WITNESS\", witness.ENABLED[0])" >> $out 2>&1' < $X/rep/todo.txt
for be in rust python; do for k in orig keep; do for sw in 0 1; do
  echo "$be $k sw=$sw passed $(grep -l "^EXIT 0" $X/rep/$be-$k-$sw-*.log 2>/dev/null | wc -l) of $(ls $X/rep/$be-$k-$sw-*.log | wc -l); asserts: $(grep -h "assert" $X/rep/$be-$k-$sw-*.log | sed 's/.*py:\([0-9]*\): /\1 /' | sort | uniq -c | tr '\n' ';')"
done; done; done > $X/rep/rep-sum.txt
grep -h "^TREE" $X/rep/*.log | sort | uniq -c > $X/rep/trees.txt
echo "END $(date -u +%FT%TZ)" > $X/pre-end.txt
