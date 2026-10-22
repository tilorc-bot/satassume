"""Structural templates for special functions (#180, C-NOTMPL, part B).

``multigamma`` and the beta functions (``beta``, ``betainc``,
``betainc_regularized``).  The other gamma functions are rows
(:mod:`.gamma_functions`), and so are the error functions, their
inverses, the integrals and ``owens_t`` (:mod:`.error_functions`),
``zeta``, ``dirichlet_eta`` and ``polylog`` (:mod:`.zeta_functions`),
``LambertW`` (:mod:`.lambertw`) and the Airy and Bessel functions
(:mod:`.bessel`).

Each rule is a theorem about the value under SymPy's conventions
(``gamma(-n) = zoo``, principal branches).
SymPy's own handlers are not followed where they are not theorems:

* ``beta(x, y)`` and ``betainc`` of real arguments are not always real
  (``beta(5, -3) = oo``, ``betainc(1/2, 1, 0, -1)`` is not real);
* ``multigamma(-1/2, 1) = -2*sqrt(pi)`` is real.

A node with another number of arguments than the rules are written for
gets no facts.  Unary templates: the argument is index 0, the node index 1,
slots from 2; n-ary ones (:func:`.functions.nary`): the arguments, the
node at index ``n``, slots from ``n + 1``.
"""
from __future__ import annotations

from collections import Counter

from sympy import S
from sympy.core.add import Add
from sympy.core.mul import Mul
from sympy.functions.special.beta_functions import beta, betainc, betainc_regularized
from sympy.functions.special.gamma_functions import multigamma

from ._common import Rules, const_key, facts
from .atoms import value_units
from .functions import _table, _unary, nary, shifted
from .registry import registry

X, N, M, Q = 0, 1, 2, 3


def _register(cls, tag, gen, slots=None):
    registry.register(cls)(_unary(tag, gen, slots=slots))


# ---------------------------------------------------------------------------
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
