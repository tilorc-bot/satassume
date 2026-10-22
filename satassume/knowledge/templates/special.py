"""Structural templates for special functions (#180, C-NOTMPL, part B).

The gamma family (``gamma``, ``loggamma``, ``polygamma``, ``digamma``,
``trigamma``, ``multigamma``, ``lowergamma``, ``uppergamma``),
``erf2``, ``erfinv``, ``erfcinv``, ``expint``, ``li``, ``Li``,
``owens_t``, the beta functions
(``beta``, ``betainc``, ``betainc_regularized``), ``LambertW``, ``zeta``,
``dirichlet_eta``, ``polylog``, the Airy functions and the Bessel
functions ``besselj``, ``bessely``, ``besseli``, ``besselk``.  The unary
error functions and integrals are rows (:mod:`.error_functions`).

Each rule is a theorem about the value under SymPy's conventions
(``gamma(-n) = zoo``, ``loggamma(-n) = oo``, ``erfcinv(0) = oo``,
``li(1) = -oo``, ``zeta(1) = zoo``, ``LambertW(0, k) = -oo`` for ``k !=
0``, principal branches).
SymPy's own handlers are not followed where they are not theorems:

* ``beta(x, y)`` and ``betainc`` of real arguments are not always real
  (``beta(5, -3) = oo``, ``betainc(1/2, 1, 0, -1)`` is not real);
* ``LambertW(-1/E) = -1`` is real; ``multigamma(-1/2, 1) = -2*sqrt(pi)``
  is real; ``polygamma(1, 0) = zoo`` is not positive and
  ``polygamma(n, 0)`` is not complex;
* ``gamma(oo)`` is not real (``noninteger`` includes ``oo``), ``zeta(s)``
  is not finite at ``s = -oo``;
* the Airy functions have non-real points where the value is real
  (their complex zeros), so a non-real argument gives no claim.

A node with another number of arguments than the rules are written for
gets no facts.  Unary templates: the argument is index 0, the node index 1,
slots from 2; n-ary ones (:func:`.functions.nary`): the arguments, the
node at index ``n``, slots from ``n + 1``.
"""
from __future__ import annotations

from collections import Counter

from sympy import S, exp
from sympy.core.add import Add
from sympy.core.mul import Mul
from sympy.functions.elementary.exponential import LambertW
from sympy.functions.special.bessel import (
    airyai,
    airyaiprime,
    airybi,
    airybiprime,
    besseli,
    besselj,
    besselk,
    bessely,
)
from sympy.functions.special.beta_functions import beta, betainc, betainc_regularized
from sympy.functions.special.error_functions import Li, erf2, erfcinv, erfinv, expint, li
from sympy.functions.special.gamma_functions import (
    digamma,
    gamma,
    loggamma,
    lowergamma,
    multigamma,
    polygamma,
    trigamma,
    uppergamma,
)
from sympy.functions.special.zeta_functions import dirichlet_eta, polylog, zeta

from ._common import Rules, const_key, facts
from .atoms import value_units
from .functions import _table, _unary, nary, shifted
from .registry import registry

try:  # new in SymPy 1.15
    from sympy.functions.special.error_functions import owens_t
except ImportError:  # pragma: no cover - depends on the SymPy version
    owens_t = None

X, N, M, Q = 0, 1, 2, 3

_ENTIRE = ((('finite',), 'finite'), (('complex',), 'complex'))


def _register(cls, tag, gen, slots=None):
    registry.register(cls)(_unary(tag, gen, slots=slots))


def _minus(*cs):
    """Slots ``x - c`` for the numbers ``cs``."""
    return lambda x: tuple(shifted(x, S(-c)) for c in cs)


# ---------------------------------------------------------------------------
# gamma: poles (zoo) at the nonpositive integers, gamma(oo) = oo, never 0;
# real and nonzero at real non-integers, positive for x > 0, of sign
# (-1)**n on (-n, -n + 1).  Slot 2: x - 1/2 (gamma(e + 1/2) for even e).
# ---------------------------------------------------------------------------

