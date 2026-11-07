#!/bin/sh
# Each history case on Python, on rust mode with no cache and on rust mode with it. Usage: run_cases.sh OUTDIR
. ~/sa-rust-ids-work/env.sh
C=$(cd "$(dirname "$0")/../../.." && pwd)
export PYTHONPATH=$C:$W/sympy:$W/shim SLICE_DIR=$C/rust-spike/slice
R=$1; mkdir -p "$R"; cd "$SLICE_DIR"
for c in default_engine_nondefault_registry template_from_other_module class_registered_midway new_class_after_fill extensions_register undefined_function_equal_classes sympy_handlers patch_as_base_exp patch_op_priority patch_add patch_atoms patch_class_key patch_hashable_content patch_ordering_of_classes patch_is_number_class_flag; do
  timeout 200 "$PY" conv_floor/cases.py $c --py > $R/$c.py.json 2> $R/$c.py.err
  SLICE_CONV_CACHE= timeout 200 "$PY" conv_floor/cases.py $c > $R/$c.off.json 2> $R/$c.off.err
  SLICE_CONV_CACHE=1 timeout 200 "$PY" conv_floor/cases.py $c > $R/$c.on.json 2> $R/$c.on.err
done
echo DONE > $R/rc
