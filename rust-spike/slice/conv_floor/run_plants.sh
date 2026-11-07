#!/bin/sh
# Every planted field on each target class. Usage: run_plants.sh OUTDIR REFDIR WORKLOAD "CLASSES" [JOBS]. REFDIR holds WORKLOAD-py.txt.
. ~/sa-rust-ids-work/env.sh
C=$(cd "$(dirname "$0")/../../.." && pwd)
export PYTHONPATH=$C:$W/sympy:$W/shim SLICE_DIR=$C/rust-spike/slice SLICE_CONV_CACHE=1
R=$1; REF=$2; WL=$3; CL=$4; J=${5:-3}; mkdir -p "$R"; cd "$SLICE_DIR"
for f in name kind rank flags_number flags_plain_ops flags_symbol flags_commfixed class_key templates structural custom_content; do for c in $CL; do echo "$f $c"; done; done |
  xargs -P "$J" -L1 sh -c 'P='"$R/$WL"'-$0-$1; timeout 900 '"$PY"' conv_floor/plant_row.py '"$WL"' $P $0 $1 > $P.log 2>&1; echo "$0 $1 rc=$?" >> '"$R"'/rc'
echo DONE >> "$R/rc"
