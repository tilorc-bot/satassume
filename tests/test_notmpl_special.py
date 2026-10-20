"""Templates for special functions that had none (#180 C-NOTMPL, part B).

A node of a class without a template got no facts, whatever SymPy's own
``_eval_is_*`` knew.  These classes now have templates (``special.py``):
the gamma family, the error functions and their inverses, the exponential,
logarithmic, trigonometric and Fresnel integrals, ``owens_t``, the beta
functions, ``LambertW``, ``zeta``, ``dirichlet_eta``, ``polylog``, the Airy
functions and ``besselj``, ``bessely``, ``besseli``, ``besselk``.  Each
rule is a theorem about the value under SymPy's conventions; several of
SymPy's own handlers are not (``beta(5, -3) = oo`` is not real,
``LambertW(-1/E) = -1`` is real, ``polygamma(1, 0) = zoo`` is not
positive), and those answers differ or stay None here.
"""
import pytest
from _point_oracle import POOL, POOL2, check
from sympy import (Chi, Ci, E, Ei, I, LambertW, Li, Rational, S, Shi, Si, Symbol, airyai,
                   airyaiprime, airybi, airybiprime, besseli, besselj, besselk, bessely, beta,
                   betainc, betainc_regularized, digamma, dirichlet_eta, erf, erf2, erfc, erfcinv,
                   erfi, erfinv, exp, expint, fresnelc, fresnels, gamma, li, loggamma, lowergamma,
                   multigamma, oo, pi, polygamma, polylog, symbols, trigamma, uppergamma, zeta)

from satassume import DictCache, Engine

try:
    from sympy import owens_t
except ImportError:     # SymPy < 1.15
    owens_t = None

x, y = symbols('x y')
p = Symbol('p', positive=True)
neg = Symbol('neg', negative=True)
r = Symbol('r', real=True)
er = Symbol('er', extended_real=True)
nn = Symbol('nn', nonnegative=True)
i = Symbol('i', imaginary=True)
c = Symbol('c', complex=True, extended_real=False)
k = Symbol('k', integer=True)
kp = Symbol('kp', integer=True, positive=True)
kn = Symbol('kn', integer=True, negative=True)
knp = Symbol('knp', integer=True, nonpositive=True)
m = Symbol('m', integer=True, nonnegative=True)
od = Symbol('od', odd=True, positive=True)
ev = Symbol('ev', even=True, positive=True)
en = Symbol('en', even=True, negative=True)
nni = Symbol('nni', negative=True, integer=False)
inf = Symbol('inf', infinite=True)


def fresh():
    return Engine(cache=DictCache())


