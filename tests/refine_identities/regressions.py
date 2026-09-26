"""Per-bug regressions: one row per ``refine`` input that once went wrong.

Run by ``test_regressions.py`` in both identity modes (``generated`` and
``live``) and under each backend in ``backends`` (``None``: the one
``SATREFINE_BACKEND`` selects, ``combined`` by default).

A row is ``Case(expr, assumptions, expected, bug, reason, backends=None)``:

``expected``
    a SymPy object (``refine`` returns it, compared with ``==``), or one of
    :data:`UNCHANGED` (``refine`` returns ``expr``), :data:`NO_CRASH`
    (``refine`` returns), :class:`OneOf` (one of the given results; use
    :data:`UNCHANGED` among them for the input), :class:`SameValueAt` (the
    result equals the input at the given point, the bug was a wrong value
    there), :class:`AfterDoit` (``result.doit()`` is the given object).
``bug``
    where the bug is recorded: ``#10 B1`` (issue #10's list), ``default``
    (found by making ``handlers_identities`` the default, phase 3; see
    ``agent-reports/2026-09-25-phase3-default-report.md``), ``matfixes``
    (the matrix differential, phase 3), ``checker``/``engine`` (phase 2
    requests), ``diff`` (a differential or fuzz finding).
``reason``
    what went wrong, in a few words.

Tests that check more than a ``refine`` result (engine internals, the guard,
oracles, numeric sweeps) are test functions in the subdirectory of the module
they test.  Each group below names the test file it came from (in
``tests/refine_identities/`` before #13 step 5); the longer explanations are in
that file's history (``git log -- tests/refine_identities/<file>``).
"""
from __future__ import annotations

from typing import Any, NamedTuple

from sympy import (Abs, Add, Eq, HadamardProduct, I, Identity, KroneckerDelta, MatAdd, MatMul, MatrixSymbol, Max,
                   Min, Ne, Piecewise, Q, Rem, RisingFactorial, S, Symbol, acot, acoth, acsch, arg, atan2, ceiling,
                   conjugate, cos, cosh, csc, csch, exp, factorial, floor, gamma, log, nan, oo, pi, sec, sech, sign,
                   sin, sinh, sqrt, symbols, zoo, ZeroMatrix)


class _Unchanged:
    def __repr__(self) -> str:
        return "UNCHANGED"


class _NoCrash:
    def __repr__(self) -> str:
        return "NO_CRASH"


UNCHANGED = _Unchanged()
NO_CRASH = _NoCrash()


class OneOf(tuple):
    """Any of these results (``UNCHANGED`` stands for the input)."""
    def __new__(cls, *options: Any) -> "OneOf":
        return super().__new__(cls, options)


class SameValueAt(dict):
    """The result and the input agree after ``subs(point)``."""


class AfterDoit(tuple):
    """``result.doit()`` is ``AfterDoit(value)[0]``."""
    def __new__(cls, value: Any) -> "AfterDoit":
        return super().__new__(cls, (value,))


class Case(NamedTuple):
    expr: Any
    assumptions: Any
    expected: Any
    bug: str
    reason: str
    backends: tuple | None = None


def holds(case: Case, result: Any) -> bool:
    """Whether ``result`` is what ``case.expected`` asks for."""
    expected, expr = case.expected, case.expr
    if expected is UNCHANGED:
        return result == expr
    if expected is NO_CRASH:
        return True
    if isinstance(expected, OneOf):
        return any(result == (expr if option is UNCHANGED else option) for option in expected)
    if isinstance(expected, SameValueAt):
        return result.subs(expected) == expr.subs(expected)
    if isinstance(expected, AfterDoit):
        return result.doit() == expected[0]
    return result == expected


x, y, z, n, m, k, p, q = symbols("x y z n m k p q")
X = MatrixSymbol("X", 2, 2)
Y = MatrixSymbol("Y", 2, 2)
X3 = MatrixSymbol("X", 3, 3)
A3 = MatrixSymbol("A", 3, 3)
x3 = MatrixSymbol("x", 3, 3)
ip, jp = Symbol("i", positive=True), Symbol("j", positive=True)
i, j = Symbol("i"), Symbol("j")
ALL_BACKENDS = ("sympy", "satassume", "combined")

