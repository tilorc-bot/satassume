"""The rules of ``gamma``, ``loggamma``, ``digamma``, ``trigamma``,
``polygamma``, ``lowergamma`` and ``uppergamma``, written as ``for_all``
statements (``templates/gamma_functions.py``, compiled by
``templates/wiring.py``, #249), against the generators they replace
(``tests/_legacy_gamma_functions_rules.py``, verbatim from d149951).

The comparison is ``tests/_rows_equivalence.py``'s: the rows and the
legacy generators plus :data:`ADDED` entail each other on every node of
its corpus (the heads of two arguments on every pair of arguments), though
the clauses differ.  Rows of the legacy generators the rows leave out
because the rule base and the other rows imply them: ``trigamma``'s
``real & ~integer -> real`` (positive there).  :data:`ADDED`
are the facts the rows give that the legacy rules did not, each with its
argument; a test checks that each is new.
"""
import os
import subprocess
import sys

import pytest

pytest.importorskip("sympy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _legacy_gamma_functions_rules as legacy  # noqa: E402
import _rows_equivalence as eq  # noqa: E402
from sympy import (  # noqa: E402
    Add, Float, I, Q, S, Symbol, digamma, gamma, loggamma, lowergamma, pi, polygamma, trigamma,
    uppergamma,
)

from satassume.knowledge.templates import _common, wiring  # noqa: E402
from satassume.knowledge.templates._rows import rules, x  # noqa: E402
from satassume.knowledge.templates.functions import N, X, _unary, nary, shifted  # noqa: E402

HEADS = (gamma, loggamma, digamma, trigamma, polygamma, lowergamma, uppergamma)

#: facts the rows give and the legacy rules did not
ADDED = {}


def _nary(gen):
    """``gen`` as ``functions.nary`` called it, with the number of arguments,
    which ``wiring.template`` takes from ``gen.arity``."""
    def nary_gen(R, n):
        gen(R, n)
    nary_gen.arity = 2
    return nary_gen


LEGACY_GEN = {
    gamma: legacy._gamma, loggamma: legacy._loggamma,
    digamma: lambda R, c: legacy._polygamma_rules(R, None, X, N, 0),
    trigamma: lambda R, c: legacy._polygamma_rules(R, None, X, N, 1),
    polygamma: _nary(legacy._polygamma), lowergamma: _nary(legacy._lowergamma),
    uppergamma: _nary(legacy._uppergamma),
}


def test_rows_entail_exactly_the_legacy_rules_and_the_added_facts():
    new = eq.check_rows_entail_exactly(HEADS, "gamma_functions", LEGACY_GEN, ADDED)
    # the corpus reaches gamma's slot x - 1/2 (3 objects) and the node of
    # polygamma(n, x), slot 2
    assert any(len(c.objs) == 3 for e, (cs, _) in new.items() if type(e) is gamma for c in cs)
    assert {c.pattern.node for e, (cs, _) in new.items() if type(e) is polygamma
            for c in cs} == {2}


def test_each_added_fact_is_new():
    eq.check_added_are_new(LEGACY_GEN, ADDED)


def test_the_templates_keep_their_pattern_keys_and_slot_objects():
    """The template of each head from its rows caches its patterns under the
    keys of the legacy template (``special.py`` at d149951), over the same
    objects: ``gamma``'s slot ``x - 1/2`` is ``shifted(x, -1/2)`` (#184:
    ``Add(y, -y, 1/2) - 1/2`` is not 0)."""
    old = {gamma: _unary('gamma', legacy._gamma, slots=lambda a: (shifted(a, -S.Half),)),
           loggamma: _unary('loggamma', legacy._loggamma),
           digamma: _unary('digamma', LEGACY_GEN[digamma]),
           trigamma: _unary('trigamma', LEGACY_GEN[trigamma]),
           polygamma: nary('polygamma', legacy._polygamma),
           lowergamma: nary('lowergamma', legacy._lowergamma),
           uppergamma: nary('uppergamma', legacy._uppergamma)}
    rows = eq.rows_templates(HEADS, "gamma_functions")
    y = Symbol('y')
    extra = [gamma(Add(y, -y, S.Half, evaluate=False), evaluate=False)]
    try:
        for e in eq.nodes(HEADS) + extra:
            seen = []
            for t in (old[type(e)], rows[type(e)]):
                _common._CACHE.clear()
                c = t(e)
                seen.append(None if c is None else (tuple(_common._CACHE), c.objs))
            assert seen[0] == seen[1], e
    finally:
        _common._CACHE.clear()
    assert rows[gamma](extra[0]).objs[2] == Add(extra[0].args[0], -S.Half, evaluate=False)
    _common._CACHE.clear()


# -- rational numbers in rows ------------------------------------------------

def _specs(head, table):
    R = _common.Rules()
    rules(head, table, __name__)(R, None)
    return sorted((sorted(p), c) for p, c in R.rules)


def test_an_inequality_with_a_rational_is_a_fact_about_x_minus_c():
    # Q.gt(x, 1/2) is extended_positive(x - 1/2), as for an integer
    for rel, lit in ((Q.gt(x, S.Half), ('extended_positive', True)),
                     (Q.le(x, S.Half), ('extended_nonpositive', True)),
                     (Q.ne(x, S.Half), ('zero', False)),
                     (Q.lt(S.Half, x), ('extended_positive', True))):
        assert _specs(gamma, rel >> Q.real(gamma(x))) == [([(2, *lit)], [(1, 'real', True)])]
    assert rules(gamma, Q.gt(x, S.Half) >> Q.real(gamma(x)), __name__).shifts == (-S.Half,)
    assert rules(gamma, Q.gt(x, -S.Half) >> Q.real(gamma(x)), __name__).shifts == (S.Half,)


def test_a_fact_about_x_minus_c_that_is_not_its_sign_is_written_on_the_term():
    assert _specs(gamma, Q.even(x - S.Half) >> Q.positive(gamma(x))) == [
        ([(2, 'even', True)], [(1, 'positive', True)])]
    # the term and an inequality with the same c share the slot
    row = (Q.odd(x - S.Half) & Q.lt(x, S.Half)) >> Q.negative(gamma(x))
    assert _specs(gamma, row) == [
        ([(2, 'extended_negative', True), (2, 'odd', True)], [(1, 'negative', True)])]
    # and an integer c
    assert _specs(gamma, Q.even(x + 1) >> Q.real(gamma(x))) == [
        ([(2, 'even', True)], [(1, 'real', True)])]


def test_the_slots_of_rationals_are_by_abs_c_x_minus_c_first():
    rows = (Q.eq(x, 1) >> Q.zero(gamma(x)), Q.odd(x + S.Half) >> Q.zero(gamma(x)),
            Q.gt(x, -1) >> Q.zero(gamma(x)), Q.even(x - S.Half) >> Q.zero(gamma(x)),
            Q.lt(x, 2) >> Q.zero(gamma(x)))
    gen = rules(gamma, rows, __name__)
    assert gen.shifts == (-S.Half, S.Half, -1, 1, -2)
    y = Symbol('y')
    a = Add(y, -y, 1, evaluate=False)
    _common._CACHE.clear()
    try:
        [c], _ = eq.compiled({gamma: wiring.template(gamma, gen)}, gamma(a, evaluate=False))
    finally:
        _common._CACHE.clear()
    assert c.objs[2:] == tuple(shifted(a, d) for d in (-S.Half, S.Half, -1, 1, -2))


@pytest.mark.parametrize("row, match", [
    # the sign of x - c is the inequality
    (Q.positive(x - S.Half) >> Q.real(gamma(x)), "is an inequality"),
    (Q.extended_nonnegative(x - S.Half) >> Q.real(gamma(x)), "is an inequality"),
    (Q.zero(x + 1) >> Q.real(gamma(x)), "Q.gt\\(x, 1\\) and the like"),
    # a term is the argument plus an exact real number
    (Q.even(x - Float(0.5)) >> Q.real(gamma(x)), "plus a number"),
    (Q.even(2*x - 1) >> Q.real(gamma(x)), "plus a number"),
    (Q.even(x + Symbol('y')) >> Q.real(gamma(x)), "plus a number"),
    (Q.even(Symbol('y', real=True) + 1) >> Q.real(gamma(x)), "plain Symbol"),
    # an inequality compares the argument with an exact real number
    (Q.gt(x, Float(0.5)) >> Q.real(gamma(x)), "with a number"),
    (Q.gt(x, I) >> Q.real(gamma(x)), "with a number"),
])
def test_rows_with_rationals_that_do_not_compile(row, match):
    with pytest.raises(ValueError, match=match):
        rules(type(row.args[1].arguments[0]), row, __name__)


def test_terms_with_an_exact_real_number_or_of_any_argument_compile():
    # accepted since the zeta/Bessel language (exact real numbers, terms of
    # any argument of a function of several)
    for row in (Q.even(x - pi) >> Q.real(gamma(x)), Q.gt(x, pi) >> Q.real(gamma(x))):
        assert rules(gamma, row, __name__).terms == {1: ((0, -pi),)}
    a = Symbol('a')
    gen = rules(lowergamma, Q.even(x - S.Half) >> Q.real(lowergamma(a, x)), __name__)
    assert (gen.arity, gen.terms) == (2, {2: ((1, -S.Half),)})


def test_gamma_functions_are_compiled_on_their_own_first_use():
    code = """
import sys
from sympy import Q, S, Symbol, digamma, gamma, loggamma, lowergamma, polygamma, trigamma
from sympy import uppergamma
from satassume.knowledge.templates.registry import registry
from satassume.sympy_api import ask
ROWS = "satassume.knowledge.templates.gamma_functions"
WIRING = "satassume.knowledge.templates.wiring"
x, s = Symbol('x'), Symbol('s', even=True, negative=True)
assert ask(Q.positive(gamma(s + S.Half))) is True
for other in ("special", "beta_functions", "trig"):
    assert "satassume.knowledge.templates." + other not in sys.modules, other
pending = {m for _, m in registry._lazy}
assert WIRING + ":gamma_functions" not in pending
assert WIRING + ":beta_functions" in pending
# the rows are read compiled: the family module is not imported
assert ROWS not in sys.modules
for h in (gamma, loggamma, digamma, trigamma, polygamma, lowergamma, uppergamma):
    assert [t.__module__ for t in registry._by_class[h]] == [WIRING + ":gamma_functions"]
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