REPRODUCERS = [
    # the #180 table
    (LambertW(1), 'extended_real', True), (erf(1), 'positive', True), (erf(r), 'real', True),
    # test_gamma_functions: test_issue_8657, test_issue_8524
    (gamma(kn), 'real', False), (gamma(k), 'real', None), (gamma(p), 'real', True),
    (gamma(nni), 'real', True), (gamma(r), 'real', None),
    (gamma(p), 'positive', True), (gamma(neg), 'positive', None), (gamma(nn), 'positive', None),
    (gamma(k), 'positive', None), (gamma(en + S.Half), 'positive', True),
    (gamma(en - S.Half), 'positive', False), (gamma(oo, evaluate=False), 'real', False),
    (loggamma(p), 'real', True), (loggamma(nni), 'extended_real', False),
    (loggamma(knp), 'infinite', True),
    # test_multigamma
    (multigamma(Rational(-1, 2), 3, evaluate=False), 'real', False),
    (multigamma(S.Half, 3, evaluate=False), 'real', False),
    (multigamma(0, 1, evaluate=False), 'real', False),
    (multigamma(1, 3, evaluate=False), 'real', False),
    (multigamma(-1.0, 3, evaluate=False), 'real', False),
    (multigamma(0.7, 3, evaluate=False), 'real', True),
    (multigamma(3, 3, evaluate=False), 'real', True),
    (multigamma(Rational(-1, 2), 1, evaluate=False), 'real', True),
    (polygamma(od, p), 'positive', True), (polygamma(ev, p), 'negative', True),
    (polygamma(m, p), 'real', True), (polygamma(m, knp), 'finite', False),
    (digamma(p, evaluate=False), 'real', True), (trigamma(nni, evaluate=False), 'positive', True),
    (lowergamma(p, p), 'positive', True), (uppergamma(r, p), 'positive', True),
    # test_error_functions: test_erfi, test_erfcinv, test_fresnel
    (erfi(I), 'real', False), (erfi(0, evaluate=False), 'real', True),
    (erfi(0, evaluate=False), 'zero', True), (erfi(i), 'imaginary', True),
    (erfcinv(0, evaluate=False), 'infinite', True), (erfcinv(2, evaluate=False), 'infinite', True),
    (erfcinv(1, evaluate=False), 'zero', True), (erfinv(Rational(1, 3)), 'positive', True),
    (fresnels(r), 'extended_real', True), (fresnels(r), 'finite', True),
    (fresnels(x), 'extended_real', None), (fresnels(x), 'finite', None),
    (fresnelc(r), 'extended_real', True), (fresnels(c), 'finite', True),
    (fresnels(p), 'positive', True), (fresnelc(neg), 'negative', True),
    (erf(er), 'real', True), (erf(p), 'positive', True), (erf(oo, evaluate=False), 'odd', True),
    (erfc(r), 'positive', True), (erfc(-oo, evaluate=False), 'even', True),
    (erfc(i), 'real', False), (erf2(r, er), 'real', True),
    # exponential, logarithmic and trigonometric integrals
    (Ei(neg), 'negative', True), (Ei(p), 'real', True), (Ei(0, evaluate=False), 'infinite', True),
    (expint(r, p), 'positive', True), (expint(1, p), 'positive', True),
    (li(Rational(1, 2)), 'negative', True), (li(1, evaluate=False), 'extended_negative', True),
    (Li(3), 'positive', True), (Li(Rational(3, 2)), 'negative', True),
    (Si(p), 'positive', True), (Si(i), 'imaginary', True), (Shi(neg), 'negative', True),
    (Ci(p), 'real', True), (Ci(neg), 'extended_real', False), (Chi(neg), 'real', False),
    # beta functions: test_betainc, test_betainc_regularized
    (betainc(1, 2, 0, -5), 'real', True), (betainc(1, 2, 0, x), 'real', None),
    (betainc_regularized(3, 5, 0, -1), 'real', True),
    (betainc_regularized(3, 5, 0, x), 'real', None), (beta(p, p), 'positive', True),
    # LambertW (#180: 65 records), test_lambert_multivariate
    (LambertW(p), 'positive', True), (LambertW(-exp(-1), evaluate=False), 'real', True),
    (LambertW(-exp(-1), evaluate=False), 'negative', True), (LambertW(-1), 'extended_real', False),
    (LambertW(-pi/10), 'negative', True), (LambertW(-pi/10, -1), 'real', True),
    (LambertW(2, -1), 'extended_real', False), (LambertW(2), 'transcendental', True),
    (LambertW(-Rational(1, 5), 1), 'extended_real', False), (LambertW(c), 'real', False),
    # zeta, dirichlet_eta, polylog
    (zeta(3), 'positive', True), (zeta(Rational(1, 2)), 'negative', True),
    (zeta(1, evaluate=False), 'finite', False), (zeta(-2, evaluate=False), 'zero', True),
    (zeta(ev), 'transcendental', True), (zeta(p + 1), 'positive', True),
    (dirichlet_eta(p), 'positive', True), (polylog(3, Rational(1, 2)), 'positive', True),
    (polylog(r, -p), 'real', True), (polylog(nn, neg), 'negative', True),
    # test_bessel: test_airy_base, test_expand
    (airyai(r), 'extended_real', True), (airyai(nn), 'positive', True),
    (airyaiprime(nn), 'negative', True), (airybi(p), 'positive', True),
    (airybiprime(r), 'real', True),
    (besselj(k, p), 'extended_real', True), (besselj(k, x), 'extended_real', None),
    (besselj(x, y), 'extended_real', None), (besselj(k, r), 'extended_real', True),
    (bessely(k, p), 'extended_real', True), (bessely(k, r), 'extended_real', None),
    (besseli(k, r), 'extended_real', True), (besseli(k, p), 'positive', True),
    (besselk(k, p), 'extended_real', True), (besselk(k, r), 'extended_real', None),
    (besselk(r, p), 'positive', True),
]
if owens_t is not None:
    hr, ar = symbols('hr ar', extended_real=True)
    REPRODUCERS += [
        # test_owent_is_extended_real, test_owent_sign_and_finite, test_owent_is_zero
        (owens_t(hr, ar), 'extended_real', True), (owens_t(r, p), 'positive', True),
        (owens_t(r, p), 'negative', False), (owens_t(r, neg), 'negative', True),
        (owens_t(r, neg), 'zero', False), (owens_t(x, p), 'positive', None),
        (owens_t(r, y), 'positive', None), (owens_t(r, p), 'finite', True),
        (owens_t(x, y), 'finite', None), (owens_t(i, p), 'positive', True),
    ]


@pytest.mark.parametrize("expr, pred, expected", REPRODUCERS)
def test_reproducers(expr, pred, expected):
    assert fresh().is_(expr, pred) is expected


