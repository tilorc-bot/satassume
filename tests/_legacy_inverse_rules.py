"""Verbatim copies of the ``asin``, ``acos``, ``atan``, ``acot``, ``asinh``,
``acosh``, ``atanh``, ``acoth``, ``asech``, ``acsch``, ``asec`` and ``acsc``
generators from ``satassume/knowledge/templates/functions.py`` at d149951,
before they became rows in ``templates/inverse.py`` (#249).  Test-only:
``tests/test_inverse_rows.py`` compares the clauses the rows emit with the
clauses these functions emit.  Do not edit them to follow a later rule
change; change the test's reference instead (``git show
d149951:satassume/knowledge/templates/functions.py``)."""
from satassume.knowledge.templates.functions import M, N, X

from _legacy_helpers import P1, _TRANSCENDENTAL, _equiv, _table


def _asin(R, c):
    R.equiv([], (N, 'zero', True), (X, 'zero', True))
    R.rule([(N, 'real', True)], (X, 'real', True))
    R.equiv([(N, 'real', True)], (N, 'positive', True), (X, 'positive', True))
    R.equiv([(N, 'real', True)], (N, 'negative', True), (X, 'negative', True))
    # asin is real on [-1, 1].
    R.rule([(X, 'nonnegative', True), (M, 'nonpositive', True)], (N, 'real', True))
    _table(R, ((('finite',), 'finite'), (('complex',), 'complex'),
               (('imaginary',), 'imaginary'), _TRANSCENDENTAL))


def _acos(R, c):
    R.rule([(N, 'real', True)], (N, 'nonnegative', True))
    R.rule([(N, 'real', True)], (X, 'real', True))
    # acos(x) == 0 iff x == 1.
    R.equiv([], (N, 'zero', True), (M, 'zero', True))
    _table(R, ((('zero',), 'positive'), (('finite',), 'finite'), (('complex',), 'complex')))
    R.rule([(X, 'algebraic', True), (N, 'zero', False)], (N, 'transcendental', True))



def _atan(R, c):
    R.rule([(X, 'extended_real', True)], (N, 'real', True))
    R.equiv([], (N, 'zero', True), (X, 'zero', True))
    R.equiv([(X, 'extended_real', True)], (N, 'positive', True), (X, 'extended_positive', True))
    R.equiv([(X, 'extended_real', True)], (N, 'negative', True), (X, 'extended_negative', True))
    # atan(I) == oo*I, so restrict to real arguments.
    R.rule([(X, 'real', True), (X, 'algebraic', True), (X, 'zero', False)],
           (N, 'transcendental', True))
    # atan(x) is real iff x is real (atan(I*t) is imaginary, infinite or
    # non-real complex).
    R.rule([(X, 'imaginary', True)], (N, 'extended_real', False))


_ACOT = (
    (('extended_real',), 'real'),
    (('nonnegative',), 'positive'),           # acot(0) == pi/2
    (('negative',), 'negative'),
    (('extended_nonnegative',), 'nonnegative'),
    (('extended_negative',), 'nonpositive'),  # acot(-oo) == 0
    (('real',), ('zero', False)),
    (('infinite', 'extended_real'), 'zero'),
    (('real', 'algebraic'), 'transcendental'),
    (('imaginary',), ('extended_real', False)),
    # acot(0) == pi/2, acot(+-I) is infinite, acot(x) == atan(1/x) otherwise.
    (('algebraic',), ('algebraic', False)),
)


def _acot(R, c):
    _table(R, _ACOT)



_ASINH = (
    (('real',), 'real'), (('extended_real',), 'extended_real'),
    (('finite',), 'finite'), (('complex',), 'complex'),
    (('infinite',), 'infinite'),                    # asinh(oo*I) == oo, asinh(zoo) == zoo
    # asinh(I*t) == I*asin(t): imaginary for |t| <= 1, else a real part
    (('imaginary',), ('extended_real', False)),
    _TRANSCENDENTAL,
)


def _asinh(R, c):
    _table(R, _ASINH)
    R.equiv([], (N, 'zero', True), (X, 'zero', True))
    _equiv(R, [(X, 'extended_real', True)], ('extended_positive', 'extended_negative'))


