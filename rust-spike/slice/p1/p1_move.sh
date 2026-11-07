#!/bin/bash
# Move at sampled call indices on fuzz, every 16th call, 16 shards; compared with fresh Python.
O=$B/fresh2; M=$B/mv; mkdir -p $M; date -u >$M/start
$PY move_every_call.py count fuzz $M/count.jsonl >$M/count.tot 2>$M/count.err
$PY -c "
import json
c=[json.loads(x)[1] for x in open('$M/count.jsonl.counts')]
print('queries',len(c),'with calls',sum(1 for x in c if x),'calls',sum(c),'max',max(c))" >$M/count.txt
STRIDE=$(cat $HOME/move_stride 2>/dev/null || echo 16)
echo $STRIDE >$M/stride
for i in $(seq 0 15); do
  $PY move_every_call.py run fuzz $M/count.jsonl.counts $M/s$i.jsonl --shard $i/16 --stride $STRIDE >$M/s$i.tot 2>$M/s$i.err &
done
wait
$PY move_every_call.py cmp $O/fuzz-py.jsonl $M/s?.jsonl $M/s1?.jsonl >$M/fuzz.cmp 2>&1
$PY - >$M/branch.txt <<'PY'
import glob, json
n = at = ex = 0; end = 0
for f in glob.glob('$M/s*.jsonl'.replace('$M', __import__('os').environ['B'] + '/mv')):
    for l in open(f):
        r = json.loads(l)
        for s in r.get('sessions', []):
            if (s['group'] or '').startswith('moved:forced'):
                for b_end, e, b_mv in s['branching']:
                    if b_mv is None: continue
                    n += 1; at += b_mv > 0; end += b_end > 0; ex += e
print('forced moved sessions', n, 'branched before the move', at, 'branched by the end', end, 'exhausted at end', ex)
PY
date -u >$M/done
