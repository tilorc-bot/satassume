"""The rows of ``Pow`` (``templates/power.py``, its template
``wiring.power``, #294) entail exactly what the generator they replace
emitted (``tests/_legacy_pow_rules.py``, verbatim from 8ddd549).

For every power of the corpus (bases and exponents symbolic and constant,
``E``, ``-1``, ``1``, ``I``, ``-I``, ``k/2``, ``1/q``, ``2 mod 4``,
``0 mod 4``, floats, ``pi``, ``GoldenRatio``, ``Catalan``, the infinities and
``nan``, ``exp(u)`` and unevaluated ``E**u`` bases, ``b**b``, sums as bases,
``E**(I*pi*c*s)``, integers ``|b| >= 2``, ``0 < |b| < 1``, algebraic irrational
exponents, unit-angle bases with numeric exponents; each unevaluated, and
evaluated where that is still a power) the compiled blocks of the two
templates are computed, each from empty caches.  The slots differ (the
legacy template had the fixed slots ``u, s, 2*e, b - 1, b + 1`` = 3..7, the
rows number their terms), so each block's clauses are mapped to the
objects of their slots; then each side, with the rule base on every
object and the links between ``b`` and ``b +- 1`` (``_shift_links``: the
rows say ``Q.lt(base, -1)``, ``extended_negative(b + 1)``, where the legacy
row said ``negative(b + 1)`` next to ``integer(b)``), must entail every
clause of the other.  No fact is added: the answers are those of the
legacy template.  The plain formulas (the facts of a unit-angle base to a
numeric power) and the bound blocks of a sum base must be identical.  The
powers among the random terms and synthetic nodes of
``tests/test_template_tables.py`` are compared too.

    PYTHONHASHSEED=0 python -m pytest -q tests/test_power_rows.py -s
"""
import os
import subprocess
import sys
from itertools import product

import pytest