def _acosh(R, c):
    # acosh(x) == 0 iff x == 1; real (and >= 0) iff x >= 1
    R.equiv([], (N, 'zero', True), (M, 'zero', True))
    R.rule([(X, 'real', True), (M, 'nonnegative', True)], (N, 'nonnegative', True))
    R.rule([(X, 'real', True), (M, 'positive', True)], (N, 'positive', True))
    # x < 1: I*acos(x) for x in [-1, 1), log(-x + sqrt(x**2 - 1)) + I*pi below
    R.rule([(X, 'real', True), (M, 'negative', True)], (N, 'extended_real', False))
    R.rule([(X, 'infinite', True), (X, 'extended_real', True)], (N, 'extended_positive', True))
    _table(R, (
        (('finite',), 'finite'), (('complex',), 'complex'), (('infinite',), 'infinite'),
        # acosh(I*t) == asinh(|t|) +- I*pi/2
        (('imaginary',), ('extended_real', False)), (('imaginary',), ('imaginary', False)),
    ))
    R.rule([(X, 'algebraic', True), (N, 'zero', False)], (N, 'transcendental', True))


def _atanh(R, c):
    R.equiv([], (N, 'zero', True), (X, 'zero', True))
    # real on (-1, 1) with the sign of x; +-oo at +-1; not real beyond
    R.rule([(M, 'negative', True), (P1, 'positive', True)], (N, 'real', True))
    R.rule([(X, 'positive', True), (M, 'negative', True)], (N, 'positive', True))
    R.rule([(X, 'negative', True), (P1, 'positive', True)], (N, 'negative', True))
    R.rule([(X, 'positive', True), (M, 'positive', True)], (N, 'extended_real', False))
    R.rule([(X, 'negative', True), (P1, 'negative', True)], (N, 'extended_real', False))
    R.rule([(X, 'positive', True), (M, 'zero', True)], (N, 'infinite', True))
    R.rule([(X, 'positive', True), (M, 'zero', True)], (N, 'extended_positive', True))
    R.rule([(X, 'negative', True), (P1, 'zero', True)], (N, 'infinite', True))
    R.rule([(X, 'negative', True), (P1, 'zero', True)], (N, 'extended_negative', True))
    R.rule([(X, 'infinite', True), (X, 'extended_real', True)], (N, 'imaginary', True))
    R.rule([(X, 'complex', True), (M, 'zero', False), (P1, 'zero', False)], (N, 'complex', True))
    # atanh(I*t) == I*atan(t), atan(t) in (-pi/2, pi/2) \ {0}
    R.rule([(X, 'imaginary', True)], (N, 'imaginary', True))
    R.rule([(X, 'algebraic', True), (X, 'zero', False), (M, 'zero', False), (P1, 'zero', False)],
           (N, 'transcendental', True))


def _acoth(R, c):
    # acoth(x) == atanh(1/x): 0 only at the infinities, acoth(0) == I*pi/2;
    # SymPy evaluates acoth(+-oo), acoth(zoo) and acoth(+-oo*I) to 0 but
    # leaves acoth(1 + oo*I) alone (its evalf is nan): no claim there
    R.rule([(N, 'zero', True)], (X, 'infinite', True))
    R.rule([(X, 'infinite', True), (X, 'extended_real', True)], (N, 'zero', True))
    R.rule([(X, 'positive', True), (M, 'positive', True)], (N, 'positive', True))
    R.rule([(X, 'negative', True), (P1, 'negative', True)], (N, 'negative', True))
    R.rule([(X, 'real', True), (M, 'negative', True), (P1, 'positive', True)],
           (N, 'extended_real', False))
    R.rule([(X, 'positive', True), (M, 'zero', True)], (N, 'infinite', True))
    R.rule([(X, 'positive', True), (M, 'zero', True)], (N, 'extended_positive', True))
    R.rule([(X, 'negative', True), (P1, 'zero', True)], (N, 'infinite', True))
    R.rule([(X, 'negative', True), (P1, 'zero', True)], (N, 'extended_negative', True))
    R.rule([(X, 'complex', True), (M, 'zero', False), (P1, 'zero', False)], (N, 'complex', True))
    # acoth(I*t) == -I*atan(1/t)
    R.rule([(X, 'imaginary', True)], (N, 'imaginary', True))
    R.rule([(X, 'algebraic', True), (M, 'zero', False), (P1, 'zero', False)],
           (N, 'transcendental', True))