def _gamma(R, c):
    _table(R, (
        (('positive',), 'positive'),
        (('real', ('integer', False)), 'real'),
        (('real', ('integer', False)), ('zero', False)),
        (('integer', 'nonpositive'), 'infinite'),
        (('integer', 'nonpositive'), ('extended_real', False)),
        (('complex', ('extended_real', False)), 'complex'),
        (('complex', ('extended_real', False)), ('zero', False)),
        (('infinite', 'extended_positive'), 'infinite'),
        (('infinite', 'extended_positive'), 'extended_positive'),
        (('integer', 'positive'), 'integer'),
    ))
    # x == s + 1/2 < 0 with s even lies in (s, s + 1), s == -n with n even
    R.rule([(M, 'even', True), (X, 'negative', True), (X, 'integer', False)],
           (N, 'positive', True))
    R.rule([(M, 'odd', True), (X, 'negative', True), (X, 'integer', False)],
           (N, 'negative', True))


_register(gamma, 'gamma', _gamma, slots=lambda x: (shifted(x, -S.Half),))


# loggamma: log(gamma(x)) for x > 0, analytic continuation elsewhere (its
# imaginary part at a negative non-integer is a nonzero multiple of pi);
# SymPy: loggamma(-n) = oo, loggamma(-oo) = loggamma(oo*I) = zoo.

def _loggamma(R, c):
    _table(R, (
        (('positive',), 'real'),
        (('real', ('integer', False)), 'complex'),
        (('negative', ('integer', False)), ('extended_real', False)),
        (('integer', 'nonpositive'), 'infinite'),
        (('complex', ('extended_real', False)), 'complex'),
        # not "non-real x -> non-real value": gamma is real on a curve
        # through its minimum x0 ~ 1.4616, so loggamma is real at
        # 7/5 + 0.6388873...*I (#194 review)
        (('infinite',), 'infinite'),
        (('infinite', 'extended_positive'), 'extended_positive'),
    ))


_register(loggamma, 'loggamma', _loggamma)


# polygamma(n, z) for integers n >= 0: poles (zoo) at the nonpositive
# integers, real at the other reals, (-1)**(n + 1)*n!*sum(1/(z + k)**(n + 1))
# for n >= 1 (positive for odd n at every real non-pole, negative for even
# n at z > 0); polygamma(0, oo) = oo, polygamma(n, oo) = 0.  n = -1 is
# loggamma and other n get no claim.

def _polygamma_rules(R, n, z, node, order=None):
    """``order`` is the constant order (digamma 0, trigamma 1) or None."""
    def k(*lits):
        return [(n, p, v) for p, v in lits] if order is None else []

    nonneg = k(('integer', True), ('nonnegative', True))
    R.rule([*nonneg, (z, 'positive', True)], (node, 'real', True))
    R.rule([*nonneg, (z, 'real', True), (z, 'integer', False)], (node, 'real', True))
    R.rule([*nonneg, (z, 'complex', True), (z, 'extended_real', False)], (node, 'complex', True))
    R.rule([*nonneg, (z, 'integer', True), (z, 'nonpositive', True)], (node, 'infinite', True))
    R.rule([*nonneg, (z, 'integer', True), (z, 'nonpositive', True)],
           (node, 'extended_real', False))
    if order is None or order > 0:
        odd = k(('odd', True), ('positive', True))
        even = k(('even', True), ('positive', True))
        pos = k(('integer', True), ('positive', True))
        if order is None or order % 2:
            R.rule([*odd, (z, 'positive', True)], (node, 'positive', True))
            R.rule([*odd, (z, 'real', True), (z, 'integer', False)], (node, 'positive', True))
        if order is None or not order % 2:
            R.rule([*even, (z, 'positive', True)], (node, 'negative', True))
        R.rule([*pos, (z, 'infinite', True), (z, 'extended_positive', True)],
               (node, 'zero', True))
    if order is None or order == 0:
        zero = k(('zero', True))
        R.rule([*zero, (z, 'infinite', True), (z, 'extended_positive', True)],
               (node, 'infinite', True))
        R.rule([*zero, (z, 'infinite', True), (z, 'extended_positive', True)],
               (node, 'extended_positive', True))