CASES: list[Case] = []


def _add(bug: str, reason: str, rows: list, backends: tuple | None = None) -> None:
    CASES.extend(Case(*row, bug=bug, reason=reason, backends=backends) for row in rows)


# --- core: bounds on the extended reals (from test_engine_bounds_infinity.py) ---------------------
# A one-sided bound holds at x = oo: it proves extended signs, not finite ones.
_add("#10 B1", "x < oo read as provable from x > 1", [
    (Piecewise((0, x < oo), (1, True)), Q.gt(x, 1), UNCHANGED),
    (Piecewise((0, x < oo), (1, True)), Q.ge(x, oo), UNCHANGED),
])
_add("#10 B2", "Eq(oo, 2*oo) is True; the bound made x finite", [
    (Piecewise((0, Eq(x, 2*x)), (1, True)), Q.gt(x, 1), UNCHANGED),
    (Piecewise((0, Ne(x, 2*x)), (1, True)), Q.gt(x, 1), UNCHANGED),
])
_add("#10 B3", "KroneckerDelta with both indices infinite", [
    (KroneckerDelta(x, 2*x), Q.gt(x, 1), UNCHANGED),
    (KroneckerDelta(x, 3*x + 1), Q.lt(x, -1), UNCHANGED),
    (KroneckerDelta(x + 1, 2*x), Q.lt(x, -1), UNCHANGED),
])
_add("#10 B4", "sign(exp(-oo)) = 0", [
    (sign(exp(-x)), Q.gt(x, 1), UNCHANGED),
    (sign(exp(x)), Q.lt(x, -1), UNCHANGED),
    (sign(exp(x)), Q.ge(x, -oo) & Q.le(x, -5), UNCHANGED),
])
_add("#10 B5", "log(1) vs 0*oo at x = oo, n = 0", [
    (log(x**n), Q.gt(x, 1) & Q.real(n), UNCHANGED),
])
_add("#10 B6", "acsch(csch(oo)) = acsch(0) = zoo", [
    (acsch(csch(x)), Q.gt(x, 1), UNCHANGED),
    (acsch(csch(x)), Q.lt(x, -1), UNCHANGED),
])
_add("#10 B7", "RisingFactorial: oo vs nan at y = 1", [
    (RisingFactorial(x, y), Q.gt(x, 1), UNCHANGED),
])
_add("#10 B1-B7", "the same rewrites still fire where x is finite", [
    (log(x**n), Q.positive(x - 1) & Q.real(n), n*log(x)),             # a sign fact makes x finite
    (log(x**n), Q.gt(x, 1) & Q.lt(x, 5) & Q.real(n), n*log(x)),       # bounds on both sides
    (log(x**n), Q.gt(x, 1) & Q.finite(x) & Q.real(n), n*log(x)),      # ask proves x finite
    (log(x**n), Q.gt(x, 1) & Q.real(x) & Q.real(n), n*log(x)),
    (sign(exp(-x)), Q.gt(x, 1) & Q.real(x), 1),
    (acsch(csch(x)), Q.gt(x, 1) & Q.lt(x, 3), x),
    (KroneckerDelta(x, 2*x), Q.gt(x, 1) & Q.finite(x), 0),
    (Piecewise((0, x < oo), (1, True)), Q.gt(x, 1) & Q.finite(x), 0),
    (Piecewise((0, Eq(x, 2*x)), (1, True)), Q.gt(x, 1) & Q.lt(x, 2), 1),
    (RisingFactorial(x, y), Q.positive(x - 1), gamma(x + y)/gamma(x)),
    (Abs(x), Q.gt(x, 1) & Q.real(x), x),
])

