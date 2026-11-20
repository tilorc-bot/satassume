"""The Rust walker against `_Walk` (issue 323, the convert step): `convert.convert` on the same input objects under
Python's walker and under Rust's gives the same thing, item by item.

"The same" (`convert_diff.diff`, the differential test's own comparison): the same `Kept` reason and detail, or the
same exception type and message, or tables equal token for token and type for type (strings, class rows, term rows,
powers, settings, formula, the counts), `ids` holding the same objects under the same ids in the same order (the first
occurrence kept: ruling R1), `objects` and `classes` the same objects, and every lazy read of every term answering
alike afterwards (tokens, strings, counts, `raised`), each walker's reads asked in fresh state: a forked child each.
Each item of `convert.RUST_ITEMS` is checked alone (the rest on Python) and all together.

Plants 670-674 (`SLICE_CONVERT_PLANT`, one per item, each a wrong value at one site of walk.rs): the comparison, which
reads nothing of the plant, finds differences under each. As a script: prints `{"inputs": n, "differences": d}` for
the items in SLICE_CONVERT_ITEMS (default: all).

Bit 32 of a term row's flags (the old F_MAYBE_NAN) is reserved: `test_reserved_bit_is_zero` holds both walkers to 0
there, on inputs where `_may_be_nan` is True. Plants 746-748 and `nan_cases` went with the bit.
"""
import json
import os
import subprocess
import sys

import pytest
from sympy import (Add, Basic, Dummy, Float, Function, I, Integer, Integral, MatrixSymbol, Mul, Piecewise, Pow, Q, Rational,
                   S, Subs, Sum, Symbol, Wild, cos, exp, log, nan, oo, pi, sin, sqrt, zoo)
from sympy.core.expr import Expr

import convert
from convert_diff import diff
from satassume import engine as E

HERE = os.path.dirname(os.path.abspath(__file__))
x, y, z = Symbol('x'), Symbol('y'), Symbol('z')
p = Symbol('p', positive=True)
n = Symbol('n', commutative=False)
f, g = Function('f'), Function('g')
ALL_PLANTS = {670: ('enc-true-as-false', 'enc'), 671: ('klass-no-is-expr', 'klass'), 672: ('term-row-no-number', 'term_row'),
          673: ('walk-args-unreversed', 'walk'), 674: ('enc-int-no-sign', 'enc_int'),
          768: ('calls-structural-not', 'klass,klass_calls'), 769: ('power-rows-drop-last', 'power_rows'),
          770: ('read-commutative-not', 'read'), 771: ('entry-no-assumptions', 'entry')}
# An item's plant, once it's ported. `klass_calls` acts inside Rust's `klass`, so its plant runs with both.
PLANTS = {k: v for k, v in ALL_PLANTS.items() if all(i in convert.RUST_ITEMS for i in v[1].split(','))}


class Content(Expr):
    """Hashable content `.args` doesn't reach: every kind of value `enc` tells apart."""
    def __new__(cls, *args, extra=()):
        obj = Expr.__new__(cls, *args)
        obj.extra = extra
        return obj

    def _hashable_content(self):
        return self._args + tuple(self.extra)


class IntSub(int):
    pass


class StrSub(str):
    pass


class NoKey(Expr):
    @classmethod
    def class_key(cls):
        raise ValueError('no key')


class BadArgs(Expr):
    @property
    def args(self):
        return (x, 3)


class ListArgs(Expr):
    @property
    def args(self):
        return [x, y, x + y]


OPAQUE = object()


