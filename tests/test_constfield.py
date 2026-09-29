"""Tests of satassume/constfield.py: exact numbers in Q(pi, E, sqrt(2), ...).

Oracles independent of the implementation:

* mpmath at 1500 digits for values and signs (a definite answer must agree
  wherever the reference value is not tiny; Undecided is allowed only
  where noted);
* z3's ``rcf`` module (de Moura and Passmore's real closed field, which
  knows ``sqrt(2)`` exactly) for signs, zero tests and comparisons of
  random expressions (skipped without ``z3-solver``);
* algebraic identities for the normal form (hash and ``==`` of equal
  numbers built differently).
"""
from __future__ import annotations

import math
import random
from fractions import Fraction as F

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from satassume import constfield as cf
from satassume.constfield import PI, E, Element, Undecided, from_sympy

mpmath = pytest.importorskip("mpmath")
mp = mpmath.mp

SQRT2 = cf.radical(2, 2)
CBRT3 = cf.radical(3, 3)


def ref(x, dps=1500):
    """High-precision value of a Fraction or Element (independent of the
    enclosures: evaluates the normal form's polynomials with mpmath)."""
    with mp.workdps(dps):
        vals = {"pi": mp.pi, "E": mp.e, ("root", F(2), 2): mp.sqrt(2),
                ("root", F(3), 3): mp.cbrt(3)}

        def ev(p):
            if type(p) is F:
                return mp.mpf(p.numerator) / p.denominator
            t = vals[cf._CONSTANTS[p[0]].key]
            r = mp.mpf(0)
            for c in reversed(p[1]):
                r = r * t + ev(c)
            return r
        if type(x) is F:
            return ev(x)
        return ev(x.numerator) / ev(x.denominator)


def mp_sign(v, dps=1500):
    if abs(v) < mp.mpf(10) ** (-(dps - 100)):
        return None                          # too close to 0 to tell
    return 1 if v > 0 else -1


# ----------------------------------------------------------------------
# exactness and the normal form
# ----------------------------------------------------------------------

def test_cancellations_collapse_to_fractions():
    assert PI / PI == 1 and type(PI / PI) is F
    r = (-PI / 2) / PI + F(1, 2)
    assert r == 0 and type(r) is F
    assert type((3 * PI / 2) / PI) is F and (3 * PI / 2) / PI == F(3, 2)
    assert type(PI - PI) is F and (PI + E) - E is not None and (PI + E) - E == PI
    assert (PI * E) / (E * PI) == 1
    assert ((PI + 1) * (PI - 1) - PI ** 2) == -1


def test_refine_endpoints():
    # ask(Q.integer(x/pi + 1/2), Q.gt(x, -pi/2) & Q.lt(x, pi/2)): the form
    # x/pi + 1/2 at the ends of the interval is exactly 0 and 1
    lo, hi = -PI / 2, PI / 2
    form = lambda x: x / PI + F(1, 2)
    assert form(lo) == 0 and type(form(lo)) is F
    assert form(hi) == 1 and type(form(hi)) is F
    mid = form(F(1, 3))                       # strictly inside
    assert 0 < mid < 1 and math.floor(mid) == 0 and math.ceil(mid) == 1
    # just inside the ends, by less than 1e-30
    eps = F(1, 10 ** 30)
    assert 0 < form(lo + eps) < form(hi - eps) < 1
    # x <= 3*pi/2 with x = 3*pi/2 - pi: exact tie against pi/2
    assert 3 * PI / 2 - PI == PI / 2
    assert (x := 3 * PI / 2) / PI == F(3, 2) and x > 4 and x < 5


def test_normal_form_hash_and_eq():
    a = (PI * PI - 1) / (PI - 1)
    b = PI + 1
    assert a == b and hash(a) == hash(b) and repr(a) == repr(b)
    assert len({a, b, PI + F(2, 2)}) == 1
    c = (PI * E + 1) / (PI - E)
    d = (E * PI * E + E) / (E * PI - E * E)   # multiplied through by E
    assert c == d and hash(c) == hash(d)
    # multivariate common factor (pi + E)(pi - sqrt 2)
    g = (PI + E) * (PI - SQRT2)
    assert (g * (E + 3)) / (g * (PI * PI + SQRT2)) == (E + 3) / (PI * PI + SQRT2)
    assert {(1, PI / 2): "x"}[(1, (PI * PI / 2) / PI)] == "x"


