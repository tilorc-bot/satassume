#!/bin/sh
# inside the container: /work = ~/sa-lzr-bench
mkdir -p /tmp/shim && ln -sf /work/evalbench /tmp/shim/evalbench
export SA_EVAL_DATA=/work/data PYTHONPATH=/work/src/sa-lzr:/work/sympy:/tmp/shim PYTHONHASHSEED=0
for r in 0 1 2 3 4 5; do for wl in dev fuzz; do for m in base nolink nolink+noxfer; do python /work/ceilw.py $m $wl; done; done; done
