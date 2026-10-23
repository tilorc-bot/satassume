"""The template of the rows of ``Add`` (``templates/add.py``,
``wiring.addition``, #299, U1): the pattern keys, the blocks of a node (the
rows over the terms, then the strict-sign formulas of a wide sum, then the
sums of a special shape), that every compiled rule is used, and the first
use.  That the rows entail exactly what the templates before them emitted
was checked against a verbatim copy of those (removed with it); that each
rule is true, by ``tests/test_rows_numeric.py``; that none is lost, by
``tests/test_rows_baseline.py``."""
import subprocess
import sys

import pytest

pytest.importorskip("sympy")

from sympy import (  # noqa: E402
    Add, Basic, E, Float, I, Integer, S, Symbol, oo, pi, symbols, zoo,
)

from satassume.knowledge.templates import _common, registry, wiring  # noqa: E402
from satassume.knowledge.templates._common import Compiled, consts_of, pattern_key  # noqa: E402
from satassume.knowledge.templates._compiled_rows import FAMILIES  # noqa: E402
from satassume.knowledge.templates._rows import generator  # noqa: E402

FAMILY = f"{wiring.__name__}:add"
ARITIES = (2, 3, 4, 5, 6, 7, 8)
#: ``2*I`` is no constant (not atomic): a term of its own
CONSTANTS = (S.Zero, S.One, S.NegativeOne, Integer(2), S.Half, Integer(-3), Float(2.0),
             Float(2.5), oo, -oo, zoo, S.NaN, pi, E, I, -I, 2*I)


def rows_template():
    """The template of the rows, registered for Add and attributed to the
    family."""
    registry.templates_for(Add)
    [t] = [t for t in registry._by_class[Add] if t.__module__ == FAMILY]
    return t


def patterns(n):
    """Constants at no position, at each one, and at the first and the last."""
    yield {}
    for k in range(n):
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


x, y = symbols('x y')
n = Symbol('n', integer=True)


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
    assert not gen.specs and len(gen.schemas) == 44
    rules = [_single(gen, s) for s in gen.schemas]
    nodes = [e for k in ARITIES for e in pattern_nodes(k)]
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
    def add(e):
        return pattern_key('add', len(e.args), consts_of(e.args))
    for e in (Basic.__new__(Add, x, Integer(2), y), Basic.__new__(Add, pi, x), x + y):
        assert run(rows_template(), e)[1] == {add(e)}
    e = 3 + 2*n
    assert run(rows_template(), e)[1] == {add(e), ('add_bound', 3, 2)}
    e = 1 + 2/x
    assert run(rows_template(), e)[1] == {add(e), ('add_bound', 1, 2), ('add_recip', 1, 2)}
    e = n/2 + S.Half
    assert run(rows_template(), e)[1] == {add(e), ('add_bound', S.Half, S.Half),
                                          ('add_half', 1, (1,), ())}
    e = I*x + I
    assert run(rows_template(), e)[1] == {add(e), ('add_imag', (1,), frozenset({1}), ())}


def test_the_blocks_of_a_node():
    # the rows over the terms, then past 32 terms the strict-sign rows as
    # one formula each, then the sums of a special shape
    out, _ = run(rows_template(), 1 + 2/x)
    assert [c.objs for c in out] == [(1, 2/x, 1 + 2/x), (1/x, 1 + 2/x), (x, 1 + 2/x)]
    xs = symbols('a:40')
    out, _ = run(rows_template(), Add(*xs))
    assert len(out) == 3 and isinstance(out[0], Compiled)
    assert not any(isinstance(f, Compiled) for f in out[1:])
    assert len(run(rows_template(), Add(*xs[:32]))[0]) == 1
    # a constant term 1 is not nonpositive: no formula of a negative sum
    out, _ = run(rows_template(), Add(*xs[:33]) + 1)
    assert len(out) == 2 and 'extended_positive' in str(out[1])


def test_a_node_of_one_term_is_that_term():
    # SymPy builds no sum of one term, but a node built by hand is its
    # term: 2 is neither composite, nor 1 prime or composite (the rows of
    # two terms or more)
    from satassume.sympy_api import ask
    from sympy import Q, Symbol
    z = Symbol('z')
    one = Basic.__new__(Add, z)
    assert ask(Q.composite(one), Q.even(z) & Q.positive(z)) is None
    assert ask(Q.prime(one) | Q.composite(one), Q.integer(z) & Q.positive(z)) is None
    two = Basic.__new__(Add, z, z)
    assert ask(Q.composite(two), Q.even(z) & Q.positive(z)) is True


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

