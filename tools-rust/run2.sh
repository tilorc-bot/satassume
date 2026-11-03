#!/bin/sh
# Second pinned batch: the items outside the boundary (out), alternating with base; then moncall once.
mkdir -p /tmp/shim && ln -sf /work/evalbench /tmp/shim/evalbench
export SA_EVAL_DATA=/work/data PYTHONHASHSEED=0 PYTHONPATH=/work/src/base-9bafaa5:/work/sympy:/tmp/shim
run() { python /work/tools-rust/rc.py $2 $3 | sed "s/^{/{\"round\": \"$1\", /"; }
O="base out"
for R in 0 1 2 3 4 5 6; do
  for wl in dev fuzz; do for m in $O; do run $R $m $wl; done; done
  O="${O#* } ${O%% *}"
done
for wl in dev fuzz; do run once moncall $wl; done
