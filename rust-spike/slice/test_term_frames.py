"""term_live's per-query frames on Rust (term/live.rs, SLICE_TERM_FRAMES=rust; issue 323, the term_live step).

Each check asserts behaviour of one moved site (`current`, `term_id`, `_ids`, `_relation_atom`'s `run`, `_guarded`'s
wrapper, `_Mark`'s init) and reads no plant flag. A check runs in its own process (`python test_term_frames.py CHECK
py|rust`), on Python's frames and on Rust's, and must hold on both. Plants 740-745 (`SLICE_TERM_PLANT=tl-*`, in the Rust
frames) are each run under the check named in CAUGHT, which must then fail on an assertion.

Run from this directory by plain pytest.
"""
import collections
import os
import subprocess
import sys

import pytest

CHECKS = {}
#: plant -> the check that catches it
CAUGHT = {
    'tl-term-stale': 'a_term_table_dies_with_its_query',        # 740, term_id
    'tl-ids-reversed': 'relation_atoms_match_python',           # 741, _ids
    'tl-current-outer': 'current_is_the_innermost_query',       # 742, current
    'tl-run-flip': 'relation_atoms_match_python',               # 743, run
    'tl-guard-quiet': 'a_fault_is_no_ordinary_exception',       # 744, the guard
    'tl-mark-skip': 'the_mark_matches_python_and_rolls_back',   # 745, _Mark._note
}


def check(f):
    CHECKS[f.__name__] = f
    return f


def _setup(frames):
    import term_live
    plant = os.environ.get('SLICE_TERM_PLANT')      # as term_live.from_env sets it
    term_live.PLANT[0] = term_live._Plant(plant) if plant else None
    term_live.use_rust(frames == 'rust')
    assert (term_live.FRAMES[0] is not None) == (frames == 'rust')
    return term_live


def _conv(tl, *terms):
    from sympy import And, Q
    from satassume import sympy_api as A
    return tl._convert(And(*[Q.positive(t) for t in terms]), True, A.default_engine())


@check
def current_is_the_innermost_query(tl):
    from sympy import Symbol
    x, y = Symbol('x'), Symbol('y')
    assert tl.current() is None
    q1, q2 = _conv(tl, x + 1), _conv(tl, y + 2)
    s = tl.stack()
    s.append(q1)
    assert tl.current() is q1
    s.append(q2)
    try:
        assert tl.current() is q2
    finally:
        s.pop()
        s.pop()
    assert tl.current() is None


@check
def relation_atoms_match_python(tl):
    from sympy import S, Symbol, oo
    from satassume import relations as R
    x, y = Symbol('x'), Symbol('y')
    undo = tl.install(terms=True)
    try:
        for a, b in [(x, y), (y, x), (x + 1, y), (2*x, S(1)), (oo, x), (x, 2*y + 1)]:
            q = _conv(tl, a, b)
            tl.stack().append(q)
            try:
                i, j = tl.term_id(q, a, 't'), tl.term_id(q, b, 't')
                assert i is not None and j is not None and tl._ids(q, 't', a, b) == [i, j]
                for name in ('eq', 'ne', 'lt', 'gt', 'le', 'ge'):
                    got, want = R.relation_atom(name, a, b), R.relation_atom.__wrapped__(name, a, b)
                    assert got == want and repr(got) == repr(want), (name, a, b, got, want)
            finally:
                tl.stack().pop()
        assert tl.COUNTS['term:rust:relation_atom'] >= 36
        assert R.relation_atom('lt', x, y) == R.relation_atom.__wrapped__('lt', x, y)      # no query: Python's
    finally:
        undo()


@check
def a_term_table_dies_with_its_query(tl):
    from sympy import Symbol
    x, y, z = Symbol('x'), Symbol('y'), Symbol('z')
    t = x + 3       # a term Python builds: no input row in either query
    q1 = _conv(tl, x)
    i1 = tl.term_id(q1, t, 't')
    assert i1 >= q1.table.n_input and tl.scaffold(q1, i1, 't') == t
    q2 = _conv(tl, x, y, z, y*z, y + z, x*y, x*z + y)
    assert q2.table.n_input > i1        # so the first query's id is another term's row here
    i2 = tl.term_id(q2, t, 't')
    assert i2 >= q2.table.n_input and q2.derived[t] == i2 and tl.scaffold(q2, i2, 't') == t
    assert all(o.items() == [] for o in tl.NATIVE_EXTRA if o.name == 'term.live.STALE')


