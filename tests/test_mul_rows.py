"""The rows of ``Mul`` (``templates/mul.py``, their template
``wiring.product``, #299, U2) entail exactly what the templates they
replace emitted (``tests/_legacy_mul.py``, verbatim from e068e49).

Their rules depend only on the pattern: the number ``n`` of factors and the
constants among them by position (and the factor sets and the quotient on
the node).  So the main check is per pattern: ``n`` in 2 .. 8 (around
``at_most=6``, 4 and 2), 31, 32, 33 (the zero row is one formula past 32)
and 40, with constants at no position, at each position (one; for a wide
node at the first, second and last), and at the first and the last (two),
drawn from :data:`CONSTANTS`.  The node is built with ``Basic.__new__`` so
that SymPy keeps every factor in place (``Mul(2, x, 3)`` is ``6*x``), as a
template sees only the arguments.  Then per node: SymPy's own products
(``2*x``, ``-x``, ``I*x``, ``pi*x``, ``x*y*z``, quotients ``x/y**2``,
repeated bases, the factor sets of ``3*x*y`` and ``I*pi*c*s``) and the Mul
nodes among the totality checker's.

For each node, both templates run from empty pattern caches; the pattern
keys must be the same and the blocks in the same order, over the same
objects (the rows' block of two factors has one more slot after the node,
for ``2*coefficient``, which no clause uses).  Then for each block each
side's clauses, with the rule base on every slot, must entail every clause
of the other (SAT, both ways): ADDED (clauses of the rows the legacy
template does not entail) and MISSING (the reverse) must be empty.  The
formulas of a wide node must be equal.  Every rule of the compiled rows
must be used by some pattern.

    PYTHONHASHSEED=0 python -m pytest -q tests/test_mul_rows.py -s
"""
import os
import subprocess
import sys

import pytest