def test_denominator_is_monic():
    a = 1 / (2 * PI + 4)
    assert a.denominator == (0, (F(2), F(1)))
    assert a.numerator == F(1, 2)
    assert (3 * PI) / (6 * PI + 3) == PI / (2 * PI + 1)


# ----------------------------------------------------------------------
# mixing with Fraction and int; delta-rationals
# ----------------------------------------------------------------------

def test_mixed_arithmetic():
    for q in (F(1, 3), 2, F(-7, 5)):
        assert (PI + q) - q == PI
        assert q + PI == PI + q
        assert q - PI == -(PI - q)
        assert (PI * q) / q == PI and q * PI == PI * q
        assert q / PI == 1 / (PI / q)
        assert type(PI * 0) is F and PI * 0 == 0 and 0 * PI == 0
    assert type(F(1) + PI) is Element
    assert PI > 3 and 3 < PI and PI < F(22, 7) and F(22, 7) > PI
    assert PI >= F(333, 106) and PI <= F(355, 113) and not PI > F(355, 113)
    assert PI != 3 and 3 != PI and not (PI == F(22, 7))
    assert sum([PI, E, F(1)]) == PI + E + 1
    with pytest.raises(TypeError):
        F(PI)
    with pytest.raises(TypeError):
        PI + 0.5
    assert cf.num(3) == F(3) and cf.num(PI) is PI and cf.num("1/3") == F(1, 3)
    with pytest.raises(TypeError):
        cf.num(0.5)


def test_delta_rational_pairs():
    # the simplex compares (q, d) pairs lexicographically
    lo = (-PI / 2, F(1))
    assert lo > (-PI / 2, F(0)) and lo < (-PI / 2 + F(1, 10 ** 40), F(-1))
    assert (PI / 2, F(0)) == ((PI * PI) / (2 * PI), F(0))
    assert max([(PI, F(0)), (F(3), F(5)), (PI, F(-1))]) == (PI, F(0))
    assert sorted([PI, F(3), E, F(22, 7), PI / 2]) == [PI / 2, E, F(3), PI, F(22, 7)]


def test_floor_and_ceil():
    assert math.floor(PI) == 3 and math.ceil(PI) == 4
    assert math.floor(-PI) == -4 and math.ceil(-PI) == -3
    assert math.floor(1000 * E) == 2718 and math.floor(PI ** 10) == 93648
    assert math.floor(PI / 2 - F(3, 2)) == 0      # 0.0707...
    assert math.floor(SQRT2 * 7) == 9 and math.ceil(CBRT3 * 10) == 15
    with mp.workdps(80):
        assert math.floor((PI - 3) * 10 ** 50) == int(mp.floor((mp.pi - 3) * mp.mpf(10) ** 50))


def test_floor_matches_mpmath_on_scaled_constants():
    with mp.workdps(200):
        for k in range(0, 60, 7):
            for c, v in ((PI, mp.pi), (E, mp.e), (SQRT2, mp.sqrt(2))):
                s = F(10) ** k
                assert math.floor(c * s) == int(mp.floor(v * s))
                assert math.ceil(-c * s) == int(mp.ceil(-v * s))


# ----------------------------------------------------------------------
# enclosures of the constants
# ----------------------------------------------------------------------

@pytest.mark.parametrize("prec", [1, 2, 10, 53, 64, 100, 128, 255, 256, 1000, 3000])
def test_constant_enclosures(prec):
    with mp.workprec(prec + 200):
        for c, v in ((PI, mp.pi), (E, mp.e), (SQRT2, mp.sqrt(2)), (CBRT3, mp.cbrt(3))):
            lo, hi = c.constants()[0].enclose(prec)
            s = v * mp.mpf(2) ** prec
            assert lo <= s <= hi, (c, prec)
            assert hi - lo <= 4, (c, prec)


def test_radical_enclosure_is_exact_integer_root():
    for r, b in ((F(2), 2), (F(3), 3), (F(5, 7), 2), (F(10 ** 9 + 7), 5)):
        c = cf.radical(r, b).constants()[0]
        for prec in (1, 64, 500):
            lo, hi = c.enclose(prec)
            n = r * (1 << (b * prec))
            assert lo ** b <= n <= hi ** b
            assert (lo + 1) ** b > n or lo + 1 > hi


# ----------------------------------------------------------------------
# random expressions: signs against mpmath (and z3 below)
# ----------------------------------------------------------------------

