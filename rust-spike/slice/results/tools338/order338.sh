#!/bin/bash
# order338.sh TREE OUT BACKEND SWITCH MODE [pytest args...] (sa-port-338): one process, no xdist, of TREE's
# tests/test_templates.py, tests/test_p4_review.py and tests/test_witness.py (or the pytest args given) on BACKEND
# (rust|python) with SLICE_WITNESS=SWITCH, in the order MODE names (plug/order338.py: file, first, last, interleaved,
# seed:N). run_suite.sh's environment and plugins, bar.sh suite()'s hypothesis profile.
# OUT gets NAME.log (pytest) and NAME.txt (order338.py: where the two leaking tests and the seven ids ran, outcomes).
# PLUG = the directory holding order338.py (default: next to this script's directory, ../plug).
T=$(cd "$1" && pwd); out=$2; backend=$3; sw=$4; mode=$5; shift 5
PLUG=${PLUG:-$(cd "$(dirname "$0")/../plug" && pwd)}
. ~/sa-rust-ids-work/env.sh
mkdir -p "$out"; out=$(cd "$out" && pwd)
name=$backend-sw$sw-$(echo $mode | tr : -)${TAG:+-$TAG}
cd "$T"
unset SLICE_WITNESS_CAP SLICE_WITNESS_PLANT SLICE_CONVERT SLICE_TERM_FRAMES
export PYTHONPATH=$T:$W/sympy:$W/shim:$T/rust-spike/slice:$PLUG SLICE_SUITE_OUT=$out/rows-$name SLICE_SUITE_BACKEND=$backend
export HYPOTHESIS_STORAGE_DIRECTORY=$out/hyp SLICE_WITNESS=$sw ORDER338=$mode ORDER338_OUT=$out/$name.txt
mkdir -p $SLICE_SUITE_OUT
[ $# -eq 0 ] && set -- tests/test_templates.py tests/test_p4_review.py tests/test_witness.py
$PY -c 'import satassume; print(satassume.__file__)' > "$out/tree-$name.txt"
$PY -m pytest -p rust_plugin -p handler_count -p order338 -q --tb=short -p no:cacheprovider -p hyp_profile --hypothesis-profile=bar "$@" > "$out/$name.log" 2>&1
echo "$name exit $? $(tail -1 "$out/$name.log") | $(grep '^mode' "$out/$name.txt")"
