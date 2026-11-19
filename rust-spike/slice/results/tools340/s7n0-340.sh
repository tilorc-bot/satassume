#!/bin/bash
# s7n0-340.sh TREE OUT (sa-port-340, pareto0): the [138b] diagnostic. The suite as bar.sh's suite() runs a convert:* row
# (rust backend, SLICE_CONVERT=rust, the bar's plugins and hypothesis profile), but under -n 0: one process, pytest's own
# fixed order, so no xdist worker order. Two runs side by side: `plant` (SLICE_CONVERT_PLANT=enc-int-no-sign) and
# `noplant`. The row read is tests/test_s7_trig.py::test_numbers_sound[cos]. End marker: OUT/end.txt.
H=${1:?tree}; O=${2:?out}; export HOME=/home/tilo/sp19
mkdir -p $O; rm -f $O/end.txt
. $HOME/sa-rust-ids-work/env.sh; export PY W SA_EVAL_DATA PYTHONHASHSEED
S=$H/rust-spike/slice
row() { d=$O/$1; rm -rf $d; mkdir -p $d
  ( [ $1 = plant ] && export SLICE_CONVERT_PLANT=enc-int-no-sign
    export SLICE_CONVERT=rust SLICE_SUITE_OUT=$d SLICE_SUITE_BACKEND=rust PYTHONPATH=$H:$W/sympy:$W/shim:$S HYPOTHESIS_STORAGE_DIRECTORY=$d/hyp
    cd $H; $PY -c 'import satassume, sa_solver; print(satassume.__file__, sa_solver.__file__)' > $d/tree.txt
    s=$SECONDS
    $PY -m pytest -p rust_plugin -p handler_count -p plant_count -p hyp_profile --hypothesis-profile=bar -n 0 -rA -q --tb=line -p no:cacheprovider tests > $d/pytest.log 2>&1
    echo "exit $? wall $((SECONDS-s)) $(tail -n 1 $d/pytest.log)" > $d/exit.txt ); }
row plant & row noplant & wait
for r in plant noplant; do echo "$r: $(cat $O/$r/exit.txt)"; grep -E '^(PASSED|FAILED|ERROR) tests/test_s7_trig.py::test_numbers_sound\[cos\]' $O/$r/pytest.log; done > $O/s7.txt
echo "END $(date -u +%FT%TZ)" > $O/end.txt
