"""knowledge_leak.py run WL OUT.jsonl --mode plain|atoms [--limit N]; knowledge_leak.py cmp PLAIN ATOMS; knowledge_leak.py fire: what does conversion leave in Python?

Same order and no SymPy cache clear, as knowledge_fresh. Per query: satassume's module memos by name, SymPy `cacheit` writes by
function, and the `_assumptions` entries of the query's terms. A `cacheit` write is a miss. `currsize` can't be the count: cacheit
is an LRU of 1000, so once a function's cache is full a write evicts and its size doesn't move. `fire` plants a write on a full
cache and shows `misses` sees it where `currsize` doesn't. Hits are counted apart: they write nothing but reorder the LRU. atoms also snapshots around `convert.convert` alone, which is the
direct answer: whatever it wrote stays there while Python runs the query, kept or not. cmp prints conversion's writes by table,
kept queries apart, and where plain and atoms end differently, each with its first query.
"""
import argparse
import collections
import hashlib
import importlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def run(a):
    from harness import state as S
    from harness.state import reset_module_state
    from satassume import sympy_api, engine as E
    from sympy.core.cache import CACHE
    from evalbench.common import workload
    if a.wl == 'fuzz':
        from evalbench.fuzz import queries
        pairs = queries(424242)
    else:
        pairs = workload(a.wl)
    pairs = pairs[:a.limit] if a.limit else pairs
    S.import_all()

    def resolve():
        out = []
        for mod, attr, _ in S.inventory():
            o = vars(importlib.import_module(mod))
            if '.' in attr:
                c, attr = attr.split('.', 1)
                o = vars(o[c])
            out.append((f'{mod}.{attr}', o, attr))
        return out
    tables = resolve()

    def walk(*xs):
        seen, out, st = set(), [], [x for x in xs if hasattr(x, 'args')]
        while st:
            t = st.pop()
            if id(t) not in seen:
                seen.add(id(t))
                out.append(t)
                st.extend(t.args)
        return out

    def snap(terms):
        memos = {n: len(o[k]) for n, o, k in tables if hasattr(o.get(k), '__len__') and len(o[k])}
        sym = {}
        for f in CACHE:
            n = f.cache_info().misses
            if n:
                name = getattr(f, '__qualname__', repr(f))
                sym[name] = sym.get(name, 0) + n
        facts = {}
        for pos, t in enumerate(terms):
            d = getattr(t, '_assumptions', None)
            if d:
                # By walk position, never str(t): printing writes to cacheit and asks is_* itself, so it would count its own writes as conversion's.
                facts[f'{pos}:{type(t).__name__}'] = sorted(map(repr, d.items()))
        return memos, sym, facts

    def hits():
        return sum(f.cache_info().hits for f in CACHE)

    def delta(a, b):
        return {k: b.get(k, 0) - a.get(k, 0) for k in set(a) | set(b) if b.get(k, 0) != a.get(k, 0)}
    conv = {}
    K = None
    if a.mode == 'atoms':
        import convert
        import knowledge_live as K
        py_convert = convert.convert

        def c(p, q, eng):
            terms = walk(p, q)
            m0, s0, f0 = snap(terms)
            h0 = hits()
            r = py_convert(p, q, eng)
            m1, s1, f1 = snap(terms)
            conv.update(hits=hits() - h0, kept=getattr(r, 'reason', None), memo=delta(m0, m1), sympy=delta(s0, s1),
                        facts=sum(len(v) for v in f1.values()) - sum(len(v) for v in f0.values()),
                        fact_ex=next((k for k in f1 if f1[k] != f0.get(k)), None))
            return r
        convert.convert = c
        K.install()
    with open(a.out, 'w') as fh:
        for i, (p, q) in enumerate(pairs):
            reset_module_state(sympy_cache=False)
            sympy_api.set_default_engine(E.Engine())
            conv.clear()
            _, s0, _ = snap(())
            try:
                r = sympy_api.ask(p, q)
            except Exception as e:
                r = 'raise:' + type(e).__name__
            m, s1, f = snap(walk(p, q))
            s = delta(s0, s1)
            fd = hashlib.blake2b(repr(sorted(f.items())).encode(), digest_size=8).hexdigest()
            fh.write(json.dumps(dict(i=i, r=str(r), memo=m, sympy=s, facts=fd, n_facts=sum(map(len, f.values())), conv=dict(conv))) + '\n')
        fh.write('{"end": true}\n')