pytest.importorskip("sympy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _legacy_pow_rules as legacy  # noqa: E402
from sympy import (  # noqa: E402
    Add, Catalan, E, EulerGamma, Float, GoldenRatio, I, Integer, Mul, Pow, Rational, S, Symbol,
    exp, oo, pi, sqrt, zoo,
)

from satassume.knowledge.rules import BASIS, RULE_CLAUSES  # noqa: E402
from satassume.knowledge.templates import _common, registry, wiring  # noqa: E402
from satassume.knowledge.templates._compiled_rows import FAMILIES  # noqa: E402
from satassume.knowledge.templates._rows import generator  # noqa: E402
from satassume.knowledge.templates.registry import _split  # noqa: E402
from satassume.sat.solver import Solver  # noqa: E402

FAMILY = f"{wiring.__name__}:power"

x, y = Symbol('x'), Symbol('y')
n, k = Symbol('n', integer=True), Symbol('k', integer=True, positive=True)
r, p = Symbol('r', real=True), Symbol('p', positive=True)
im, z = Symbol('i', imaginary=True), Symbol('z', zero=True)
ev, od = Symbol('e', even=True), Symbol('o', odd=True)


def bases():
    consts = [S.Zero, S.One, S.NegativeOne, Integer(2), Integer(3), Integer(-2), Integer(4),
              Integer(-4), Integer(8), Rational(1, 2), Rational(-1, 2), Rational(2, 3),
              Rational(3, 2), Rational(-3, 2), Rational(4, 9), Rational(1, 4), Rational(1, 8),
              E, pi, I, -I, 2*I, GoldenRatio, Catalan, EulerGamma, oo, -oo, zoo, S.NaN,
              Float(0.5), Float(2.0), Float(-2.5), Float(1.0), Float(-0.25), Float(0.0)]
    exps = [exp(x), exp(2), exp(I*x), exp(r), Pow(E, x, evaluate=False),
            Pow(E, 2, evaluate=False), Pow(E, im, evaluate=False), exp(I*pi*x)]
    other = [x + 1, n + 1, 2*n - 3, 1 - 2*n, n/2 + 1, x - 1, Add(y, -y, 1, evaluate=False),
             Add(y, -y, -1, evaluate=False), sqrt(2), 2 + I, oo*I, x*y, x**2, I*x, -x]
    return [x, y, n, k, r, p, im, z, ev, od] + consts + exps + other


def exponents():
    consts = [S.Zero, S.One, S.NegativeOne, Integer(2), Integer(3), Integer(-2), Integer(-3),
              Integer(4), Integer(6), Integer(-4), Integer(-6), Integer(8), S.Half, -S.Half,
              Rational(3, 2), Rational(-3, 2), Rational(5, 2), Rational(1, 3), Rational(-1, 3),
              Rational(2, 3), Rational(1, 4), Rational(-5, 4), Float(0.5), Float(2.0),
              Float(-1.0), Float(0.0), pi, E, I, -I, 2*I, GoldenRatio, Catalan, oo, -oo, zoo,
              S.NaN]
    other = [sqrt(2), -sqrt(3), I*pi, -I*pi, 2*I*pi, I*pi/3, I*pi*x, I*pi*n, I*pi*n/2,
             2*I*pi*n, Rational(3, 2)*I*pi*n, Mul(I, pi, 0, x, evaluate=False), I*pi*x*y,
             Mul(I, pi, 2, evaluate=False), Mul(I, pi, 2, evaluate=False)*n,
             x + 1, 2*x, x/2, I*x, -x, y**2]
    return [x, y, n, k, r, p, im, z, ev, od] + consts + other


def corpus():
    out = {}
    bs = bases()
    for b, e in product(bs, exponents()):
        out[Pow(b, e, evaluate=False)] = None
        try:
            v = b**e
        except (ValueError, TypeError, ArithmeticError):
            continue
        if isinstance(v, Pow):
            out[v] = None
    for b in bs:
        out[Pow(b, b, evaluate=False)] = None
    return list(out)


def rows_template():
    """The template of the rows, registered for Pow and attributed to the family."""
    registry.templates_for(Pow)
    [t] = [t for t in registry._by_class[Pow] if t.__module__ == FAMILY]
    return t


def run(template, nodes):
    _common._CACHE.clear()
    try:
        out = {}
        for e in nodes:
            cs, formulas = [], []
            _split(template(e), cs, formulas)
            out[e] = (cs, sorted(map(str, formulas)))
        return out
    finally:
        _common._CACHE.clear()


_B = {q: i for i, q in enumerate(BASIS)}


class _Space:
    """The objects of two blocks, each a block of variables: a slot is its
    object, so that ``b`` and ``e`` of ``b**b`` are one."""

    def __init__(self, *blocks):
        self.index = {}
        for c in blocks:
            for k in c.pattern.used:
                o = c.objs[k]
                assert o is not None, (c.objs, k)
                self.index.setdefault(o, len(self.index))

    def var(self, o, pred):
        return self.index[o] * len(BASIS) + _B[pred] + 1

    def clauses(self, c):
        return [[(-1 if neg else 1) * self.var(c.objs[k], BASIS[i]) for k, i, neg in lits]
                for lits, _, _ in c.pattern.clauses]

    def solver(self, c):
        """The clauses of ``c``, the rule base on each object, and the links
        of ``x`` and ``x +- 1``."""
        s = Solver()
        for o in self.index:
            for cl in RULE_CLAUSES:
                s.add_clause([(1 if q > 0 else -1) * self.var(o, BASIS[abs(q) - 1])
                              for q in cl])
        for cl in self.clauses(c):
            s.add_clause(cl)
        for a, b in product(self.index, repeat=2):
            if a is not b and any(b == a + d for d in (S.One, S.NegativeOne)):
                self.link(s, a, b)
        return s

    def link(self, s, a, b):
        """``b == a + c`` for a real number ``c != 0``: the same finiteness,
        complex and extended real, and the same infinity
        (``_rows_equivalence._shift_links`` before #287)."""
        for q in ('finite', 'complex', 'extended_real'):
            s.add_clause([-self.var(a, q), self.var(b, q)])
            s.add_clause([self.var(a, q), -self.var(b, q)])
        fa, fb = self.var(a, 'finite'), self.var(b, 'finite')
        for q in ('extended_positive', 'extended_negative'):
            s.add_clause([fa, -self.var(a, q), self.var(b, q)])
            s.add_clause([fb, self.var(a, q), -self.var(b, q)])


def not_entailed(space, a, b):
    """The clauses of ``b`` that ``a`` (with the rule base and links) does not entail."""
    s = space.solver(a)
    return [cl for cl in space.clauses(b) if s.solve([-q for q in cl])]


def differences(new, old):
    """Per node: the clauses of the rows' blocks the legacy blocks do not
    entail (added), and the reverse (lost); and the number of clauses compared."""
    out, count, seen = {}, 0, {}
    for e in new:
        (cn, fn), (co, fo) = new[e], old[e]
        assert fn == fo, e
        assert len(cn) == len(co), e
        for a, b in zip(cn[1:], co[1:]):
            # a sum base's bounds (core._pow_bound_templates): the same block
            assert a.objs == b.objs and a.pattern.clauses == b.pattern.clauses, e
        a, b = cn[0], co[0]
        assert a.objs[:3] == b.objs[:3] == (*e.args, e)
        assert not a.pattern.wide and not b.pattern.wide, e
        space = _Space(a, b)
        key = (id(a.pattern), id(b.pattern), tuple(space.index.values()),
               tuple(space.index[a.objs[k]] for k in a.pattern.used),
               tuple(space.index[b.objs[k]] for k in b.pattern.used),
               tuple((i, j) for i, j in product(space.index.values(), repeat=2)
                     if i != j and _linked(space, i, j)))
        r = seen.get(key)
        if r is None:
            r = seen[key] = (not_entailed(space, b, a), not_entailed(space, a, b))
            count += len(a.pattern.clauses) + len(b.pattern.clauses)
        if r[0] or r[1]:
            out[e] = r
    return out, count, len(seen)


def _linked(space, i, j):
    objs = list(space.index)
    a, b = objs[i], objs[j]
    return any(b == a + d for d in (S.One, S.NegativeOne))



def compare(nodes, template=None):
    new = run(template or rows_template(), nodes)
    old = run(legacy.pow_templates, nodes)
    return differences(new, old), new


def test_the_rows_entail_exactly_the_legacy_rules():
    nodes = corpus()
    (diff, count, patterns), new = compare(nodes)
    print(f"\n{len(nodes)} powers, {patterns} pairs of patterns, {count} clauses compared, "
          f"{len(diff)} differ")
    assert not diff, [(e, d) for e, d in list(diff.items())[:3]]
    # most nodes have a block with clauses, and every hook is reached
    assert sum(1 for cs, _ in new.values() if cs[0].pattern.clauses) > 0.9 * len(nodes)
    assert any(len(cs) > 1 for cs, _ in new.values())          # a sum base's bounds
    assert any(fs for _, fs in new.values())                   # a unit-angle base


def test_the_rows_entail_exactly_on_random_and_synthetic_powers():
    # the powers among the random terms and the synthetic nodes of
    # tests/test_template_tables.py (the fuzz generator's terms and their
    # subterms; the totality checker's shapes)
    from test_template_tables import _subexprs, random_terms, synthetic_nodes
    nodes = [e for e in _subexprs([*random_terms(), *synthetic_nodes()]) if isinstance(e, Pow)]
    (diff, count, patterns), _ = compare(nodes)
    print(f"\n{len(nodes)} powers, {patterns} pairs of patterns, {count} clauses compared, "
          f"{len(diff)} differ")
    assert not diff, [(e, d) for e, d in list(diff.items())[:3]]
    assert len(nodes) > 500


def _mutated(change):
    """The template of the rows with ``change`` applied to their compiled rules."""
    [(fn, arity, terms, specs)] = dict(FAMILIES)['power']
    ((m, rules),) = specs
    gen = generator(fn, arity, terms, ((m, change(list(rules))),), FAMILY)
    return wiring.power(gen)


def _first(rules, test):
    return next(i for i, r in enumerate(rules) if test(r))


def test_the_comparison_sees_a_wrong_row():
    """Mutation checks of the comparison itself: a dropped conjunct, a
    removed row, base and exponent swapped, a broken shape."""
    nodes = [Pow(b, e, evaluate=False) for b, e in product(
        (x, n, p, im, E, S.NegativeOne, Integer(2), Rational(1, 2), exp(x)),
        (x, n, k, S.NegativeOne, S.One, Integer(2), S.Half, sqrt(2), I))]

    def drop_conjunct(rules):
        # Positive base, real exponent: positive
        i = _first(rules, lambda r: set(r[0]) == {(0, 'positive', True), (1, 'real', True)})
        rules[i] = (rules[i][0][:1], *rules[i][1:])
        return rules

    def remove_row(rules):
        # Nonnegative integer power of an odd number: odd
        del rules[_first(rules, lambda r: set(r[0]) == {
            (0, 'odd', True), (1, 'integer', True), (1, 'nonnegative', True)})]
        return rules

    def swap(rules):
        # Odd power of a negative number: negative
        i = _first(rules, lambda r: set(r[0]) == {(0, 'negative', True), (1, 'odd', True)})
        rules[i] = (((1, 'negative', True), (0, 'odd', True)), *rules[i][1:])
        return rules

    def shape(rules):
        # An integer power of -1 is odd: of 1 instead
        i = _first(rules, lambda r: len(r) > 2 and r[2] == (('value', -1), None))
        rules[i] = (*rules[i][:2], (('value', 1), None))
        return rules

    for change in (drop_conjunct, remove_row, swap, shape):
        (diff, _, _), _ = compare(nodes, _mutated(change))
        assert diff, change.__name__


def test_power_is_compiled_on_its_own_first_use():
    code = """
import sys
from sympy import Q, Symbol
from satassume.knowledge.templates.registry import registry
from satassume.sympy_api import ask
POWER = "satassume.knowledge.templates.power"
WIRING = "satassume.knowledge.templates.wiring"
x = Symbol('x')
assert ask(Q.positive(x + 1), Q.positive(x)) is True
assert WIRING not in sys.modules
assert ask(Q.real(x**2), Q.real(x)) is True
# the compiled rows, not the module of the rows
assert WIRING in sys.modules and POWER not in sys.modules
from sympy import Pow
[t] = registry._by_class[Pow]
assert t.__module__ == WIRING + ":power", t.__module__
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         timeout=120)
    assert out.returncode == 0, out.stderr
