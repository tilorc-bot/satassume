#!/bin/bash
# run_suite.sh WORK rust|python [pytest args...]: the suite on one backend, 4 workers, recorded by rust_plugin.py.
# WORK gets rows.PID.jsonl as tests end, pytest.log, and exit.txt last. With no pytest args it runs `tests`.
# PYTEST_N overrides the workers ("-n 4"). Hash seed from env.sh unless SEED is set.
# handlers.PID.jsonl: what handler_count saw at the two quiet handlers, per test id.
# The tree under test is the one holding this script, not the path env.sh names; tree.txt records what imported.
T=$(cd "$(dirname "$0")/../.." && pwd)
. ~/sa-rust-ids-work/env.sh
PYTHONPATH=$T:$W/sympy:$W/shim
work=$1; backend=$2; shift 2
mkdir -p "$work"; work=$(cd "$work" && pwd)
cd "$T"
export PYTHONPATH=$PYTHONPATH:$PWD/rust-spike/slice SLICE_SUITE_OUT=$work SLICE_SUITE_BACKEND=$backend
export PYTHONHASHSEED=${SEED:-$PYTHONHASHSEED} HYPOTHESIS_STORAGE_DIRECTORY=$work/hyp
[ $# -eq 0 ] && set -- tests
$PY -c 'import satassume; print(satassume.__file__)' > "$work/tree.txt"
$PY -m pytest -p rust_plugin -p handler_count ${PYTEST_N--n 4} -q --tb=short -p no:cacheprovider "$@" > "$work/pytest.log" 2>&1
echo "$? $(tail -1 "$work/pytest.log")" > "$work/exit.txt"
cat "$work/exit.txt"
