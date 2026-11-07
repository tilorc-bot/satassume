#!/bin/bash
# guard_pinned.sh WORK CORE: the same test as guard_probe.sh, audit on, Rust and then injected Python, 3 seeds at once on one core, to see what
# load does to the whole-test guard. WORK/CASE-SEED/probe.json as there; WORK/finished.txt comes last.
work=$1; core=$2; mkdir -p "$work"; work=$(cd "$work" && pwd)
T=tests/test_lra_fuzz.py::test_fuzz_entails_and_implied
here=$(dirname "$0")
for c in "rust rust 0" "python-inject python 1"; do
  set -- $c
  for s in 0 1 2; do
    d=$work/$1-$s; mkdir -p "$d"
    SLICE_GUARD_OUT=$d/probe.json SLICE_GUARD_INJECT=$3 PYTEST_N= timeout 1500 taskset -c "$core" \
      bash "$here/run_suite.sh" "$d" "$2" -p guard_probe --hypothesis-seed="$s" --hypothesis-show-statistics $T > /dev/null 2>&1 &
  done
  wait
done
date -u > "$work/finished.txt"
