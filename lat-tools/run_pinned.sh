#!/bin/sh
# inside bench-container: interleaved base / c2-prototype passes, cold processes
export PYTHONPATH=/work/src/base:/work/sympy:/work SA_EVAL_DATA=/work/data PYTHONHASHSEED=0
cd /work/tools
for r in 1 2 3; do
  for w in dev stream battery fuzz:424242; do
    if [ $((r % 2)) = 1 ]; then ms="base latds"; else ms="latds base"; fi
    for m in $ms; do
      python cost_child.py $w $m | sed "s/^{/{\"round\": $r, /" >> /results/cost.jsonl
    done
  done
done
