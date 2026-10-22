"""The rows of ``beta``, ``betainc`` and ``betainc_regularized``
(``templates/beta_functions.py``, compiled by ``templates/wiring.py``,
#249): rows of several numbers of arguments, a constructor without
``evaluate``, the slots of the templates, and the family compiled on its
own first use.  Whether each compiled rule is true is checked at concrete
points in ``tests/test_rows_numeric.py``.
"""
import os
import subprocess
import sys

import pytest

pytest.importorskip("sympy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _rows_templates import compiled, rows_templates  # noqa: E402
from sympy import Basic, Q, Symbol, beta, betainc, betainc_regularized  # noqa: E402

from satassume.knowledge.templates import _common  # noqa: E402
from satassume.knowledge.templates._rows import by_function, f, for_all, rules, x, y  # noqa: E402

HEADS = (beta, betainc, betainc_regularized)


def test_the_node_is_slot_n_after_the_n_arguments():
    # a node of another number of arguments gets no facts
    rows = rows_templates(HEADS, "beta_functions")
    a, b, c, d = Symbol('a'), Symbol('b'), Symbol('c'), Symbol('d')
    for h, args in ((beta, (a,)), (beta, (a, b)), (betainc, (a, b, c, d)),
                    (betainc_regularized, (a, b, c, d))):
        e = Basic.__new__(h, *args)
        assert [(cs.objs, cs.pattern.node) for cs in compiled(rows, e)[0]] == [
            ((*args, e), len(args))]
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
