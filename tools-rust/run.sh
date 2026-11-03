#!/bin/sh
# NOT YET RUN. Inside bench-container: /work = pareto1:~/sa-rust-bench (src/base-9bafaa5 = git archive
# of 9bafaa5; tools-rust/, data/, evalbench/, sympy/ copied from ~/sa-lzr-bench). Round 0 is a warmup.
mkdir -p /tmp/shim && ln -sf /work/evalbench /tmp/shim/evalbench
export SA_EVAL_DATA=/work/data PYTHONHASHSEED=0 PYTHONPATH=/work/src/base-9bafaa5:/work/sympy:/tmp/shim
for R in 0 1 2 3 4 5 6; do
  case $((R % 3)) in
    0) O="base bdry mon samp fn enc";; 1) O="fn enc base bdry mon samp";; 2) O="mon samp fn enc base bdry";;
  esac
  for wl in dev fuzz; do for m in $O; do
    python /work/tools-rust/rc.py $m $wl | sed "s/^{/{\"round\": $R, /"
  done; done
done
