"""B's item (1), refuse:object (sa-port-290): a formula holding two `==` but distinct objects for one node with no visit used
to refuse in Rust (`refuse:object`), and Python compiled it. Now Rust compiles it: conversion notes each atom's own object
and compiling, when it takes an atom's variable, gives the node that object (session.rs `reach`), as Python's compiler
passes it: the slot keeps the first object compiling reaches (R1: the first occurrence in the query's input, in Python's
compile order), and a node's visit takes the atom's own.

Kept test (planner's condition (b)): the twin objects in both orders, in several shapes, plus test_session_limits.py's
formula cases; which object the slot holds, which each visit got, and the clauses, Python against Rust.
Plant 624 `occ-walk-first`: `reach` does nothing, so a node keeps the object conversion walked to first. Caught by the
comparison with Python (not by the plant's counter)."""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _twin_cases():
    import test_session_limits as L
    from sympy import Symbol
    from satassume.sat.formula import ITE, And, Equivalent, Exclusive, Implies, Not, Or, P
    z = Symbol('z')
    shapes = {
        'and': lambda a, b: And(P('positive', a), P('real', b)),
        'and-basis-first': lambda a, b: And(P('real', a), P('positive', b)),
        'or': lambda a, b: Or(P('positive', a), P('negative', b), P('real', z)),
        'or-def': lambda a, b: Or(And(P('positive', a), P('nonzero', b)), P('real', z)),
        'or-def-second': lambda a, b: Or(P('real', z), And(P('nonzero', b), P('positive', a))),
        'not-and': lambda a, b: Not(And(P('positive', a), P('integer', b))),
        'implies': lambda a, b: Or(Not(P('positive', a)), P('real', b)),
        'implies-node': lambda a, b: Implies(P('positive', a), P('real', b)),
        'ite': lambda a, b: ITE(P('real', z), P('positive', a), P('negative', b)),
        'equiv': lambda a, b: Equivalent(P('positive', a), P('real', b)),
        'xor': lambda a, b: Exclusive(P('positive', a), P('real', b), P('real', z)),
        'or-of-ands': lambda a, b: Or(And(P('real', z), P('positive', a)), And(P('positive', b), P('nonzero', b))),
        'or-cost': lambda a, b: Or(And(P('real', z), P('integer', z), P('positive', a)), And(P('nonzero', b), P('positive', b))),
        'and-or': lambda a, b: And(Or(P('real', z), P('positive', a)), P('negative', b)),
        # a custom atom takes no slot, so the walk's first object isn't the one the slot keeps
        'custom-first': lambda a, b: Or(P('mine', a), P('real', b)),
        'custom-first-and': lambda a, b: And(P('mine', a), P('positive', b), P('mine', b)),
        'custom-not-or': lambda a, b: Or(P('mine', a), Not(Or(P('even', b), P('integer', a)))),
    }
    out = {}
    for first in (0, 1):
        for k, shape in shapes.items():
            out[f'assume:{k}:{first}'] = L._object_case(first, lambda s, a, b, shape=shape: s.assume_formula(shape(a, b)))
            out[f'literal:{k}:{first}'] = L._object_case(first, lambda s, a, b, shape=shape: s.literal_of(shape(a, b)))
    return out


def _kept_formula_swapped(seed):
    """test_session_limits.py's `kept:formula:<seed>` with the two tagged objects of each node swapped: the other order."""
    def run(s):
        import random
        import satassume.engine as E
        import test_session_limits as L
        t, old = L._tagged(), L._tagged
        swapped = t[2:] + t[:2]
        L._tagged = lambda: swapped
        try:
            f = L._random_formula(random.Random(seed), 3)
        finally:
            L._tagged = old
        E.compile_formula(f, s.table, s.emit, s.dvar)
        return L._kept(s)
    return run


def _cases():
    import test_session_limits as L
    out = _twin_cases()
    out.update({f'kept:formula:{i}': L._kept_formula(i) for i in range(120)})
    out.update({f'kept:swapped:{i}': _kept_formula_swapped(i) for i in range(120)})
    out.update({k: v for k, v in L._object_rule_cases().items()
                if k.split(':')[1] in ('assume', 'assume-and', 'literal_of', 'formula', 'formula-two')})
    return out


def _main(mode):
    import test_session_limits as L
    live = None
    if mode != 'py':
        live = L._rust()
        if mode == 'plant':
            import sa_solver
            sa_solver.formula_plant('occ-walk-first')
    c0 = dict(live.counts()) if live else {}
    got = {k: L._case(fn) for k, fn in _cases().items()}
    c1 = dict(live.counts()) if live else {}
    counts = {k: c1.get(k, 0) - c0.get(k, 0) for k in ('refuse:object', 'occ:reach', 'occ:two')} if live else None
    json.dump(dict(cases=got, counts=counts), sys.stdout)


def _run(mode):
    e = dict(os.environ, PYTHONPATH=os.pathsep.join([HERE, os.environ.get('PYTHONPATH', '')]), PYTHONHASHSEED='0')
    e.pop('SLICE_SESSION_PLANT', None)
    r = subprocess.run([sys.executable, __file__, mode], capture_output=True, text=True, env=e, cwd=HERE)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout)


def test_rust_holds_the_object_python_holds_with_no_refusal():
    py, rust = _run('py'), _run('rust')
    assert set(py['cases']) == set(rust['cases'])
    bad = [k for k in py['cases'] if py['cases'][k] != rust['cases'][k]]
    assert not bad, bad[:5]
    assert rust['counts']['refuse:object'] == 0, rust['counts']
    # the counters fire: these formulas hold a second object (occ:two), and compiling reaches one first (occ:reach)
    assert rust['counts']['occ:two'] > 0 and rust['counts']['occ:reach'] > 0, rust['counts']
    # the twin cases take the same slot in both orders (the first in compile order, named by position); the tagged
    # formulas tell the order apart: the swapped formula's slots hold the other tag
    seen = {(py['cases'][f'kept:formula:{i}']['out'][1], py['cases'][f'kept:swapped:{i}']['out'][1]) for i in range(120)}
    assert any(a != b for a, b in seen)


def test_plant_624_is_caught_by_the_comparison():
    py, planted = _run('py'), _run('plant')
    bad = [k for k in py['cases'] if py['cases'][k] != planted['cases'][k]]
    # caught in both orders
    assert any(k.startswith('kept:formula:') for k in bad) and any(k.startswith('kept:swapped:') for k in bad), bad


if __name__ == '__main__':
    _main(sys.argv[1])
