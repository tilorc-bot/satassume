#!/bin/sh
# Inside bench-container: /work = pareto1:~/sa-rust-bench (src/base-9bafaa5 = git archive of 9bafaa5;
# tools-rust/, data/, evalbench/, sympy/ copied from ~/sa-lzr-bench). Round 0 is a warmup. Modes rotate one
# place each round, so each mode has a different neighbour; base and dbl are the uninstrumented references.
mkdir -p /tmp/shim && ln -sf /work/evalbench /tmp/shim/evalbench
export SA_EVAL_DATA=/work/data PYTHONHASHSEED=0 PYTHONPATH=/work/src/base-9bafaa5:/work/sympy:/tmp/shim
run() { python /work/tools-rust/rc.py $2 $3 | sed "s/^{/{\"round\": \"$1\", /"; }
O="base bdry mon samp fn enc dbl"
for R in 0 1 2 3 4 5 6; do
  for wl in dev fuzz; do for m in $O; do run $R $m $wl; done; done
  O="${O#* } ${O%% *}"
done
# counts and the split of SymPy entries by fn group: deterministic, one run each
for wl in dev fuzz; do for m in dblc monfn moncall; do run once $m $wl; done; done