def _asech(R, c):
    # asech(x) == acosh(1/x): real (and >= 0) on (0, 1], 0 iff x == 1
    R.equiv([], (N, 'zero', True), (M, 'zero', True))
    R.rule([(X, 'positive', True), (M, 'nonpositive', True)], (N, 'nonnegative', True))
    R.rule([(X, 'positive', True), (M, 'negative', True)], (N, 'positive', True))
    R.rule([(X, 'zero', True)], (N, 'infinite', True))
    R.rule([(X, 'zero', True)], (N, 'extended_positive', True))
    # x > 1: I*acos(1/x); x < 0: acosh of a number below 0
    R.rule([(X, 'positive', True), (M, 'positive', True)], (N, 'imaginary', True))
    R.rule([(X, 'negative', True)], (N, 'extended_real', False))
    R.rule([(X, 'infinite', True), (X, 'extended_real', True)], (N, 'imaginary', True))
    R.rule([(X, 'complex', True), (X, 'zero', False)], (N, 'complex', True))
    R.rule([(X, 'imaginary', True)], (N, 'extended_real', False))
    R.rule([(X, 'imaginary', True)], (N, 'imaginary', False))
    R.rule([(X, 'algebraic', True), (X, 'zero', False), (N, 'zero', False)],
           (N, 'transcendental', True))


def _acsch(R, c):
    # acsch(x) == asinh(1/x): 0 exactly at the infinities, acsch(0) == zoo
    R.equiv([], (N, 'zero', True), (X, 'infinite', True))
    R.rule([(X, 'extended_real', True), (X, 'zero', False)], (N, 'real', True))
    R.rule([(X, 'positive', True)], (N, 'positive', True))
    R.rule([(X, 'negative', True)], (N, 'negative', True))
    R.rule([(X, 'extended_real', True)], (N, 'imaginary', False))
    R.rule([(X, 'zero', True)], (N, 'infinite', True))
    R.rule([(X, 'zero', True)], (N, 'extended_real', False))
    R.rule([(X, 'complex', True), (X, 'zero', False)], (N, 'complex', True))
    R.rule([(X, 'imaginary', True)], (N, 'extended_real', False))
    R.rule([(X, 'algebraic', True), (X, 'zero', False)], (N, 'transcendental', True))


def _asec(R, c):
    # asec(x) == acos(1/x): real for |x| >= 1, 0 iff x == 1, pi/2 at every
    # infinity
    R.equiv([], (N, 'zero', True), (M, 'zero', True))
    R.rule([(X, 'infinite', True)], (N, 'positive', True))
    R.rule([(X, 'zero', True)], (N, 'infinite', True))
    R.rule([(X, 'zero', True)], (N, 'extended_real', False))
    R.rule([(X, 'positive', True), (M, 'nonnegative', True)], (N, 'nonnegative', True))
    R.rule([(X, 'negative', True), (P1, 'nonpositive', True)], (N, 'positive', True))
    R.rule([(X, 'real', True), (M, 'negative', True), (P1, 'positive', True)],
           (N, 'extended_real', False))
    R.rule([(X, 'complex', True), (X, 'zero', False)], (N, 'complex', True))
    # asec(I*t) == pi/2 + I*asinh(1/t)
    R.rule([(X, 'imaginary', True)], (N, 'extended_real', False))
    R.rule([(X, 'imaginary', True)], (N, 'imaginary', False))
    R.rule([(X, 'algebraic', True), (X, 'zero', False), (N, 'zero', False)],
           (N, 'transcendental', True))


def _acsc(R, c):
    # acsc(x) == asin(1/x): real for |x| >= 1 with the sign of x, 0 exactly
    # at the infinities
    R.equiv([], (N, 'zero', True), (X, 'infinite', True))
    R.rule([(X, 'zero', True)], (N, 'infinite', True))
    R.rule([(X, 'zero', True)], (N, 'extended_real', False))
    R.rule([(X, 'positive', True), (M, 'nonnegative', True)], (N, 'positive', True))
    R.rule([(X, 'negative', True), (P1, 'nonpositive', True)], (N, 'negative', True))
    R.rule([(X, 'real', True), (M, 'negative', True), (P1, 'positive', True)],
           (N, 'extended_real', False))
    R.rule([(X, 'complex', True), (X, 'zero', False)], (N, 'complex', True))
    # acsc(I*t) == -I*asinh(1/t)
    R.rule([(X, 'imaginary', True)], (N, 'imaginary', True))
    R.rule([(X, 'algebraic', True), (X, 'zero', False)], (N, 'transcendental', True))


# Not verbatim: the slots x + c of each generator's registration at
# d149951 (``slots=_minus_one``, ``slots=_minus_plus_one``), as
# templates/_rows.py's rules() records them for rows.
for _gen in (_asin, _acos, _acosh, _asech):
    _gen.shifts = (-1,)
for _gen in (_atanh, _acoth, _asec, _acsc):
    _gen.shifts = (-1, 1)