LEAVES = [PI, E, SQRT2, CBRT3]


def rand_expr(rng, depth, leaves=LEAVES):
    """A random Fraction or Element built by arithmetic; None if a
    division hit a divisor not shown nonzero."""
    if depth == 0 or rng.random() < 0.25:
        if rng.random() < 0.5:
            return rng.choice(leaves)
        return F(rng.randint(-9, 9), rng.randint(1, 5))
    a, b = rand_expr(rng, depth - 1, leaves), rand_expr(rng, depth - 1, leaves)
    if a is None or b is None:
        return None
    op = rng.choice("+-*/")
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    try:
        return a / b
    except (ZeroDivisionError, Undecided):
        return None


def check_sign(x, allow_undecided=False):
    v = ref(x)
    s = mp_sign(v)
    try:
        got = cf.sign(x)
    except Undecided:
        assert allow_undecided or s is None, (x, v)
        return None
    if s is not None:
        assert got == s, (x, v)
    else:
        assert type(x) is F and x == 0
    return got


def test_random_signs_against_mpmath():
    rng = random.Random(1)
    n = 0
    for _ in range(1500):
        x = rand_expr(rng, 4)
        if x is None:
            continue
        check_sign(x, allow_undecided=bool(set(x.constants()) - {PI.constants()[0]})
                   if type(x) is Element else False)
        n += 1
    assert n > 1000


def test_near_ties_decided_exactly():
    # pi against its own dyadic truncations just below and above
    with mp.workprec(4200):
        for k in (10, 63, 64, 65, 127, 128, 129, 500, 1000, 2000, 4000):
            t = int(mp.floor(mp.pi * mp.mpf(2) ** k))
            lo, hi = F(t, 2 ** k), F(t + 1, 2 ** k)
            assert PI > lo and PI < hi and PI != lo
            assert (PI - lo).sign() == 1 and (hi - PI).sign() == 1
            # the same through a rational function of pi
            x = (PI * PI + 1) / (PI - 3)
            v = (mp.pi ** 2 + 1) / (mp.pi - 3)
            q = F(int(mp.floor(v * mp.mpf(2) ** k)), 2 ** k)
            assert x > q and not x < q


def test_signs_of_polynomials_with_tiny_values():
    # p(pi) with p the minimal-ish polynomial of a rational approximation:
    # 113*pi - 355 is about 3e-5, (113*pi - 355)**6 about 1e-27
    x = (113 * PI - 355) ** 6 * (E - F(2718281828, 10 ** 9))
    assert check_sign(x) == 1
    y = (PI - F(355, 113)) ** 20            # about 3e-132
    assert y > F(1, 10 ** 132) and y < F(1, 10 ** 131)


# ----------------------------------------------------------------------
# Undecided: really zero, or closer than the cap
# ----------------------------------------------------------------------

def test_algebraic_zero_is_undecided():
    z = SQRT2 * SQRT2 - 2                    # formally t**2 - 2, value 0
    assert type(z) is Element
    for f in (z.sign, lambda: bool(z), lambda: z == 0, lambda: z != 0,
              lambda: z < 0, lambda: z > 0, lambda: z <= 0, lambda: 0 == z,
              lambda: 1 / z, lambda: PI / z, lambda: SQRT2 * SQRT2 == 2,
              lambda: math.floor(SQRT2 * SQRT2), lambda: math.ceil(CBRT3 ** 3)):
        with pytest.raises(Undecided):
            f()
    # decided when not zero
    assert SQRT2 * SQRT2 > F(19999, 10000) and SQRT2 * SQRT2 < F(20001, 10000)
    assert z + F(1, 10 ** 100) > 0


def test_exact_rational_radical_is_undecided_not_ordered():
    # 4**(1/2) is exactly 2, and its enclosures are exactly 2 at every
    # precision: touching the rational 2 must not order them
    r = cf.radical(4, 2)
    for f in (lambda: r < 2, lambda: r > 2, lambda: r == 2, lambda: 2 < r,
              lambda: r <= F(2), lambda: (r, F(0)) < (F(2), F(0))):
        with pytest.raises(Undecided):
            f()
    assert math.floor(r) == 2 and r > F(199, 100) and r < 3
    assert cf.radical(F(9, 4), 2) > F(3, 2) - F(1, 10 ** 30)


