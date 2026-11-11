#!/bin/bash
# one_test.sh FILE LOG: one rust-spike/slice test file, run the way the file says it runs (item 4f), from rust-spike/slice
# with $PY and PYTHONPATH set as bar.sh sets them. Prints "FILE exit CODE LAST-LOG-LINE".
#   test_handler_count.py, test_catch_count.py: pytest with -p rust_plugin -p handler_count (SLICE_SUITE_OUT is a fresh
#     directory next to LOG, where handler_count writes its rows)
#   test_cf_diff.py: a script (seed 1, 20,000 ops); exit 1 unless its last count reads "MISMATCHES 0"
#   anything else: plain pytest
f=$1; log=$2
case $f in
  test_handler_count.py|test_catch_count.py)
    d=${log%.log}.out; rm -rf "$d"; mkdir -p "$d"
    SLICE_SUITE_OUT=$d $PY -m pytest -p rust_plugin -p handler_count "$f" -q --tb=short -p no:cacheprovider > "$log" 2>&1; e=$?;;
  test_cf_diff.py)
    $PY "$f" 1 20000 > "$log" 2>&1; e=$?
    [ $e = 0 ] && ! grep -q '^MISMATCHES 0 ' "$log" && e=1;;
  *) $PY -m pytest "$f" -q --tb=short -p no:cacheprovider > "$log" 2>&1; e=$?;;
esac
echo "$f exit $e $(tail -n 1 "$log")"
