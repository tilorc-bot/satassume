"""The rows of ``Add`` (``templates/add.py``, their template
``wiring.addition``, #299, U1) entail exactly what the templates they
replace emitted (``tests/_legacy_add.py``, verbatim from ae78e6f).

Their rules depend only on the pattern: the number ``n`` of terms and the
constants among them by position (and the sums of a special shape on the
node).  So the main check is per pattern: ``n`` in 2 .. 8 (around
``at_most=3`` and 6), 31, 32, 33 (the strict-sign rows are one formula
past 32) and 40, with constants at no position, at each position (one;
for a wide node at the first, second and last), and at the first and the
last (two), drawn from :data:`CONSTANTS`.  The node is built with
``Basic.__new__`` so that SymPy keeps every term in place (``Add(2, x,
3)`` is ``x + 5``), as a template sees only the arguments.  Then per node:
SymPy's own sums (``x - y``, ``x + 1``, ``x + I*y``, ``pi + x``, ``x +
oo``, sums of 2 .. 9 terms, the sums of a special shape: half-integer
coefficients, ``c0 + c1*u``, ``c0 + c1/v``, ``I*(c_1*x_1 + ...)``) and the
Add nodes among the totality checker's.

For each node, both templates run from empty pattern caches; the pattern
keys must be the same and the blocks in the same order, over the same
objects.  Then for each block each side's clauses, with the rule base on
every slot, must entail every clause of the other (SAT, both ways): ADDED
(clauses of the rows the legacy template does not entail) and MISSING (the
reverse) must be empty.  The formulas of a wide node must be equal.  Every
rule of the compiled rows must be used by some pattern.

    PYTHONHASHSEED=0 python -m pytest -q tests/test_add_rows.py -s
"""
import os
import subprocess
import sys

import pytest

pytest.importorskip("sympy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _legacy_add as legacy  # noqa: E402
from sympy import (  # noqa: E402
    Add, Basic, E, Float, I, Integer, Rational, S, Symbol, cos, oo, pi, sin, sqrt, symbols, zoo,
)

from satassume.knowledge.rules import BASIS, RULE_CLAUSES  # noqa: E402
from satassume.knowledge.templates import _common, registry, wiring  # noqa: E402
from satassume.knowledge.templates._common import Compiled, consts_of, pattern_key  # noqa: E402
from satassume.knowledge.templates._compiled_rows import FAMILIES  # noqa: E402
from satassume.knowledge.templates._rows import generator  # noqa: E402
from satassume.sat.solver import Solver  # noqa: E402

FAMILY = f"{wiring.__name__}:add"
ARITIES = (2, 3, 4, 5, 6, 7, 8, 31, 32, 33, 40)
#: ``2*I`` is no constant (not atomic): a term of its own
CONSTANTS = (S.Zero, S.One, S.NegativeOne, Integer(2), S.Half, Integer(-3), Float(2.0),
             Float(2.5), oo, -oo, zoo, S.NaN, pi, E, I, -I, 2*I)


def rows_template():
    """The template of the rows, registered for Add and attributed to the
    family."""
    registry.templates_for(Add)
    [t] = [t for t in registry._by_class[Add] if t.__module__ == FAMILY]
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
        yield Basic.__new__(Add, *(consts.get(k, x) for k, x in enumerate(xs)))


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
        self.nodes = self.blocks = self.clauses = self.formulas = self.wide = 0
        self.added, self.missing, self.other = [], [], []


def _wide(c):
    """The rules of a block past ``MAX_EXPAND`` (``Pattern.wide``, encoded as
    formulas): the premises of the extended real sum without oo and -oo
    from 5 terms on, which expand to ``2**n`` clauses."""
    return {(frozenset(ps), frozenset(cs)) for ps, cs in c.pattern.wide}


def compare(nodes, template=None):
    """Both templates on each node: the differences (:class:`Result`)."""
    template = template or rows_template()
    out = Result()
    for e in nodes:
        new, new_keys = run(template, e)
        old, old_keys = run(legacy.add_templates, e)
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
            if a.objs != b.objs:
                out.other.append((e, 'slots differ', a.objs, b.objs))
                continue
            if _wide(a) != _wide(b):
                out.other.append((e, 'rules past MAX_EXPAND differ'))
            out.wide += len(a.pattern.wide)
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
          f"{r.formulas} formulas, {r.wide} rules past MAX_EXPAND, ADDED {len(r.added)}, MISSING {len(r.missing)}, "
          f"other {len(r.other)}")


def test_the_rows_entail_exactly_the_legacy_rules_per_pattern():
    nodes = [e for n in ARITIES for e in pattern_nodes(n)]
    r = compare(nodes)
    _report("patterns", r)
    assert not (r.added or r.missing or r.other), (r.added[:2], r.missing[:2], r.other[:2])
    k = len(CONSTANTS)
    assert len(nodes) == sum(1 + k * len(positions(n)) + k * k for n in ARITIES)
    assert r.formulas > 100           # the strict-sign formulas of 33 and 40 terms


x, y, z, w = symbols('x y z w')
r, p, ng = Symbol('r', real=True), Symbol('p', positive=True), Symbol('ng', negative=True)
n, m, ev, od = Symbol('n', integer=True), Symbol('m', integer=True), Symbol('e', even=True), \
    Symbol('o', odd=True)
A, B = symbols('A B', commutative=False)


