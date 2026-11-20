#!/bin/sh
# run351.sh WL ARM [OUT] (sa-port-351): diff351.py on orion with this worktree's tree and .so; not a timing.
T=$(cd "$(dirname "$0")/../../../.." && pwd)
. "$HOME/sa-rust-ids-work/env.sh"
export PYTHONPATH=$T:$W/sympy:$W/shim SLICE_DIR=$T/rust-spike/slice SLICE_WITNESS=${SLICE_WITNESS-1} SLICE_CONVERT=${SLICE_CONVERT-rust} SLICE_TERM_FRAMES=${SLICE_TERM_FRAMES-rust}
exec $PY "$T/rust-spike/slice/results/tools351/diff351.py" "$@"