def _polygamma(R, n):
    if n == 2:
        _polygamma_rules(R, 0, 1, 2)


registry.register(polygamma)(nary('polygamma', _polygamma))
_register(digamma, 'digamma', lambda R, c: _polygamma_rules(R, None, X, N, 0))
_register(trigamma, 'trigamma', lambda R, c: _polygamma_rules(R, None, X, N, 1))


# multigamma(x, p) = pi**(p*(p - 1)/4)*Product(gamma(x + (1 - j)/2), (j, 1, p))
# for a positive integer p (other p raise).  With 2*x a non-integer every
# factor is finite, real and nonzero; with 2*x > p - 1 every factor is
# positive; with 2*x an integer <= p - 1 and p >= 2 one factor is a pole
# (j = 2*x + 1 for 2*x >= 0, j = 1 or 2 for 2*x < 0), and gamma never
# vanishes, so the value is zoo.  For p = 1 it is gamma(x)
# (multigamma(-1/2, 1) = -2*sqrt(pi) is real).  Only a constant p is
# handled.  Slots: 3 is 2*x, 4 is 2*x - p + 1.

#: largest constant ``p`` whose value is computed for a constant ``x``
MAX_MULTIGAMMA_P = 50


def _doubled(x):
    """``2*x`` as a slot object (an Add whose terms do not rebuild to
    themselves stays as it is, see :func:`.functions.shifted`)."""
    if x.is_Add:
        t = Add(*x.args)
        if not (t.is_Add and Counter(t.args) == Counter(x.args)):
            return Mul(S(2), x, evaluate=False)
    return 2*x


def _multigamma_rules(p):
    def build():
        R = Rules()
        x, node, y, d = 0, 2, 3, 4
        R.rule([(x, 'real', True), (y, 'integer', False)], (node, 'real', True))
        R.rule([(x, 'real', True), (y, 'integer', False)], (node, 'zero', False))
        R.rule([(x, 'real', True), (d, 'positive', True)], (node, 'positive', True))
        R.rule([(x, 'complex', True), (x, 'extended_real', False)], (node, 'complex', True))
        R.rule([(x, 'complex', True), (x, 'extended_real', False)], (node, 'zero', False))
        if p > 1:
            for concl in ((node, 'infinite', True), (node, 'extended_real', False)):
                R.rule([(y, 'integer', True), (d, 'nonpositive', True)], concl)
        else:
            for concl in ((node, 'infinite', True), (node, 'extended_real', False)):
                R.rule([(x, 'integer', True), (x, 'nonpositive', True)], concl)
            for concl in ((node, 'real', True), (node, 'zero', False)):
                R.rule([(x, 'real', True), (x, 'integer', False)], concl)
        return R.rules
    return build


@registry.register(multigamma)
def multigamma_templates(expr):
    if len(expr.args) != 2:
        return None
    x, p = expr.args
    if not (p.is_Integer and p > 0):
        return None
    y = _doubled(x)
    d = shifted(y, 1 - p)
    objs = (x, p, expr, y, d)
    consts = {k: o for k, o in enumerate(objs) if k != 2 and o.is_Atom and o.is_number}
    key = ('multigamma', int(p)) + tuple(const_key(o) if k in consts else None
                                         for k, o in enumerate(objs) if k not in (1, 2))
    out = facts(key, _multigamma_rules(int(p)), consts, objs, 2)
    if x.is_Atom and x.is_number and p <= MAX_MULTIGAMMA_P:
        # multigamma(-1.0, 3): the value of a constant node (gamma(-1.0) is
        # zoo, Float(-2.0).is_integer is None)
        try:
            v = expr.func(x, p)
        except (ValueError, TypeError, ArithmeticError):
            v = None
        if v is not None and v.is_Atom and v.is_number and v is not S.NaN:
            return [out, value_units(v, expr)]
    return out


