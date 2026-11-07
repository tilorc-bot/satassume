"""Medians over rounds 1-5 per arm and workload, range, digests. Usage: ana_floor.py DIR"""
import json, statistics as st, sys, collections
R = sys.argv[1]; rows = [json.loads(l) for l in open(R + '/floor.jsonl')]
W = {'dev': '31cd0945c07f02a6', 'fuzz': '173502b6ef285ad6'}
for wl in ('dev', 'fuzz'):
    print(wl)
    m = {}
    for a in ('base', 'off', 'cache', 'lazy', 'both', 'term-py'):
        rs = [r for r in rows if r['wl'] == wl and r['arm'] == a and r['round'] > 0]
        ss = [r['s'] for r in rs]; m[a] = st.median(ss)
        ds = collections.Counter(r.get('digest') for r in rs)
        extra = {k: rs[0][k] for k in rs[0] if k not in ('round', 'arm', 'wl', 's', 'digest') and not isinstance(rs[0][k], (dict, list))}
        print(f"  {a:8} n={len(ss)} median {m[a]:.3f} range {min(ss):.3f}-{max(ss):.3f} digests {dict(ds)} match={set(ds)=={W[wl]}} {extra}")
    print(f"  conversion cost (base - term-py) {m['base']-m['term-py']:.3f}; both - term-py {m['both']-m['term-py']:.3f}; saved by cache {m['off']-m['cache']:.3f} lazy {m['off']-m['lazy']:.3f} both {m['off']-m['both']:.3f}; off-base {m['off']-m['base']:.3f}")
