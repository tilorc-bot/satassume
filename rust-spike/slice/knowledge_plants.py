"""knowledge_plants.py: bugs planted on purpose, for showing the history and discard compares can fire. A zero from a compare that can't fire says nothing.

Each is a run of knowledge_fresh with `--plant NAME`, compared with its plain row:
  noncomm  discard mode: conversion leaves a wrong `_NONCOMM` entry behind.
  facts    discard mode: conversion leaves a wrong `_assumptions` entry on a compound input term.
  stale    atoms mode: a cross-query memo of patterns keyed by printed name; clears nothing between queries. Should move with order.
  hash     atoms mode: clause order follows the string hash. Should move with PYTHONHASHSEED.
"""


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

    def plant(f):
        def g(expr):
            c = f(expr)
            if name == 'stale':
                return Compiled((expr,), memo.setdefault(str(expr), c.pattern))
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
