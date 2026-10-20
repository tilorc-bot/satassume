"""Templates for classes that had none (#180 C-NOTMPL, part A: elementary
and combinatorial functions).

A node of a class without a template got no facts, whatever SymPy's own
``_eval_is_*`` knew.  These classes now have templates: the reciprocal
and inverse trigonometric and hyperbolic functions, ``exp_polar``,
``polar_lift``, ``principal_branch``, ``Mod``, ``Max``, ``Min``,
``Piecewise``, ``factorial2``, ``subfactorial``, ``rf``, ``ff``,
``binomial``, ``catalan``, ``andre``, ``genocchi``, ``partition``,
``expm1`` and ``log1p``.  Each rule is a theorem about the value under
SymPy's conventions; several of SymPy's own handlers are not (``acsch(0) =
zoo`` is not extended real, ``rf(pi, 0) = 1`` is an integer), and those
answers stay None here.
"""
from itertools import product

import mpmath
import pytest
from sympy import (AccumBounds, E, I, Max, Min, Mod, Piecewise, Rational, S, Symbol, acosh, acoth,
                   acsc, acsch, asec, asech, asinh, atanh, binomial, catalan, coth, csc, csch,
                   exp_polar, factorial2, ff, genocchi, oo, partition, pi, rf, sec, sech, sqrt,
                   subfactorial, symbols, zoo)
from sympy.codegen.cfunctions import expm1, log1p
from sympy.functions.combinatorial.numbers import andre
from sympy.functions.elementary.complexes import polar_lift, principal_branch

from satassume import DictCache, Engine
from satassume.knowledge.templates import registry
from satassume.sat.formula import And, Implies, Not, Or, P

x, y = symbols('x y')
p, p_ = symbols('p p_', positive=True)
n, n_ = symbols('n n_', negative=True)
r = Symbol('r', real=True)
er = Symbol('er', extended_real=True)
nn = Symbol('nn', nonnegative=True)
i = Symbol('i', imaginary=True)
k = Symbol('k', integer=True)
kp = Symbol('kp', integer=True, positive=True)
m = Symbol('m', integer=True, nonnegative=True)
kn = Symbol('kn', integer=True, negative=True)
q1 = Symbol('q1', integer=True)
q2 = Symbol('q2', integer=True, nonzero=True)
ev = Symbol('ev', even=True)
nonint = Symbol('nonint', rational=True, integer=False)
tte = Symbol('tte', even=True, nonnegative=True)
tpe = Symbol('tpe', even=True, positive=True)
tto = Symbol('tto', odd=True, nonnegative=True)
tfo = Symbol('tfo', odd=True, nonnegative=False)
z0 = Symbol('z0', zero=True)
inf = Symbol('inf', infinite=True)


def fresh():
    return Engine(cache=DictCache())