# lowergamma(a, x) = integral of t**(a - 1)*exp(-t) over (0, x), positive
# for a > 0, x > 0; uppergamma(a, x), over (x, oo), positive for real a
# and x > 0.

def _lowergamma(R, n):
    if n == 2:
        R.rule([(0, 'positive', True), (1, 'positive', True)], (2, 'positive', True))


def _uppergamma(R, n):
    if n == 2:
        R.rule([(0, 'real', True), (1, 'positive', True)], (2, 'positive', True))


registry.register(lowergamma)(nary('lowergamma', _lowergamma))
registry.register(uppergamma)(nary('uppergamma', _uppergamma))


# ---------------------------------------------------------------------------
# erf2, erfinv, erfcinv (erf, erfc and erfi are rows: .error_functions)
# ---------------------------------------------------------------------------

def _erf2(R, n):
    """erf2(x, y) = erf(y) - erf(x)."""
    if n == 2:
        for pred, concl in (('extended_real', 'real'), ('finite', 'finite'),
                            ('complex', 'complex')):
            R.rule([(0, pred, True), (1, pred, True)], (2, concl, True))
        R.rule([(0, 'zero', True), (1, 'zero', True)], (2, 'zero', True))


# erfinv: the inverse of erf on (-1, 1), erfinv(+-1) = +-oo; erfcinv(z) =
# erfinv(1 - z): real on (0, 2), erfcinv(0) = oo, erfcinv(2) = -oo.
# Slots: erfinv 2: x - 1, 3: x + 1; erfcinv 2: z - 1, 3: z - 2.

def _erfinv(R, c):
    R.equiv([], (N, 'zero', True), (X, 'zero', True))
    R.rule([(X, 'positive', True), (M, 'negative', True)], (N, 'positive', True))
    R.rule([(X, 'negative', True), (Q, 'positive', True)], (N, 'negative', True))
    for concl in ((N, 'infinite', True), (N, 'extended_positive', True)):
        R.rule([(X, 'positive', True), (M, 'zero', True)], concl)
    for concl in ((N, 'infinite', True), (N, 'extended_negative', True)):
        R.rule([(X, 'negative', True), (Q, 'zero', True)], concl)


def _erfcinv(R, c):
    R.equiv([], (N, 'zero', True), (M, 'zero', True))
    R.rule([(X, 'positive', True), (M, 'negative', True)], (N, 'positive', True))
    # the sign premises on z and z - 1 are implied, but the slots are
    # separate children: without them a block whose children are given
    # contradictory facts is unsatisfiable (tools/totality.py)
    R.rule([(X, 'positive', True), (M, 'positive', True), (Q, 'negative', True)], (N, 'negative', True))
    for concl in ((N, 'infinite', True), (N, 'extended_positive', True)):
        R.rule([(X, 'zero', True), (M, 'negative', True)], concl)
    for concl in ((N, 'infinite', True), (N, 'extended_negative', True)):
        R.rule([(X, 'positive', True), (M, 'positive', True), (Q, 'zero', True)], concl)


registry.register(erf2)(nary('erf2', _erf2))
_register(erfinv, 'erfinv', _erfinv, slots=lambda x: (shifted(x, S.NegativeOne), shifted(x, S.One)))
_register(erfcinv, 'erfcinv', _erfcinv, slots=_minus(1, 2))


# ---------------------------------------------------------------------------
# expint, li, Li (Ei, Si, Ci, Shi, Chi and the Fresnel integrals are rows:
# .error_functions)
# ---------------------------------------------------------------------------
# expint(nu, z) = integral of exp(-z*t)/t**nu over (1, oo), positive for
# real nu and z > 0 (E1(z) is expint(1, z)).
# li(x) = integral of 1/log(t) over (0, x): li(0) = 0, li(1) = -oo,
# li(oo) = oo, negative on (0, 1), real for x > 0.  Li(x) = li(x) - li(2):
# Li(2) = 0, increasing on (1, oo).  Slots 2: x - 1, 3: x - 2.

