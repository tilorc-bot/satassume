"""The rows of ``sin``, ``cos``, ``tan``, ``cot``, ``sec`` and ``csc``
(``satassume/knowledge/templates/trig.py``, #249) emit exactly the clauses
of the generators they replace (``tests/_legacy_trig_rules.py``, verbatim
from f9291ab), and the row compiler (``templates/_rows.py``) rejects a row
it cannot compile as written.

For every node of the corpus (each head applied, unevaluated, to constants,
special values, multiples of ``pi`` and ``I*pi`` and symbols), the clauses
of the head's template are computed once with the rows and once with the
legacy generator, each from empty caches, and compared after
canonicalization (literals of a clause sorted, clauses sorted): rule order
is not kept, since ``And`` sorts its arguments.
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
    pi, sec, sin, sqrt, tan,
)

from satassume.knowledge.templates import _common, registry, trig  # noqa: E402
from satassume.knowledge.templates._rows import rules  # noqa: E402
from satassume.knowledge.templates.functions import _pi_trig, _unary  # noqa: E402
from satassume.knowledge.templates.registry import _split  # noqa: E402

HEADS = (sin, cos, tan, cot, sec, csc)
LEGACY = {
    sin: _pi_trig('sin', legacy._sin, False),
    cos: _pi_trig('cos', legacy._cos, True),
    tan: _unary('tan', legacy._tan),
    cot: _unary('cot', legacy._cot),
    sec: _unary('sec', legacy._sec),
    csc: _unary('csc', legacy._csc),
}


def _arguments():
    x, n = Symbol('x'), Symbol('n', integer=True)
    r, p, im = Symbol('r', real=True), Symbol('p', positive=True), Symbol('i', imaginary=True)
    consts = [S.Zero, S.One, S.NegativeOne, Rational(2), Rational(1, 2), Rational(-3, 2),
              pi, E, I, -I, S.Infinity, S.NegativeInfinity, S.ComplexInfinity, S.NaN,
              Float(0.5), Float(2.0), GoldenRatio, EulerGamma, sqrt(2), 2 + I]
    pis = [Mul(c, pi, evaluate=False) for c in (Rational(1, 2), Rational(3, 2), Rational(-1, 4),
                                                  Rational(7, 6), Rational(1, 3), 2, 3, -1)]
    pis += [pi*c*s for c in (1, 2, 3, Rational(1, 2), Rational(3, 2), Rational(1, 3))
            for s in (x, n, r)]
    pis += [pi*c*s for c in (1, 2, Rational(1, 2)) for s in (Rational(1, 3), 2, -1)
            if not (pi*c*s).is_Atom]
    pis += [I*pi, I*pi*n, I*pi*n/2, I*x, I*r]
    syms = [x, n, r, p, im, x + 1, x - pi, Add(x, -x, evaluate=False), 1/x, x**2]
    return consts + pis + syms


NODES = [h(a, evaluate=False) for h in HEADS for a in _arguments()]


def _canonical(result):
    compiled, formulas = [], []
    _split(result, compiled, formulas)
    blocks = sorted((tuple(map(str, c.objs)), c.pattern.node,
                     tuple(sorted(tuple(sorted(lits)) for lits, _, _ in c.pattern.clauses)))
                    for c in compiled)
    return tuple(blocks), tuple(sorted(map(str, formulas)))


def _run(templates):
    _common._CACHE.clear()
    try:
        out = {}
        for e in NODES:
            try:
                out[e] = _canonical(templates[type(e)](e))
            except Exception as exc:  # noqa: BLE001  (compared like a result)
                out[e] = ("raises", type(exc).__name__, str(exc))
        return out
    finally:
        _common._CACHE.clear()


def _rows_templates():
    out = {}
    for h in HEADS:
        ts = [t for t in registry.templates_for(h) if t.__module__ == trig.__name__]
        assert len(ts) == 1, (h, ts)
        out[h] = ts[0]
    return out


def test_rows_emit_the_legacy_clauses():
    new, old = _run(_rows_templates()), _run(LEGACY)
    diff = [e for e in NODES if new[e] != old[e]]
    assert not diff, [(e, new[e], old[e]) for e in diff[:3]]
    # the corpus reaches the pi*c*s rules and nodes with clauses
    assert any(len(b[0]) == 3 for blocks, _ in new.values() for b in blocks)
    assert sum(1 for blocks, _ in new.values() if blocks) > len(NODES) // 2


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
x = Symbol('x')
assert TRIG not in sys.modules
assert ask(Q.real(sin(x)), Q.real(x)) is True
assert TRIG in sys.modules and all(m != TRIG for _, m in registry._lazy)
assert "satassume.knowledge.templates.special" not in sys.modules
for h in (sin, cos, tan, cot, sec, csc):
    assert [t.__module__ for t in registry._by_class[h]] == [TRIG]
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr


x = Symbol('x')


def _specs(head, rows):
    R = _common.Rules()
    rules(head, rows, __name__)(R, None)
    return sorted(R.rules)


def test_conclusions_split_on_and_not_on_or():
    assert _specs(cos, [Q.zero(x) >> (Q.odd(cos(x)) & Q.positive(cos(x)))]) == [
        ([(0, 'zero', True)], [(1, 'odd', True)]),
        ([(0, 'zero', True)], [(1, 'positive', True)])]
    [(prem, concl)] = _specs(sin, [Q.real(x) >> (Q.positive(sin(x)) | Q.nonpositive(sin(x)))])
    assert prem == [(0, 'real', True)] and sorted(concl) == [(1, 'nonpositive', True),
                                                              (1, 'positive', True)]
    assert _specs(tan, [(Q.real(x) & Q.finite(tan(x))) >> ~Q.imaginary(tan(x))]) == [
        (sorted([(0, 'real', True), (1, 'finite', True)]), [(1, 'imaginary', False)])]


def test_rows_keep_the_callers_module():
    assert rules(sin, [Q.zero(x) >> Q.zero(sin(x))], "some.module").__module__ == "some.module"


y = Symbol('y')
yr = Symbol('y', real=True)


@pytest.mark.parametrize("head, row, match", [
    # >> binds tighter than &: And(real(x), Implies(finite(x), real(sin(x))))
    (sin, Q.real(x) & Q.finite(x) >> Q.real(sin(x)), "not an implication"),
    (sin, Q.real(x) >> Q.finite(x), "does not mention the node"),
    (sin, Q.real(sin(x)) >> Q.real(sin(x)), "not an implication"),    # SymPy: True
    (sin, Q.real(x) >> Q.positive_definite(sin(x)), "not a template predicate"),
    # SymPy builds cos(x + pi/2) as -sin(x)
    (cos, Q.zero(x) >> Q.zero(cos(x + pi/2)), "neither the argument"),
    (sin, Q.real(yr) >> Q.real(sin(yr)), "plain Symbol"),
    (sin, Q.real(y) >> Q.real(sin(x)), "more than one argument"),
    (sin, (Q.real(x) | Q.zero(x)) >> Q.real(sin(x)), "not a literal"),
])
def test_rows_that_do_not_compile_as_written(head, row, match):
    with pytest.raises((TypeError, ValueError), match=match):
        rules(head, [row], __name__)
