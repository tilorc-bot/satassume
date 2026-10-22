"""The rules of ``beta``, ``betainc`` and ``betainc_regularized``, written
as ``for_all`` statements (``templates/beta_functions.py``, compiled by
``templates/wiring.py``, #249), against the generators they replace
(``tests/_legacy_beta_functions_rules.py``, verbatim from d149951).

The comparison is ``tests/_rows_equivalence.py``'s: the rows and the
legacy generators plus :data:`ADDED` entail each other on every node of
its corpus (``beta`` of one argument and of every pair, ``betainc`` and
``betainc_regularized`` of every four of its smaller corpus), though the
clauses differ.  Rows of the legacy generators the rows leave out because
the rule base and the other rows imply them: none.  :data:`ADDED` are the
facts the rows give that the legacy rules did not, each with its argument;
a test checks that each is new.
"""
import os
import subprocess
import sys

import pytest

pytest.importorskip("sympy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _legacy_beta_functions_rules as legacy  # noqa: E402
import _rows_equivalence as eq  # noqa: E402
from sympy import Basic, Q, Symbol, beta, betainc, betainc_regularized  # noqa: E402

from satassume.knowledge.templates import _common  # noqa: E402
from satassume.knowledge.templates._rows import by_function, f, for_all, rules, x, y  # noqa: E402
from satassume.knowledge.templates.functions import nary  # noqa: E402

HEADS = (beta, betainc, betainc_regularized)

#: the numbers of arguments the corpus gives beta: beta(x) is beta(x, x)
ARITIES = {beta: (1, 2)}

#: facts the rows give and the legacy rules did not
ADDED = {}


def _nary(gen, arity):
    """``gen`` as ``functions.nary`` called it, with the number of arguments,
    which ``wiring.template`` takes from ``gen.arity``."""
    def nary_gen(R, n):
        gen(R, n)
    nary_gen.arity = arity
    return nary_gen


LEGACY_GEN = {beta: _nary(legacy._beta, (1, 2)), betainc: _nary(legacy._betainc, 4),
              betainc_regularized: _nary(legacy._betainc, 4)}


def test_rows_entail_exactly_the_legacy_rules_and_the_added_facts():
    new = eq.check_rows_entail_exactly(HEADS, "beta_functions", LEGACY_GEN, ADDED, ARITIES)
    # the node is slot n, after the n arguments
    assert {(len(e.args), c.pattern.node) for e, (cs, _) in new.items() for c in cs} == {
        (1, 1), (2, 2), (4, 4)}


def test_each_added_fact_is_new():
    eq.check_added_are_new(LEGACY_GEN, ADDED)


def test_the_templates_keep_their_pattern_keys_and_slot_objects():
    """The template of each head from its rows caches its patterns under the
    keys of the legacy template (``special.py`` at d149951), over the same
    objects; a node of another number of arguments gets no facts."""
    old = {beta: nary('beta', legacy._beta), betainc: nary('betainc', legacy._betainc),
           betainc_regularized: nary('betainc_regularized', legacy._betainc)}
    rows = eq.rows_templates(HEADS, "beta_functions")
    try:
        for e in eq.nodes(HEADS, ARITIES):
            seen = []
            for t in (old[type(e)], rows[type(e)]):
                _common._CACHE.clear()
                c = t(e)
                seen.append((tuple(_common._CACHE), c.objs))
            assert seen[0] == seen[1], e
    finally:
        _common._CACHE.clear()
    a = Symbol('a')
    assert rows[beta](Basic.__new__(beta, a, a, a)) is None
    assert rows[betainc](Basic.__new__(betainc, a, a, a)) is None


# -- rows of several numbers of arguments ------------------------------------

def _specs(gen, n):
    R = _common.Rules()
    gen(R, n)
    return sorted((sorted(p), c) for p, c in R.rules)


def test_rows_of_several_numbers_of_arguments_compile_for_each():
    [(_, rows)] = by_function((for_all((beta,),
        Q.positive(x) >> Q.positive(f(x)),
        (Q.positive(x) & Q.positive(y)) >> Q.positive(f(x, y))),))
    gen = rules(beta, rows, __name__)
    assert gen.arity == (1, 2)
    assert _specs(gen, 1) == [([(0, 'positive', True)], [(1, 'positive', True)])]
    assert _specs(gen, 2) == [([(0, 'positive', True), (1, 'positive', True)],
                               [(2, 'positive', True)])]
    assert _specs(gen, 3) == []
    # one number of arguments: every row, whatever gen is called with
    gen = rules(beta, rows[1], __name__)
    assert gen.arity == 2 and len(_specs(gen, None)) == 1


def test_rows_of_several_numbers_of_arguments_may_compare_with_a_number():
    # accepted since the zeta/Bessel language: each number of arguments gets
    # the terms of its own rows (gen.terms), as slots after its node
    rows = (Q.gt(x, 1) >> Q.positive(beta(x, evaluate=False)),
            (Q.positive(x) & Q.positive(y)) >> Q.positive(beta(x, y)))
    gen = rules(beta, rows, __name__)
    assert (gen.arity, gen.terms) == ((1, 2), {1: ((0, -1),), 2: ()})
    assert _specs(gen, 1) == [([(2, 'extended_positive', True)], [(1, 'positive', True)])]
    assert _specs(gen, 2) == [([(0, 'positive', True), (1, 'positive', True)],
                               [(2, 'positive', True)])]


def test_a_function_whose_constructor_takes_no_evaluate_is_bound():
    # betainc_regularized.__new__ takes no keyword
    [(_, rows)] = by_function((for_all((betainc_regularized,),
        Q.real(x) >> Q.real(f(x, y, Symbol('a'), Symbol('b')))),))
    assert rows[0].args[1].arguments[0].func is betainc_regularized
    gen = rules(betainc_regularized, rows, __name__)
    assert gen.arity == 4
    assert _specs(gen, 4) == [([(0, 'real', True)], [(4, 'real', True)])]


def test_beta_functions_are_compiled_on_their_own_first_use():
    code = """
import sys
from sympy import Q, Symbol, beta, betainc, betainc_regularized
from satassume.knowledge.templates.registry import registry
from satassume.sympy_api import ask
ROWS = "satassume.knowledge.templates.beta_functions"
WIRING = "satassume.knowledge.templates.wiring"
x, y = Symbol('x'), Symbol('y')
assert ask(Q.positive(beta(x, y)), Q.positive(x) & Q.positive(y)) is True
assert ask(Q.positive(beta(x, evaluate=False)), Q.positive(x)) is True
for other in ("special", "gamma_functions", "trig"):
    assert "satassume.knowledge.templates." + other not in sys.modules, other
pending = {m for _, m in registry._lazy}
assert WIRING + ":beta_functions" not in pending
assert WIRING + ":gamma_functions" in pending
# the rows are read compiled: the family module is not imported
assert ROWS not in sys.modules
for h in (beta, betainc, betainc_regularized):
    assert [t.__module__ for t in registry._by_class[h]] == [WIRING + ":beta_functions"]
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
