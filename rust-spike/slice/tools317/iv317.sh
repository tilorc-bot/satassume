#!/bin/bash
# iv317.sh (sa-port-317, orion): 314's iv314.sh (312's iv.sh, planner addition 5: the history check), NO plant, on the head of
# port/mark-note with the Rust frames ON only (the column this step changes). One pytest process per run (-n 0), bar.sh
# suite()'s plugins and hypothesis profile. fwd = ref, scope, zero_glue; rev = the reverse; fwd5/rev5 add test_transfer and
# test_relevance. Cache on and off; backends rust and python; 2 runs each = 32 runs. Rows under iv/NAME. End: iv/end.txt (last line).
T=/home/tilo/dev/sa-port-5; S=$T/rust-spike/slice; X=$HOME/sa-rust-ids-work/sa-port-317; R=$X/iv
. ~/sa-rust-ids-work/env.sh; export PY W SA_EVAL_DATA PYTHONHASHSEED
mkdir -p $R; cd $T; git rev-parse --short HEAD > $R/source.txt
one() { # one NAME BACKEND CACHE FRAMES FILES...
  local O=$R/$1 be=$2 cache=$3 fr=$4; shift 4
  rm -rf $O; mkdir -p $O
  ( unset SLICE_SESSION_PLANT SLICE_TERM_PLANT SLICE_CONVERT_PLANT SLICE_CONVERT SLICE_TERM_FRAMES
    [ $cache = off ] && export SYMPY_USE_CACHE=no
    [ $fr = rust ] && export SLICE_TERM_FRAMES=rust
    export SLICE_SUITE_OUT=$O SLICE_SUITE_BACKEND=$be PYTHONPATH=$T:$W/sympy:$W/shim:$S:$X/plug HYPOTHESIS_STORAGE_DIRECTORY=$O/hyp
    $PY -c 'import satassume, sympy, sa_solver; print(satassume.__file__, sympy.__file__, sa_solver.__file__)' > $O/tree.txt
    $PY -m pytest -p rust_plugin -p handler_count -p plant_count -p hyp_profile -p frames_seen --hypothesis-profile=bar -n 0 -q --tb=short -p no:cacheprovider "$@" > $O/pytest.log 2>&1
    echo "$? $(tail -n 1 $O/pytest.log)" > $O/exit.txt )
}
F="tests/test_ref.py tests/test_scope.py tests/test_zero_glue.py"; B="tests/test_zero_glue.py tests/test_scope.py tests/test_ref.py"
F5="tests/test_transfer.py tests/test_relevance.py $F"; B5="$B tests/test_relevance.py tests/test_transfer.py"
for fr in rust; do for be in rust python; do for cache in on off; do for i in 1 2; do
  one fwd-$be-$cache-$fr-$i $be $cache $fr $F; one rev-$be-$cache-$fr-$i $be $cache $fr $B
  one fwd5-$be-$cache-$fr-$i $be $cache $fr $F5; one rev5-$be-$cache-$fr-$i $be $cache $fr $B5
done; done; done; done
echo "END $(date -u +%FT%TZ)" > $R/end.txt
