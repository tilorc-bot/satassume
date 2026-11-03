#!/bin/sh
# Inside bench-container: /work = pareto1:~/sa-rust-bench, /work/spike/cross = this directory and the built modules.
# A cold process per run, round 0 a warmup, runs rotate one place each round.
mkdir -p /tmp/shim && ln -sf /work/evalbench /tmp/shim/evalbench
D=/work/spike/cross
export SA_EVAL_DATA=/work/data PYTHONHASHSEED=0 XB_STRIDE_fuzz=17 XB_STRIDE_dev=1
SRC=/work/src/base-9bafaa5:/work/sympy:/tmp/shim
one() {
  case $2 in
    base)  PYTHONPATH=$SRC python /work/tools-rust/rc.py base $3 ;;
    micro) PYTHONPATH=$D/full python $D/crossing.py micro ;;
    microabi3) PYTHONPATH=$D/abi3 python $D/crossing.py micro ;;
    real)  PYTHONPATH=$SRC:$D/full python $D/crossing.py real $3 ;;
    realabi3) PYTHONPATH=$SRC:$D/abi3 python $D/crossing.py real $3 ;;
    samp)  PYTHONPATH=$SRC:$D/full python $D/crossing.py samp $3 ;;
  esac | sed "s/^{/{\"round\": \"$1\", \"run\": \"$2\", \"wlx\": \"$3\", /"
}
O="${MODES:-micro base real samp microabi3 realabi3}"
for R in ${ROUNDS:-0 1 2 3 4 5 6}; do
  for wl in dev fuzz; do for m in $O; do
    # the micro runs have no workload: run them once per round
    case $m in micro*) [ $wl = fuzz ] && continue ;; esac
    one $R $m $wl
  done; done
  O="${O#* } ${O%% *}"
done