def cmp(a):
    load = lambda f: [json.loads(x) for x in open(f)]
    P, Q = load(a.plain), load(a.atoms)
    print('finished', P[-1].get('end'), Q[-1].get('end'), 'queries', len(P) - 1, len(Q) - 1)
    P, Q = P[:-1], Q[:-1]
    for label, keep in (('converted', lambda r: not r['conv'].get('kept')), ('kept', lambda r: r['conv'].get('kept'))):
        rs = [r for r in Q if keep(r) and r['conv']]
        memo, sym = collections.Counter(), collections.Counter()
        first = {}
        wrote = 0
        for r in rs:
            c = r['conv']
            wrote += bool(c['memo'] or c['sympy'] or c['facts'])
            for k, v in c['memo'].items():
                memo[k] += v
                first.setdefault(k, r['i'])
            for k, v in c['sympy'].items():
                sym[k] += v
                first.setdefault(k, r['i'])
        fx = [r for r in rs if r['conv']['facts']]
        print(f'conversion alone, {label}: {len(rs)} queries, {wrote} wrote something; satassume memos {len(memo)} tables, SymPy cacheit {len(sym)} functions, '
              f'_assumptions entries added {sum(r["conv"]["facts"] for r in fx)} on {len(fx)} queries')
        for k, v in memo.most_common(12):
            print('  memo', v, k, 'first query', first[k])
        for k, v in sym.most_common(12):
            print('  sympy', v, k, 'first query', first[k])
        if fx:
            print('  facts first', fx[0]['i'], fx[0]['conv']['fact_ex'])
    print('answers differ', sum(x['r'] != y['r'] for x, y in zip(P, Q)))
    for field in ('memo', 'sympy', 'facts'):
        names = collections.Counter()
        first = {}
        for x, y in zip(P, Q):
            if x[field] != y[field]:
                if field == 'facts':
                    names['facts'] += 1
                    first.setdefault('facts', x['i'])
                else:
                    for k in set(x[field]) | set(y[field]):
                        if x[field].get(k, 0) != y[field].get(k, 0):
                            names[k] += 1
                            first.setdefault(k, x['i'])
        print(f'end state differs, {field}: {sum(names.values())} rows')
        for k, v in names.most_common(15):
            print('  ', v, k, 'first query', first[k])
    tot = lambda rows: collections.Counter(k for r in rows for k, v in r['sympy'].items() for _ in range(v))
    tp, tq = tot(P), tot(Q)
    print('cacheit writes over the query, plain', sum(tp.values()), 'atoms', sum(tq.values()), 'hits in conversion', sum(r['conv'].get('hits', 0) for r in Q))
    for k in sorted(set(tp) | set(tq), key=lambda k: -abs(tq[k] - tp[k]))[:12]:
        print('  ', k, 'plain', tp[k], 'atoms', tq[k])
    print('end n_facts sum, plain', sum(x['n_facts'] for x in P), 'atoms', sum(y['n_facts'] for y in Q))


def fire(a):
    """A planted write on a full LRU: the size reading says nothing and the miss reading says 1. Both are shown because a zero from `misses` is only worth something if this row is 1."""
    from sympy.core.cache import cacheit, CACHE

    @cacheit
    def planted(x):
        return x
    f = next(w for w in CACHE if getattr(w, '__wrapped__', None) is planted.__wrapped__)
    n = f.cache_info().maxsize
    for i in range(n):
        planted(i)
    i0 = f.cache_info()
    planted(n + 1)
    i1 = f.cache_info()
    print('maxsize', n, 'currsize moved', i1.currsize - i0.currsize, 'misses moved', i1.misses - i0.misses)
    assert i1.currsize == i0.currsize and i1.misses == i0.misses + 1


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest='cmd', required=True)
    r = sp.add_parser('run'); r.add_argument('wl'); r.add_argument('out'); r.add_argument('--mode', default='atoms'); r.add_argument('--limit', type=int)
    c = sp.add_parser('cmp'); c.add_argument('plain'); c.add_argument('atoms')
    sp.add_parser('fire')
    a = ap.parse_args()
    dict(run=run, cmp=cmp, fire=fire)[a.cmd](a)