@pytest.mark.parametrize("expr, pred", [
    # beta(5, -3) == oo; betainc(1/2, 1, 0, -1) is not real
    (beta(5, -3), 'real'), (beta(3, y), 'real'), (betainc(S.Half, 1, 0, -1), 'real'),
    (betainc(r, r, r, r), 'real'),
    # gamma(oo) == oo, gamma(0) == zoo, loggamma(0) == oo
    (gamma(er), 'real'), (gamma(nn), 'finite'), (loggamma(nn), 'real'),
    # polygamma(1, 0) == zoo; polygamma(-1, x) is loggamma(x) - log(2*pi)/2
    (polygamma(1, r), 'positive'), (polygamma(m, r), 'complex'), (polygamma(k, p), 'real'),
    # the complex zeros of erf: erf, erfi and the Fresnel integrals can be real
    # (0) at non-real points; zeta has non-real zeros
    (erf(c), 'real'), (erf(c), 'zero'), (erfi(c), 'extended_real'), (erfi(c), 'zero'),
    (fresnels(c), 'real'), (airybi(c), 'extended_real'), (zeta(c), 'zero'),
    # zeta(-oo) has no value; erfinv beyond [-1, 1]
    (zeta(er), 'finite'), (erfinv(r), 'real'), (erfcinv(r), 'real'),
    # Ei has a zero on (0, oo); li changes sign at 1.45...; Ci(0) == zoo
    (Ei(p), 'positive'), (li(p + 1), 'positive'), (Ci(nn), 'finite'),
    # LambertW(x, k) for a non-integer k has no value; W_k(0) == -oo for k != 0
    (LambertW(p, x), 'real'), (LambertW(nn, k), 'finite'), (LambertW(r), 'real'),
    # polylog(-3, -1/2) > 0; polylog(s, 2) is not real
    (polylog(r, neg), 'negative'), (polylog(r, 2), 'real'),
    # multigamma(-1/2, 1) == -2*sqrt(pi); a symbolic p
    (multigamma(x, k), 'real'),
    # Ai'(-oo) has no value; bessely(k, 0) == zoo
    (airyaiprime(er), 'real'), (bessely(k, nn), 'real'), (besselj(x, p), 'real'),
])
def test_undecided(expr, pred):
    assert fresh().is_(expr, pred) is None


def test_other_argument_counts_get_no_facts():
    from sympy import Basic

    from satassume.knowledge.templates import registry
    # dirichlet_eta(s, a) has no rules; the others are built around the
    # argument check of Function (a node of another arity has no value)
    nodes = [dirichlet_eta(x, y)] + [Basic.__new__(f, *args) for f, args in (
        (polygamma, (x, y, p)), (betainc, (x, y, p)), (zeta, (x, y, p)), (erf, (x, p)),
        (multigamma, (x, 3, 1)), (LambertW, (x, y, p)), (beta, (x, y, p)), (besselj, (p,)))]
    for expr in nodes:
        assert not registry.facts_for(expr), expr


# ---------------------------------------------------------------------------
# soundness at concrete points, with a numerical oracle (_point_oracle)
# ---------------------------------------------------------------------------

UNARY = [gamma, loggamma, digamma, trigamma, erf, erfc, erfi, erfinv, erfcinv, Ei, li, Li, Si,
         Ci, Shi, Chi, fresnels, fresnelc, LambertW, zeta, dirichlet_eta, airyai, airybi,
         airyaiprime, airybiprime]
BINARY = [polygamma, lowergamma, uppergamma, erf2, expint, beta, LambertW, zeta, polylog,
          besselj, bessely, besseli, besselk] + ([owens_t] if owens_t is not None else [])


def _unary(f, a):
    return f(a, evaluate=False) if f in (digamma, trigamma) else f(a)


# (digamma, trigamma, polygamma and polylog at symbolic orders, lowergamma
# and Hurwitz zeta take minutes at these points with mpmath; they are checked
# by the numerical sweep of the PR, not here)
FAST_UNARY = [f for f in UNARY if f not in (digamma, trigamma)]
FAST_BINARY = [f for f in BINARY if f not in (polygamma, polylog, lowergamma, zeta)]
SAMPLES = ([f(a) for f in FAST_UNARY for a in (x, x + 1, x - 1, 2*x, x - S.Half)]
           + [f(x, y) for f in FAST_BINARY]
           + [LambertW(x, -1), LambertW(x, 1), zeta(x, 2), multigamma(x, 1, evaluate=False),
              multigamma(x, 2, evaluate=False), multigamma(x, 3, evaluate=False),
              besselj(1, x), besseli(2, x), beta(x, evaluate=False)])

#: more points for the slots of these functions (around -1/E, 1, 2, -2)
POOL_X = POOL + [-exp(-1), -1/(2*E), -S(2)/5, Rational(5, 2), Rational(-5, 2), Rational(-1, 2) - 4,
                 Rational(1, 10), Rational(9, 10), 3*I]
POOL_XY = POOL2 + [S(3), S(-2), Rational(-1, 2), Rational(7, 3), 2*I, -exp(-1)]


@pytest.mark.parametrize("expr", SAMPLES, ids=str)
def test_sound_at_points(expr):
    wrong = check(expr, POOL_X, POOL_XY)
    assert not wrong, wrong[:5]


def test_sound_at_constant_points():
    # nodes left unevaluated at constant arguments
    for expr in (multigamma(Rational(-1, 2), 3, evaluate=False), erfcinv(2, evaluate=False),
                 LambertW(-exp(-1), evaluate=False), zeta(-2, evaluate=False),
                 gamma(-3, evaluate=False), loggamma(0, evaluate=False), Ci(0, evaluate=False),
                 polylog(S.Half, Rational(1, 3)), owens_t(I, 1) if owens_t else erf(1)):
        assert not check(expr), expr
