"""The `_CACHE` fix (issue 323, the planner's ruling of 10 Nov ~12:53): knowledge_live's atom templates read and fill
`_common._CACHE` under Python's keys (common.rs `atom_pattern`), so both backends hold one pattern per key and `_SPLIT`
(keyed on `id(pattern.clauses)`) gets no second copy. And the question carried with it: the cache key determines the
cached value, whichever call filled the entry (cache_det.py), with plant 664 as the entry that depends on history.
Also here: `memos.PROCESS.clear()` empties Rust's per-node memo with Python's (plant 665), or `_CACHE` stays short of keys.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pytest
from sympy import Integer, Q, Symbol, genocchi, pi

from harness.state import reset_module_state
from satassume import engine as E
from satassume import sympy_api
from satassume.knowledge.templates import _common, atoms

import cache_det
import knowledge_common_live
import knowledge_live as K

FIELDS = K.FIELDS
X = Symbol('x', positive=True)
Z = Symbol('z', positive=True)          # X's key
Y = Symbol('y', negative=True)          # the same assumption names as X's, other values
G = genocchi(8, evaluate=False)         # its value, 17, is read as a constant's
QUERIES = [Q.positive(X + 3), Q.positive(Z + 3), Q.positive(pi), Q.positive(G), Q.negative(Y * pi)]
KEY_X = ('symbol', frozenset(X.assumptions0.items()))
KEY_PI = ('const', (type(pi), pi))
KEY_17 = ('const', (Integer, Integer(17)))


def fresh():
    reset_module_state(sympy_cache=False)
    sympy_api.set_default_engine(E.Engine())


def atom_rows():
    """`_CACHE`'s atom entries: key -> the pattern's fields."""
    return {k: tuple(getattr(p, f) for f in FIELDS) for k, p in _common._CACHE.items()
            if type(k) is tuple and k[0] in ('symbol', 'const')}


def run(queries):
    fresh()
    answers = [sympy_api.ask(q) for q in queries]
    return answers, atom_rows(), len(E._SPLIT)


@pytest.fixture
def python_rows():
    return run(QUERIES)


def install(plant=None):
    K.COUNTS.clear()
    K.PLANT[0] = plant
    undo_k = K.install()
    undo_det = cache_det.install()
    cache_det.STATE['hits'].clear(), cache_det.STATE['mismatch'].clear()

    def undo():
        undo_det()
        undo_k()
        K.PLANT[0] = None
        reset_module_state(sympy_cache=False)
    return undo


@pytest.fixture
def live():
    undo = install()
    yield knowledge_common_live.COMMON[0]
    undo()


def test_rust_fills_the_cache_under_pythons_keys_with_pythons_values(python_rows, live):
    answers, rows, split = run(QUERIES)
    assert set(rows) >= {KEY_X, KEY_PI, KEY_17} and len(rows) == 4
    assert (answers, rows, split) == python_rows          # the keys, each pattern field by field, and `_SPLIT`'s row count
    c = live.counts()
    assert c['common:atom:miss'] == 4 and c['common:atom:hit'] == 1, dict(c)       # Z is served X's pattern


def test_one_pattern_per_key_and_one_split_row(live):
    fresh()
    sympy_api.ask(QUERIES[0])
    p, n = _common._CACHE[KEY_X], len(E._SPLIT)
    sympy_api.ask(QUERIES[1])
    assert _common._CACHE[KEY_X] is p
    # `_SPLIT` is keyed on `id(pattern.clauses)`: Z's rows are X's, as on Python (before the fix, one more per call)
    undo = K._UNDO[0]
    assert undo is not None
    rust = len(E._SPLIT) - n
    undo()
    try:
        fresh()
        sympy_api.ask(QUERIES[0])
        n = len(E._SPLIT)
        sympy_api.ask(QUERIES[1])
        assert rust == len(E._SPLIT) - n
    finally:
        K.install()


def test_either_filler_gives_the_same_pattern(python_rows, live):
    """Python's template first and then Rust's, and the other way round: one entry, the same fields, Python's."""
    out = []
    for python_first in (True, False):
        fresh()
        if not python_first:
            sympy_api.ask(QUERIES[0]), sympy_api.ask(QUERIES[2])
        a = atoms.symbol_units(X).pattern                  # Python's template (the registry holds Rust's), Python's key
        b = atoms.value_units.__wrapped__(pi, pi).pattern
        if python_first:
            sympy_api.ask(QUERIES[0]), sympy_api.ask(QUERIES[2])
        assert _common._CACHE[KEY_X] is a and _common._CACHE[KEY_PI] is b
        out.append(atom_rows())
    assert out[0] == out[1] == {k: python_rows[1][k] for k in (KEY_X, KEY_PI)}
    assert live.counts()['common:atom:hit'] == 2           # Rust was served Python's two


def test_every_hit_builds_what_the_table_holds(live):
    fresh()
    for q in QUERIES:
        sympy_api.ask(q)
    K.DISPATCH[0].clear_memos()                            # the per-node results go; `_CACHE` stays, so every atom is a hit
    sympy_api.set_default_engine(E.Engine())
    for q in QUERIES:
        sympy_api.ask(q)
    t = cache_det.totals()
    assert t['hits'].get('symbol', 0) >= 3 and t['hits'].get('constant', 0) >= 1 and t['hits'].get('value', 0) >= 1, t
    assert not t['mismatch'], t                            # and that zero can fire: plant 664 below


def test_plant_664_an_entry_that_depends_on_history_is_caught():
    """Plant 664 `atom-symbol-key-names`: a symbol's key without its values, so B is served A's pattern when A came first."""
    a, b = Symbol('a', prime=True), Symbol('b', composite=True)
    assert set(a.assumptions0) == set(b.assumptions0)
    queries = [Q.prime(a), Q.prime(b)]
    python = run(queries)
    undo = install()
    try:
        assert run(queries) == python and not cache_det.totals()['mismatch']
    finally:
        undo()
    undo = install('atom-symbol-key-names')
    try:
        answers, rows, _ = run(queries)
        t = cache_det.totals()
        fired = knowledge_common_live.COMMON[0].counts().get('plant:fired', 0)
    finally:
        undo()
    assert fired > 0
    assert t['mismatch'].get('symbol', 0) >= 1, t          # the probe: B's own build is not what the table holds
    assert rows != python[1] and len(rows) == 1            # the table against Python's two entries
    assert python[0] == [True, False] and answers == [True, True]      # and an answer


def test_a_memo_clear_empties_rusts_node_memo_too(python_rows, live):
    """`reset_module_state` empties `_CACHE` and Python's `registry._clauses_cache`. Rust's memo of compiled nodes goes
    with them, so the next query fills `_CACHE` again as Python's does."""
    run(QUERIES)
    assert run(QUERIES) == python_rows
    assert K.DISPATCH[0].counts()['registry:memos-clear'] >= 2


def test_plant_665_a_node_memo_that_outlives_the_clear_is_caught(python_rows):
    undo = install('dispatch-keeps-memo')
    try:
        run(QUERIES)
        _, rows, _ = run(QUERIES)
        fired = K.DISPATCH[0].counts().get('plant:fired', 0)
    finally:
        undo()
    assert fired > 0 and rows != python_rows[1] and len(rows) < 4
