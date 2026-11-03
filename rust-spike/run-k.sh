#!/bin/sh
# Inside bench-container: /work = pareto1:~/sa-rust-bench, /work/spike = the traces, tools and binaries.
# Cold process per run, round 0 a warmup, modes rotate one place each round.
mkdir -p /tmp/shim && ln -sf /work/evalbench /tmp/shim/evalbench
export SA_EVAL_DATA=/work/data PYTHONHASHSEED=0 PYTHONPATH=/work/src/base-9bafaa5:/work/sympy:/tmp/shim
D=/work/spike
T=$D/traces
one() {
  case $2 in
    base)    python /work/tools-rust/rc.py base $3 ;;
    timers)  python $D/record.py $3 /tmp/unused --timers ;;
    py)      python $D/replay_py.py $3 $T timed ;;
    pynogc)  python $D/replay_py.py $3 $T nogc ;;
    pyempty) python $D/replay_py.py $3 $T empty ;;
    pytape)  python $D/replay_py.py $3 $T tape ;;
    rs|rsfx|rslto) $D/$2 $3 $T timed | sed "s/\"rs\"/\"$2\"/" ;;
    pybyop)  python $D/replay_py.py $3 $T byop ;;
    rsbyop)  $D/rsprof $3 $T byop ;;
    rsempty) $D/rs $3 $T empty ;;
    rstape)  $D/rs $3 $T tape ;;
  esac | sed "s/^{/{\"round\": \"$1\", \"run\": \"$2\", /"
}
O="${MODES:-base py rs rsfx rslto pynogc timers pyempty pytape rsempty rstape}"
for R in ${ROUNDS:-0 1 2 3 4 5 6}; do
  for wl in dev fuzz; do for m in $O; do one $R $m $wl; done; done
  O="${O#* } ${O%% *}"
done
