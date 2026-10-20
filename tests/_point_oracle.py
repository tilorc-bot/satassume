"""A numerical oracle for template soundness at concrete points (#180
C-NOTMPL): the three-valued truth of a predicate for a concrete value
(SymPy's facts of an atom, else ``evalf`` at 50 digits) and Kleene
evaluation of the emitted formulas.  Shared by ``test_notmpl_elementary``
and ``test_notmpl_special``."""
from itertools import product

import mpmath
from sympy import AccumBounds, E, I, Rational, S, oo, pi, sqrt, zoo

from satassume.knowledge.templates import registry
from satassume.sat.formula import And, Implies, Not, Or, P

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


def check(expr, pool=None, pool2=None):
    facts = registry.facts_for(expr)
    assert facts, expr
    syms = sorted(expr.free_symbols, key=str)
    wrong = []
    for values in product((pool or POOL) if len(syms) == 1 else (pool2 or POOL2),
                          repeat=len(syms)):
        asg = dict(zip(syms, values))
        cache = {}

        def val(atom):
            if atom not in cache:
                # SymPy and mpmath raise more than these at some special
                # points (KeyError, UnboundLocalError): no value, uncheckable
                try:
                    v = atom.expr.xreplace(asg).doit()
                    cache[atom] = _value(v, atom.pred)
                except Exception:
                    cache[atom] = None
            return cache[atom]
        wrong += [(asg, f) for f in facts if _kleene(f, val) is False]
    return wrong