# --- core: the firing cap and the result cache ----------------------------------------------------
# from test_engine_firing_cap_on_wide_input.py
_add("checker: firing cap", "the cap counted independent firings: 501 terms raised RefineLoopError", [
    (Add(*[Abs(x + t) for t in range(1, 502)]), Q.positive(x), Add(*[x + t for t in range(1, 502)])),
])
# from test_engine_conditions.py (from needs/test_checker_atan2_power_firing_cap.py)
_add("checker: atan2 firing cap", "each Piecewise branch refined n**y again until 500 firings", [
    (atan2(y, n**y + 1), Q.negative(y) & Q.nonpositive(n), UNCHANGED),
    (atan2(y, n**y), Q.negative(y) & Q.nonpositive(n), UNCHANGED),
    (atan2(sqrt(z), k**k), Q.even(z) & Q.integer(k) & Q.negative(z), UNCHANGED),   # differential seed 3
])
_add("engine: head refuses a refined child", "n**k refines to nan here and Max raised on it", [
    (Max(n**k, log(x)), Q.imaginary(n) & Q.negative(k) & Q.positive(x) & Q.gt(n, 0), UNCHANGED),
])
# from test_engine_eq_of_equal_infinities.py
_add("checker: Eq of equal infinities", "no proof of u = v for two arguments at the same infinite endpoint", [
    (Piecewise((1, Eq(x, y)), (0, True)), Q.positive_infinite(x) & Q.positive_infinite(y), 1),
    (Piecewise((1, Eq(x, y)), (0, True)), Q.negative_infinite(x) & Q.negative_infinite(y), 1),
])

# --- inconsistent assumptions: the input comes back (from test_default_inconsistent_assumptions.py) ---
# Decided in agent-reports/2026-09-26-phase3-fixes-report.md: every result is correct under
# inconsistent assumptions, and raising would depend on which question the engine asks first.
_add("default: inconsistent assumptions", "top-level refine returns its input (B9), under every backend", [
    (conjugate(x), Q.infinite(x) & Q.real(x), UNCHANGED),
    (Abs(x), Q.positive(x) & Q.negative(x), UNCHANGED),
    (gamma(n), Q.infinite(n) & Q.integer(n), UNCHANGED),
], backends=ALL_BACKENDS)

# --- rules: complex_parts (from test_default_arg_of_zero.py) -------------------------------------
_add("default: arg of zero", "arg(x) under Q.zero(x) stayed arg(x); arg(0) is nan", [
    (arg(x), Q.zero(x), nan),
])

# --- rules: integer_funcs -------------------------------------------------------------------------
# from test_default_floor_ceiling.py: SymPy's test_floor_ceiling; floor(+-oo), floor(zoo) are the argument
_add("default: floor/ceiling", "floor/ceiling of an infinite argument, of a sum of floors", [
    (floor(x), Q.infinite(x), x),
    (ceiling(x), Q.infinite(x), x),
    (ceiling(ceiling(x) + y + floor(z)), True, ceiling(x) + ceiling(y) + floor(z)),
    (floor(floor(x) + floor(y)), True, floor(x) + floor(y)),
    (ceiling(ceiling(x) - ceiling(y)), True, ceiling(x) - ceiling(y)),
])
# from test_default_rem_zero_dividend.py
_add("default: Rem zero dividend", "Rem(0, q) = 0 was not applied", [
    (Rem(p, q), Q.zero(p), S.Zero),
])

# --- rules: hyperbolic (from test_default_hyperbolic_i_pi_shift.py) ------------------------------
_add("default: hyperbolic i*pi shift", "f(x + n*I*pi) = (-1)**n*f(x) for integer n was missing", [
    (f(x + n*I*pi), Q.integer(n), (-1)**n*f(x)) for f in (sinh, cosh, sech, csch)
])

# --- rules: combinatorial, minmax_deltas (from test_default_infinite_arguments.py) ----------------
_add("default: infinite arguments", "factorial, Max, Min of an argument known to be oo or -oo", [
    (factorial(n), Q.positive_infinite(n), S.Infinity),
    (Max(x, y), Q.positive_infinite(x), x),
    (Max(x, y), Q.positive_infinite(y), y),
    (Max(x, y), Q.negative_infinite(x), y),
    (Max(x, y), Q.negative_infinite(y), x),
    (Min(x, y), Q.negative_infinite(x), x),
    (Min(x, y), Q.negative_infinite(y), y),
    (Min(x, y), Q.positive_infinite(x), y),
    (Min(x, y), Q.positive_infinite(y), x),
])

