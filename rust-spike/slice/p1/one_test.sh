#!/bin/bash
# one_test.sh FILE LOG: one rust-spike/slice test file, run the way the file says it runs (item 4f), from rust-spike/slice
# with $PY and PYTHONPATH set as bar.sh sets them. Prints "FILE exit CODE LAST-LOG-LINE".
#   test_handler_count.py, test_catch_count.py: pytest with -p rust_plugin -p handler_count (SLICE_SUITE_OUT is a fresh
#     directory next to LOG, where handler_count writes its rows)
#   test_cbm_noid.py: on Rust, under the suite's plugin (SLICE_SUITE_BACKEND=rust), as its docstring says; plain pytest is
#     Python, which skips the counts and plants (B's item (3)). A skip fails it.
#   test_cf_diff.py: a script (seed 1, 20,000 ops); exit 1 unless its last count reads "MISMATCHES 0"
#   anything else: plain pytest
f=$1; log=$2
case $f in
  test_handler_count.py|test_catch_count.py)
    d=${log%.log}.out; rm -rf "$d"; mkdir -p "$d"
    SLICE_SUITE_OUT=$d $PY -m pytest -p rust_plugin -p handler_count "$f" -q --tb=short -p no:cacheprovider > "$log" 2>&1; e=$?;;
  test_cbm_noid.py)
    d=${log%.log}.out; rm -rf "$d"; mkdir -p "$d"
    SLICE_SUITE_OUT=$d SLICE_SUITE_BACKEND=rust $PY -m pytest -p rust_plugin "$f" -q --tb=short -p no:cacheprovider > "$log" 2>&1; e=$?
    [ $e = 0 ] && tail -n 1 "$log" | grep -q skipped && e=1;;
  test_cf_diff.py)
    $PY "$f" 1 20000 > "$log" 2>&1; e=$?
    [ $e = 0 ] && ! grep -q '^MISMATCHES 0 ' "$log" && e=1;;
  *) $PY -m pytest "$f" -q --tb=short -p no:cacheprovider > "$log" 2>&1; e=$?;;
esac
echo "$f exit $e $(tail -n 1 "$log")"
