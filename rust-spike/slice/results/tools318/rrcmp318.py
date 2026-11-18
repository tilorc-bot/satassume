# rrcmp318.py: the eight runs of suite row term:tl-term-stale (two bars' rows and rr318.sh's six), compared by id.
import glob, json, os, itertools, collections
W = os.path.expanduser('~/sp19/sa-rust-ids-work')
def row(d):
    r = {}
    for p in glob.glob(os.path.join(d, 'rows.*.jsonl')):
        for line in open(p):
            j = json.loads(line); r[j['id']] = j.get('outcome')
    return r
runs = {'314-bar': row(W + '/sa-port-314/bar/suite-term:tl-term-stale'), '317-bar': row(W + '/sa-port-317/bar/suite-term:tl-term-stale')}
for d in sorted(glob.glob(W + '/sa-port-318/rr/tl-term-stale-*')):
    n = os.path.basename(d).replace('tl-term-stale-', '')
    runs[n] = row(d); print(n, open(d + '/exit.txt').read().strip()[:110], '|', ' '.join(open(d + '/tree.txt').read().split()[:3])[:60])
plain = {'314': row(W + '/sa-port-314/bar/suite'), '317': row(W + '/sa-port-317/bar/suite')}
PH = 'tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence'
names = list(runs)
for n in names:
    r = runs[n]; c = collections.Counter(r.values()); src = n[:3]
    print(f"{n}: ids {len(r)} failed {c['failed']} passed {c['passed']} | changed vs 314's plain {sum(1 for i in r if i != PH and r[i] != plain['314'].get(i))} (planted-history left out; it is {r.get(PH)})")
def nd(a, b): return sum(1 for i in set(a) | set(b) if i != PH and a.get(i) != b.get(i))
print('pairwise ids differing (planted-history left out):')
print('          ' + ' '.join(f"{n:>8}" for n in names))
for a in names: print(f"{a:>9} " + ' '.join(f"{nd(runs[a], runs[b]):>8}" for b in names))
same = lambda s: [nd(runs[a], runs[b]) for a, b in itertools.combinations([n for n in names if n.startswith(s)], 2)]
cross = [nd(runs[a], runs[b]) for a in names for b in names if a.startswith('314') and b.startswith('317')]
print('within 5b1d96f (4 runs, 6 pairs):', sorted(same('314')), '| within 46750d4:', sorted(same('317')), '| across (16 pairs): min', min(cross), 'max', max(cross))
allids = set().union(*runs.values()) - {PH}
var = [i for i in allids if len({runs[n].get(i) for n in names}) > 1]
files = collections.Counter(i.split('::')[0] for i in var)
print('ids not the same in all 8 runs:', len(var), '| by file:', dict(files.most_common(8)))
for s in ('314', '317'):
    v = [i for i in allids if len({runs[n].get(i) for n in names if n.startswith(s)}) > 1]
    print(f"  varying within source {s}: {len(v)}")
fa = lambda s: set.union(*[{i for i in runs[n] if runs[n][i] == 'failed'} for n in names if n.startswith(s)])
print('ids that failed in some run: 314', len(fa('314')), '317', len(fa('317')), 'only under 314', len(fa('314') - fa('317')), 'only under 317', len(fa('317') - fa('314')))
for i in sorted(fa('317') - fa('314'))[:8]: print('   only 317:', i[:150])
for i in sorted(fa('314') - fa('317'))[:8]: print('   only 314:', i[:150])