@check
def frames_match_python(tl):
    """Rust's `term_id` and `_ids` against Python's own on a twin query: the same ids, maps and counts."""
    from sympy import Float, Integer, S, Symbol, pi
    x, y = Symbol('x'), Symbol('y')
    n = Symbol('n', commutative=False)
    terms = [x, y, x + 1, 2*x, x + y + pi, S(1)/2, Integer(2), Float(2.0), 1, True, 'a', n*x, x**2, 2*(x + 1), x + 3, 7]
    out = []
    for term_id, ids in ((tl.term_id, tl._ids), (tl._PY_FRAMES['term_id'], tl._PY_FRAMES['_ids'])):
        q = _conv(tl, x + 1, 2*y, Integer(2) + x)
        before = collections.Counter(tl.COUNTS)
        got = [term_id(q, e, site) for site in ('key', 't') for e in terms]
        got.append(ids(q, 't', x, y, x + 1))
        got.append(ids(q, 't', x, 'a'))
        got.append(ids(None, 't', x))
        delta = collections.Counter(tl.COUNTS)
        delta.subtract(before)
        out.append((got, dict(q.derived), dict(q.rev), dict(q.ints), dict(q.int_ids), {k: v for k, v in delta.items() if v}))
    assert out[0] == out[1]
    assert out[0][0][0] is not None and out[0][5]['term:learned'] >= 1


class _Stop(BaseException):
    pass


@check
def a_fault_is_no_ordinary_exception(tl):
    def bad(a, b=0):
        return a / b

    def stop():
        raise _Stop()
    g = tl._guarded('site', bad)
    assert g(6, b=3) == 2 and g.__wrapped__ is bad
    n = tl.COUNTS['fault']
    try:
        g(1)
    except tl.TermFault as e:
        assert str(e) == 'site: ZeroDivisionError: division by zero' and isinstance(e.__cause__, ZeroDivisionError)
        assert not isinstance(e, Exception) and tl.COUNTS['fault'] == n + 1
    except Exception as e:
        raise AssertionError(f'an ordinary exception came out, for a quiet handler to read: {e!r}')
    else:
        raise AssertionError('nothing raised')
    with pytest.raises(_Stop):
        tl._guarded('site', stop)()
    assert tl.COUNTS['fault'] == n + 1


@check
def the_mark_matches_python_and_rolls_back(tl):
    from satassume import sympy_api as A
    from satassume.theories.lra import constfield
    from sympy import Q, Symbol
    x = Symbol('x')
    A.ask(Q.positive(x + 1), Q.positive(x))     # so the memos hold something
    eng = A.default_engine()
    m, p = tl._new_mark(eng), tl._Mark(eng)
    assert type(m) is tl._Mark and len(p.tables) > 3
    assert list(m.tables) == list(p.tables) and list(m.natives) == list(p.natives)
    assert list(m.engines) == list(p.engines) and list(m.facts) == list(p.facts) and m.cache == p.cache == []
    assert m.cache_n == p.cache_n
    for k, (t, size, stamp, last) in p.tables.items():
        t2, size2, stamp2, last2 = m.tables[k]
        assert t2 is t and size2 == size and stamp2 is stamp and last2 is last
    for k, (e, mark, constructing) in p.engines.items():
        assert m.engines[k][0] is e and m.engines[k][2] == constructing
    tl._mark_add(m, eng)
    assert list(m.engines) == list(p.engines)
    t = constfield._BY_KEY
    size = len(t)
    t['__test_term_frames__'] = 1
    m.rollback()
    assert '__test_term_frames__' not in t and len(t) == size


def run(name, frames, plant=None):
    env = dict(os.environ)
    env.pop('SLICE_TERM_PLANT', None)
    if plant:
        env['SLICE_TERM_PLANT'] = plant
    return subprocess.run([sys.executable, os.path.abspath(__file__), name, frames], env=env, capture_output=True, text=True,
                          cwd=os.path.dirname(os.path.abspath(__file__)))


@pytest.mark.parametrize('frames', ['py', 'rust'])
@pytest.mark.parametrize('name', sorted(CHECKS))
def test_the_check_holds(name, frames):
    r = run(name, frames)
    assert r.returncode == 0, r.stderr[-3000:]


@pytest.mark.parametrize('plant,name', sorted(CAUGHT.items()))
def test_the_plant_is_caught(plant, name):
    r = run(name, 'rust', plant)
    assert r.returncode != 0 and ('AssertionError' in r.stderr or 'DID NOT RAISE' in r.stderr), r.stderr[-3000:]
    assert run(name, 'py', plant).returncode == 0       # the plant sits in the Rust frames only


if __name__ == '__main__':
    CHECKS[sys.argv[1]](_setup(sys.argv[2]))
