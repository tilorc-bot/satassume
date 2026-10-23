"""The rows of ``Max``, ``Min`` and ``Piecewise`` (``templates/selection.py``,
their template ``wiring.any_arity``, #299) entail exactly what the templates
they replace emitted (``tests/_legacy_selection.py``, verbatim from eaaa6d2).

Their rules depend only on the pattern: the head, the number ``n`` of
values and the constants among them by position.  So the main check is
per pattern: for each head, ``n`` in 1 (a node of one argument, built with
``Basic.__new__``: SymPy evaluates ``Max(x)`` to ``x``), 2 .. 8, 12 and 33
(the derived negatives are left out from 5 values, or 3), and constants at
no position, at each position (one) and at the first and the last (two),
drawn from :data:`CONSTANTS`.  The node is built with ``Basic.__new__`` so
that SymPy keeps every argument (``Max(1, 2)`` is ``2``, ``Max(I, x)``
raises), as a template sees only the arguments.  Then per node: SymPy's own
``Max`` and ``Min`` of 2 .. 6 arguments, ``Piecewise`` with and without a
final ``True``, one of Booleans, and the nodes of these heads among the
totality checker's.

For each, both templates run from empty pattern caches; the pattern keys
must be the same, and so the slots (the values, then the node).  Then each
side's clauses, with the rule base on every slot, must entail every clause
of the other (SAT, both ways): ADDED (clauses of the rows the legacy
template does not entail) and MISSING (the reverse) must be empty.  No
formula past ``MAX_EXPAND`` is encoded by either: a rule over too many
clauses is left out.  Every rule of the compiled rows must be used by some
pattern.

    PYTHONHASHSEED=0 python -m pytest -q tests/test_selection_rows.py -s
"""
import os
import subprocess
import sys

import pytest

