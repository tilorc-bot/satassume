#!/bin/bash
# cell368.sh OUT NAME CELL WL [FILE...] (sa-port-368, orion, counts only): one bis368.py cell, gocnt367.sh's environment.
#   CELL: default   the package alone, no SLICE_ switch (cnt367 mode py)
#         rust-nat  SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust SLICE_WITNESS=1 SLICE_WITNESS_CAP=32 SLICE_WITNESS_RUST=1
#         py-ref    the slice installed, SLICE_CONVERT=py and no Rust switch (the Python reference of the ruling)
# B368_* knobs are taken from the caller's environment. Output: OUT/NAME.{line,err,ans,json}; prints "NAME digest".
WT=$(cd "$(dirname "$0")/../../../.." && pwd); S=$WT/rust-spike/slice; T=$S/results/tools368; OUT=$1; NAME=$2; CELL=$3; WL=$4; shift 4
mkdir -p $OUT
. ~/sa-rust-ids-work/env.sh; export SA_EVAL_DATA; export PYTHONHASHSEED=${HASHSEED368:-$PYTHONHASHSEED}
for v in $(env | grep -o '^SLICE_[A-Z_0-9]*'); do unset $v; done
export PYTHONPATH=$WT:$W/sympy:$W/shim SLICE_DIR=$S B368_ANS=$OUT/$NAME.ans
case $CELL in
  default) MODE=py;;
  rust-nat) MODE=rust; export SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust SLICE_WITNESS=1 SLICE_WITNESS_CAP=32 SLICE_WITNESS_RUST=1;;
  py-ref) MODE=rust; export SLICE_CONVERT=py;;
  *) echo "bad cell $CELL"; exit 2;;
esac
[ $# = 0 ] && export B368_STOP=1
$PY $T/bis368.py $WL $MODE $OUT/$NAME.json "$@" > $OUT/$NAME.line 2> $OUT/$NAME.err
rc=$?
echo "$NAME rc=$rc $($PY -c 'import json,sys; r=json.loads(open(sys.argv[1]).read() or "{}"); print(r.get("digest"), "so", r.get("so"), "fields", r.get("nfields"), "failed", len((r.get("plant") or {}).get("failed") or []))' $OUT/$NAME.line 2>&1 | tail -1)"
