#!/bin/sh
# State through fresh.py, one arm against Python's rows. Usage: run_arms_check.sh OUTDIR "ARM ..."; an arm is off, cache, check, lazy or both.
. ~/sa-rust-ids-work/env.sh
C=$(cd "$(dirname "$0")/../../.." && pwd)
export PYTHONPATH=$C:$W/sympy:$W/shim SLICE_DIR=$C/rust-spike/slice
R=$1; mkdir -p "$R"; cd "$SLICE_DIR"
for wl in dev fuzz; do
  ( timeout 600 "$PY" fresh.py $wl py $R/$wl-py.txt --handlers $R/$wl-py.handlers > $R/$wl-py.log 2>&1; echo "$wl-py rc=$?" >> $R/rc ) &
done
for arm in $2; do
  case $arm in off) c=; l=;; cache) c=1; l=;; check) c=check; l=;; lazy) c=; l=1;; both) c=1; l=1;; bothcheck) c=check; l=1;; esac
  for wl in dev fuzz; do
    ( SLICE_CONV_CACHE=$c SLICE_CONV_LAZY=$l timeout 900 "$PY" conv_floor/fresh_arm.py $wl $R/$wl-$arm > $R/$wl-$arm.log 2>&1; echo "$wl-$arm rc=$?" >> $R/rc ) &
  done
  wait
done
wait
for arm in $2; do for wl in dev fuzz; do
  cmp $R/$wl-py.txt $R/$wl-$arm.txt >> $R/rc 2>&1 && echo "$wl py $arm IDENTICAL $(wc -l < $R/$wl-py.txt) lines" >> $R/rc || echo "$wl py $arm DIFFER" >> $R/rc
done; done
echo DONE >> $R/rc
