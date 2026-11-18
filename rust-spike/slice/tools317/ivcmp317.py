"""ivcmp317.py DIR312 DIR314 DIR317: every id's outcome per (file set, backend) over 312's iv rows (c229014, frames py),
314's (5b1d96f, frames rust and py) and 317's (head, frames rust): how many ids differ between any two runs; the failed
set per column; and what frames_seen recorded in 317's runs."""
import glob, json, os, sys, collections
def load(D):
    runs = {}
    for d in sorted(os.listdir(D)):
        fs = glob.glob(os.path.join(D, d, 'rows.*.jsonl'))
        if fs: runs[d] = {json.loads(l)['id']: json.loads(l)['outcome'] for f in fs for l in open(f)}
    return runs
runs = {}
for src, D in zip(('312', '314', '317'), sys.argv[1:4]):
    runs.update({(src, n): r for n, r in load(D).items()})
def key(k):
    p = k[1].split('-')
    return (p[0].replace('fwd', '').replace('rev', '') or '3', p[1])
def col(k):
    src, n = k; p = n.split('-')
    return 'c229014 py' if src == '312' else ('5b1d96f ' if src == '314' else 'head ') + p[3]
groups = collections.defaultdict(list)
for k in runs: groups[key(k)].append(k)
for g, ks in sorted(groups.items()):
    ids = set().union(*(runs[k] for k in ks)); moved = [i for i in ids if len({runs[k].get(i) for k in ks}) > 1]
    cols = collections.Counter(col(k) for k in ks)
    failed = {c: sorted({i for k in ks if col(k) == c for i, o in runs[k].items() if o == 'failed'}) for c in cols}
    print(f'files {g[0]} backend {g[1]}: runs {dict(cols)} ids {len(ids)} moved {len(moved)}')
    for c in sorted(failed): print(f'   {c}: failed {failed[c]}')
    for i in moved: print('   MOVED', i, collections.Counter((col(k), runs[k].get(i)) for k in ks))
seen = collections.Counter()
for d in sorted(os.listdir(sys.argv[3])):
    for f in glob.glob(os.path.join(sys.argv[3], d, 'frames.*.txt')):
        p = d.split('-'); seen[(p[1], p[3], open(f).read().strip())] += 1
for k, n in sorted(seen.items()): print('frames_seen', k, n)
