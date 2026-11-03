#!/bin/sh
# Inside bench-container: /work = pareto1:~/sa-rust-bench, /work/lra = this directory, traces and binaries.
# Cold process per run, round 0 a warmup, modes rotate one place each round.
mkdir -p /tmp/shim && ln -sf /work/evalbench /tmp/shim/evalbench
export SA_EVAL_DATA=/work/data PYTHONHASHSEED=0 PYTHONPATH=/work/src/base-9bafaa5:/work/sympy:/tmp/shim
D=/work/lra
T=$D/traces
one() {
  case $2 in
    base)    python /work/tools-rust/rc.py base $3 ;;
    timers)  python $D/record_lra.py $3 /tmp/unused --timers ;;
    py)      python $D/replay_lra.py $3 $T timed ;;
    pyempty) python $D/replay_lra.py $3 $T empty ;;
    rs|rsfx|rslto) $D/$2 $3 $T timed | sed "s/\"rs\"/\"$2\"/" ;;
    rsempty) $D/rs $3 $T empty ;;
  esac | sed "s/^{/{\"round\": \"$1\", \"run\": \"$2\", /"
}
O="${MODES:-base py rs rsfx rslto timers pyempty rsempty}"
for R in ${ROUNDS:-0 1 2 3 4 5 6}; do
  for wl in dev fuzz; do for m in $O; do one $R $m $wl; done; done
  O="${O#* } ${O%% *}"
done