def inputs():
    out = [
        (Q.positive(x), True), (Q.positive(x + y), Q.positive(x) & Q.positive(y)),
        (Q.real(x * y), Q.real(x) & Q.real(y)), (Q.zero(x * y), Q.zero(x) | Q.zero(y)),
        (Q.positive(x**2 + 1), Q.real(x)), (Q.negative(-p), True), (Q.integer(x + Rational(1, 2)), Q.integer(x)),
        (Q.positive(exp(x)), Q.real(x)), (Q.positive(sqrt(x)), Q.positive(x)), (Q.real(log(x)), Q.positive(x)),
        (Q.positive(f(x)), Q.positive(f(x))), (Q.positive(f(g(x), y)), Q.positive(g(x))),
        (Q.commutative(n * x), True), (Q.positive(pi + S.Exp1), True), (Q.real(I * x), Q.imaginary(x)),
        (Q.finite(x + oo), Q.finite(x)), (Q.positive(nan), True), (Q.positive(zoo * x), True),
        (Q.positive(Float('1.5') * x), Q.positive(x)), (Q.positive(x**y), Q.positive(x) & Q.real(y)),
        (Q.positive(x**Rational(1, 3)), Q.positive(x)), (Q.gt(x, y), Q.gt(x, 0) & Q.lt(y, 0)),
        (x > y, (x > 1) & (y < 0)), (Q.positive(x) >> Q.real(x), True), (~Q.positive(x), Q.negative(x)),
        (Q.positive(Integer(2)**70 * x), Q.positive(x)), (Q.positive(x - 2**63), True), (Q.positive(x + 2**63 - 1), True),
        (Q.positive(x - (2**63 - 1)), True), (Q.positive(x + 2**63), True), (Q.positive(Rational(-2**64, 3) * x), True),
        (Q.positive(Sum(x, (x, 1, 3))), True), (Q.positive(Integral(x, x)), True),
        (Q.positive(Dummy('d') + Wild('w')), True), (Q.positive(MatrixSymbol('M', 2, 2)), True),
        (Q.positive(Piecewise((x, x > 0), (y, True))), Q.positive(y)), (Q.positive(sin(x)**2 + cos(x)**2), Q.real(x)),
        (Q.positive(Add(Float(1.0), Float(1.0), evaluate=False)), True),
        (Q.positive(Mul(x, Pow(x, -1, evaluate=False), evaluate=False)), Q.nonzero(x)),
        (Q.positive(Content(x, extra=(1, -7, 2**80, -2**63, 'name', None, True, False, (1, ('a', (x + y,))), Rational(3, 4)))), True),
        (Q.positive(Content(x, extra=(IntSub(5), StrSub('s'), 1.5, OPAQUE, IntSub(-2**70)))), True),
        (Q.positive(Content(x, extra=(1, [1]))), True),
        (Q.positive(Content(y, extra=(z + 1, f(z)))), True), (Q.positive(NoKey(x)), True),
        (Q.positive(BadArgs()), True), (Q.positive(ListArgs()), True), (Q.positive(x), 5), (5, True), (True, True),
        (Q.positive(x), Q.positive(x) & Q.real(Content(z, extra=(OPAQUE, OPAQUE)))),
    ]
    e = x
    for _ in range(40):
        e = f(e + 1)
    out.append((Q.positive(e), Q.positive(x)))
    return out


def outcome(walk, proposition, assumptions):
    convert.WALK[0] = walk
    try:
        return convert.convert(proposition, assumptions, E.Engine())
    except Exception as e:      # the same type and message, whatever it is
        return e
    finally:
        convert.WALK[0] = None


def differences(items):
    """(inputs, [(input index, what differs)]) for Rust's `items` against Python's walker."""
    rust = convert.rust_walk(items)
    assert rust.ITEMS == tuple(i for i in convert.RUST_ITEMS if i in items)
    found = []
    ins = inputs()
    for k, (pr, asm) in enumerate(ins):
        d = diff(outcome(None, pr, asm), outcome(rust, pr, asm))
        if d:
            found.append((k, d))
    return len(ins), found


@pytest.mark.parametrize('items', [(i,) for i in convert.RUST_ITEMS] + [convert.RUST_ITEMS], ids=','.join)
def test_rust_walk_is_pythons(items):
    n, found = differences(items)
    assert n >= 51 and found == []