def _expint(R, n):
    if n == 2:
        R.rule([(0, 'real', True), (1, 'positive', True)], (2, 'positive', True))


def _li(R, c):
    R.rule([(X, 'zero', True)], (N, 'zero', True))
    R.rule([(X, 'positive', True), (M, 'negative', True)], (N, 'negative', True))
    R.rule([(X, 'positive', True), (M, 'positive', True)], (N, 'real', True))
    for concl in ((N, 'infinite', True), (N, 'extended_negative', True)):
        R.rule([(X, 'positive', True), (M, 'zero', True)], concl)
    _table(R, ((('infinite', 'extended_positive'), 'infinite'),
              (('infinite', 'extended_positive'), 'extended_positive')))
    R.rule([(X, 'complex', True), (M, 'zero', False)], (N, 'complex', True))


def _Li(R, c):
    R.rule([(X, 'positive', True), (M, 'zero', False)], (N, 'real', True))
    R.rule([(X, 'positive', True), (M, 'negative', True)], (N, 'negative', True))
    R.rule([(M, 'positive', True), (Q, 'negative', True)], (N, 'negative', True))
    R.rule([(M, 'positive', True), (Q, 'zero', True)], (N, 'zero', True))
    R.rule([(M, 'positive', True), (Q, 'positive', True)], (N, 'positive', True))
    _table(R, ((('infinite', 'extended_positive'), 'infinite'),
              (('infinite', 'extended_positive'), 'extended_positive')))
    R.rule([(X, 'complex', True), (M, 'zero', False)], (N, 'complex', True))


registry.register(expint)(nary('expint', _expint))
_register(li, 'li', _li, slots=_minus(1))
_register(Li, 'Li', _Li, slots=_minus(1, 2))


# ---------------------------------------------------------------------------
# owens_t(h, a) = integral of exp(-h**2*(1 + t**2)/2)/(1 + t**2)/(2*pi)
# over (0, a): real with the sign of a for real h (also a = +-oo:
# +-erfc(|h|/sqrt(2))/4), 0 for h = +-oo (SymPy) or a = 0 (h not nan); for h = I*s and
# real a the integrand is positive as well.
# ---------------------------------------------------------------------------

def _owens_t(R, n):
    if n != 2:
        return
    h, a, node = 0, 1, 2
    R.rule([(h, 'extended_real', True), (a, 'extended_real', True)], (node, 'real', True))
    # owens_t(nan, 0) is nan (and owens_t(x + y, 0) at x = oo, y = -oo)
    for hp in ('complex', 'extended_real'):
        R.rule([(h, hp, True), (a, 'zero', True)], (node, 'zero', True))
    R.rule([(h, 'infinite', True), (h, 'extended_real', True), (a, 'extended_real', True)],
           (node, 'zero', True))
    for hp in ('real', 'imaginary'):
        sign = 'extended_' if hp == 'real' else ''
        R.rule([(h, hp, True), (a, sign + 'positive', True)], (node, 'positive', True))
        R.rule([(h, hp, True), (a, sign + 'negative', True)], (node, 'negative', True))
    R.rule([(h, 'imaginary', True), (a, 'real', True)], (node, 'real', True))


if owens_t is not None:
    registry.register(owens_t)(nary('owens_t', _owens_t))


# ---------------------------------------------------------------------------
# beta(x, y) = gamma(x)*gamma(y)/gamma(x + y): positive for x, y > 0 (one
# argument: beta(x, x)).  betainc(a, b, x1, x2) is the integral of
# t**(a - 1)*(1 - t)**(b - 1) over (x1, x2): for positive integers a, b a
# polynomial with rational coefficients, so real (rational) at real
# (rational) bounds; betainc_regularized divides it by beta(a, b), a
# positive rational.
# ---------------------------------------------------------------------------

