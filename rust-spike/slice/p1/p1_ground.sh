#!/bin/bash
# The ground workload: fresh compare, move at every call, and the dump mutants of the two fields dev never had.
G=$B/ground; D=$G/dm; mkdir -p $D; date -u >$G/start
$PY live.py ground py $G/py.jsonl --check entry --fork >$G/py.tot 2>$G/py.err &
$PY live.py ground rust $G/rust.jsonl --check entry --fork >$G/rust.tot 2>$G/rust.err &
wait
$PY livecmp.py $G/py.jsonl $G/rust.jsonl >$G/fresh.cmp 2>&1
$PY move_every_call.py count ground $G/count.jsonl >$G/count.tot 2>$G/count.err
$PY move_every_call.py run ground $G/count.jsonl.counts $G/mv.jsonl >$G/mv.tot 2>$G/mv.err
$PY move_every_call.py cmp $G/py.jsonl $G/mv.jsonl >$G/mv.cmp 2>&1
export G D
$PY - >$G/prof.txt 2>&1 <<'P'
import json, os
import dump_mutants as DM
G = os.environ["G"]
items = []
for q, c in sorted(json.loads(x) for x in open(G + "/count.jsonl.counts")):
    items += [(q, g) for g in range(c)]
pid = os.fork()
if pid == 0:
    DM.go(None, "ground", items, G + "/prof.jsonl")
    os._exit(0)
os.wait()
prof = [json.loads(x) for x in open(G + "/prof.jsonl.eff")]
print("items", len(items), "profiled", len(prof))
for f in ("_ground", "_pending_ground"):
    print(f, "non-empty at a move:", sum(1 for _, _, fs in prof if f in fs), "queries", len({q for q, _, fs in prof if f in fs}))
for name, (field, how) in DM.MUT.items():
    if field in ("_ground", "_pending_ground"):
        it = [[q, g] for q, g, fs in prof if field in fs][:200]
        json.dump(it, open(f"{G}/dm/{name.replace(':', '_')}.in", "w"))
        print(name, len(it))
P
for f in $D/*.in; do n=$(basename $f .in); m=$(echo $n | sed 's/_/:/'); $PY dump_mutants.py run $m ground $f $D/$n.jsonl >$D/$n.tot 2>$D/$n.err & done
wait
$PY dump_mutants.py score $G/py.jsonl $D >$D/score.txt 2>&1
date -u >$G/done