@pytest.mark.parametrize('items', [('term_row',), convert.RUST_ITEMS], ids=','.join)
def test_reserved_bit_is_zero(items):
    """Bit 32 of a term row's flags is 0 under both walkers, also where `_may_be_nan` is True (the bit's old value)."""
    from satassume.knowledge.templates import _may_be_nan
    for t in (nan, x + oo, f(x + oo), Subs(f(x), x, oo), f(x)):
        assert _may_be_nan(t) is (t != f(x))
        for walk in (convert._Walk, convert.rust_walk(items)):
            w = walk()
            for cls in convert._PREFIX:
                w.klass(cls)
            w.walk(t)
            for o in list(w.objects):
                row = []
                w.term_row(o, row)
                assert row[-4] == convert.T_INT and row[-2] == convert.T_INT
                assert row[-3] & convert.F_READ and not row[-3] & convert.F_RESERVED_32


def test_the_inputs_reach_every_branch():
    """The comparison isn't over refusals only: converted queries, each `Kept` reason the walk gives, big ints, opaque values."""
    got = [outcome(None, pr, asm) for pr, asm in inputs()]
    reasons = {c.reason for c in got if isinstance(c, convert.Kept)}
    assert {'non-basic', 'class-no-row', 'sum-product-integral', 'args-eq-not-is', 'out-of-scope'} <= reasons
    done = [c for c in got if isinstance(c, convert.Converted)]
    assert len(done) >= 35
    assert any(c.counts['opaque'] for c in done)
    assert any(convert.T_BIG in c.tables['terms'] for c in done)


def test_reads_are_compared_in_fresh_state():
    """`finite` of `p*ComplexRootOf._new(...)` raises or answers True by SymPy's assumptions shuffle and by who asked
    before (finite_history_repro.py). Each outcome's reads run in their own forked child of one state, so both walkers
    ask first and agree under every seed, Python's against itself too; the second ask in Python's child does answer
    differently under some seed (`reread`); and a walker whose read differs is still seen."""
    from sympy import Poly
    from sympy.core import random as sympy_random
    from sympy.polys.rootoftools import ComplexRootOf
    pr, asm = Q.positive(p * ComplexRootOf._new(Poly(z**5 + z + 1, z), 1)), Q.positive(p)
    rust = convert.rust_walk(convert.RUST_ITEMS)
    wrong = type('WrongFinite', (convert._Walk,), {'_read_finite': lambda self, t: True})
    seen, again = {}, []
    for seed in range(6):
        sympy_random._assumptions_rng.seed(seed)
        assert diff(outcome(None, pr, asm), outcome(None, pr, asm), None, seen) == [] and seen['reads'] and not seen['slow']
        again += seen['reread']
        assert diff(outcome(None, pr, asm), outcome(rust, pr, asm)) == []
    assert any(name.startswith('finite ') for name in again)
    found = diff(outcome(None, pr, asm), outcome(wrong, pr, asm))
    assert found and all(name.startswith('read finite ') or name == 'counts' for name in found)


def test_a_read_past_its_time_stops_both_children_alike(monkeypatch):
    """`complex(sin(exp(exp(exp(5)))))` doesn't end. Each child is killed at that read: the reads before it are compared,
    the input is named under `slow` and isn't a difference; a walker that answers where the other is killed is one."""
    import convert_diff
    monkeypatch.setattr(convert_diff, 'READ_SECONDS', 2.0)
    pr, asm = Q.lt(x, sin(exp(exp(exp(5))))), Q.positive(x)
    quick = type('QuickComplex', (convert._Walk,), {'_read_complex': lambda self, t: (0, 0)})
    seen = {}
    assert diff(outcome(None, pr, asm), outcome(convert.rust_walk(convert.RUST_ITEMS), pr, asm), None, seen) == []
    assert seen['slow'].startswith('complex ') and seen['reads'] > 0
    found = diff(outcome(None, pr, asm), outcome(quick, pr, asm))
    assert any(name.startswith('reads stopped ') for name in found)