def _beta(R, n):
    if n in (1, 2):
        R.rule([(k, 'positive', True) for k in range(n)], (n, 'positive', True))


def _betainc(R, n):
    if n != 4:
        return
    ab = [(0, 'integer', True), (0, 'positive', True), (1, 'integer', True), (1, 'positive', True)]
    for pred in ('real', 'rational'):
        R.rule([*ab, (2, pred, True), (3, pred, True)], (4, pred, True))


registry.register(beta)(nary('beta', _beta))
registry.register(betainc)(nary('betainc', _betainc))
registry.register(betainc_regularized)(nary('betainc_regularized', _betainc))


# ---------------------------------------------------------------------------
# LambertW(x, k): w*exp(w) == x on branch k (k = 0 when absent).  W_0 is
# finite at finite x, real and >= -1 on [-1/E, oo) with the sign of x
# (W_0(-1/E) = -1), not real below -1/E; W_-1 is real and <= -1 on
# [-1/E, 0), W_-1(0) = -oo, not real elsewhere on the real line; the other
# branches are not real at a real x != 0 and are -oo at 0.  A real w makes
# x real, so a non-real x gives a non-real value.  w == 0 forces x == 0;
# for algebraic x != 0, w is transcendental (a nonzero algebraic w would
# make exp(w) == x/w algebraic, against Lindemann-Weierstrass).  An infinite
# x gives an infinite value (LambertW(oo) = oo).  Slots: x + 1/E and, with
# a branch, k + 1.
# ---------------------------------------------------------------------------

def _lambertw_slots(args):
    if not args:
        return ()                      # Basic.__new__(LambertW): no facts
    out = (shifted(args[0], exp(-1)),)
    if len(args) == 2:
        out += (shifted(args[1], S.One),)
    return out


def _lambertw(R, n):
    if n not in (1, 2):
        return
    x, node, e = 0, n, n + 1
    kint = [(1, 'integer', True)] if n == 2 else []
    k0 = [(1, 'zero', True)] if n == 2 else []

    R.rule([(node, 'zero', True)], (x, 'zero', True))
    R.rule([*kint, (x, 'infinite', True)], (node, 'infinite', True))
    R.rule([*kint, (x, 'algebraic', True), (x, 'zero', False)], (node, 'transcendental', True))
    R.rule([*kint, (x, 'complex', True), (x, 'extended_real', False)], (node, 'complex', True))
    R.rule([*kint, (x, 'complex', True), (x, 'extended_real', False)],
           (node, 'extended_real', False))
    # the principal branch
    R.rule([*k0, (x, 'zero', True)], (node, 'zero', True))
    R.rule([*k0, (x, 'complex', True)], (node, 'complex', True))
    R.rule([*k0, (x, 'positive', True)], (node, 'positive', True))
    R.rule([*k0, (x, 'negative', True), (e, 'nonnegative', True)], (node, 'negative', True))
    R.rule([*k0, (x, 'negative', True), (e, 'negative', True)], (node, 'extended_real', False))
    R.rule([*k0, (x, 'infinite', True), (x, 'extended_positive', True)],
           (node, 'extended_positive', True))
    if n == 2:
        km1 = [(n + 2, 'zero', True)]
        R.rule([*km1, (x, 'negative', True), (e, 'nonnegative', True)], (node, 'negative', True))
        R.rule([*km1, (x, 'negative', True), (e, 'negative', True)],
               (node, 'extended_real', False))
        R.rule([*km1, (x, 'positive', True)], (node, 'extended_real', False))
        for concl in ((node, 'infinite', True), (node, 'extended_negative', True)):
            R.rule([*kint, (1, 'zero', False), (x, 'zero', True)], concl)
        R.rule([*kint, (1, 'zero', False), (n + 2, 'zero', False), (x, 'real', True),
                (x, 'zero', False)], (node, 'extended_real', False))


registry.register(LambertW)(nary('LambertW', _lambertw, slots=_lambertw_slots))