def test_beyond_the_cap_is_undecided():
    k = cf.PREC_CAP + 200
    with mp.workprec(k + 50):
        t = F(int(mp.floor(mp.pi * mp.mpf(2) ** k)), 2 ** k)
    x = PI - t                               # about 2**-(cap + 200)
    with pytest.raises(Undecided):
        x.sign()
    with pytest.raises(Undecided):
        PI < t
    assert PI != t                           # formal: pi is transcendental


def test_two_transcendentals_need_evaluation():
    # pi != E formally; their independence is open, so == is decided by
    # the numbers (and succeeds)
    assert PI != E and not (PI == E) and PI + E != 5
    assert (PI * E) == (E * PI)
    assert PI * E > 8 and PI * E < 9


def test_generic_constants_have_limited_precision():
    sympy = pytest.importorskip("sympy")
    l2 = from_sympy(sympy.log(2))
    assert l2 > F(693, 1000) and l2 < F(694, 1000)
    with mp.workdps(100):
        q = F(int(mp.floor(mp.log(2) * mp.mpf(2) ** 100)), 2 ** 100)
    with pytest.raises(Undecided):
        (l2 - q).sign()
    assert l2 == from_sympy(sympy.log(2)) and l2 * 3 == from_sympy(3 * sympy.log(2))
    with pytest.raises(Undecided):         # log(8) and 3*log(2) are unrelated
        from_sympy(sympy.log(8)) == 3 * l2


def test_division_by_zero():
    with pytest.raises(ZeroDivisionError):
        PI / 0
    with pytest.raises(ZeroDivisionError):
        1 / (PI - PI)


# ----------------------------------------------------------------------
# SymPy conversion
# ----------------------------------------------------------------------

def test_from_sympy():
    sympy = pytest.importorskip("sympy")
    from sympy import Float, I, Rational, S, Symbol, exp, nan, oo, pi, sqrt, zoo
    assert from_sympy(Rational(3, 7)) == F(3, 7) and type(from_sympy(S(2))) is F
    assert from_sympy(pi) is PI and from_sympy(S.Exp1) is E
    assert from_sympy(pi / 2) == PI / 2 and from_sympy(3 * pi / 2) == 3 * PI / 2
    assert from_sympy(1 / pi) == 1 / PI and from_sympy(pi ** -2) == 1 / (PI * PI)
    assert from_sympy(sqrt(2)) == SQRT2 and from_sympy(sqrt(8)) == 2 * SQRT2
    assert from_sympy(2 ** Rational(2, 3)) == cf.radical(2, 3) ** 2
    assert from_sympy(exp(2)) == E * E and from_sympy(exp(-3)) == E ** -3
    assert from_sympy((pi + 1) / (pi - 1) + sqrt(2) * pi) == (PI + 1) / (PI - 1) + SQRT2 * PI
    x = Symbol("x")
    for bad in (x, pi * x, Float(0.5), pi + Float(0.5), I, I * pi, oo, -oo, zoo, nan,
                sqrt(-2), sympy.Integral(x, (x, 0, 1))):
        assert from_sympy(bad) is None, bad
    e = from_sympy(sympy.sin(1) + pi)
    assert e is not None and e > F(398, 100) and e < F(399, 100)
    for v in ((PI + 1) / (PI - E), SQRT2 * PI - 3 * E ** 2, PI / 2):
        assert from_sympy(v.to_sympy()) == v
        assert abs(float(v.to_sympy().evalf(30)) - float(ref(v))) < 1e-12


# ----------------------------------------------------------------------
# polynomial gcd
# ----------------------------------------------------------------------

def test_multivariate_gcd():
    t = [c.numerator for c in (PI, E, SQRT2)]
    p, e, s = t
    P = cf._add
    M = cf._mul
    a = P(M(p, e), F(1))                       # pi*E + 1
    b = P(M(s, s), M(F(-1), e))                # s**2 - E
    c = P(M(p, p), M(F(3), s))                 # pi**2 + 3 s
    g = cf._gcd(M(M(a, b), c), M(M(a, c), P(p, e)))
    assert g == cf._monic(M(a, c))
    assert cf._gcd(M(a, a), a) == cf._monic(a)
    assert cf._gcd(a, b) == 1 and cf._gcd(F(0), b) == cf._monic(b)
    assert cf._divexact(M(M(a, b), c), M(a, c)) == b
    with pytest.raises(ArithmeticError):
        cf._divexact(M(a, b), c)