@pytest.mark.parametrize("expr, pred, expected", [
    # test_hyperbolic: test_csch, test_sech, test_sign_assumptions, test_atanh, test_acoth
    (csch(p), 'real', True), (sech(p), 'real', True),
    (csch(n), 'negative', True), (csch(p), 'positive', True),
    (sech(n), 'positive', True), (sech(p), 'positive', True),
    (coth(n), 'negative', True), (coth(p), 'positive', True),
    (atanh(S(2)), 'real', False), (atanh(Rational(1, 5)), 'real', True),
    (acoth(S(2)), 'real', True), (acoth(S(2)), 'finite', True), (acoth(S(2)), 'extended_real', True),
    # the #180 table
    (acsch(p), 'positive', True), (acosh(p + 1), 'positive', True), (sec(r), 'imaginary', False),
    (asinh(r), 'real', True), (asec(p + 1), 'real', True),
    (exp_polar(0), 'zero', False), (exp_polar(0), 'rational', True),
    # test_arit: test_polar, test_Mod_is_integer, test_Mod_is_nonposneg
    (polar_lift(-2)*Symbol('pp', polar=True), 'polar', True),
    (Mod(q1, q2), 'integer', True), (Mod(k, 3), 'nonnegative', True),
    (Mod(k, -3), 'nonpositive', True), (Mod(k, kp), 'nonnegative', True),
    (Mod(k, -kp), 'nonpositive', True),
    # test_miscellaneous: test_Max, test_minmax_assumptions
    (Max(p, p_, n, r), 'positive', True), (Max(p, p_, n, r), 'nonnegative', True),
    (Max(p, p_, n, r), 'negative', False), (Max(n, n_), 'positive', False),
    (Max(n, n_), 'negative', True), (Max(n, nn, r), 'nonnegative', True),
    (Max(n, nn, r), 'negative', False), (Min(p, p_), 'positive', True), (Min(n, r), 'negative', True),
    (Max(ev, nonint), 'odd', False), (Min(ev, nonint), 'odd', False), (Max(r, k), 'real', True),
    # test_piecewise: test_issue_10258, test_piecewise_complex
    (Piecewise((-1, x < 1), (1, True)), 'zero', False),
    (Piecewise((0, x < 1), (z0, True)), 'zero', True),
    (Piecewise((1, x < 1), (2, True)), 'nonzero', True),
    (Piecewise((0, x < 1), (1, True)), 'finite', True),
    (Piecewise((2, x < 0), (1, True)), 'imaginary', False),
    (Piecewise((2, x < 0), (1, True)), 'real', True),
    (Piecewise((2*I, x < 0), (I, True)), 'imaginary', True),
    (Piecewise((2*I, x < 0), (I, True)), 'real', False),
    # test_comb_factorials, test_comb_numbers
    (factorial2(m - 1), 'integer', True), (factorial2(tte - 1), 'integer', True),
    (factorial2(tte + 2), 'even', True), (factorial2(tpe), 'odd', False),
    (factorial2(tto), 'odd', True), (factorial2(tfo), 'even', False),
    (factorial2(z0), 'odd', True), (factorial2(tto - 1), 'positive', True),
    (subfactorial(m), 'integer', True), (subfactorial(m), 'nonnegative', True),
    (subfactorial(tte), 'odd', True), (subfactorial(tto), 'even', True),
    (rf(k, m), 'integer', True), (ff(k, m), 'integer', True),
    (catalan(nn), 'positive', True), (catalan(m), 'integer', True),
    (catalan(kp + 3), 'composite', True),
    (genocchi(2*kp), 'odd', True), (genocchi(2*kp), 'even', False),
    (genocchi(2*kp + 1), 'even', True), (genocchi(kp), 'integer', True),
    (genocchi(4*kp), 'positive', True), (genocchi(4*kp + 2), 'negative', True),
    (genocchi(4*kp + 1), 'negative', False),
    (genocchi(6, evaluate=False), 'prime', False), (genocchi(8, evaluate=False), 'prime', True),
    (andre(m), 'integer', True), (andre(m), 'positive', True),
    (partition(k), 'integer', True), (partition(k), 'negative', False),
    (partition(k), 'nonnegative', True), (partition(kn), 'zero', True),
    (partition(m), 'positive', True),
    (binomial(k, q1), 'integer', True), (binomial(x, kn), 'zero', True),
    # test_cfunctions: test_expm1
    (expm1(r), 'real', True), (expm1(r), 'finite', True), (expm1(p), 'positive', True),
    (log1p(p), 'positive', True), (log1p(r), 'real', None),
])
def test_reproducers(expr, pred, expected):
    assert fresh().is_(expr, pred) is expected