# ---------------------------------------------------------------------------
# zeta(s): zeta(1) = zoo, zeta(oo) = 1, finite at every complex s != 1,
# real at real s != 1, > 1 for s > 1, negative on [0, 1), 0 at the negative
# even integers, rational at the nonpositive integers, a nonzero rational
# times pi**s at the positive even ones.  zeta(s, a) (Hurwitz): zoo at
# s = 1, positive for s > 1, a > 0.  Slot: s - 1.
# dirichlet_eta(s) = (1 - 2**(1 - s))*zeta(s) (log(2) at 1) is entire:
# real at real s, positive for s > 0, 0 at the negative even integers.
# ---------------------------------------------------------------------------

def _zeta(R, n):
    if n not in (1, 2):
        return
    s, node, m = 0, n, n + 1
    # s == 1 (the sign and parity premises keep the rule apart from the
    # even s, which nothing at depth 1 relates to s - 1)
    pole = [(m, 'zero', True)] + ([(s, 'positive', True), (s, 'even', False)] if n == 1 else [])
    # zeta(1, nan) is nan (and zeta(1, x + y) at x = oo, y = -oo)
    poles = [pole] if n == 1 else [pole + [(1, ap, True)] for ap in ('complex', 'extended_real')]
    for premises in poles:
        for concl in ((node, 'infinite', True), (node, 'extended_real', False)):
            R.rule(premises, concl)
    if n == 2:
        R.rule([(s, 'positive', True), (m, 'positive', True), (1, 'positive', True)],
               (node, 'positive', True))
        return
    R.rule([(s, 'positive', True), (m, 'positive', True)], (node, 'positive', True))
    R.rule([(s, 'real', True), (m, 'negative', True)], (node, 'real', True))
    # negative on [0, 1) (zeta(0) = -1/2); the premises keep the rule apart
    # from the even s > 0, which nothing at depth 1 relates to s - 1
    R.rule([(s, 'zero', True)], (node, 'negative', True))
    R.rule([(s, 'positive', True), (s, 'integer', False), (m, 'negative', True)],
           (node, 'negative', True))
    R.rule([(s, 'complex', True), (m, 'zero', False)], (node, 'complex', True))
    R.rule([(s, 'infinite', True), (s, 'extended_positive', True)], (node, 'odd', True))
    R.rule([(s, 'infinite', True), (s, 'extended_positive', True)], (node, 'positive', True))
    R.rule([(s, 'even', True), (s, 'negative', True)], (node, 'zero', True))
    R.rule([(s, 'integer', True), (s, 'nonpositive', True)], (node, 'rational', True))
    R.rule([(s, 'even', True), (s, 'positive', True)], (node, 'positive', True))
    R.rule([(s, 'even', True), (s, 'positive', True)], (node, 'transcendental', True))


def _dirichlet_eta(R, n):
    if n != 1:
        return
    _table(R, ((('real',), 'real'), (('complex',), 'complex'), (('positive',), 'positive')))
    R.rule([(X, 'even', True), (X, 'negative', True)], (N, 'zero', True))


registry.register(zeta)(nary('zeta', _zeta,
                                     slots=lambda args: (shifted(args[0], S.NegativeOne),) if args else ()))
registry.register(dirichlet_eta)(nary('dirichlet_eta', _dirichlet_eta))


# polylog(s, z) = sum(z**k/k**s): for real s real on z < 1, positive on
# (0, 1); for s >= 0 negative at z < 0 (z/Gamma(s) times a positive
# integral, z/(1 - z) for s = 0); 0 at z = 0; finite at complex s and
# z != 1 (polylog(s, 1) = zeta(s)).  Slot 3: z - 1.

def _polylog(R, n):
    if n != 2:
        return
    s, z, node, m = 0, 1, 2, 3
    R.rule([(s, 'real', True), (z, 'real', True), (m, 'negative', True)], (node, 'real', True))
    R.rule([(s, 'real', True), (z, 'positive', True), (m, 'negative', True)],
           (node, 'positive', True))
    R.rule([(s, 'nonnegative', True), (z, 'negative', True)], (node, 'negative', True))
    R.rule([(z, 'zero', True)], (node, 'zero', True))
    R.rule([(s, 'complex', True), (z, 'complex', True), (m, 'zero', False)],
           (node, 'complex', True))