def test_monomial_gcd_and_division():
    p, e = PI.numerator, E.numerator
    M, P = cf._mul, cf._add
    t2, t3 = M(p, p), M(M(p, p), p)
    q = P(M(t3, P(e, F(1))), M(t2, e))         # pi**3 (E + 1) + pi**2 E
    assert cf._gcd(q, t3) == t2 and cf._gcd(t3, q) == t2
    assert cf._gcd(q, M(F(5), p)) == p and cf._gcd(P(p, F(1)), t2) == 1
    assert cf._divexact(q, M(F(3), t2)) == cf._scale(P(M(p, P(e, F(1))), e), F(1, 3))
    with pytest.raises(ArithmeticError):
        cf._divexact(P(q, F(1)), p)
    assert (PI ** 3 + PI ** 2) / PI ** 2 == PI + 1


def _poly_sympy(p, syms):
    import sympy
    if type(p) is F:
        return sympy.Rational(p.numerator, p.denominator)
    return sum((_poly_sympy(c, syms) * syms[p[0]] ** k for k, c in enumerate(p[1])),
               sympy.S(0))


_small_polys = st.recursive(
    st.one_of(st.fractions(-5, 5, max_denominator=3).filter(bool),
              st.sampled_from([c.numerator for c in LEAVES])),
    lambda ch: st.tuples(st.sampled_from([cf._add, cf._mul]), ch, ch).map(lambda t: t[0](t[1], t[2])),
    max_leaves=6)


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(_small_polys, _small_polys, _small_polys)
def test_gcd_against_sympy(a, b, c):
    sympy = pytest.importorskip("sympy")
    assume(not cf._zero(a) and not cf._zero(b) and not cf._zero(c))
    x, y = cf._mul(a, c), cf._mul(b, c)
    g = cf._gcd(x, y)
    syms = {i: sympy.Symbol(f"t{i}") for i in range(len(cf._CONSTANTS))}
    ref_g = sympy.gcd(_poly_sympy(x, syms), _poly_sympy(y, syms))
    ratio = sympy.cancel(_poly_sympy(g, syms) / ref_g)
    assert ratio.is_Rational and ratio != 0, (g, ref_g)
    assert cf._lcrec(g) == 1
    assert cf._mul(cf._divexact(x, g), g) == x and cf._mul(cf._divexact(y, g), g) == y


# ----------------------------------------------------------------------
# property-based tests
# ----------------------------------------------------------------------

rats = st.fractions(min_value=-20, max_value=20, max_denominator=12)
leaf = st.one_of(rats, st.sampled_from(LEAVES))


def _combine(children):
    def build(t):
        op, a, b = t
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        try:
            return a / b
        except (ZeroDivisionError, Undecided):
            return a
    return st.tuples(st.sampled_from("+-*/"), children, children).map(build)


numbers = st.recursive(leaf, _combine, max_leaves=8)
PROP = settings(max_examples=150, deadline=None,
                suppress_health_check=[HealthCheck.too_slow])


@PROP
@given(numbers, numbers, numbers)
def test_field_axioms(a, b, c):
    assert a + b == b + a and a * b == b * a
    assert (a + b) + c == a + (b + c)
    assert (a * b) * c == a * (b * c)
    assert a * (b + c) == a * b + a * c
    assert a - a == 0 and type(a - a) is F
    assert (a + b) - b == a
    try:
        inv = 1 / b
    except (ZeroDivisionError, Undecided):
        return
    assert (a * b) * inv == a and (a / b) * b == a
    assert b * inv == 1 and type(b * inv) is F


@PROP
@given(numbers, numbers)
def test_hash_consistent_with_eq(a, b):
    try:
        eq = a == b
    except Undecided:
        return
    if eq:
        assert hash(a) == hash(b)
    c = (a * b + a) - a * b                    # equal to a, built differently
    assert c == a and hash(c) == hash(a)
    assert type(c) is type(a)


@PROP
@given(numbers)
def test_sign_against_mpmath(a):
    check_sign(a, allow_undecided=True)
    try:
        s = cf.sign(a)
    except Undecided:
        return
    assert s == -cf.sign(-a)
    assert (a > 0) == (s > 0) and (a < 0) == (s < 0) and (a == 0) == (s == 0)