pytest.importorskip("sympy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _legacy_selection as legacy  # noqa: E402
from sympy import (  # noqa: E402
    Basic, E, Float, I, Integer, Max, Min, Piecewise, S, Symbol, oo, pi, symbols, zoo,
)
from sympy.logic.boolalg import BooleanFalse, BooleanTrue  # noqa: E402

from satassume.knowledge.rules import BASIS, RULE_CLAUSES  # noqa: E402
from satassume.knowledge.templates import _common, registry, wiring  # noqa: E402
from satassume.knowledge.templates._common import consts_of, pattern_key, resolve  # noqa: E402
from satassume.knowledge.templates._compiled_rows import FAMILIES  # noqa: E402
from satassume.knowledge.templates._rows import generator  # noqa: E402
from satassume.sat.solver import Solver  # noqa: E402

FAMILY = f"{wiring.__name__}:selection"
HEADS = (Max, Min, Piecewise)
LEGACY = {Max: legacy.max_templates, Min: legacy.min_templates,
          Piecewise: legacy.piecewise_templates}
ARITIES = (1, 2, 3, 4, 5, 6, 7, 8, 12, 33)
CONSTANTS = (S.Zero, S.One, S.NegativeOne, Integer(2), S.Half, Float(2.0), Float(2.5), oo, -oo,
             zoo, S.NaN, pi, E, I)


def rows_template(head):
    """The template of the rows, registered for ``head`` and attributed to
    the family."""
    registry.templates_for(head)
    [t] = [t for t in registry._by_class[head] if t.__module__ == FAMILY]
    return t


def node(head, args):
    """``head`` of ``args`` as the template sees it: unevaluated, every
    argument kept; a Piecewise of the values with a final ``True``."""
    if head is Piecewise:
        conds = [Symbol(f'c{i}') > 0 for i in range(len(args) - 1)] + [S.true]
        return Basic.__new__(Piecewise, *(Basic.__new__(_pair(), a, c)
                                          for a, c in zip(args, conds)))
    return Basic.__new__(head, *args)


def _pair():
    from sympy.functions.elementary.piecewise import ExprCondPair
    return ExprCondPair


def patterns(n):
    """Constants at no position, at each one, and at the first and the last."""
    yield {}
    for k in range(n):
        for c in CONSTANTS:
            yield {k: c}
    if n > 1:
        for c in CONSTANTS:
            for d in CONSTANTS:
                yield {0: c, n - 1: d}


def pattern_nodes(head):
    for n in ARITIES:
        xs = symbols(f'x:{n}')
        for consts in patterns(n):
            yield node(head, [consts.get(k, x) for k, x in enumerate(xs)])


def run(template, e):
    """``(compiled, keys)``: the template's output for ``e`` from an empty
    pattern cache, and the keys it cached."""
    _common._CACHE.clear()
    try:
        return template(e), set(_common._CACHE)
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
        self.nodes = self.clauses = self.empty = 0
        self.added, self.missing, self.other = [], [], []


def compare(nodes, templates=None):
    """Both templates on each node: the differences (:class:`Result`)."""
    out = Result()
    for e in nodes:
        head = type(e)
        new, new_keys = run((templates or {}).get(head) or rows_template(head), e)
        old, old_keys = run(LEGACY[head], e)
        out.nodes += 1
        if new is None or old is None:
            if not (new is None and old is None):
                out.other.append((e, 'None on one side'))
            out.empty += 1
            continue
        if isinstance(new, list) or isinstance(old, list):
            out.other.append((e, 'formulas besides the block'))       # wiring.wide_formulas
            continue
        if new_keys != old_keys or new.objs != old.objs:
            out.other.append((e, 'keys or slots differ'))
            continue
        if new.pattern.wide or old.pattern.wide:
            out.other.append((e, 'a formula past MAX_EXPAND'))
        nobjs = len(new.objs)
        out.clauses += len(new.pattern.clauses) + len(old.pattern.clauses)
        added = not_entailed(old, new, nobjs)
        missing = not_entailed(new, old, nobjs)
        if added:
            out.added.append((e, added))
        if missing:
            out.missing.append((e, missing))
    return out


def _report(what, r):
    print(f"\n{what}: {r.nodes} nodes ({r.empty} without facts), {r.clauses} clauses compared, "
          f"ADDED {len(r.added)}, MISSING {len(r.missing)}, other {len(r.other)}")


@pytest.mark.parametrize("head", HEADS, ids=lambda h: h.__name__)
def test_the_rows_entail_exactly_the_legacy_rules_per_pattern(head):
    nodes = list(pattern_nodes(head))
    r = compare(nodes)
    _report(f"{head.__name__} patterns", r)
    assert not (r.added or r.missing or r.other), (r.added[:2], r.missing[:2], r.other[:2])
    assert r.empty == 0
    assert len(nodes) == sum(1 + 14 * n + (196 if n > 1 else 0) for n in ARITIES)


x, y, z, w, v, u = symbols('x y z w v u')
r, p, ng = Symbol('r', real=True), Symbol('p', positive=True), Symbol('ng', negative=True)
n, ev, od = Symbol('n', integer=True), Symbol('e', even=True), Symbol('o', odd=True)


def sympy_nodes():
    """SymPy's own nodes: Max and Min of 2 .. 6 arguments (around the switch
    of the derived negatives, at 2/3 and 4/5 values), with constants, and
    Piecewise with and without a final True, and of Booleans."""
    syms = (x, r, p, ng, n, ev, od, y, z, w)
    out = []
    for head in (Max, Min):
        for k in range(2, 7):
            out.append(head(*syms[:k]))
            out.append(head(*syms[1:k + 1]))
            out.append(head(*syms[:k - 1], Integer(3)))
            out.append(head(*syms[:k - 1], S.Half))
            out.append(head(*syms[:k - 1], pi))
            out.append(head(*syms[:k - 1], oo))
        out += [head(x, y, z, w, v, u), head(x, 2*y, y**2, z + 1), head(x, -oo),
                head(*symbols('a:40', real=True))]
    c = [x > 0, y < 1, z > 2, w > 3, v > 4]
    for k in range(1, 6):
        vals = (x, r, Integer(2), pi, ev, S.Half)[:k + 1]
        out.append(Piecewise(*zip(vals, c[:k] + [True])))                 # a final True
        out.append(Piecewise(*zip(vals, c[:k + 1]), evaluate=False))      # without
    out += [Piecewise((x, x > 0), (y, True)), Piecewise((1, x > 0), (2, True)),
            Piecewise((x, x > 0), (oo, True)), Piecewise((I, x > 0), (x, True)),
            Piecewise((x, x > 0)),
            Piecewise((S.true, x > 0), (S.false, True), evaluate=False),   # of Booleans
            Piecewise((x > 1, x > 0), (y > 1, True)),
            Piecewise(*((Symbol(f'q{i}'), x > i) for i in range(12)), (y, True))]
    return out


def test_the_rows_entail_exactly_the_legacy_rules_per_node():
    from test_template_tables import _subexprs, synthetic_nodes
    nodes = [e for e in sympy_nodes() if isinstance(e, HEADS)]     # Max(x, -oo) is x
    synthetic = [e for e in _subexprs(synthetic_nodes()) if isinstance(e, HEADS)]
    assert len(nodes) > 70 and len(synthetic) > 5
    nodes += synthetic
    r = compare(nodes)
    _report("nodes", r)
    assert not (r.added or r.missing or r.other), (r.added[:2], r.missing[:2], r.other[:2])
    # no facts for a Piecewise without a final True or of Booleans, only
    assert 0 < r.empty < 15
    assert any(isinstance(e.args[0].expr, (BooleanTrue, BooleanFalse)) for e in nodes
               if isinstance(e, Piecewise))


def test_every_compiled_rule_is_used():
    # every rule of the compiled rows gives a rule of some pattern, which
    # its constants do not decide
    for name, *_, schemas in dict(FAMILIES)['selection']:
        gen = generator(name, (), (), (), FAMILY, schemas)
        unused = set(range(len(gen.schemas)))
        for n in ARITIES:
            for consts in patterns(n):
                for i in list(unused):
                    rules = wiring.expand(gen.schemas[i:i + 1], n, consts, True)
                    if resolve(rules, consts):
                        unused.discard(i)
        assert not unused, (name, [gen.schemas[i] for i in unused])


def test_the_pattern_keys_are_legacys():
    # the cache is keyed as before: ('Max', n, consts)
    for head in HEADS:
        for e in (node(head, [x, Integer(2), y]), node(head, [pi, x])):
            values = e.args if head is not Piecewise else tuple(a.expr for a in e.args)
            _, keys = run(rows_template(head), e)
            assert keys == {pattern_key(head.__name__, len(values), consts_of(values))}


def test_selection_is_compiled_on_its_own_first_use():
    code = """
import sys
from sympy import Max, Min, Piecewise, Q, Symbol
from satassume.knowledge.templates.registry import registry
from satassume.sympy_api import ask
SELECTION = "satassume.knowledge.templates.selection"
WIRING = "satassume.knowledge.templates.wiring"
x, y = Symbol('x'), Symbol('y')
assert ask(Q.positive(x + 1), Q.positive(x)) is True
assert WIRING not in sys.modules
assert ask(Q.integer(Max(x, y)), Q.integer(x) & Q.integer(y)) is True
# the compiled rows, not the module of the rows
assert WIRING in sys.modules and SELECTION not in sys.modules
for h in (Max, Min, Piecewise):
    [t] = registry._by_class[h]
    assert t.__module__ == WIRING + ":selection", t.__module__
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         timeout=120)
    assert out.returncode == 0, out.stderr
