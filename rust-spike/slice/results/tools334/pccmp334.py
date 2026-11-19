"""pccmp334.py DIR [BASEDIR]: read pc334.sh's cells under DIR (fpy-cpy ...). Totals by file per cell, templates/__init__.py
by function and by caller (20 workloads; dev and fuzz per query), knowledge_live per workload equal across cells, and with
BASEDIR: per-file change against it per cell, any per-function rise, and knowledge_live per workload equal to BASEDIR's."""
import json, sys, collections
WLS = "lra f6 wiring scope dev fuzz ground port loop zero cert budget core opaque rootof value twin transfer760 transfer2340 cls".split()
cells = ['fpy-cpy', 'frust-cpy', 'fpy-crust', 'frust-crust']
INIT = '__init__.py:'


def load(d):
    return {(c, w): json.load(open(f'{d}/{c}/{w}.json')) for c in cells for w in WLS}


def files(D):
    tot = {c: collections.Counter() for c in cells}
    for (c, w), d in D.items():
        for k, v in d['by_qualname'].items():
            tot[c][k.split(':')[0]] += v
    return tot


D = load(sys.argv[1])
tot = files(D)
q = {w: D[('fpy-cpy', w)]['queries'] for w in WLS}
print('queries', sum(q.values()), 'dev', q['dev'], 'fuzz', q['fuzz'])
print('file | ' + ' | '.join(cells))
for f in sorted(set().union(*tot.values()), key=lambda f: -tot['fpy-cpy'][f]):
    print(f, *[tot[c][f] for c in cells], sep=' | ')
print('files with 0 calls in frust-crust:', sorted(f for f in set().union(*tot.values()) if tot['frust-crust'][f] == 0))
for c in cells:
    fn, by = collections.Counter(), collections.Counter()
    for w in WLS:
        for k, v in D[(c, w)]['by_qualname'].items():
            if k.startswith(INIT):
                fn[k] += v
        for k, v in D[(c, w)].get('init_callers', {}).items():
            by[k] += v
    per = {w: sum(v for k, v in D[(c, w)]['by_qualname'].items() if k.startswith(INIT)) for w in ('dev', 'fuzz')}
    print(f'{c} __init__.py: total {sum(fn.values())}; per query dev {per["dev"]/q["dev"]:.2f} fuzz {per["fuzz"]/q["fuzz"]:.2f}')
    print('   by function:', dict(fn.most_common()))
    print('   by caller:', dict(by.most_common()))
    print('   workloads with any:', {w: n for w in WLS if (n := sum(v for k, v in D[(c, w)]['by_qualname'].items() if k.startswith(INIT)))})
kl = lambda D, c: {w: sum(v for k, v in D[(c, w)]['by_qualname'].items() if k.startswith('knowledge_live.py:')) for w in WLS}
print('knowledge_live per wl equal across cells:', all(kl(D, c) == kl(D, 'fpy-cpy') for c in cells), kl(D, 'fpy-cpy'))
if len(sys.argv) > 2:
    B = load(sys.argv[2])
    bt = files(B)
    print('against base, per file (base -> this), cells', cells)
    for f in sorted(set().union(*tot.values(), *bt.values())):
        ch = [(bt[c][f], tot[c][f]) for c in cells]
        print('  ', f, ' | '.join(f'{a} -> {b}' if a != b else f'{a} =' for a, b in ch))
    rise = [(c, w, k, B[(c, w)]['by_qualname'].get(k, 0), v) for c in cells for w in WLS
            for k, v in D[(c, w)]['by_qualname'].items() if v > B[(c, w)]['by_qualname'].get(k, 0)]
    fall = collections.Counter()
    for c in cells:
        for w in WLS:
            for k, v in B[(c, w)]['by_qualname'].items():
                if v > D[(c, w)]['by_qualname'].get(k, 0):
                    fall[(c, k)] += v - D[(c, w)]['by_qualname'].get(k, 0)
    print('per-function rises against base:', len(rise), rise[:8])
    print('per-function falls against base:', dict(fall))
    print('knowledge_live per wl equal to base in every cell:', all(kl(D, c) == kl(B, c) for c in cells))
    print('queries equal to base:', all(D[k]['queries'] == B[k]['queries'] for k in D))
