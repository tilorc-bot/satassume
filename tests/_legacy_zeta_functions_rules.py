"""Verbatim copies of the ``zeta``, ``dirichlet_eta`` and ``polylog`` generators from
``satassume/knowledge/templates/special.py`` at d149951, before they
became rows in ``templates/zeta_functions.py`` (#249).  Test-only:
``tests/test_zeta_functions_rows.py`` compares the clauses the rows emit with the
clauses these functions emit.  The ``registry.register`` lines are left
out (a test module's template would count as a user's); the test gives the slots ``s - 1`` (``zeta``) and ``z - 1`` (``polylog``) of those lines.  Do not edit
them to follow a later rule change; change the test's reference instead
(``git show d149951:satassume/knowledge/templates/special.py``)."""
from satassume.knowledge.templates.functions import N, X, _table


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

