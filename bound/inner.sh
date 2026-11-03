#!/bin/sh
# runs inside the bench container, /work = ~/sa-lzp-bench
export SA_EVAL_DATA=/work/data SA_EVAL_SYMPY=/work/sympy SA_EVAL_SHIM=/tmp/shim PYTHONHASHSEED=0
mkdir -p /tmp/shim && ln -sf /work/evalbench /tmp/shim/evalbench
export PYTHONPATH=/work/src/lzp:/work/sympy:/tmp/shim
cd /tmp
for i in 1 2 3; do
  python -m evalbench.replay dev | tail -1 > /results/plain-dev-$i.json
  LZP_TIMING=1 python -P /work/lzp_bound.py dev > /results/timing-dev-$i.json
done
python -m evalbench.replay dev > /dev/null 2>&1 || true
LZP_TIMING=1 python -P /work/lzp_bound.py fuzz 424242 > /results/timing-fuzz.json
