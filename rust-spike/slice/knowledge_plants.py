"""knowledge_plants.py: bugs planted on purpose, for showing the history and discard compares can fire. A zero from a compare that can't fire says nothing.

Each is a run of knowledge_fresh with `--plant NAME`, compared with its plain row:
  noncomm  discard mode: conversion leaves a wrong `_NONCOMM` entry behind.
  facts    discard mode: conversion leaves a wrong `_assumptions` entry on a compound input term.
  stale    atoms mode: a cross-query memo of patterns keyed by printed name. Fired on nothing in dev's first 600, where no name recurs with other facts: a plant no query can reach.
  stale2   atoms mode: the same memo keyed by the node's class, so the first term of a class decides for the rest. Should move with order. Prints how many calls it changed, since a plant that changed nothing shows nothing.
  hash     atoms mode: clause order follows the string hash. Should move with PYTHONHASHSEED.
"""
import atexit


def walk(*xs):
    seen, out, st = set(), [], [x for x in xs if hasattr(x, 'args')]
    while st:
        t = st.pop()
        if id(t) not in seen:
            seen.add(id(t))
            out.append(t)
            st.extend(t.args)
    return out


def after_convert(name, p, a):
    if name == 'noncomm':
        from satassume.knowledge import domain
        for k in list(domain._NONCOMM):
            domain._NONCOMM[k] = not domain._NONCOMM[k]
    elif name == 'facts':
        for t in walk(p, a):
            if t.args and getattr(t, '_assumptions', None) is not None and hasattr(t, 'is_real'):
                t._assumptions['real'] = False


def wrap_templates(name):
    from satassume.knowledge.templates import registry
    from satassume.knowledge.templates._common import Compiled
    memo = {}
    calls = [0, 0]

    def report():
        print('plant', name, 'calls', calls[0], 'pattern swapped', calls[1], flush=True)
    atexit.register(report)

    def plant(f):
        def g(expr):
            c = f(expr)
            if name in ('stale', 'stale2'):
                pat = memo.setdefault(str(expr) if name == 'stale' else type(expr), c.pattern)
                calls[0] += 1
                calls[1] += pat.clauses != c.pattern.clauses
                return Compiled((expr,), pat)
            c.pattern.clauses = sorted(c.pattern.clauses, key=lambda x: hash(str(x)))
            return c
        for k in ('__name__', '__qualname__', '__module__'):
            setattr(g, k, getattr(f, k))
        g.__wrapped__ = f.__wrapped__
        g.__dict__.update(f.__dict__)
        return g
    for ts in registry._by_class.values():
        ts[:] = [plant(t) if t.__name__ in ('symbol_units', 'constant_units') else t for t in ts]
    registry._mro_cache.clear()
    registry._clauses_cache.clear()