registry.register(polylog)(nary('polylog', _polylog,
                                slots=lambda args: (shifted(args[1], S.NegativeOne),)
                                if len(args) == 2 else ()))


# ---------------------------------------------------------------------------
# Airy functions: entire, real on the real line; Ai(x) > 0, Ai'(x) < 0,
# Bi(x) > 0 and Bi'(x) > 0 for x >= 0; Ai(+-oo) = 0, Bi(oo) = oo, Bi(-oo)
# = 0, Ai'(oo) = 0, Bi'(oo) = oo (SymPy leaves Ai'(-oo) alone).  Bi has
# non-real zeros, so a non-real argument gives no claim.
# ---------------------------------------------------------------------------

def _airy(kind):
    def gen(R, c):
        _table(R, _ENTIRE + ((('real',), 'real'),))
        sign = 'negative' if kind == 'aiprime' else 'positive'
        R.rule([(X, 'nonnegative', True)], (N, sign, True))
        if kind in ('bi', 'biprime'):
            _table(R, ((('infinite', 'extended_positive'), 'infinite'),
                      (('infinite', 'extended_positive'), 'extended_positive')))
        else:
            _table(R, ((('infinite', 'extended_positive'), 'zero'),))
        if kind in ('ai', 'bi'):
            _table(R, ((('infinite', 'extended_negative'), 'zero'),))
    return gen


for _cls, _kind in ((airyai, 'ai'), (airybi, 'bi'), (airyaiprime, 'aiprime'),
                    (airybiprime, 'biprime')):
    _register(_cls, 'airy' + _kind, _airy(_kind))


# ---------------------------------------------------------------------------
# Bessel functions of order nu at z: J_n and I_n are entire for integer n
# (real at real z), J_nu, Y_nu, I_nu, K_nu are real at real nu and z > 0,
# I_n(x) > 0 and K_nu(x) > 0 there; J(nu, +-oo) = Y(nu, +-oo) = K(nu, oo)
# = 0 and I(nu, oo) = oo (SymPy); Y and K are infinite at z = 0 for real nu.
# ---------------------------------------------------------------------------

def _bessel(kind):
    def gen(R, n):
        if n != 2:
            return
        nu, z, node = 0, 1, 2
        nreal, nint = (nu, 'real', True), (nu, 'integer', True)
        posinf = [(z, 'infinite', True), (z, 'extended_positive', True)]
        R.rule([nreal, (z, 'positive', True)], (node, 'real', True))
        if kind in ('j', 'i'):
            R.rule([nint, (z, 'real', True)], (node, 'real', True))
        if kind == 'j':
            R.rule([nreal, (z, 'infinite', True), (z, 'extended_real', True)], (node, 'zero', True))
        elif kind == 'i':
            R.rule([nint, (z, 'positive', True)], (node, 'positive', True))
            R.rule([nreal, *posinf], (node, 'infinite', True))
            R.rule([nreal, *posinf], (node, 'extended_positive', True))
        else:
            # SymPy's value: bessely(nu, 0) = besselk(nu, 0) = zoo for real nu (the limit of
            # Y_nu at 0 is 0 for a negative half-integer nu, but SymPy evaluates the node to zoo)
            R.rule([nreal, (z, 'zero', True)], (node, 'infinite', True))
            R.rule([nreal, *posinf], (node, 'zero', True))
            if kind == 'k':
                R.rule([nreal, (z, 'positive', True)], (node, 'positive', True))
    return gen


for _cls, _kind in ((besselj, 'j'), (bessely, 'y'), (besseli, 'i'), (besselk, 'k')):
    registry.register(_cls)(nary('bessel' + _kind, _bessel(_kind)))