def nested(levels):
    """A formula of `levels` connectives, one inside the other (an odd one: a Not round the rest)."""
    from sympy import And, Not, Or
    e = Q.positive(x)
    for _ in range(levels // 2):
        e = Or(And(e, Q.positive(y), evaluate=False), Q.real(z), evaluate=False)
    return Not(e, evaluate=False) if levels % 2 else e


def counted(walk, pr, asm):
    import sa_solver
    before = sa_solver.walk_counts()
    c = outcome(walk, pr, asm)
    return c, {k: v - before[k] for k, v in sa_solver.walk_counts().items() if v != before[k]}


def test_the_entry_runs_in_rust_and_its_counters_fire():
    """Counters 740-742: with every item on, `convert`'s body, both `formula` calls and each read run in Rust, no
    `_RustWalk` is made, and `tables['reads']` is Rust's method. With an item off, the Python walker is made."""
    import sa_solver
    rust = convert.rust_walk(convert.RUST_ITEMS)
    made = []
    init = rust.__init__
    rust.__init__ = lambda self: (made.append(1), init(self))[1]
    try:
        c, n = counted(rust, Q.positive(x + y), Q.positive(x) & Q.positive(y))
        assert n == {'cv:entry': 1, 'cv:formula': 2} and made == []
        assert type(c.tables['reads'].__self__) is sa_solver.Walk
        py = outcome(None, Q.positive(x + y), Q.positive(x) & Q.positive(y))
        assert list(c.counts) == list(py.counts) and c.raised == [] == py.raised
        before = sa_solver.walk_counts()
        for kind, name in enumerate(convert.READS):
            for i in range(len(c.objects)):
                assert typed_read(c, kind, i) == typed_read(py, kind, i), (name, i)
        assert c.counts == py.counts and c.raised == py.raised and c.raised and c.counts['read_raised'] == len(c.raised)
        after = sa_solver.walk_counts()
        assert after['cv:read'] - before['cv:read'] == len(convert.READS) * len(c.objects)
        assert after['cv:py:own_base'] - before['cv:py:own_base'] == len(c.objects)
    finally:
        del rust.__init__
    part = convert.rust_walk(('entry', 'walk'))
    c, n = counted(part, Q.positive(x + y), True)
    assert n == {'cv:entry': 1, 'cv:formula': 1} and type(c.tables['reads'].__self__) is part


def typed_read(c, kind, i):
    got = c.tables['reads'](kind, i)
    return None if got is None else (list(got[0]), [type(v) for v in got[0]], list(got[1]))


def exception_handled_tool():
    """True when some `sys.monitoring` tool has EXCEPTION_HANDLED on: globally, or locally on the code of Python's
    `formula` (its generator expression included). Nothing else is looked at: no plugin name, no environment."""
    mon = getattr(sys, 'monitoring', None)
    if mon is None:
        return False
    handled = mon.events.EXCEPTION_HANDLED
    code = convert._ORIGINAL['formula'].__code__
    codes = [code] + [k for k in code.co_consts if isinstance(k, type(code))]
    for tool in range(6):
        if mon.get_events(tool) & handled:
            return True
        if mon.get_tool(tool) is not None and any(mon.get_local_events(tool, k) & handled for k in codes):
            return True
    return False


#: OWED [157]: with an EXCEPTION_HANDLED callback registered, CPython (3.12.14, 3.13.15 and 3.14.7 alike) never returns
#: from a RecursionError raised by a call made from a generator-expression frame at the recursion limit, which is how
#: Python's `formula` says 'too-deep'. The condition is read at the test's setup, so a plain pytest run runs the case.
TOO_DEEP = pytest.param(700, 'too-deep', marks=pytest.mark.skipif(
    'exception_handled_tool()',
    reason='OWED [157]: a sys.monitoring tool has EXCEPTION_HANDLED on, and CPython then never returns from the '
           'RecursionError at the limit (repro: rust-spike/slice/results/tools358/repro.py 2 91 m)'))


@pytest.mark.parametrize('levels,kept', [(90, None), (100, None), (101, None), (130, None), TOO_DEEP])
def test_a_deep_formula_is_pythons(levels, kept):
    """Counter 743: `formula` nested past the native bound (100) is answered by Python's, so its recursion limit is the
    one that says 'too-deep'; the outcome is Python's either way. 101 is the first depth that falls back: the formula
    is then read twice (Rust's try, then Python's from the top), and `counts` and `raised` are still Python's, key for
    key in the same order, before any read and (by `diff`) after every read."""
    rust = convert.rust_walk(convert.RUST_ITEMS)
    for pr, asm in ((nested(levels), Q.positive(x)), (Q.positive(x), nested(levels))):
        py = outcome(None, pr, asm)
        c, n = counted(rust, pr, asm)
        assert (py.reason if isinstance(py, convert.Kept) else None) == kept
        assert n.get('cv:fallback:depth', 0) == (levels > 100)
        if kept is None:
            assert n == dict({'cv:entry': 1, 'cv:formula': 2 - (levels > 100)}, **({'cv:fallback:depth': 1} if levels > 100 else {}))
            assert list(c.counts.items()) == list(py.counts.items()) and c.raised == py.raised == []
            assert typed_read(c, 0, 0) == typed_read(py, 0, 0)
            assert list(c.counts.items()) == list(py.counts.items()) and c.raised == py.raised
        assert diff(py, c) == []


def test_template_names_are_pythons(monkeypatch):
    """`_template_name` in Rust: a function, an object without `__qualname__` (the name holds `repr(type(f))`), a
    `__module__` that isn't a str; and counter 744: a template whose class has its own metaclass goes to Python's
    function, so that metaclass's `__repr__` runs as often as under Python's walker."""
    import functools
    reprs = []

    class Meta(type):
        def __repr__(cls):
            reprs.append(cls.__name__)
            return 'meta ' + cls.__name__

    class Plain:
        __module__ = 'satassume.fake'

    class Odd(metaclass=Meta):
        __module__ = 'satassume.fake'
        __qualname__ = 'odd'

    class Mod(str):
        def __format__(self, spec):
            return 'satassume.formatted'

    def named(t):
        return t
    named.__module__ = Mod('satassume.mod')
    some = functools.partial(named)
    some.__module__ = 'satassume.partial'
    was = convert.TEMPLATES_FOR[0]
    for found, falls in (([named, Plain(), some], 0), ([Odd(), named], 1)):
        monkeypatch.setattr(convert, 'TEMPLATES_FOR', convert.TEMPLATES_FOR)    # the same list, restored at the end
        convert.TEMPLATES_FOR[0] = lambda cls, found=found: found
        pr, asm = Q.positive(x + y), Q.positive(x)
        del reprs[:]
        py = outcome(None, pr, asm)
        seen = list(reprs)
        del reprs[:]
        c, n = counted(convert.rust_walk(convert.RUST_ITEMS), pr, asm)
        assert isinstance(py, convert.Converted) and diff(py, c, 0) == [] and reprs == seen
        convert.TEMPLATES_FOR[0] = was
        assert n.get('cv:fallback:name', 0) == falls * c.tables['n_classes'] and bool(seen) == bool(falls)


def test_a_replaced_definition_is_called(monkeypatch):
    """P1, counter 746 (plant 773 fails this): a `_Walk` method or a function of convert.py that a test or an
    instrument replaced is called by name under the Rust walker too. Its item is off for that query and the rest stays
    Rust's; `term`, which every item stands on, gives the query to Python's walker."""
    replaced_checks(monkeypatch)


def replaced_checks(monkeypatch):
    rust = convert.rust_walk(convert.RUST_ITEMS)
    pr, asm = Q.positive(x + y), Q.positive(x)
    calls = []

    def spy(owner, name):
        real = getattr(owner, name)

        def f(*a, **k):
            calls.append((name, a))
            return real(*a, **k)
        monkeypatch.setattr(owner, name, f)

    spy(convert._Walk, '_read_commutative')
    c, n = counted(rust, pr, asm)
    assert n == {'cv:patched': 1, 'cv:entry': 1, 'cv:formula': 2} and calls == []
    c.tables['reads'](convert.READS.index('commutative'), 0)
    assert [(name, a[1]) for name, a in calls] == [('_read_commutative', c.objects[0])]
    monkeypatch.undo()

    del calls[:]
    spy(convert._Walk, 'term_row')
    c, n = counted(rust, pr, asm)
    assert n == {'cv:patched': 1, 'cv:entry': 1, 'cv:formula': 2} and [a[1] for _, a in calls] == c.objects
    monkeypatch.undo()

    for name in ('_structural_class', '_template_name'):    # the module's functions that Rust's `klass` calls per class
        del calls[:]
        spy(convert, name)
        outcome(None, pr, asm)
        seen = [a[0] for _, a in calls]
        del calls[:]
        c, n = counted(rust, pr, asm)
        assert n == {'cv:patched': 1, 'cv:entry': 1, 'cv:formula': 2}
        assert len(seen) > 0 and len(calls) == len(seen) and all(a[0] is s for (_, a), s in zip(calls, seen)), name
        monkeypatch.undo()

    del calls[:]
    spy(convert, 'formula')
    c, n = counted(rust, pr, asm)
    assert n == {'cv:patched': 1} and [a[0] for _, a in calls] == [pr, asm]
    assert type(c.tables['reads'].__self__).__name__ == '_RustWalk'
    monkeypatch.undo()

    del calls[:]
    spy(convert._Walk, 'term')
    c, n = counted(rust, pr, asm)
    assert n == {'cv:patched': 1} and calls and type(c.tables['reads'].__self__) is convert._Walk
    monkeypatch.undo()

    c, n = counted(rust, pr, asm)
    assert n == {'cv:entry': 1, 'cv:formula': 2} and diff(outcome(None, pr, asm), c) == []


def run(plant=None, items=None, check=None):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path))
    env.pop('SLICE_CONVERT_PLANT', None)
    env.pop('SLICE_CONVERT_CHECK', None)
    if check:
        env['SLICE_CONVERT_CHECK'] = check
    if plant:
        env['SLICE_CONVERT_PLANT'] = plant
    if items:
        env['SLICE_CONVERT_ITEMS'] = items
    r = subprocess.run([sys.executable, os.path.join(HERE, 'test_convert_walk.py')], env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize('number', sorted(PLANTS))
def test_plant_is_caught(number):
    """Each item's plant gives differences, with all items on Rust and with that item alone; none without the plant."""
    name, item = PLANTS[number]
    assert run()['differences'] == 0
    assert run(name)['differences'] > 0
    assert run(name, item)['differences'] > 0


def test_plant_773_is_caught():
    """Plant 773 (entry-skip-replaced: the entry doesn't look for replaced definitions): the checks of
    `test_a_replaced_definition_is_called` hold without it and fail under it. They read the replacement's own calls,
    nothing of the plant."""
    assert run(check='replaced') == {'replaced': 'held'}
    assert run('entry-skip-replaced', check='replaced')['replaced'].startswith('failed')


if __name__ == '__main__':
    plant = os.environ.get('SLICE_CONVERT_PLANT')
    if plant:
        import sa_solver
        sa_solver.walk_plant(convert.WALK_PLANTS[plant])
    if os.environ.get('SLICE_CONVERT_CHECK') == 'replaced':
        try:
            with pytest.MonkeyPatch.context() as patch:
                replaced_checks(patch)
            print(json.dumps(dict(replaced='held')))
        except AssertionError as e:
            print(json.dumps(dict(replaced='failed ' + str(e)[:200])))
        sys.exit(0)
    its = tuple(os.environ.get('SLICE_CONVERT_ITEMS', ','.join(convert.RUST_ITEMS)).split(','))
    n, found = differences(its)
    for k, d in found[:10]:
        print(k, d[:4], file=sys.stderr)
    print(json.dumps(dict(inputs=n, differences=len(found))))
