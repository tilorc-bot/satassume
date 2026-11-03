#!/bin/sh
# Inside docker: /work = ~/sa-rust-bench, /work/lra = this directory (from rsync). $1 = dev|fuzz, $2.. = extra flags.
mkdir -p /tmp/shim && ln -sf /work/evalbench /tmp/shim/evalbench
export SA_EVAL_DATA=/work/data PYTHONHASHSEED=0 PYTHONPATH=/work/src/base-9bafaa5:/work/sympy:/tmp/shim
python /work/lra/record_lra.py "$1" "${OUT:-/work/lra/traces}" $2
