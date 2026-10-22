"""The rules of ``sin``, ``cos``, ``tan``, ``cot``, ``sec`` and ``csc``,
written as ``for_all`` statements (``templates/trig.py``, compiled by
``templates/wiring.py``) in the row language (``templates/_rows.py``, #249),
against the generators they replace (``tests/_legacy_trig_rules.py``,
verbatim from f9291ab).

The comparison is ``tests/_rows_equivalence.py``'s: the rows and the
legacy generators plus :data:`ADDED` entail each other on every node of
its corpus, though the clauses differ (an implied row is not written:
``cot``'s ``algebraic -> ~algebraic`` follows from its ``zero`` and
``transcendental`` rows, and ``real -> ~imaginary`` of ``tan``, ``cot``,
``sec`` and ``csc`` from ``real & finite(f) -> real(f)``).  :data:`ADDED`
are the facts the rows give that the legacy rules did not, each with its
argument; a test checks that each is new.
"""
import importlib
import os
import subprocess
import sys

import pytest

pytest.importorskip("sympy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _legacy_trig_rules as legacy  # noqa: E402
import _rows_equivalence as eq  # noqa: E402
from sympy import (  # noqa: E402
    Add, Equivalent, Float, I, Q, Symbol, acos, atanh, cos, cot, csc, oo, pi, sec, sin, tan,
)

from satassume.knowledge.templates import ROW_FAMILIES, _common, wiring  # noqa: E402
from satassume.knowledge.templates._rows import (  # noqa: E402
    by_function, closed, f, for_all, rows_of, rules, x,
)
from satassume.knowledge.templates.functions import shifted  # noqa: E402

HEADS = (sin, cos, tan, cot, sec, csc)

#: facts the rows give and the legacy rules did not
ADDED = {
    # tan is meromorphic: where it is finite its value is a number
    tan: ((Q.complex(x) & Q.finite(tan(x))) >> Q.complex(tan(x)),),
    # cos(0) == sec(0) == 1, neither prime nor composite
    cos: (Q.zero(x) >> (~Q.prime(cos(x)) & ~Q.composite(cos(x))),),
    sec: (Q.zero(x) >> (~Q.prime(sec(x)) & ~Q.composite(sec(x))),
          # sec(I*t) == 1/cosh(t) is in (0, 1) for real t != 0
          Q.imaginary(x) >> Q.noninteger(sec(x))),
}

LEGACY_GEN = {sin: legacy._sin, cos: legacy._cos, tan: legacy._tan, cot: legacy._cot,
              sec: legacy._sec, csc: legacy._csc}


def test_rows_entail_exactly_the_legacy_rules_and_the_added_facts():
    new = eq.check_rows_entail_exactly(HEADS, "trig", LEGACY_GEN, ADDED)
    # the corpus reaches the pi*c*s rules
    assert any(len(c.objs) == 3 for cs, _ in new.values() for c in cs)


def test_each_added_fact_is_new():
    eq.check_added_are_new(LEGACY_GEN, ADDED)


def test_trig_is_a_builtin_module():
    # loaded on first use, and its templates are attributed to it, so the
    # registry takes them as built-in (a template attributed to another
    # module would be a user's: every module loaded, every memo emptied)
    code = """
import sys
from sympy import Q, Symbol, cos, cot, csc, sec, sin, tan
from satassume.knowledge.templates.registry import registry
from satassume.sympy_api import ask
TRIG = "satassume.knowledge.templates.trig"
HYPERBOLIC = "satassume.knowledge.templates.hyperbolic"
WIRING = "satassume.knowledge.templates.wiring"
x = Symbol('x')
assert TRIG not in sys.modules and WIRING not in sys.modules
assert ask(Q.real(sin(x)), Q.real(x)) is True
assert TRIG in sys.modules and all(m != WIRING + ":trig" for _, m in registry._lazy)
# each family is compiled on its own first use
assert HYPERBOLIC not in sys.modules
assert "satassume.knowledge.templates.special" not in sys.modules
for h in (sin, cos, tan, cot, sec, csc):
    assert [t.__module__ for t in registry._by_class[h]] == [WIRING + ":trig"]
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr


def _resolved(declared):
    """The declared functions, one declared by name (``"module:Class"``,
    new in a later SymPy) where this SymPy has it."""
    for fn in declared:
        if isinstance(fn, str):
            module, _, name = fn.partition(":")
            fn = getattr(importlib.import_module(module), name, None)
        if fn is not None:
            yield fn


def test_the_declared_functions_are_those_the_rows_name():
    # templates/__init__.py declares each family for its functions without
    # importing the rows (a class of a module SymPy does not import by its
    # name, "module:Class"); the two lists must not drift apart
    for family, declared in ROW_FAMILIES:
        assert wiring.functions(family) == tuple(_resolved(declared)), family
    assert dict(ROW_FAMILIES)["trig"] == HEADS


# -- the row language -------------------------------------------------------

def _specs(head, table):
    R = _common.Rules()
    rules(head, table, __name__)(R, None)
    return sorted(R.rules)


def test_conclusions_split_on_and_not_on_or():
    assert _specs(cos, Q.zero(x) >> (Q.odd(cos(x)) & Q.positive(cos(x)))) == [
        ([(0, 'zero', True)], [(1, 'odd', True)]),
        ([(0, 'zero', True)], [(1, 'positive', True)])]
    [(prem, concl)] = _specs(sin, Q.real(x) >> (Q.positive(sin(x)) | Q.nonpositive(sin(x))))
    assert prem == [(0, 'real', True)] and sorted(concl) == [(1, 'nonpositive', True),
                                                              (1, 'positive', True)]


def test_closed_sets_join_with_and_and_take_a_condition():
    assert _specs(tan, closed(tan, Q.real) & closed(tan, Q.complex)) == [
        ([(0, 'complex', True)], [(1, 'complex', True)]),
        ([(0, 'real', True)], [(1, 'real', True)])]
    rs = Q.finite(tan(x)) >> (closed(tan, Q.real) & closed(tan, Q.complex))
    assert _specs(tan, rs) == sorted([
        (sorted([(0, 'real', True), (1, 'finite', True)]), [(1, 'real', True)]),
        (sorted([(0, 'complex', True), (1, 'finite', True)]), [(1, 'complex', True)])])
    # a row joins a set too, on either side
    assert len(_specs(tan, (Q.zero(x) >> Q.zero(tan(x))) & closed(tan, Q.real))) == 2
    assert len(_specs(tan, closed(tan, Q.real) & (Q.zero(x) >> Q.zero(tan(x))))) == 2


def _each_way(specs):
    return sorted((sorted(p), c) for p, c in specs)


def test_equivalent_is_a_rule_each_way():
    zero = Equivalent(Q.zero(tan(x)), Q.zero(x))
    assert _each_way(_specs(tan, Q.extended_real(x) >> zero)) == [
        ([(0, 'extended_real', True), (0, 'zero', True)], [(1, 'zero', True)]),
        ([(0, 'extended_real', True), (1, 'zero', True)], [(0, 'zero', True)])]
    # a row without premises, and one joined with other rows under a condition
    assert _each_way(_specs(tan, zero)) == [
        ([(0, 'zero', True)], [(1, 'zero', True)]), ([(1, 'zero', True)], [(0, 'zero', True)])]
    assert len(_specs(tan, Q.real(x) >> (closed(tan, Q.complex) & zero))) == 3
    assert len(_specs(tan, Q.real(x) >> (zero & closed(tan, Q.complex)))) == 3


def test_an_inequality_with_an_integer_is_a_fact_about_x_minus_c():
    # Q.gt(x, 1) is extended_positive(x - 1), and so on; the slots of the
    # terms x - c are by |c|, x - c first, whatever order the rows use
    row = (Q.positive(x) & Q.lt(x, 1) & Q.gt(x, -1)) >> Q.real(atanh(x))
    assert _each_way(_specs(atanh, row)) == [
        ([(0, 'positive', True), (2, 'extended_negative', True), (3, 'extended_positive', True)],
         [(1, 'real', True)])]
    for rel, lit in ((Q.gt(x, 1), ('extended_positive', True)),
                     (Q.lt(x, 1), ('extended_negative', True)),
                     (Q.ge(x, 1), ('extended_nonnegative', True)),
                     (Q.le(x, 1), ('extended_nonpositive', True)),
                     (Q.eq(x, 1), ('zero', True)), (Q.ne(x, 1), ('zero', False)),
                     # the integer on the left, and a negation
                     (Q.lt(1, x), ('extended_positive', True)),
                     (~Q.ge(x, 1), ('extended_nonnegative', False))):
        assert _specs(atanh, rel >> Q.real(atanh(x))) == [([(2, *lit)], [(1, 'real', True)])]
    # comparing with 0 is a fact about x; an inequality in a conclusion
    assert _specs(atanh, Q.gt(x, 0) >> Q.real(atanh(x))) == [
        ([(0, 'extended_positive', True)], [(1, 'real', True)])]
    assert _specs(atanh, Equivalent(Q.zero(atanh(x)), Q.eq(x, -1))) == [
        ([(1, 'zero', True)], [(2, 'zero', True)]), ([(2, 'zero', True)], [(1, 'zero', True)])]
    rows = (Q.eq(x, 2) >> Q.zero(atanh(x)), Q.eq(x, -3) >> Q.zero(atanh(x)),
            Q.eq(x, 1) >> Q.zero(atanh(x)))
    gen = rules(atanh, rows, __name__)
    assert gen.shifts == (-1, -2, 3)
    assert sorted(_specs(atanh, rows)) == [([(k, 'zero', True)], [(1, 'zero', True)])
                                           for k in (2, 3, 4)]


def test_the_slots_of_inequalities_are_built_as_shifted_builds_them():
    # the template has the slots its rows use; the objects are shifted's:
    # Add(y, -y, 1) - 1 is not 0, it is nan at y = oo (#184)
    y_ = Symbol('y')
    for a in (Symbol('t'), Add(y_, -y_, 1, evaluate=False), Float(0.5)):
        e = atanh(a, evaluate=False)
        for row, objs in (
                (Q.zero(x) >> Q.zero(atanh(x)), (a, e)),
                (Q.eq(x, 1) >> Q.infinite(atanh(x)), (a, e, shifted(a, -1))),
                (Q.eq(x, -1) >> Q.infinite(atanh(x)), (a, e, shifted(a, 1))),
                ((Q.eq(x, -1) & Q.eq(x, 2)) >> Q.infinite(atanh(x)),
                 (a, e, shifted(a, 1), shifted(a, -2)))):
            _common._CACHE.clear()
            [c], _ = eq.compiled({atanh: wiring.template(atanh, rules(atanh, row, __name__))}, e)
            assert c.objs == objs
    _common._CACHE.clear()


def test_a_condition_without_parentheses_is_refused():
    # cond >> a & b parses as (cond >> a) & b, which would drop the
    # condition from b: complex(x) -> complex(tan(x)) is false at a pole
    with pytest.raises(TypeError, match=r"write cond >> \(a & b\)"):
        Q.finite(tan(x)) >> closed(tan, Q.real) & closed(tan, Q.complex)


def test_for_all_states_rows_for_each_function():
    st = (for_all((sec, csc),
              Q.complex(x) >> ~Q.zero(f(x)),
              closed(f, Q.real)),
          for_all((sec,),
              Q.zero(x) >> Q.positive(f(x))))
    assert by_function(st) == (
        (sec, (Q.complex(x) >> ~Q.zero(sec(x)), Q.real(x) >> Q.real(sec(x)),
               Q.zero(x) >> Q.positive(sec(x)))),
        (csc, (Q.complex(x) >> ~Q.zero(csc(x)), Q.real(x) >> Q.real(csc(x)))))


@pytest.mark.parametrize("make, match", [
    # a row of for_all is about f, not about one of the functions
    (lambda: for_all((sec,), Q.complex(x) >> ~Q.zero(sec(x))), "does not mention f"),
    (lambda: for_all((), Q.complex(x) >> ~Q.zero(f(x))), "no function"),
    (lambda: by_function((Q.complex(x) >> ~Q.zero(f(x)),)), "not a for_all statement"),
    # f of anything but x is no node
    (lambda: rules(sec, dict(by_function((for_all((sec,), Q.zero(x) >> Q.zero(f(x + 1))),)))[sec],
                   __name__), "neither the argument"),
])
def test_for_all_statements_that_are_refused(make, match):
    with pytest.raises((TypeError, ValueError), match=match):
        make()


def test_a_table_is_its_rows_in_order():
    assert rows_of((closed(sec, Q.real), (Q.zero(x) >> Q.zero(sec(x)),))) == [
        Q.real(x) >> Q.real(sec(x)), Q.zero(x) >> Q.zero(sec(x))]


y = Symbol('y')
yr = Symbol('y', real=True)


@pytest.mark.parametrize("head, row, match", [
    # >> binds tighter than &: And(real(x), Implies(finite(x), real(sin(x))))
    (sin, Q.real(x) & Q.finite(x) >> Q.real(sin(x)), "not an implication"),
    (sin, Q.real(sin(x)) >> Q.real(sin(x)), "not an implication"),    # SymPy: True
    (sin, Q.real(x) >> Q.finite(x), "does not mention the node"),
    (sin, Q.real(x) >> Q.positive_definite(sin(x)), "not a template predicate"),
    # SymPy builds cos(x + pi/2) as -sin(x)
    (cos, Q.zero(x) >> Q.zero(cos(x + pi/2)), "neither the argument"),
    (sin, Q.real(yr) >> Q.real(sin(yr)), "plain Symbol"),
    (sin, Q.real(y) >> Q.real(sin(x)), "more than one argument"),
    (sin, (Q.real(x) | Q.zero(x)) >> Q.real(sin(x)), "not a literal"),
    # a term of the argument is written as an inequality: Q.gt(x, 1)
    (acos, Q.zero(x - 1) >> Q.zero(acos(x)), "Q.gt\\(x, 1\\) and the like"),
    (acos, Q.zero(2*x) >> Q.positive(acos(x)), "neither the argument"),
    # an inequality compares the argument with an exact real number
    (acos, Q.gt(x, y) >> Q.positive(acos(x)), "with a number"),
    (acos, Q.gt(2*x, 1) >> Q.positive(acos(x)), "with a number"),
    (acos, Q.gt(x, Float(1)) >> Q.positive(acos(x)), "with a number"),
    (acos, Q.gt(x, I) >> Q.positive(acos(x)), "with a number"),
    (acos, Q.gt(x, oo) >> Q.positive(acos(x)), "with a number"),
    (acos, Q.gt(y, 1) >> Q.positive(acos(x)), "more than one argument"),
    (acos, Q.gt(yr, 1) >> Q.positive(acos(yr)), "plain Symbol"),
])
def test_rows_that_do_not_compile_as_written(head, row, match):
    with pytest.raises((TypeError, ValueError), match=match):
        rules(head, row, __name__)


def test_show_rows_lists_each_row_with_its_source():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = subprocess.run([sys.executable, os.path.join(root, "tools", "show_rows.py"), "sec"],
                         capture_output=True, text=True, timeout=120,
                         env={**os.environ, "PYTHONPATH": root})
    assert out.returncode == 0, out.stderr
    lines = out.stdout.splitlines()
    assert lines[0] == "sec"
    # labelled with the title above each for_all
    assert any(l.strip().startswith("Nonvanishing ") and l.endswith("~Q.zero(sec(x))")
               for l in lines[1:])
    assert any(l.strip().startswith("sec on the imaginary axis ") and l.endswith(
        "Q.imaginary(x) >> (Q.noninteger(sec(x)) & Q.positive(sec(x)))") for l in lines[1:])
