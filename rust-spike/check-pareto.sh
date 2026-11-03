#!/bin/sh
# Inside sa-eval-bench:1, not timed: both replays in check mode, per-query counters compared, then every run mode once.
mkdir -p /tmp/shim && ln -sf /work/evalbench /tmp/shim/evalbench
export SA_EVAL_DATA=/work/data PYTHONHASHSEED=0 PYTHONPATH=/work/src/base-9bafaa5:/work/sympy:/tmp/shim
D=/work/spike
for wl in dev fuzz; do
  python $D/replay_py.py $wl $D/traces check
  for b in rs rsfx rslto; do $D/$b $wl $D/traces check | sed "s/\"rs\"/\"$b\"/"; done
  python - "$D/traces/$wl" <<'PY'
import json, sys
p, r, m = (json.load(open(sys.argv[1] + s)) for s in (".perq-py.json", ".perq-rs.json", ".meta.json"))
print(sys.argv[1], "queries", len(p), "py==rs", p == r, "py==recorded", p == m["perq"])
PY
done
ROUNDS=check sh $D/run-k.sh | cut -c1-300
