#!/bin/bash
# history.sh: can interning order move answers? live with hash = random 61 bits per id (seed S), recorded and shuffled order; control: base under other PYTHONHASHSEED.
. ~/sa-rust-ids-work/env.sh; cd ~/dev/sa-rust/rust-spike/ids
one() { # label env... -- args
  l=$1; shift; r=$(env "$@" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["digest"], d["s"])'); echo "$l $r"; }
{ for w in dev fuzz; do
  for s in 1 2 3 4 5 6; do echo "live-rand$s-recorded-$w IDS_RANDOM=$s $PY run.py live $w recorded --out $W/hist-rand$s-rec-$w.json"; done
  for s in 1 2 3; do echo "live-rand$s-shuf$s-$w IDS_RANDOM=$s $PY run.py live $w shuffled:$s --out $W/hist-rand$s-shuf-$w.json"; done
  for s in 1 2 3; do echo "live-seq-shuf$s-$w $PY run.py live $w shuffled:$s --out $W/hist-seq$s-shuf-$w.json"; done
  for s in 1 2 3 4; do echo "base-seed$s-$w PYTHONHASHSEED=$s $PY run.py base $w recorded --out $W/hist-base$s-$w.json"; done
done; } | xargs -P 3 -I{} bash -c 'set -- {}; l=$1; shift; r=$(env "$@" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[\"digest\"], d[\"s\"])"); echo "$l $r"'
