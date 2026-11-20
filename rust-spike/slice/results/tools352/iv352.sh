#!/bin/bash
# iv352.sh (sa-port-352, pareto0 under HOME=~/sp19, inside job352b.sh; tools336/iv336.sh with the native switch as the
# compared pair): NO plant, on the staged tree of SHA, each run once with SLICE_WITNESS=1 (wit: Python's witness.py)
# and once with SLICE_WITNESS=1 SLICE_WITNESS_RUST=1 (nat). As iv336.sh: SLICE_CONVERT=rust, frames rust and py, one
# pytest process per run (-n 0), bar.sh suite()'s plugins and hypothesis profile plus frames_seen, walk_seen and
# wn_seen; fwd = ref, scope, zero_glue; rev = the reverse; fwd5/rev5 add test_transfer and test_relevance; cache on and
# off; backends rust and python; 2 runs each = 64 runs per switch, 128 in all. Rows under OUT/iv/NAME-SW.
# End: OUT/iv/end.txt (the last line of this script).
T=$G/bench-$SHA/tree; S=$T/rust-spike/slice; R=$OUT/iv
. ~/sa-rust-ids-work/env.sh; export PY W SA_EVAL_DATA PYTHONHASHSEED T S R G
if [ "$1" = one ]; then # one NAME BACKEND CACHE FRAMES SWITCH FILES...
  shift; O=$R/$1-$5; be=$2; cache=$3; fr=$4; sw=$5; shift 5
  rm -rf $O; mkdir -p $O; cd $T
  unset SLICE_SESSION_PLANT SLICE_TERM_PLANT SLICE_CONVERT_PLANT SLICE_CONVERT SLICE_TERM_FRAMES SLICE_WITNESS SLICE_WITNESS_PLANT SLICE_WITNESS_CAP SLICE_WITNESS_WORK SLICE_WITNESS_RUST SLICE_WITNESS_RUST_PLANT
  [ $cache = off ] && export SYMPY_USE_CACHE=no
  [ $fr = rust ] && export SLICE_TERM_FRAMES=rust
  [ $sw = nat ] && export SLICE_WITNESS_RUST=1
  export SLICE_CONVERT=rust SLICE_WITNESS=1
  export SLICE_SUITE_OUT=$O SLICE_SUITE_BACKEND=$be PYTHONPATH=$T:$W/sympy:$W/shim:$S:$G/plug HYPOTHESIS_STORAGE_DIRECTORY=$O/hyp
  $PY -c 'import satassume, sympy, sa_solver; from satassume import witness; print(satassume.__file__, sympy.__file__, sa_solver.__file__, "witness", witness.ENABLED[0])' > $O/tree.txt
  $PY -m pytest -p rust_plugin -p handler_count -p plant_count -p hyp_profile -p frames_seen -p walk_seen -p wn_seen --hypothesis-profile=bar -n 0 -q --tb=short -rf -p no:cacheprovider "$@" > $O/pytest.log 2>&1
  echo "$? $(tail -n 1 $O/pytest.log)" > $O/exit.txt
  exit 0
fi
mkdir -p $R; cat $G/bench-$SHA/SHA > $R/source.txt; sha256sum $S/sa_solver.so >> $R/source.txt
F="tests/test_ref.py tests/test_scope.py tests/test_zero_glue.py"; B="tests/test_zero_glue.py tests/test_scope.py tests/test_ref.py"
F5="tests/test_transfer.py tests/test_relevance.py $F"; B5="$B tests/test_relevance.py tests/test_transfer.py"
for sw in wit nat; do for fr in rust py; do for be in rust python; do for cache in on off; do for i in 1 2; do
  echo "fwd-$be-$cache-$fr-$i $be $cache $fr $sw $F"; echo "rev-$be-$cache-$fr-$i $be $cache $fr $sw $B"
  echo "fwd5-$be-$cache-$fr-$i $be $cache $fr $sw $F5"; echo "rev5-$be-$cache-$fr-$i $be $cache $fr $sw $B5"
done; done; done; done; done > $R/todo.txt
xargs -P ${N:-16} -L 1 bash $G/tools/iv352.sh one < $R/todo.txt
echo "END $(date -u +%FT%TZ)" > $R/end.txt
