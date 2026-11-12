import json, collections, sys
for wl in ('dev', 'fuzz'):
    d = json.load(open(f'split-{wl}.json')); N = d['N']
    rows = d['rows']
    print(f'== {wl}: N {N}')
    byroot = collections.Counter(); 
    for root, F, kind, key, n in rows: byroot[root] += n
    print(' roots', dict(byroot))
    for root in ('convert', 'read'):
        tot = byroot[root]
        kinds = collections.Counter(); keys = collections.Counter(); fk = collections.Counter()
        for r, F, kind, key, n in rows:
            if r != root: continue
            kinds[kind] += n; keys[key] += n; fk[(F, kind)] += n
        print(f' -- {root}: {tot} = {100*tot/N:.1f}% of N; kinds', {k: f'{v} ({100*v/tot:.1f}%)' for k, v in kinds.most_common()})
        for k, v in keys.most_common(int(sys.argv[1])):
            print(f'    {v:6d} {100*v/tot:5.1f}%  {k}')
        Fs = collections.Counter()
        for (F, kind), n in fk.items(): Fs[F] += n
        for F, n in Fs.most_common(12):
            print(f'    F {F:40s} {n:6d} ' + ' '.join(f'{k}={fk[(F,k)]}' for k in ('bytecode', 'c', 'py', 'rust')))