def sympy_nodes():
    """SymPy's own sums: a constant and a term, x - y, x + I*y, pi + x,
    infinite terms, sums of 2 .. 9 terms, the sums of a special shape
    (half-integer coefficients, c0 + c1*u, c0 + c1/v, I*(c_1*x_1 + ...)),
    non-commutative terms and wide ones."""
    syms = (x, r, p, ng, n, ev, od, y, z, w)
    out = []
    for c in (Integer(2), Integer(-3), S.Half, Rational(-3, 2), Float(2.5), oo, -oo, zoo, pi,
              E, I, -I, 2*I, sqrt(2)):
        out += [Add(c, x, evaluate=False), Add(x, c, evaluate=False), Add(c, n, evaluate=False),
                Add(c, x, y, evaluate=False), Add(x, c, y, evaluate=False)]
    out += [x + 1, x - 1, x - y, x + y, x + y + z, -x - y, x + I*y, r + I*y, pi + x, x + oo,
            x - oo, n + oo, x + zoo, p + ng, p + r, ev + od, ev + ev*od, n + m, n - m + 1,
            Add(*syms[:5]), Add(*syms[:6]), Add(*syms[:7]), Add(*syms[:8]), Add(*syms[:9]),
            Add(*syms), x*y + z, x**2 + 1, sin(x) + cos(x),
            # half-integer coefficients
            x/2 + y/2 + S.Half, n/2 + S.Half, n/2 + m/2, 3*n/2 + m/2 + S(3)/2, n/2 + m/4,
            Add(S.Half, S.Half, n/2, evaluate=False), n*m/2 + S.Half, n/2 + x*(1/x)/2,
            ev/2 + od/2 + n/2 + m/2 + x/2 + y/2,
            # c0 + c1*u and c0 + c1/v
            3 + 2*x, 3 + 2*n, 1 - n, -1 + 2*n, S.Half - n, -3 - 2*ev, 2 + od, 1 + 2/x,
            1 - 1/n, 2 + 1/n, -1 + 3/ev, S.Half + 1/(2*n), Rational(1, 3) - n/3, 2 + 2.5*n,
            # I*(c_1*x_1 + ...)
            I*x - 2*I*y + I, I*x + I, I*x + I*y, I*p + 2*I*r, I*x - I, 2*I*x - 3*I*y - I,
            -sqrt(3)*I/2 + Float('0.866025403784439')*I, I*pi + I, I*x + I*pi, I*sqrt(2) + I,
            Add(*[I*s for s in symbols('i:7')]), Add(*[I*s for s in symbols('i:6')]),
            I*x + y,
            # non-commutative and wide
            A + B, A + 1, A + B + x,
            Add(*symbols('a:40')), Add(*symbols('a:40', positive=True)),
            Add(*symbols('a:33')) + 1, Add(*symbols('a:34')) + oo, Add(*symbols('a:32')),
            Add(*symbols('a:33', nonnegative=True)) - 1]
    return out


def test_the_rows_entail_exactly_the_legacy_rules_per_node():
    from test_template_tables import _subexprs, synthetic_nodes
    nodes = [e for e in sympy_nodes() if isinstance(e, Add)]
    synthetic = [e for e in _subexprs(synthetic_nodes()) if isinstance(e, Add)]
    assert len(nodes) > 120 and len(synthetic) > 30
    nodes += synthetic
    r = compare(nodes)
    _report("nodes", r)
    assert not (r.added or r.missing or r.other), (r.added[:2], r.missing[:2], r.other[:2])
    # the sums of a special shape are blocks too
    assert r.blocks > r.nodes + 30


def _single(gen, schema):
    """A generator of ``gen``'s terms with one schema."""
    g = generator('Add', gen.arity, (), (), FAMILY)
    g.terms = gen.terms
    g.specs = {}
    g.schemas = (schema,)
    return g


def test_every_compiled_rule_is_used():
    # every rule of the compiled rows gives a rule in the block of some
    # pattern: its constants do not decide it.  Two give no clause: their
    # conclusion is commutative, which the rule base reads as true (every
    # term in scope is commutative), the closure and the commutative term
    # of a commutative sum
    [(name, arity, terms, specs, schemas)] = dict(FAMILIES)['add']
    gen = generator(name, arity, terms, specs, FAMILY, schemas)
    assert not gen.specs and len(gen.schemas) == 42
    rules = [_single(gen, s) for s in gen.schemas]
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
    assert not no_rule, [gen.schemas[i] for i in no_rule]
    assert len(no_clause) == 2 and all(rules[i].schemas[0][2][0][1][0][1] == 'commutative'
                                       for i in no_clause), no_clause


def test_the_pattern_keys_are_legacys():
    # the cache is keyed as before: ('add', n, consts), then the keys of the
    # sums of a special shape
    for e in (Basic.__new__(Add, x, Integer(2), y), Basic.__new__(Add, pi, x), x + 1,
              3 + 2*n, 1 + 2/x, n/2 + S.Half, I*x + I):
        _, keys = run(rows_template(), e)
        _, old = run(legacy.add_templates, e)
        assert pattern_key('add', len(e.args), consts_of(e.args)) in keys and keys == old


def test_add_is_compiled_on_its_own_first_use():
    code = """
import sys
from sympy import Add, Q, Symbol
from satassume.knowledge.templates.registry import registry
from satassume.sympy_api import ask
ADD = "satassume.knowledge.templates.add"
WIRING = "satassume.knowledge.templates.wiring"
x, y = Symbol('x'), Symbol('y')
assert ask(Q.positive(x), Q.positive(x) & Q.real(y)) is True
assert WIRING not in sys.modules
assert ask(Q.positive(x + y), Q.positive(x) & Q.positive(y)) is True
assert ask(Q.real(x), Q.real(x - 2)) is True
# the compiled rows, not the module of the rows
assert WIRING in sys.modules and ADD not in sys.modules
[t] = registry._by_class[Add]
assert t.__module__ == WIRING + ":add", t.__module__
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         timeout=120)
    assert out.returncode == 0, out.stderr

