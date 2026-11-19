"""Diagnostic only: after each test, say why satassume.witness would fall through for a fresh engine."""
import os
OUT = os.environ['WPROBE_OUT']
last = [None]

def reason():
    from satassume import witness as W
    from satassume import sympy_api as A
    eng = A.Engine()
    r = []
    if W._DEFAULT._handlers: r.append('default handlers %s' % sorted(map(str, W._DEFAULT._handlers))[:4])
    if W._DEFAULT._vocab: r.append('default vocab %s' % sorted(map(str, W._DEFAULT._vocab))[:4])
    if eng.clause_templates is None: r.append('clause_templates None')
    reg = getattr(eng._templates, '__self__', None)
    bc, lz = getattr(reg, '_by_class', None), getattr(reg, '_lazy', None)
    if bc is None or lz is None:
        r.append('no registry')
    else:
        for spec in eng._relation_specs:
            m = str(getattr(spec.factory, '__module__', ''))
            if not m.startswith(W._THEORIES): r.append('spec %s %s' % (spec.name, m))
        for c, m in lz:
            if not m.startswith(W._TEMPLATES): r.append('lazy %s %s' % (getattr(c, '__name__', c), m))
        for c, ts in bc.items():
            for t in ts:
                m = str(getattr(t, '__module__', ''))
                if not m.startswith(W._TEMPLATES): r.append('template %s %s.%s' % (getattr(c, '__name__', c), m, getattr(t, '__name__', t)))
    if eng.extensions is not None and (eng.extensions._handlers or eng.extensions._vocab): r.append('engine extensions')
    if W._patched(eng):
        cls = type(eng)
        r.append('patched %s' % [(n, getattr(getattr(cls, n, None), '__module__', None), getattr(getattr(cls, n, None), '__qualname__', None)) for n in W.GUARDED if not any(getattr(cls, n, None) is g for g in W.ACCEPTED[n])])
    return tuple(r)

def pytest_runtest_logfinish(nodeid, location):
    try:
        r = reason()
    except Exception as e:
        r = ('probe error %r' % (e,),)
    if r != last[0]:
        last[0] = r
        with open(OUT, 'a') as f:
            f.write('%s\t%s\n' % (nodeid, ' | '.join(r) or 'clear'))