@pytest.mark.parametrize("expr, pred", [
    # acsch(0) == zoo: SymPy's handler says extended real (test_acsch)
    (acsch(er), 'extended_real'),
    # rf(pi, 0) == ff(pi, 0) == 1; rf(-1, 1/2 + pi) == 0 (test_rf_eval_apply)
    (rf(pi, m), 'integer'), (rf(k, k + pi), 'integer'), (ff(pi, m), 'integer'),
    (ff(k, k + pi), 'integer'),
    # a pole (sec(pi/2) == zoo) or a branch cut on the way
    (sec(r), 'real'), (csc(r), 'finite'), (coth(r), 'real'),
    (atanh(er), 'real'), (acoth(r), 'real'), (acosh(r), 'real'), (asech(p), 'real'),
    (asec(r), 'real'), (acsc(r), 'real'), (log1p(r), 'real'),
    # coth(I*pi/2) == 0, asinh(2*I) is not imaginary, expm1(I*pi) == -2
    (coth(i), 'imaginary'), (asinh(i), 'imaginary'), (expm1(i), 'real'),
    # acoth(1 + oo*I) is left alone by SymPy (evalf: nan)
    (acoth(inf), 'zero'),
    # Mod(p, 0) raises
    (Mod(x, y), 'integer'), (Mod(q1, q1 + 1), 'nonnegative'), (Mod(x, q2), 'integer'),
    (Mod(kp, k), 'nonnegative'),
    # exp_polar(2*I*pi) is not 1; polar_lift(oo*I) is not polar
    (exp_polar(x), 'real'), (polar_lift(x), 'polar'), (principal_branch(x, y), 'polar'),
    # Max(x, y) is one of x, y
    (Max(x, y), 'positive'), (Max(n, n_, r), 'positive'), (Max(n, n_, r), 'negative'),
    (Max(n, nn, r), 'positive'), (Max(r, Rational(1, 2)), 'integer'),
    # no catch-all: nan where no condition holds (Piecewise((1, x < 1)).subs(x, 2))
    (Piecewise((1, x < 1), (z0, x < 3)), 'zero'), (Piecewise((1, x < 1), (2, x < 3)), 'positive'),
    (Piecewise((0, x < 1), (1, True)), 'zero'), (Piecewise((0, x < 1), (oo, True)), 'finite'),
    # factorial2(-4) raises, (-3)!! == -1, (-5)!! == 1/3
    (factorial2(k), 'integer'), (factorial2(k), 'positive'), (factorial2(tfo), 'odd'),
    (factorial2(tte), 'even'), (factorial2(m), 'odd'),
    (subfactorial(k), 'integer'), (subfactorial(m), 'odd'),
    # catalan(-1) == -1/2; catalan(2) == 2 and catalan(3) == 5 are prime
    (catalan(k), 'positive'), (catalan(m), 'composite'),
    # genocchi(1) == -1, genocchi(3) == 0; the polynomials get no rule
    (genocchi(m), 'zero'), (genocchi(tto), 'zero'), (genocchi(kp, x), 'integer'),
    # binomial(5, 1/2) is not an integer, binomial(-1, 1) == -1
    (binomial(k, x), 'integer'), (binomial(k, kp), 'nonnegative'),
])
def test_undecided(expr, pred):
    assert fresh().is_(expr, pred) is None


# ---------------------------------------------------------------------------
# soundness at concrete points, with a numerical oracle
# ---------------------------------------------------------------------------

_EPS0 = mpmath.mpf(10) ** -40
_EPS1 = mpmath.mpf(10) ** -25


def _value(v, pred):
    """Three-valued truth of ``pred`` for the concrete value ``v``: SymPy's
    facts of an atom, else from ``evalf`` at 50 digits (None where the
    digits cannot tell: exact zeros, integrality, algebraicity)."""
    if pred in ('polar', 'commutative'):
        return None
    if v is S.NaN:
        return None if pred in ('finite', 'infinite') else False
    if not getattr(v, 'is_number', False) or v.has(AccumBounds, S.NaN):
        return None
    if v.is_Atom or v.has(oo, -oo, zoo):
        return getattr(v, 'is_' + pred, None)
    try:
        re_, im_ = (t.evalf(50) for t in v.evalf(50).as_real_imag())
        if not (re_.is_Number and im_.is_Number) or not (re_.is_finite and im_.is_finite):
            return None
        a, b = mpmath.mpf(str(re_)), mpmath.mpf(str(im_))
    except (TypeError, ValueError):
        return None
    real = True if im_ == 0 else (False if abs(b) > _EPS1 else None)
    sign = 1 if a > _EPS1 else (-1 if a < -_EPS1 else 0)
    if pred in ('finite', 'complex'):
        return True
    if pred in ('infinite',):
        return False
    if pred in ('real', 'extended_real'):
        return real
    if pred == 'zero':
        return False if (sign or abs(b) > _EPS1) else None
    if pred == 'imaginary':
        return False if (sign or im_ == 0) else (True if re_ == 0 and abs(b) > _EPS1 else None)
    base = pred.replace('extended_', '')
    if base in ('positive', 'negative', 'nonnegative', 'nonpositive', 'nonzero'):
        if real is not True or not sign:
            return False if real is False else None
        return {'positive': sign > 0, 'negative': sign < 0, 'nonnegative': sign > 0,
                'nonpositive': sign < 0, 'nonzero': True}[base]
    if pred in ('integer', 'even', 'odd', 'prime', 'composite', 'rational', 'noninteger'):
        if real is False:
            return pred != 'noninteger' and False
        if real is True and abs(a - mpmath.nint(a)) > _EPS1:
            return pred == 'noninteger'
    return None