# --- rules: power_exp_log -------------------------------------------------------------------------
# from test_default_neg_one_power_exponent.py: SymPy's test_pow1/test_pow2
_add("default: (-1)**exponent", "the constant was reduced modulo 2 but not the result", [
    ((-1)**((-1)**x/2 - S.Half), Q.integer(x), (-1)**x),
    ((-1)**((-1)**x/2 + S.Half), Q.integer(x), (-1)**(x + 1)),
    ((-1)**((-1)**x/2 + 5*S.Half), Q.integer(x), (-1)**(x + 1)),
    ((-1)**((-1)**x/2 - 7*S.Half), Q.integer(x), (-1)**(x + 1)),
    ((-1)**((-1)**x/2 - 9*S.Half), Q.integer(x), (-1)**x),
])
# from test_default_pow_of_pow_positive_base.py (split from needs/test_default_pow_of_pow.py)
_add("default: pow of pow, positive base", "(b**a)**e -> b**(a*e) for b > 0, real a (SymPy's test_pow1)", [
    (sqrt(1/x), Q.positive(x), 1/sqrt(x)),
])
# from test_power_exp_log_zero_base.py
_add("engine: zero base", "log(1/x) under Q.zero(x) depended on the hash seed; b**e = zoo for zero b, negative e", [
    (1/x, Q.zero(x), zoo),
    (log(1/x), Q.zero(x), zoo),
])

# --- rules: trig (from test_default_odd_half_pi_sign_form.py) ------------------------------------
_add("default: odd pi/2 sign form", "a doubled sign form -(-1)**(n/2 + 3/2) instead of (-1)**((n + 1)/2)", [
    (cos(x + n*pi/2), Q.odd(n), (-1)**((n + 1)/2)*sin(x)),
    (sec(x + n*pi/2), Q.odd(n), (-1)**((n + 1)/2)*csc(x)),
    (sec(x + (2*n + 1)*pi/2), Q.integer(n), (-1)**(n + 1)*csc(x)),
    (cos(x + n*pi + m*pi/2), Q.integer(n) & Q.odd(m), (-1)**(n + (m + 1)/2)*sin(x)),
    (sec(x + n*pi + m*pi/2), Q.integer(n) & Q.odd(m), (-1)**(n + (m + 1)/2)*csc(x)),
    (cos(x + n*pi + k*pi/2 + m*pi/2), Q.integer(n) & Q.odd(k) & Q.integer(m),
     (-1)**(n + (k + 1)/2)*sin(x + m*pi/2)),
    (sin(x + n*pi + k*pi/2 + m*pi/2), Q.integer(n) & Q.odd(k) & Q.integer(m),
     (-1)**(n + (k + 3)/2)*cos(x + m*pi/2)),
    (cos(x + n*pi/2 + k*pi/2 + m*pi/2), Q.odd(n) & Q.odd(k) & Q.integer(m), (-1)**((n + k)/2)*cos(x + m*pi/2)),
])

# --- rules: inverse (from test_fuzzext_acsch_infinite.py) ---------------------------------------
# im(Abs(w)) auto-evaluates to 0, so the acsch row's _OFF_CUT_LINES admitted an infinite Abs(w).
_add("#10 B10", "acsch(csch(Abs(z))) -> Abs(z) fired where Abs(z) may be infinite (ext differential)", [
    (acsch(csch(Abs(z))), Q.infinite(z), UNCHANGED),
    (acsch(csch(Abs(z))), Q.extended_negative(z) & Q.infinite(z), UNCHANGED),
    (acsch(csch(Abs(n))), Q.gt(n, 0), UNCHANGED),
], backends=("satassume", "combined"))
_add("#10 B10", "the finite case still fires", [
    (acsch(csch(Abs(n))), Q.gt(n, 0) & Q.finite(n), OneOf(n, Abs(n))),
])

