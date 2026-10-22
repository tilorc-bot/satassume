"""Verbatim copies of the ``LambertW`` generators from
``satassume/knowledge/templates/special.py`` at d149951, before they
became rows in ``templates/lambertw.py`` (#249).  Test-only:
``tests/test_lambertw_rows.py`` compares the clauses the rows emit with the
clauses these functions emit.  The ``registry.register`` lines are left
out (a test module's template would count as a user's); the test gives the slots ``x + 1/E`` and ``k + 1`` of ``_lambertw_slots``.  Do not edit
them to follow a later rule change; change the test's reference instead
(``git show d149951:satassume/knowledge/templates/special.py``)."""
from sympy import S, exp

from satassume.knowledge.templates.functions import shifted


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

