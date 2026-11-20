#!/bin/bash
# suite352.sh ROOT NEW BASE (sa-port-352, pareto0, under a shared lease, detached; tools328/suite331.sh with the native
# switch's cells): the slice suite by id on the staged trees ROOT/s1/bench-SHA/tree, backend rust, bar.sh suite()'s
# derandomized hypothesis profile plus wn_seen, 3 workers each, four at once:
#   nat  = NEW with SLICE_WITNESS=1 SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust SLICE_WITNESS_RUST=1 (the native check)
#   wit  = NEW with the same and no SLICE_WITNESS_RUST (Python's witness.py on the same path: nat's reference)
#   off  = NEW with none of the four set (the default path);  base = BASE with none set
# Runs under HOME=~/sp19. End marker: ROOT/job-NEW/suites-end.txt, the last line here.
export HOME=/home/tilo/sp19
G=$1/s1; export OUT=$1/job-$2
mkdir -p $OUT; echo "start $(date -u +%FT%TZ) host $(hostname) new $2 base $3 lease $MACHINE_LEASE_ID load $(cut -d' ' -f1-3 /proc/loadavg)" > $OUT/start.txt
sha256sum $G/bench-$2/tree/rust-spike/slice/sa_solver.so $G/bench-$2/tree/satassume/witness.py $G/bench-$3/tree/rust-spike/slice/sa_solver.so >> $OUT/start.txt
suite() { # suite NAME SHA ENV...: run_suite.sh's lines, with the staging's plugin directory on the path
  local n=$1 s=$2; shift 2
  ( unset SLICE_WITNESS SLICE_WITNESS_CAP SLICE_WITNESS_PLANT SLICE_WITNESS_WORK SLICE_CONVERT SLICE_TERM_FRAMES SLICE_WITNESS_RUST SLICE_WITNESS_RUST_PLANT
    [ $# -gt 0 ] && export "$@"
    T=$G/bench-$s/tree; O=$OUT/suite-$n-rust; mkdir -p $O; . ~/sa-rust-ids-work/env.sh; cd $T
    export PYTHONPATH=$T:$W/sympy:$W/shim:$T/rust-spike/slice:$G/plug SLICE_SUITE_OUT=$O SLICE_SUITE_BACKEND=rust PYTHONHASHSEED HYPOTHESIS_STORAGE_DIRECTORY=$O/hyp
    $PY -c 'import satassume, sympy, sa_solver; print(satassume.__file__, sympy.__file__, sa_solver.__file__)' > $O/tree.txt
    $PY -m pytest -p rust_plugin -p handler_count -p hyp_profile --hypothesis-profile=bar -p wn_seen -n 3 -q --tb=short -rf -p no:cacheprovider tests > $O/pytest.log 2>&1
    echo "$? $(tail -1 $O/pytest.log)" > $O/exit.txt ) &
}
suite nat $2 SLICE_WITNESS=1 SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust SLICE_WITNESS_RUST=1
suite wit $2 SLICE_WITNESS=1 SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust
suite off $2
suite base $3
wait
echo "SUITES $(date -u +%FT%TZ) load $(cut -d' ' -f1-3 /proc/loadavg)" > $OUT/suites-end.txt