# --- compat: rebuilding acot/acoth (from test_bounds_acot_rebuild.py) ---------------------------
# SymPy's eval pulls the sign out of a refined argument (acot(-z) -> -acot(z)), wrong at z = 0.
_add("#10 B8", "acot/acoth of a rewritten -z changed its value at z = 0", [
    (acoth(sqrt(z**2)), Q.nonpositive(z), SameValueAt({z: 0})),
    (acoth(Abs(z)), Q.nonpositive(z), SameValueAt({z: 0})),
    (acot(Abs(z)), Q.nonpositive(z), SameValueAt({z: 0})),
    (acot(sqrt(z**2)), Q.nonpositive(z), SameValueAt({z: 0})),
    (acot(Max(z, -z)), Q.nonpositive(z), SameValueAt({z: 0})),
    (acot(Min(z, -z)), Q.nonnegative(z), SameValueAt({z: 0})),
    (acoth(I*Abs(z)), Q.nonpositive(z), SameValueAt({z: 0})),   # SymPy builds -I*acot(Abs(z)); was I*acot(z)
])
_add("#10 B8", "the sign still comes out when the argument is nonzero", [
    (acot(Abs(z)), Q.negative(z), -acot(z)),
    (acoth(Abs(z)), Q.negative(z), -acoth(z)),
])

# --- compat: matrices -----------------------------------------------------------------------------
# from test_matrices_hadamard_duplicate.py: HadamardProduct() of no arguments raised ValueError
_add("matfixes: Hadamard of a repeated atom", "binding one copy left an empty rest (matrix differential seed 2)", [
    (HadamardProduct(X, X), Q.diagonal(X), UNCHANGED),
    (HadamardProduct(X, X), Q.orthogonal(X), UNCHANGED),
    (HadamardProduct(X, X), Q.singular(X), UNCHANGED),
    (HadamardProduct(X, X), Q.orthogonal(X) & Q.symmetric(X), UNCHANGED),
    (HadamardProduct(X, X), Q.zero(X), OneOf(ZeroMatrix(2, 2), UNCHANGED)),
])
# from test_matrices_matadd_single_term.py
_add("default: one-term MatAdd", "TypeError: GenericZeroMatrix does not have a specified shape", [
    (MatAdd(X), True, MatAdd(X)),
    (MatAdd(X), Q.zero(X), ZeroMatrix(2, 2)),
])
# from test_matrices_matmul_scalar_factor.py
_add("default: scalar in a MatMul", "a scalar between factors blocked cancellation and stayed in place", [
    (MatMul(X.T, 2, X), Q.orthogonal(X), AfterDoit(2*Identity(2))),
    (MatMul(X, 2, Y), True, 2*X*Y),
])
# from test_matrices_matrixelement_index_order.py (the Q.ne(i, j) case is in needs/)
_add("default: MatrixElement index order", "the symmetric/diagonal swap kept the index order (SymPy's test_matrixelement)", [
    (x3[ip, jp], Q.symmetric(x3), x3[jp, ip]),
    (A3[i, j], Q.diagonal(A3), A3[j, i]),
    (A3[i, 0], Q.diagonal(A3), A3[0, i]),
    (x3[jp, ip], Q.symmetric(x3), x3[jp, ip]),
    (A3[i, 2*i], Q.diagonal(A3), A3[i, 2*i]),
    (A3[0, i], Q.diagonal(A3), A3[0, i]),
])
# from test_engine_matrixelement_bounds.py (matrix fuzz, seed 1)
_add("diff: MatrixElement bounds", "the bounds put a scalar in place of a matrix: TypeError from MatrixElement", [
    (conjugate(X3[-1, -2]), Q.symmetric(X3) & Q.unitary(X3), NO_CRASH),
    (conjugate(X[i, 0])*X[i, 0] + conjugate(X[i, 1])*X[i, 1],
     Q.integer(i) & Q.nonnegative(i) & Q.orthogonal(X) & Q.symmetric(X), NO_CRASH),
])
