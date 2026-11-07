#!/bin/bash
# run_suite.sh WORK rust|python [pytest args...]: the suite on one backend, 4 workers, recorded by rust_plugin.py.
# WORK gets rows.PID.jsonl as tests end, pytest.log, and exit.txt last. With no pytest args it runs `tests`.
# PYTEST_N overrides the workers ("-n 4"). Hash seed from env.sh unless SEED is set.
. ~/sa-rust-ids-work/env.sh
work=$1; backend=$2; shift 2
mkdir -p "$work"; work=$(cd "$work" && pwd)
cd ~/dev/sa-rust
export PYTHONPATH=$PYTHONPATH:$PWD/rust-spike/slice SLICE_SUITE_OUT=$work SLICE_SUITE_BACKEND=$backend
export PYTHONHASHSEED=${SEED:-$PYTHONHASHSEED} HYPOTHESIS_STORAGE_DIRECTORY=$work/hyp
[ $# -eq 0 ] && set -- tests
$PY -m pytest -p rust_plugin ${PYTEST_N--n 4} -q --tb=short -p no:cacheprovider "$@" > "$work/pytest.log" 2>&1
echo "$? $(tail -1 "$work/pytest.log")" > "$work/exit.txt"
cat "$work/exit.txt"
