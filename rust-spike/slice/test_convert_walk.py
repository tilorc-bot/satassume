"""The Rust walker against `_Walk` (issue 323, the convert step): `convert.convert` on the same input objects under
Python's walker and under Rust's gives the same thing, item by item.

"The same" (`diff`): the same `Kept` reason and detail, or the same exception type and message, or tables equal token
for token and type for type (strings, class rows, term rows, powers, settings, formula, the counts), `ids` holding the
same objects under the same ids in the same order (the first occurrence kept: ruling R1), `objects` and `classes` the
same objects, and every lazy read of every term answering alike afterwards (tokens, strings, counts, `raised`).
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


def typed(v):
    return [(type(a), a) for a in v] if isinstance(v, list) else v


def diff(a, b):
    """What differs between two outcomes, as a list of names. Empty: the same."""
    if type(a) is not type(b):
        return [f'outcome {type(a).__name__} {type(b).__name__}']
    if isinstance(a, Exception):
        return [] if str(a) == str(b) else [f'message {a} | {b}']
    if isinstance(a, convert.Kept):
        return [] if (a.reason, a.detail) == (b.reason, b.detail) else [f'kept {a.reason} {a.detail} | {b.reason} {b.detail}']
    out = []
    ta, tb = a.tables, b.tables
    if list(ta) != list(tb):
        out.append('table names')
    for k in ta:
        if k != 'reads' and typed(ta[k]) != typed(tb.get(k)):
            out.append('table ' + k)
    ia, ib = list(a.ids.items()), list(b.ids.items())
    if len(ia) != len(ib) or any(s is not t or i != j or type(i) is not type(j) for (s, i), (t, j) in zip(ia, ib)):
        out.append('ids')
    if len(a.objects) != len(b.objects) or any(s is not t for s, t in zip(a.objects, b.objects)):
        out.append('objects')
    if [(id(c), i) for c, i in a.classes.items()] != [(id(c), i) for c, i in b.classes.items()]:
        out.append('classes')
    if out:
        return out
    for kind in range(len(convert.READS)):
        for i in range(len(a.objects)):
            if ta['reads'](kind, i) != tb['reads'](kind, i):
                out.append(f'read {convert.READS[kind]} {i}')
    if a.counts != b.counts or a.raised != b.raised:
        out.append('counts')
    return out


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
