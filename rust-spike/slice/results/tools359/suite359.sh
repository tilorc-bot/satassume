#!/bin/bash
# suite359.sh (sa-port-359, pareto0 under HOME=~/sp19, inside job359.sh; tools352/suite352.sh with the walker's cells):
# the slice suite by id on the staged trees, backend rust, bar.sh suite()'s derandomized hypothesis profile plus
# wn_seen, cv_seen and walk_seen, 3 workers each, five at once:
#   rust = NEW with SLICE_WITNESS=1 SLICE_TERM_FRAMES=rust SLICE_CONVERT=rust (the port)
#   py   = NEW with the same and SLICE_CONVERT=py (Python's walker on the same path: rust's reference)
#   nat  = NEW with rust's and SLICE_WITNESS_RUST=1 (S1's configuration)
#   off  = NEW with none set (the default path);  base = BASE with rust's (de88d9b9's Rust walker)
# End marker: OUT/suites-end.txt, the last line here.
echo "start $(date -u +%FT%TZ) host $(hostname) new $NEW base $BASE lease $MACHINE_LEASE_ID load $(cut -d' ' -f1-3 /proc/loadavg)" > $OUT/start.txt
sha256sum $G/bench-$NEW/tree/rust-spike/slice/sa_solver.so $G/bench-$BASE/tree/rust-spike/slice/sa_solver.so >> $OUT/start.txt
suite() { # suite NAME SHA ENV...: run_suite.sh's lines, with the staging's plugin directory on the path
  local n=$1 s=$2; shift 2
  ( for v in $(env | grep -o '^SLICE_[A-Z_0-9]*'); do unset $v; done
    [ $# -gt 0 ] && export "$@"
    T=$G/bench-$s/tree; O=$OUT/suite-$n-rust; mkdir -p $O; . ~/sa-rust-ids-work/env.sh; cd $T
    export PYTHONPATH=$T:$W/sympy:$W/shim:$T/rust-spike/slice:$G/plug SLICE_SUITE_OUT=$O SLICE_SUITE_BACKEND=rust PYTHONHASHSEED HYPOTHESIS_STORAGE_DIRECTORY=$O/hyp
    $PY -c 'import satassume, sympy, sa_solver; print(satassume.__file__, sympy.__file__, sa_solver.__file__)' > $O/tree.txt
    $PY -m pytest -p rust_plugin -p handler_count -p hyp_profile --hypothesis-profile=bar -p wn_seen -p cv_seen -p walk_seen -n 3 -q --tb=short -rf -p no:cacheprovider tests > $O/pytest.log 2>&1
    echo "$? $(tail -n 1 $O/pytest.log)" > $O/exit.txt ) &
}
suite rust $NEW SLICE_WITNESS=1 SLICE_TERM_FRAMES=rust SLICE_CONVERT=rust
suite py $NEW SLICE_WITNESS=1 SLICE_TERM_FRAMES=rust SLICE_CONVERT=py
suite nat $NEW SLICE_WITNESS=1 SLICE_TERM_FRAMES=rust SLICE_CONVERT=rust SLICE_WITNESS_RUST=1
suite off $NEW
suite base $BASE SLICE_WITNESS=1 SLICE_TERM_FRAMES=rust SLICE_CONVERT=rust
wait
echo "SUITES $(date -u +%FT%TZ) load $(cut -d' ' -f1-3 /proc/loadavg)" > $OUT/suites-end.txt
