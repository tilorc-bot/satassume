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
"""
import json
import os
import subprocess
import sys

import pytest
from sympy import (Add, Basic, Dummy, Float, Function, I, Integer, Integral, MatrixSymbol, Mul, Piecewise, Pow, Q,
                   Rational, S, Sum, Symbol, Wild, cos, exp, log, nan, oo, pi, sin, sqrt, zoo)
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
          673: ('walk-args-unreversed', 'walk'), 674: ('enc-int-no-sign', 'enc_int')}
PLANTS = {k: v for k, v in ALL_PLANTS.items() if v[1] in convert.RUST_ITEMS}      # an item's plant, once it's ported


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


def run(plant=None, items=None):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path))
    env.pop('SLICE_CONVERT_PLANT', None)
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


if __name__ == '__main__':
    plant = os.environ.get('SLICE_CONVERT_PLANT')
    if plant:
        import sa_solver
        sa_solver.walk_plant(convert.WALK_PLANTS[plant])
    its = tuple(os.environ.get('SLICE_CONVERT_ITEMS', ','.join(convert.RUST_ITEMS)).split(','))
    n, found = differences(its)
    for k, d in found[:10]:
        print(k, d[:4], file=sys.stderr)
    print(json.dumps(dict(inputs=n, differences=len(found))))