pytest.importorskip("sympy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _legacy_mul as legacy  # noqa: E402
from sympy import (  # noqa: E402
    Basic, E, Float, I, Integer, Mul, Pow, Rational, S, Symbol, exp, oo, pi, sqrt, symbols, zoo,
)

from satassume.knowledge.rules import BASIS, RULE_CLAUSES  # noqa: E402
from satassume.knowledge.templates import _common, registry, wiring  # noqa: E402
from satassume.knowledge.templates._common import Compiled, consts_of, pattern_key  # noqa: E402
from satassume.knowledge.templates._compiled_rows import FAMILIES  # noqa: E402
from satassume.knowledge.templates._rows import generator  # noqa: E402
from satassume.sat.solver import Solver  # noqa: E402

FAMILY = f"{wiring.__name__}:mul"
ARITIES = (2, 3, 4, 5, 6, 7, 8, 31, 32, 33, 40)
CONSTANTS = (S.Zero, S.One, S.NegativeOne, Integer(2), S.Half, Integer(-3), Float(2.0),
             Float(2.5), oo, -oo, zoo, S.NaN, pi, E, I, -I)


def rows_template():
    """The template of the rows, registered for Mul and attributed to the
    family."""
    registry.templates_for(Mul)
    [t] = [t for t in registry._by_class[Mul] if t.__module__ == FAMILY]
    return t


def positions(n):
    return range(n) if n <= 8 else (0, 1, n - 1)


def patterns(n):
    """Constants at no position, at each one, and at the first and the last."""
    yield {}
    for k in positions(n):
        for c in CONSTANTS:
            yield {k: c}
    for c in CONSTANTS:
        for d in CONSTANTS:
            yield {0: c, n - 1: d}


def pattern_nodes(n):
    xs = symbols(f'x:{n}')
    for consts in patterns(n):
        yield Basic.__new__(Mul, *(consts.get(k, x) for k, x in enumerate(xs)))


def run(template, e):
    """``(output, keys)``: the template's output for ``e`` as a list, from
    an empty pattern cache, and the keys it cached."""
    _common._CACHE.clear()
    try:
        out = template(e)
        return (out if isinstance(out, list) else [out]), set(_common._CACHE)
    finally:
        _common._CACHE.clear()


def _var(k, pred):
    return k * len(BASIS) + BASIS.index(pred) + 1


def _clauses(c):
    return [[(-1 if neg else 1) * _var(k, BASIS[i]) for k, i, neg in lits]
            for lits, _, _ in c.pattern.clauses]


def not_entailed(a, b, nobjs):
    """The clauses of ``b`` that ``a``, with the rule base on each slot,
    does not entail."""
    cb = _clauses(b)
    ca = _clauses(a)
    if {frozenset(cl) for cl in cb} <= {frozenset(cl) for cl in ca}:
        return []
    s = Solver()
    for k in range(nobjs):
        for cl in RULE_CLAUSES:
            s.add_clause([(1 if q > 0 else -1) * (k * len(BASIS) + abs(q)) for q in cl])
    for cl in ca:
        s.add_clause(cl)
    return [cl for cl in cb if s.solve([-q for q in cl])]


class Result:
    def __init__(self):
        self.nodes = self.blocks = self.clauses = self.formulas = 0
        self.added, self.missing, self.other = [], [], []


def _same_objects(new, old):
    """The rows' block has the legacy block's objects, and after them only
    the empty slots of the terms of the constant, which no clause uses."""
    k = len(old.objs)
    if new.objs[:k] != old.objs or any(o is not None for o in new.objs[k:]):
        return False
    return all(lit[0] < k for lits, _, _ in new.pattern.clauses for lit in lits)


def compare(nodes, template=None):
    """Both templates on each node: the differences (:class:`Result`)."""
    template = template or rows_template()
    out = Result()
    for e in nodes:
        new, new_keys = run(template, e)
        old, old_keys = run(legacy.mul_templates, e)
        out.nodes += 1
        if new_keys != old_keys or len(new) != len(old):
            out.other.append((e, 'keys or blocks differ'))
            continue
        for a, b in zip(new, old):
            if not (isinstance(a, Compiled) and isinstance(b, Compiled)):
                out.formulas += 1
                if a != b:
                    out.other.append((e, 'formulas differ', a, b))
                continue
            if not _same_objects(a, b):
                out.other.append((e, 'slots differ', a.objs, b.objs))
                continue
            if a.pattern.wide or b.pattern.wide:
                out.other.append((e, 'a formula past MAX_EXPAND'))
            out.blocks += 1
            nobjs = len(b.objs)
            out.clauses += len(a.pattern.clauses) + len(b.pattern.clauses)
            added = not_entailed(b, a, nobjs)
            missing = not_entailed(a, b, nobjs)
            if added:
                out.added.append((e, added))
            if missing:
                out.missing.append((e, missing))
    return out


def _report(what, r):
    print(f"\n{what}: {r.nodes} nodes, {r.blocks} blocks, {r.clauses} clauses compared, "
          f"{r.formulas} formulas, ADDED {len(r.added)}, MISSING {len(r.missing)}, "
          f"other {len(r.other)}")


def test_the_rows_entail_exactly_the_legacy_rules_per_pattern():
    nodes = [e for n in ARITIES for e in pattern_nodes(n)]
    r = compare(nodes)
    _report("patterns", r)
    assert not (r.added or r.missing or r.other), (r.added[:2], r.missing[:2], r.other[:2])
    assert len(nodes) == sum(1 + 16 * len(positions(n)) + 256 for n in ARITIES)
    assert r.formulas > 100           # the wide zero formulas of 33 and 40 factors


x, y, z, w = symbols('x y z w')
r, p, ng = Symbol('r', real=True), Symbol('p', positive=True), Symbol('ng', negative=True)
n, ev, od = Symbol('n', integer=True), Symbol('e', even=True), Symbol('o', odd=True)
A, B = symbols('A B', commutative=False)


def sympy_nodes():
    """SymPy's own products: a coefficient and a factor, -x, I*x, pi*x,
    products of 2 .. 8 factors, quotients, repeated bases, the derived
    factor sets (3*x*y, I*pi*c*s), non-commutative factors and a wide one."""
    syms = (x, r, p, ng, n, ev, od, y, z, w)
    out = []
    for c in (Integer(2), Integer(-3), S.Half, Rational(-3, 2), Rational(5, 2), Float(2.5),
              Float(-1.0), oo, -oo, zoo, pi, E, I, sqrt(2)):
        out += [Mul(c, x, evaluate=False), Mul(x, c, evaluate=False), Mul(c, n, evaluate=False),
                Mul(c, x, y, evaluate=False)]
    out += [2*x, -x, -n, -ev, I*x, -I*x, pi*x, x*y, x*y*z, 2*x*y, 3*x*y*z, -x*y, x*y*z*w,
            Mul(*syms[:5]), Mul(*syms[:6]), Mul(*syms[:7]), Mul(*syms[:8]), Mul(*syms[:9]),
            x/y**2, 3/y**2, x*y**-2, n/ev**3, od/ev, 1/x, x**2*y, x**2*y**3*z, x*y**2*y**-1,
            Mul(x, x, evaluate=False), Mul(x, y, x, evaluate=False), 3*x**2, I*pi*x,
            I*pi*x*y, 3*I*pi*x*y, I*pi*n/2, Rational(1, 2)*I*pi*n*y, A*B, 2*A, A*B*x,
            Mul(*symbols('a:40')), Mul(*symbols('a:40', positive=True)), 2*Mul(*symbols('a:34')),
            exp(x)*y, sqrt(x)*y, Pow(x, -1, evaluate=False)*y]
    return out


def test_the_rows_entail_exactly_the_legacy_rules_per_node():
    from test_template_tables import _subexprs, synthetic_nodes
    nodes = [e for e in sympy_nodes() if isinstance(e, Mul)]
    synthetic = [e for e in _subexprs(synthetic_nodes()) if isinstance(e, Mul)]
    assert len(nodes) > 90 and len(synthetic) > 30
    nodes += synthetic
    r = compare(nodes)
    _report("nodes", r)
    assert not (r.added or r.missing or r.other), (r.added[:2], r.missing[:2], r.other[:2])
    # the derived factor sets and the quotient are blocks too
    assert r.blocks > r.nodes + 10


def _single(gen, schema=None, spec=None):
    """A generator of ``gen``'s terms with one schema or one fixed rule."""
    g = generator('Mul', gen.arity, (), (), FAMILY)
    g.terms = gen.terms
    g.specs = {2: (spec,)} if spec is not None else {}
    g.schemas = (schema,) if schema is not None else ()
    return g


def test_every_compiled_rule_is_used():
    # every rule of the compiled rows gives a rule in the block of some
    # pattern: its constants do not decide it.  Two give no clause: their
    # conclusion is commutative, which the rule base reads as true (every
    # term in scope is commutative), the closure and the commutative factor
    # of a commutative product
    [(name, arity, terms, specs, schemas)] = dict(FAMILIES)['mul']
    gen = generator(name, arity, terms, specs, FAMILY, schemas)
    rules = [_single(gen, schema=s) for s in gen.schemas]
    rules += [_single(gen, spec=sp) for sp in gen.specs[2]]
    assert len(gen.schemas) == 50 and len(gen.specs[2]) == 29
    nodes = [e for n in ARITIES if n <= 8 for e in pattern_nodes(n)]
    no_rule, no_clause = set(range(len(rules))), set(range(len(rules)))
    try:
        for e in nodes:
            for i in list(no_clause):
                _common._CACHE.clear()
                pattern = wiring.rows_block(f'used{i}', rules[i])(e.args, e).pattern
                if pattern.rules:
                    no_rule.discard(i)
                if pattern.clauses:
                    no_clause.discard(i)
    finally:
        _common._CACHE.clear()
    assert not no_rule, [(gen.schemas + gen.specs[2])[i] for i in no_rule]
    assert len(no_clause) == 2 and all(lit[1] == 'commutative' for i in no_clause
                                       for lit in rules[i].schemas[0][2][0][1]), no_clause


def test_the_pattern_keys_are_legacys():
    # the cache is keyed as before: ('mul', n, consts), one per factor set
    for e in (Basic.__new__(Mul, x, Integer(2), y), Basic.__new__(Mul, pi, x), 2*x, 3*x*y):
        _, keys = run(rows_template(), e)
        sets = legacy._mul_factor_sets(e)
        assert keys == {pattern_key('mul', len(f), consts_of(f)) for f in sets}


def test_mul_is_compiled_on_its_own_first_use():
    code = """
import sys
from sympy import Mul, Q, Symbol
from satassume.knowledge.templates.registry import registry
from satassume.sympy_api import ask
MUL = "satassume.knowledge.templates.mul"
WIRING = "satassume.knowledge.templates.wiring"
x, y = Symbol('x'), Symbol('y')
assert ask(Q.positive(x + 1), Q.positive(x)) is True
assert WIRING not in sys.modules
assert ask(Q.integer(x*y), Q.integer(x) & Q.integer(y)) is True
assert ask(Q.positive(x), Q.negative(-2*x)) is True
# the compiled rows, not the module of the rows
assert WIRING in sys.modules and MUL not in sys.modules
[t] = registry._by_class[Mul]
assert t.__module__ == WIRING + ":mul", t.__module__
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         timeout=120)
    assert out.returncode == 0, out.stderr
