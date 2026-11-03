#!/bin/sh
# inside bench-container: /work = pareto1:~/sa-lzr-bench. Round 0 is warmup.
mkdir -p /tmp/shim && ln -sf /work/evalbench /tmp/shim/evalbench
export SA_EVAL_DATA=/work/data PYTHONHASHSEED=0
run() { SA_LAZY=$3 PYTHONPATH=/work/src/$2:/work/sympy:/tmp/shim python /work/protime.py $1 $4 | sed "s/^{/{\"round\": $R, /"; }
for R in 0 1 2 3 4 5 6; do
  case $((R % 3)) in
    0) O="lzr1 lzr0 base";; 1) O="lzr0 base lzr1";; 2) O="base lzr1 lzr0";;
  esac
  for wl in dev fuzz; do for v in $O; do
    case $v in lzr1) run lzr1 lzr-5af2f7c 1 $wl;; lzr0) run lzr0 lzr-5af2f7c 0 $wl;; base) run base base-9bafaa5 1 $wl;; esac
  done; done
done
