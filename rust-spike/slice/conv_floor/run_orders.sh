#!/bin/sh
# Fill the row cache in six query orders, in check mode. Usage: run_orders.sh OUTDIR [ARM_LAZY]
. ~/sa-rust-ids-work/env.sh
C=$(cd "$(dirname "$0")/../../.." && pwd)
export PYTHONPATH=$C:$W/sympy:$W/shim SLICE_DIR=$C/rust-spike/slice SLICE_CONV_CACHE=check
R=$1; mkdir -p "$R"; cd "$SLICE_DIR"
for o in dev dev-rev fuzz fuzz-rev fuzz-dev dev-fuzz; do echo $o; done | xargs -P 2 -I{} sh -c "timeout 900 $PY conv_floor/row_orders.py {} $R/{}.json > $R/{}.log 2>&1; echo {} rc=\$? >> $R/rc"
echo DONE >> $R/rc
