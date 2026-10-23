"""The template of the rows of ``Mul`` (``templates/mul.py``,
``wiring.product``, #299, U2): the pattern keys, the blocks of a node (one
per factor set, then ``a/v**k``, then the zero formula of a wide product),
that every compiled rule is used, and the first use.  That the rows entail
exactly what the templates before them emitted was checked against a
verbatim copy of those (removed with it); that each rule is true, by
``tests/test_rows_numeric.py``; that none is lost, by
``tests/test_rows_baseline.py``."""
import subprocess
import sys

import pytest

pytest.importorskip("sympy")

from sympy import (  # noqa: E402
    Basic, E, Float, I, Integer, Mul, S, oo, pi, symbols, zoo,
)

from satassume.knowledge.templates import _common, registry, wiring  # noqa: E402
from satassume.knowledge.templates._common import Compiled, consts_of, pattern_key  # noqa: E402
from satassume.knowledge.templates._compiled_rows import FAMILIES  # noqa: E402
from satassume.knowledge.templates._rows import generator  # noqa: E402
from satassume.knowledge.templates.core import _mul_factor_sets  # noqa: E402

FAMILY = f"{wiring.__name__}:mul"
ARITIES = (2, 3, 4, 5, 6, 7, 8)
CONSTANTS = (S.Zero, S.One, S.NegativeOne, Integer(2), S.Half, Integer(-3), Float(2.0),
             Float(2.5), oo, -oo, zoo, S.NaN, pi, E, I, -I)


def rows_template():
    """The template of the rows, registered for Mul and attributed to the
    family."""
    registry.templates_for(Mul)
    [t] = [t for t in registry._by_class[Mul] if t.__module__ == FAMILY]
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


x, y, z = symbols('x y z')


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
    assert len(gen.schemas) == 52 and len(gen.specs[2]) == 29
    nodes = [e for n in ARITIES for e in pattern_nodes(n)]
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
        sets = _mul_factor_sets(e)
        assert keys == {pattern_key('mul', len(f), consts_of(f)) for f in sets}


def test_the_blocks_of_a_node():
    # one block per factor set, then a/v**k, then past 32 factors the zero
    # row as one formula; a block of two factors has a slot for 2*coefficient.
    # 3*x*y has no block over (3, x*y): its sign against x*y is the relation
    # glue's (relations "Products", #315)
    out, _ = run(rows_template(), 3*x*y)
    assert [c.objs for c in out] == [(3, x, y, 3*x*y)]
    out, _ = run(rows_template(), 3*x)
    assert [c.objs for c in out] == [(3, x, 3*x, None)]
    out, _ = run(rows_template(), x/y**2)
    assert len(out) == 2 and out[1].objs == (x, y, y**-2, x/y**2)
    xs = symbols('a:40')
    out, _ = run(rows_template(), Mul(*xs))
    assert len(out) == 2 and isinstance(out[0], Compiled) and not isinstance(out[1], Compiled)
    assert len(run(rows_template(), Mul(*xs[:32]))[0]) == 1


def test_a_node_of_one_factor_is_that_factor():
    # SymPy builds no product of one factor, but a node built by hand is
    # its factor: a prime, not composite (the rows of two primes or more)
    from satassume.sympy_api import ask
    from sympy import Q, Symbol
    z = Symbol('z')
    assert ask(Q.composite(Basic.__new__(Mul, z)), Q.prime(z)) is None
    assert ask(Q.composite(Basic.__new__(Mul, z, z)), Q.prime(z)) is True


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
# the rows of Add are loaded, not those of Mul
assert WIRING in sys.modules and Mul not in registry._by_class
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
