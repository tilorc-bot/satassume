"""The template of the rows of ``Max``, ``Min`` and ``Piecewise``
(``templates/selection.py``, ``wiring.any_arity``, #299): the pattern keys,
the values of a ``Piecewise`` (``wiring.piecewise_values``), and the first
use.  That the rows entail exactly what the templates before them emitted
was checked against a verbatim copy of those (removed with it); that each
rule is true, by ``tests/test_rows_numeric.py``; that none is lost, by
``tests/test_rows_baseline.py``."""
import subprocess
import sys

import pytest

pytest.importorskip("sympy")

from sympy import Integer, Max, Min, Piecewise, S, pi, symbols  # noqa: E402

from satassume.knowledge.templates import _common, registry, wiring  # noqa: E402
from satassume.knowledge.templates._common import consts_of, pattern_key  # noqa: E402

FAMILY = f"{wiring.__name__}:selection"
HEADS = (Max, Min, Piecewise)

x, y, z = symbols('x y z')


def rows_template(head):
    """The template of the rows, registered for ``head`` and attributed to
    the family."""
    registry.templates_for(head)
    [t] = [t for t in registry._by_class[head] if t.__module__ == FAMILY]
    return t


def run(head, e):
    """``(compiled, keys)``: the template's output for ``e`` from an empty
    pattern cache, and the keys it cached."""
    _common._CACHE.clear()
    try:
        return rows_template(head)(e), set(_common._CACHE)
    finally:
        _common._CACHE.clear()


def test_the_pattern_keys_are_those_before_the_rows():
    # the cache is keyed as before: ('Max', n, consts), the values, then the node
    for e in (Max(x, 2, y), Min(pi, x), Max(x, y, z),
              Piecewise((x, x > 0), (Integer(2), y > 0), (y, True))):
        head = type(e)
        values = e.args if head is not Piecewise else tuple(a.expr for a in e.args)
        out, keys = run(head, e)
        assert keys == {pattern_key(head.__name__, len(values), consts_of(values))}
        assert out.objs == (*values, e)


def test_the_values_of_a_piecewise():
    assert wiring.piecewise_values(Piecewise((x, x > 0), (y, True))) == (x, y)
    # no final True: nan where no condition holds; Booleans: no value
    for e in (Piecewise((x, x > 0), (y, y > 0)),
              Piecewise((S.true, x > 0), (S.false, True), evaluate=False)):
        assert wiring.piecewise_values(e) is None
        assert run(Piecewise, e)[0] is None


def test_wide_nodes_leave_out_the_negations_of_conjunctions():
    # ~odd of each value is two clauses over the basis: 2**n <= MAX_EXPAND
    for n in (4, 5):
        xs = symbols(f'x:{n}')
        out, _ = run(Max, Max(*xs))
        assert not out.pattern.wide
        odd = [r for r in out.pattern.rules if (n, 'odd', False) in r[1]]
        assert len(odd) == (n <= 4)


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
# the rows of Add are loaded, not those of Max
assert WIRING in sys.modules and Max not in registry._by_class
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