def _kleene(f, val):
    if isinstance(f, P):
        return val(f)
    if isinstance(f, Not):
        v = _kleene(f.args[0], val)
        return None if v is None else not v
    vs = [_kleene(a, val) for a in f.args]
    if isinstance(f, Implies):
        vs = [None if vs[0] is None else not vs[0], vs[1]]
    if isinstance(f, (Or, Implies)):
        return True if True in vs else (False if all(v is False for v in vs) else None)
    assert isinstance(f, And), f
    return False if False in vs else (True if all(v is True for v in vs) else None)


POOL = [S(0), S(1), S(-1), S(2), S(-2), S.Half, -S.Half, Rational(3, 2), Rational(-7, 3), S(3),
        S(4), S(-3), S(6), pi, -pi, sqrt(2), E, I, -I, 2*I, I/2, 1 + I, -1 - I, 2 + 3*I,
        oo, -oo, zoo, oo*I, -oo*I]
POOL2 = [S(0), S(1), S(-1), S(2), S(-3), S.Half, pi, I, 1 + I, oo, -oo, zoo]

UNARY = [sec, csc, coth, sech, csch, asinh, acosh, atanh, acoth, asech, acsch, asec, acsc,
         exp_polar, polar_lift, factorial2, subfactorial, catalan, andre, genocchi, partition,
         expm1, log1p]
SAMPLES = ([f(a) for f in UNARY for a in (x, x + 1, x - 1, 2*x)]
           + [Mod(x, y), Mod(x, 3), Max(x, y), Min(x, y), Max(x, y, 2), Min(x, -1),
              Piecewise((x, y > 1), (y, True)), Piecewise((2, x > 1), (x, True)),
              rf(x, y), ff(x, y), binomial(x, y), principal_branch(x, y)])


def _check(expr):
    facts = registry.facts_for(expr)
    assert facts, expr
    syms = sorted(expr.free_symbols, key=str)
    wrong = []
    for values in product(POOL if len(syms) == 1 else POOL2, repeat=len(syms)):
        asg = dict(zip(syms, values))
        cache = {}

        def val(atom):
            if atom not in cache:
                try:
                    v = atom.expr.xreplace(asg).doit()
                except (ValueError, TypeError, ArithmeticError):
                    v = None
                cache[atom] = None if v is None else _value(v, atom.pred)
            return cache[atom]
        wrong += [(asg, f) for f in facts if _kleene(f, val) is False]
    return wrong


@pytest.mark.parametrize("expr", SAMPLES, ids=str)
def test_sound_at_points(expr):
    wrong = _check(expr)
    assert not wrong, wrong[:5]


def test_oracle_catches_sympys_acsch_rule():
    # the canary: SymPy's ``extended_real(x) -> extended_real(acsch(x))``
    f = Implies(P('extended_real', x), P('extended_real', acsch(x)))
    assert _kleene(f, lambda a: _value(a.expr.xreplace({x: S(0)}).doit(), a.pred)) is False
