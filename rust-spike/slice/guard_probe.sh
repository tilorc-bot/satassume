#!/bin/bash
# guard_probe.sh WORK [SEEDS]: test_fuzz_entails_and_implied under guard_probe.py, 2 runs at a time: Rust audit on, Rust audit-off-2, Python,
# Python with the failure injected. WORK/CASE-SEED/probe.json is each run's summary; WORK/finished.txt comes last.
work=$1; seeds=${2:-0 1 2}; mkdir -p "$work"; work=$(cd "$work" && pwd)
T=tests/test_lra_fuzz.py::test_fuzz_entails_and_implied
one() { # case backend audit inject seed
  d=$work/$1-$5; mkdir -p "$d"
  SLICE_GUARD_OUT=$d/probe.json SLICE_GUARD_INJECT=$4 SLICE_AUDIT_OFF=$3 PYTEST_N= timeout 1200 \
    bash "$(dirname "$0")/run_suite.sh" "$d" "$2" -p guard_probe --hypothesis-seed="$5" --hypothesis-show-statistics $T > /dev/null 2>&1
}
for s in $seeds; do
  for c in "rust rust '' 0" "rust-audit2 rust 2 0" "python python '' 0" "python-inject python '' 1"; do
    eval "set -- $c"
    while [ "$(jobs -r | wc -l)" -ge 2 ]; do wait -n; done
    one "$1" "$2" "$3" "$4" "$s" &
  done
done
wait
date -u > "$work/finished.txt"
