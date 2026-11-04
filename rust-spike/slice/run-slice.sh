#!/bin/sh
# Inside bench-container: /work = pareto1:~/sa-rust-bench. Cold process per run, round 0 a warmup; time and sample passes alternate.
mkdir -p /tmp/shim && ln -sf /work/evalbench /tmp/shim/evalbench
export SA_EVAL_DATA=/work/data PYTHONHASHSEED=0 PYTHONPATH=/work/src/base-9bafaa5:/work/sympy:/tmp/shim
for R in 0 1 2 3 4 5 6 7; do
  for wl in dev fuzz; do for m in time sample; do
    python /work/slice/qtime.py $wl $m | sed "s/^{/{\"round\": $R, /" >> /work/slice/out.jsonl
  done; done
done
