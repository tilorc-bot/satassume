#!/bin/sh
# interleaved plain/lazy cold processes, ROUNDS rounds per workload
cd /work
export PYTHONPATH=/work/src/sa-lzo:/work/sympy:/work SA_EVAL_DATA=/work/data PYTHONHASHSEED=0
for w in dev fuzz:424242; do
  for r in 1 2 3 4 5 6; do
    if [ $((r % 2)) = 1 ]; then o="plain lazy"; else o="lazy plain"; fi
    for m in $o; do python -P /work/lazy_sim.py $w $m >> /results/times.jsonl; done
  done
done
