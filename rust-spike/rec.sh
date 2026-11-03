#!/bin/sh
# inside docker: /work=~/sa-rust-bench, /spike=~/sa-rust-spike
mkdir -p /tmp/shim && ln -sf /work/evalbench /tmp/shim/evalbench
export SA_EVAL_DATA=/work/data PYTHONHASHSEED=0 PYTHONPATH=/work/src/base-9bafaa5:/work/sympy:/tmp/shim
REC_DEBUG=${REC_DEBUG:-} python /spike/tools/record.py $1 /spike/traces
