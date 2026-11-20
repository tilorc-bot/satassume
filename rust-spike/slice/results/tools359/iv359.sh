#!/bin/bash
# iv359.sh (sa-port-359, pareto0 under HOME=~/sp19, inside job359.sh; tools352/iv352.sh with the walker as the compared
# pair): NO plant, on the staged tree of NEW, each run once with SLICE_CONVERT=py (Python's walker) and once with
# SLICE_CONVERT=rust, both with SLICE_WITNESS=1. As iv352.sh: frames rust and py, one pytest process per run (-n 0),
# bar.sh suite()'s plugins and hypothesis profile plus frames_seen, walk_seen, wn_seen and cv_seen; fwd = ref, scope,
# zero_glue; rev = the reverse; fwd5/rev5 add test_transfer and test_relevance; cache on and off; backends rust and
# python; 2 runs each = 64 runs per walker, 128 in all. Rows under OUT/iv/NAME-SW.
# End: OUT/iv/end.txt (the last line of this script).
T=$G/bench-$NEW/tree; S=$T/rust-spike/slice; R=$OUT/iv
. ~/sa-rust-ids-work/env.sh; export PY W SA_EVAL_DATA PYTHONHASHSEED T S R G NEW OUT
if [ "$1" = one ]; then # one NAME BACKEND CACHE FRAMES SWITCH FILES...
  shift; O=$R/$1-$5; be=$2; cache=$3; fr=$4; sw=$5; shift 5
  rm -rf $O; mkdir -p $O; cd $T
  for v in $(env | grep -o '^SLICE_[A-Z_0-9]*'); do unset $v; done
  [ $cache = off ] && export SYMPY_USE_CACHE=no
  [ $fr = rust ] && export SLICE_TERM_FRAMES=rust
  export SLICE_CONVERT=$sw SLICE_WITNESS=1
  export SLICE_SUITE_OUT=$O SLICE_SUITE_BACKEND=$be PYTHONPATH=$T:$W/sympy:$W/shim:$S:$G/plug HYPOTHESIS_STORAGE_DIRECTORY=$O/hyp
  $PY -c 'import satassume, sympy, sa_solver; print(satassume.__file__, sympy.__file__, sa_solver.__file__)' > $O/tree.txt
  $PY -m pytest -p rust_plugin -p handler_count -p plant_count -p hyp_profile -p frames_seen -p walk_seen -p wn_seen -p cv_seen --hypothesis-profile=bar -n 0 -q --tb=short -rf -p no:cacheprovider "$@" > $O/pytest.log 2>&1
  echo "$? $(tail -n 1 $O/pytest.log)" > $O/exit.txt
  exit 0
fi
mkdir -p $R; cat $G/bench-$NEW/SHA > $R/source.txt; sha256sum $S/sa_solver.so >> $R/source.txt
F="tests/test_ref.py tests/test_scope.py tests/test_zero_glue.py"; B="tests/test_zero_glue.py tests/test_scope.py tests/test_ref.py"
F5="tests/test_transfer.py tests/test_relevance.py $F"; B5="$B tests/test_relevance.py tests/test_transfer.py"
for sw in py rust; do for fr in rust py; do for be in rust python; do for cache in on off; do for i in 1 2; do
  echo "fwd-$be-$cache-$fr-$i $be $cache $fr $sw $F"; echo "rev-$be-$cache-$fr-$i $be $cache $fr $sw $B"
  echo "fwd5-$be-$cache-$fr-$i $be $cache $fr $sw $F5"; echo "rev5-$be-$cache-$fr-$i $be $cache $fr $sw $B5"
done; done; done; done; done > $R/todo.txt
xargs -P ${N:-16} -L 1 bash $G/tools/iv359.sh one < $R/todo.txt
echo "END $(date -u +%FT%TZ)" > $R/end.txt
