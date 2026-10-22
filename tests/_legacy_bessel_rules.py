"""Verbatim copies of the Airy and Bessel generators from
``satassume/knowledge/templates/special.py`` at d149951, before they
became rows in ``templates/bessel.py`` (#249).  Test-only:
``tests/test_bessel_rows.py`` compares the clauses the rows emit with the
clauses these functions emit.  The ``registry.register`` lines are left
out (a test module's template would count as a user's); the Airy templates were ``_unary``'s, the Bessel ones ``nary``'s.  Do not edit
them to follow a later rule change; change the test's reference instead
(``git show d149951:satassume/knowledge/templates/special.py``)."""
from _legacy_helpers import _ENTIRE, _table

from satassume.knowledge.templates.functions import N, X


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

