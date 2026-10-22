"""The rules of ``sin``, ``cos``, ``tan``, ``cot``, ``sec`` and ``csc``,
written as ``for_all`` statements (``templates/trig.py``, compiled by
``templates/wiring.py``) in the row language (``templates/_rows.py``, #249),
against the generators they replace (``tests/_legacy_trig_rules.py``,
verbatim from f9291ab).

For every node of the corpus (each head applied, unevaluated, to constants,
special values, multiples of ``pi`` and ``I*pi`` and symbols) the compiled
clauses of the head's template are computed with the rows and with the
legacy generator plus :data:`ADDED`, each from empty caches.  The two must
entail each other under the rule base: the same facts follow, though the
clauses differ (an implied row is not written: ``cot``'s ``algebraic ->
~algebraic`` follows from its ``zero`` and ``transcendental`` rows, and
``real -> ~imaginary`` of ``tan``, ``cot``, ``sec`` and ``csc`` from
``real & finite(f) -> real(f)``).  :data:`ADDED` are the facts the rows
give that the legacy rules did not, each with its argument; a test checks
that each is new.
"""
import os
import subprocess
import sys

import pytest

sympy = pytest.importorskip("sympy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _legacy_trig_rules as legacy  # noqa: E402
from sympy import (  # noqa: E402
    Add, E, EulerGamma, Float, GoldenRatio, I, Mul, Q, Rational, S, Symbol, cos, cot, csc,
    oo, pi, sec, sin, sqrt, tan, zoo,
)

from satassume.knowledge.rules import BASIS, RULE_CLAUSES  # noqa: E402
from satassume.knowledge.templates import ROW_FUNCTIONS, _common, registry, wiring  # noqa: E402
from satassume.knowledge.templates._rows import (  # noqa: E402
    by_function, closed, f, for_all, rows_of, rules, x,
)
from satassume.knowledge.templates.functions import _pi_trig, _unary  # noqa: E402
from satassume.knowledge.templates.registry import _split  # noqa: E402
from satassume.sat.solver import Solver  # noqa: E402

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


def _template(h, gen):
    if h in (sin, cos):
        return _pi_trig(h.__name__, gen, h is cos)
    return _unary(h.__name__, gen)


def _both(gen, extra):
    def both(R, c):
        gen(R, c)
        extra(R, c)
    return both


LEGACY = {h: _template(h, g) for h, g in LEGACY_GEN.items()}
LEGACY_PLUS = {h: _template(h, _both(g, rules(h, ADDED[h], __name__)) if h in ADDED else g)
               for h, g in LEGACY_GEN.items()}


def _arguments():
    x_, n = Symbol('x'), Symbol('n', integer=True)
    r, p, im = Symbol('r', real=True), Symbol('p', positive=True), Symbol('i', imaginary=True)
    consts = [S.Zero, S.One, S.NegativeOne, Rational(2), Rational(1, 2), Rational(-3, 2),
              pi, E, I, -I, S.Infinity, S.NegativeInfinity, S.ComplexInfinity, S.NaN,
              Float(0.5), Float(2.0), GoldenRatio, EulerGamma, sqrt(2), 2 + I]
    pis = [Mul(c, pi, evaluate=False) for c in (Rational(1, 2), Rational(3, 2), Rational(-1, 4),
                                                  Rational(7, 6), Rational(1, 3), 2, 3, -1)]
    pis += [pi*c*s for c in (1, 2, 3, Rational(1, 2), Rational(3, 2), Rational(1, 3))
            for s in (x_, n, r)]
    pis += [I*pi, I*pi*n, I*pi*n/2, I*x_, I*r]
    syms = [x_, n, r, p, im, x_ + 1, x_ - pi, Add(x_, -x_, evaluate=False), 1/x_, x_**2]
    return consts + pis + syms


NODES = [h(a, evaluate=False) for h in HEADS for a in _arguments()]


def _compiled(templates, e):
    compiled, formulas = [], []
    _split(templates[type(e)](e), compiled, formulas)
    return compiled, sorted(map(str, formulas))


def _run(templates):
    _common._CACHE.clear()
    try:
        return {e: _compiled(templates, e) for e in NODES}
    finally:
        _common._CACHE.clear()


def _var(k, i):
    return k * len(BASIS) + i + 1


def _solver(c):
    """A solver holding the pattern's clauses and the rule base on each slot."""
    s = Solver()
    for k in range(c.pattern.nobjs):
        for cl in RULE_CLAUSES:
            s.add_clause([(1 if l > 0 else -1) * _var(k, abs(l) - 1) for l in cl])
    for lits, _, _ in c.pattern.clauses:
        s.add_clause([-_var(k, i) if neg else _var(k, i) for k, i, neg in lits])
    return s


def _not_entailed(a, b):
    """The clauses of ``b`` that ``a`` (with the rule base) does not entail."""
    s = _solver(a)
    return [lits for lits, _, _ in b.pattern.clauses
            if s.solve([_var(k, i) if neg else -_var(k, i) for k, i, neg in lits])]


def _differences(new, old):
    """Per node: clauses of ``new`` that ``old`` lacks, and the reverse."""
    out = {}
    for e in NODES:
        (cn, fn), (co, fo) = new[e], old[e]
        assert fn == fo, e
        assert [(tuple(map(str, c.objs)), c.pattern.node) for c in cn] == \
               [(tuple(map(str, c.objs)), c.pattern.node) for c in co], e
        gained = [l for a, b in zip(co, cn) for l in _not_entailed(a, b)]
        lost = [l for a, b in zip(cn, co) for l in _not_entailed(a, b)]
        if gained or lost:
            out[e] = (gained, lost)
    return out


def _rows_templates():
    out = {}
    for h in HEADS:
        ts = [t for t in registry.templates_for(h) if t.__module__ == wiring.__name__]
        assert len(ts) == 1, (h, ts)
        out[h] = ts[0]
    return out


def test_rows_entail_exactly_the_legacy_rules_and_the_added_facts():
    new, old = _run(_rows_templates()), _run(LEGACY_PLUS)
    diff = _differences(new, old)
    assert not diff, list(diff.items())[:3]
    # the corpus reaches the pi*c*s rules and nodes with clauses
    assert any(len(c.objs) == 3 for cs, _ in new.values() for c in cs)
    assert sum(1 for cs, _ in new.values() if cs) > len(NODES) // 2


def test_each_added_fact_is_new():
    # every conjunct of every added row, alone on top of the legacy rules,
    # gives a clause the legacy rules do not entail
    for h, extra in ADDED.items():
        e = h(Symbol('x'), evaluate=False)
        _common._CACHE.clear()
        [old], _ = _compiled(LEGACY, e)
        for row in extra:
            prem, concl = row.args
            for c in (concl.args if isinstance(concl, sympy.And) else (concl,)):
                _common._CACHE.clear()
                plus = _template(h, _both(LEGACY_GEN[h], rules(h, prem >> c, __name__)))
                [new], _ = _compiled({h: plus}, e)
                assert _not_entailed(old, new), (h, prem, c)
    _common._CACHE.clear()


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
WIRING = "satassume.knowledge.templates.wiring"
x = Symbol('x')
assert TRIG not in sys.modules and WIRING not in sys.modules
assert ask(Q.real(sin(x)), Q.real(x)) is True
assert TRIG in sys.modules and all(m != WIRING for _, m in registry._lazy)
assert "satassume.knowledge.templates.special" not in sys.modules
for h in (sin, cos, tan, cot, sec, csc):
    assert [t.__module__ for t in registry._by_class[h]] == [WIRING]
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr


def test_the_declared_functions_are_those_the_rows_name():
    # templates/__init__.py declares .wiring for ROW_FUNCTIONS without
    # importing the rows; the two lists must not drift apart
    named = [fn for family in wiring.FAMILIES for fn in wiring.functions(family)]
    assert tuple(named) == ROW_FUNCTIONS == HEADS


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
