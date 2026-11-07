"""`atoms.value_units` from Rust (component 6, issue 323): its counters fire, it agrees with Python field by field, it leaves the
lazy modules lazy, and section 9's offline table holds what `_value_units` computes. That last test is for `functions.py`'s port:
nothing reads the table at query time yet.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pytest
from sympy import Integer, Q, Rational, S, Symbol, genocchi, multigamma

from harness.state import reset_module_state
from satassume import engine as E
from satassume import sympy_api
from satassume.knowledge.templates import atoms, functions, wiring

import knowledge_live as K

LIMIT = functions.MAX_VALUE_ARG
FIELDS = K.FIELDS


@pytest.fixture
def live():
    K.COUNTS.clear()
    K.MISMATCHES.clear()
    undo = K.install(shadow=True)
    yield K.COUNTS
    undo()
    reset_module_state(sympy_cache=False)


def ask(p, a=True):
    reset_module_state(sympy_cache=False)
    sympy_api.set_default_engine(E.Engine())
    return sympy_api.ask(p, a)


def test_a_derived_value_goes_through_rust(live):
    assert ask(Q.positive(genocchi(8, evaluate=False))) is True
    assert ask(Q.negative(genocchi(6, evaluate=False))) is True
    assert live['value:derived'] == 2
    assert live['shadow:compared'] == 2 and not live['shadow:mismatch'], K.MISMATCHES


def test_a_value_that_is_an_input_term_reads_it(live):
    ask(Q.positive(genocchi(8, evaluate=False) + 17))
    assert live['value:input'] == 1 and live['read:constant'] >= 1
    assert not live['shadow:mismatch'], K.MISMATCHES


def test_multigamma_goes_through_rust(live):
    ask(Q.integer(multigamma(Integer(1), 3, evaluate=False)))
    ask(Q.integer(multigamma(Rational(1, 2), 3, evaluate=False)))
    assert live['value:derived'] + live['value:input'] >= 1
    assert not live['shadow:mismatch'], K.MISMATCHES


def test_above_the_limit_no_value_is_read(live):
    assert functions._value_units(Integer(LIMIT + 1), genocchi(LIMIT + 1, evaluate=False)) == []
    ask(Q.positive(genocchi(LIMIT + 2, evaluate=False)))
    assert not live['value:derived'] and not live['value:input']
    # Below it the same query reads one, so this zero can fire.
    ask(Q.positive(genocchi(LIMIT, evaluate=False)))
    assert live['value:derived'] == 1


def test_with_no_query_python_answers(live):
    n = genocchi(8, evaluate=False)
    c = functions.value_units(Integer(17), n)
    assert live['py:no-query'] == 1 and c.objs == (n,)


def test_shadow_sees_a_wrong_value(live):
    """So the zeros above mean something: Rust's pattern for the wrong value, against Python's for the right one."""
    wrong = K._wrap(sa_solver_units(Integer(-17)))
    right = atoms.value_units.__wrapped__(Integer(17), Symbol('n')).pattern
    K._compare('value', Integer(17), wrong, right)
    assert live['shadow:mismatch'] >= 1


def sa_solver_units(v):
    import sa_solver
    import satassume
    import sympy
    off = sa_solver.OfflineData(os.path.join(HERE, 'offline_data.json'),
                                os.path.dirname(os.path.dirname(os.path.abspath(satassume.__file__))), sympy.__version__)
    return sa_solver.Knowledge(off).units(K._derived_facts(None, v, False))


def values():
    for fn in wiring.VALUE_AT_INTEGER:
        for n in range(-LIMIT, LIMIT + 1):
            yield fn, n, functions._value_units(Integer(n), fn(n, evaluate=False))


def test_every_value_in_range_matches_python_by_field():
    """The patterns of every value `_value_units` can reach. No query: `kn.units` against Python's `units`, whole."""
    py_value = getattr(atoms.value_units, '__wrapped__', atoms.value_units)
    seen = {}
    n_values = 0
    for fn in wiring.VALUE_AT_INTEGER:
        for n in range(-LIMIT, LIMIT + 1):
            try:
                v = fn(Integer(n))
            except (ValueError, TypeError, ArithmeticError):
                continue
            if not (v.is_Atom and v.is_number) or v is S.NaN:
                continue
            n_values += 1
            facts = tuple(K._derived_facts(None, v, False))
            if facts in seen:
                continue
            seen[facts] = v
            ours, theirs = K._wrap(sa_solver_units(v)), py_value(v, Symbol('n')).pattern
            for f in FIELDS:
                assert getattr(ours, f) == getattr(theirs, f), (fn, n, f)
    assert n_values > 1000 and len(seen) >= 3


def test_offline_table_holds_what_value_units_computes():
    """Section 9's table against today's `_value_units`, every row. A null row must be Python's `[]`."""
    with open(os.path.join(HERE, 'offline_data.json')) as fh:
        lines = [json.loads(line) for line in fh]        # one JSON document per line: a header, then the sections
    data = next(d['value_units'] for d in lines if 'value_units' in d)
    assert data['range'] == LIMIT
    py_value = getattr(atoms.value_units, '__wrapped__', atoms.value_units)
    for fn, n, got in values():
        row = data['rows'][fn.__name__][n + LIMIT]
        if row is None:
            assert got == [], (fn, n)
            continue
        assert len(got) == 1, (fn, n)
        expected = py_value(fn(Integer(n)), Symbol('n')).pattern
        from_table = K._wrap(sa_solver_units_of([tuple(f) for f in data['fact_sets'][row]]))
        for f in FIELDS:
            assert getattr(from_table, f) == getattr(expected, f), (fn, n, f)


def sa_solver_units_of(facts):
    import sa_solver
    import satassume
    import sympy
    off = sa_solver.OfflineData(os.path.join(HERE, 'offline_data.json'),
                                os.path.dirname(os.path.dirname(os.path.abspath(satassume.__file__))), sympy.__version__)
    return sa_solver.Knowledge(off).units(facts)


LAZY = """
import sys
import knowledge_live as K
from satassume.knowledge.templates import atoms
SPECIAL = 'satassume.knowledge.templates.special'
assert SPECIAL not in sys.modules
py = atoms.value_units
undo = K.install()
assert SPECIAL not in sys.modules, 'install imported a lazy module'
assert atoms.value_units is not py
from satassume.knowledge.templates import registry
from sympy import multigamma
registry.templates_for(multigamma)
m = sys.modules[SPECIAL]
assert m.value_units is atoms.value_units, 'a caller imported after install took Python'
undo()
assert atoms.value_units is py and m.value_units is py, 'undo left Rust bound'
print('ok')
"""


def test_install_keeps_the_callers_lazy_and_undo_restores():
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([HERE, os.environ.get('PYTHONPATH', '')]))
    r = subprocess.run([sys.executable, '-c', LAZY], env=env, capture_output=True, text=True, cwd=HERE)
    assert r.returncode == 0 and r.stdout.strip() == 'ok', r.stderr
