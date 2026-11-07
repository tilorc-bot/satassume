#!/bin/sh
# Python's fresh.py state against the row cache in check mode, on dev and fuzz. Usage: run_cache_check.sh OUTDIR
. ~/sa-rust-ids-work/env.sh
C=$(cd "$(dirname "$0")/../../.." && pwd)
export PYTHONPATH=$C:$W/sympy:$W/shim SLICE_DIR=$C/rust-spike/slice
R=$1; mkdir -p "$R"; cd "$SLICE_DIR"
for wl in dev fuzz; do
  ( timeout 600 "$PY" fresh.py $wl py $R/$wl-py.txt --handlers $R/$wl-py.handlers > $R/$wl-py.log 2>&1; echo "$wl-py rc=$?" >> $R/rc ) &
  ( SLICE_CONV_CACHE=check timeout 900 "$PY" conv_floor/fresh_arm.py $wl $R/$wl-check > $R/$wl-check.log 2>&1; echo "$wl-check rc=$?" >> $R/rc ) &
done
wait
for wl in dev fuzz; do cmp $R/$wl-py.txt $R/$wl-check.txt >> $R/rc 2>&1 && echo "$wl py check IDENTICAL $(wc -l < $R/$wl-py.txt) lines" >> $R/rc || echo "$wl py check DIFFER" >> $R/rc; done
echo DONE >> $R/rc