@PROP
@given(numbers, numbers)
def test_comparisons_are_consistent(a, b):
    try:
        lt, gt, eq = a < b, a > b, a == b
    except Undecided:
        return
    assert lt + gt + eq == 1
    assert (b > a) == lt and (a <= b) == (lt or eq) and (a >= b) == (gt or eq)
    assert (a != b) == (not eq)
    va, vb = ref(a, 300), ref(b, 300)
    if abs(va - vb) > mp.mpf(10) ** -250:
        assert lt == (va < vb)


@PROP
@given(st.recursive(st.one_of(rats, st.just(PI)), _combine, max_leaves=10))
def test_pi_alone_never_undecided(a):
    # one transcendental constant: every sign, zero test and floor decided
    if type(a) is F:
        return
    s = a.sign()
    assert s == mp_sign(ref(a))
    assert bool(a)
    assert math.floor(a) == int(mp.floor(ref(a, 300)))


@PROP
@given(numbers)
def test_floor_ceil_against_mpmath(a):
    try:
        f, c = math.floor(a), math.ceil(a)
    except Undecided:
        return
    v = ref(a, 300)
    assert f == int(mp.floor(v)) and c == int(mp.ceil(v))


# ----------------------------------------------------------------------
# z3's real closed field (optional)
# ----------------------------------------------------------------------

def _z3():
    z3rcf = pytest.importorskip("z3.z3rcf")
    r = [x for x in z3rcf.MkRoots([-2, 0, 1]) if x > 0][0]
    c = [x for x in z3rcf.MkRoots([-3, 0, 0, 1])][0]
    return z3rcf, {"pi": z3rcf.Pi(), "E": z3rcf.E(), ("root", F(2), 2): r,
                   ("root", F(3), 3): c}


def to_z3(x, z3rcf, vals):
    def q(f):
        return z3rcf.RCFNum(f"{f.numerator}/{f.denominator}")

    def ev(p):
        if type(p) is F:
            return q(p)
        t = vals[cf._CONSTANTS[p[0]].key]
        r = q(F(0))
        for c in reversed(p[1]):
            r = r * t + ev(c)
        return r
    if type(x) is F:
        return q(x)
    return ev(x.numerator).__div__(ev(x.denominator))


def test_against_z3_rcf():
    z3rcf, vals = _z3()
    rng = random.Random(7)
    undecided = decided = 0
    for i in range(600):
        leaves = LEAVES if i % 2 else [PI, E]
        a, b = rand_expr(rng, 3, leaves), rand_expr(rng, 3, leaves)
        if a is None or b is None:
            continue
        za, zb = to_z3(a, z3rcf, vals), to_z3(b, z3rcf, vals)
        zero = za == zb
        try:
            lt, eq = a < b, a == b
        except Undecided:
            # only a real tie that is not formal, e.g. sqrt(2)**2 vs 2
            assert zero, (a, b)
            undecided += 1
            continue
        decided += 1
        assert eq == zero and lt == (za < zb), (a, b)
    assert decided > 300


def test_z3_agrees_on_the_undecided_zero():
    z3rcf, vals = _z3()
    z = SQRT2 * SQRT2 - 2
    assert to_z3(z, z3rcf, vals) == 0          # zero indeed; we say Undecided
    with pytest.raises(Undecided):
        z.sign()


def test_against_z3_rcf_hidden_zeros_and_near_ties():
    z3rcf, vals = _z3()
    rng = random.Random(11)
    hidden = near = 0
    for i in range(200):
        a = rand_expr(rng, 2)
        if type(a) is not Element:
            continue
        # a hidden algebraic zero: a*sqrt(2)**2 against 2*a
        b, c = a * SQRT2 * SQRT2, 2 * a
        assert to_z3(b, z3rcf, vals) == to_z3(c, z3rcf, vals)
        with pytest.raises(Undecided):
            b == c
        hidden += 1
        # near ties: a against a + 10**-k
        for k in (5, 40, 300, 1000):
            d = a + F(1, 10 ** k)
            assert a < d and d > a and a != d and not (d <= a)
            near += 1
    assert hidden > 50 and near > 200


def test_formally_zero_never_raises():
    z = SQRT2 * SQRT2 - 2
    assert not cf.formally_zero(z) and cf.formally_zero(F(0)) and cf.formally_zero(0)
    assert not cf.formally_zero(PI) and not cf.formally_zero(F(1))
    assert not issubclass(Undecided, ArithmeticError)
