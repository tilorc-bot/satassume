"""Battery differences from v3 that are reviewed and accepted (the scoreboard's "accepted").

A battery case whose result is not v3's (other form, miss, or fired where v3
expects unchanged) is *accepted* when it is listed here with the same result:
our result is as good as v3's or better, or v3's expectation is questionable.
Every other difference is an *open gap*, and the scoreboard prints open gaps
separately from accepted ones.  An entry whose case no longer comes out this
way (the result changed, or it now agrees with v3) is *stale* and is printed
too, so this list is kept current.

``Accepted(kind, source, case, got, reason, modes)``:

* ``kind``: ``other``, ``miss`` or ``extra`` (``lib.battery.SHORT``);
* ``source``: the battery case's source (test id);
* ``case``: ``"<expr> | <assumptions>"``, as ``str`` prints them;
* ``got``: our result, as ``str`` prints it (for a miss, the input);
* ``reason``: why it is accepted;
* ``modes``: the ``SATREFINE_IDENTITIES`` modes it applies to (a case that
  differs in one mode only).

Reviewed 2026-09-26 (phase 3, track D rows); every "extra" is checked
numerically by the scoreboard (it counts any that is not).
"""
from __future__ import annotations

from typing import NamedTuple


class Accepted(NamedTuple):
    kind: str
    source: str
    case: str
    got: str
    reason: str
    modes: tuple = ("generated", "live")


_H = "test_hyperbolic.py::"
_HVAL = "exact value; v3 leaves it as I*sin/I*tan/... of pi*k, which is the same number"
_HPER = ("exact: sinh/cosh/sech/csch(x + I*pi*k) = (-1)**k*f(x) for integer k (the half period for odd k); "
         "v3 declines without the parity of k")
_HPER_FORM = _HPER + "; the exponent k/2 + 3/2 reads awkwardly but is right"

ACCEPTED: list[Accepted] = [
    # --- hyperbolic: exact evaluations and periods v3 does not do (ours better) ---
    *[Accepted("extra", _H + f"test_period_integer_sign_unknown_unchanged[{f}]",
               f"{f}(I*pi*k + x) | Q.integer(k)", f"(-1)**k*{f}(x)", _HPER) for f in ("sinh", "cosh", "sech", "csch")],
    Accepted("extra", _H + "test_half_period_odd_only_sign_unknown_unchanged[sinh]",
             "sinh(I*pi*k/2 + x) | Q.odd(k)", "(-1)**(k/2 + 3/2)*I*cosh(x)", _HPER_FORM),
    Accepted("extra", _H + "test_half_period_odd_only_sign_unknown_unchanged[cosh]",
             "cosh(I*pi*k/2 + x) | Q.odd(k)", "(-1)**(k/2 + 3/2)*I*sinh(x)", _HPER_FORM),
    Accepted("extra", _H + "test_half_period_odd_only_sign_unknown_unchanged[sech]",
             "sech(I*pi*k/2 + x) | Q.odd(k)", "-(-1)**(k/2 + 3/2)*I*csch(x)", _HPER_FORM),
    Accepted("extra", _H + "test_half_period_odd_only_sign_unknown_unchanged[csch]",
             "csch(I*pi*k/2 + x) | Q.odd(k)", "-(-1)**(k/2 + 3/2)*I*sech(x)", _HPER_FORM),
    *[Accepted("extra", _H + f"test_no_pole_off_the_point[{f}]", f"{f}(I*pi*k + x) | Q.integer(k)",
               f"(-1)**k*{f}(x)", _HPER) for f in ("sinh", "cosh", "sech", "csch")],
    Accepted("extra", _H + "test_no_pole_off_the_point[sinh]", "sinh(I*pi*k/2 + x) | Q.odd(k)",
             "(-1)**(k/2 + 3/2)*I*cosh(x)", _HPER_FORM),
    Accepted("extra", _H + "test_no_pole_off_the_point[cosh]", "cosh(I*pi*k/2 + x) | Q.odd(k)",
             "(-1)**(k/2 + 3/2)*I*sinh(x)", _HPER_FORM),
    Accepted("extra", _H + "test_no_pole_off_the_point[sech]", "sech(I*pi*k/2 + x) | Q.odd(k)",
             "-(-1)**(k/2 + 3/2)*I*csch(x)", _HPER_FORM),
    Accepted("extra", _H + "test_no_pole_off_the_point[csch]", "csch(I*pi*k/2 + x) | Q.odd(k)",
             "-(-1)**(k/2 + 3/2)*I*sech(x)", _HPER_FORM),
    *[Accepted("other", _H + f"test_values_at_multiples_of_pi_i[{tid}]", f"{f}(I*pi*k) | Q.{p}(k)", got, _HVAL)
      for tid, f, p, got in [
          ("sinh-0-0", "sinh", "even", "0"), ("sinh-0-0", "sinh", "odd", "0"),
          ("tanh-0-0", "tanh", "even", "0"), ("tanh-0-0", "tanh", "odd", "0"),
          ("coth-even3-odd3", "coth", "even", "zoo"), ("coth-even3-odd3", "coth", "odd", "zoo"),
          ("sech-1--1", "sech", "even", "1"), ("sech-1--1", "sech", "odd", "-1"),
          ("csch-even5-odd5", "csch", "even", "zoo"), ("csch-even5-odd5", "csch", "odd", "zoo")]],
    *[Accepted("other", _H + f"test_values_at_integer_multiples_of_pi_i[{f}-expected{i}]", f"{f}(I*pi*k) | Q.integer(k)",
               got, _HVAL + ("; (-1)**(-k) is (-1)**k" if f == "sech" else ""))
      for f, i, got in [("sinh", 0, "0"), ("tanh", 2, "0"), ("coth", 3, "zoo"), ("sech", 4, "(-1)**(-k)"),
                        ("csch", 5, "zoo")]],
    *[Accepted("other", _H + f"test_values_at_odd_multiples_of_half_pi_i[{tid}]",
               f"{f}(I*pi*(k/2)) | Q.odd(k) & Q.{p}(k/2 - 1/2)", got, _HVAL)
      for tid, f, p, got in [
          ("sinh-v10-v30", "sinh", "even", "I"), ("sinh-v10-v30", "sinh", "odd", "-I"),
          ("tanh-v12-v32", "tanh", "even", "zoo"), ("tanh-v12-v32", "tanh", "odd", "zoo"),
          ("coth-0-0", "coth", "even", "0"), ("coth-0-0", "coth", "odd", "0"),
          ("sech-v14-v34", "sech", "even", "zoo"), ("sech-v14-v34", "sech", "odd", "zoo"),
          ("csch-v15-v35", "csch", "even", "-I"), ("csch-v15-v35", "csch", "odd", "I")]],
    *[Accepted("other", _H + f"test_values_at_odd_only[{f}-expected{i}]", f"{f}(I*pi*(k/2)) | Q.odd(k)", got, _HVAL)
      for f, i, got in [("tanh", 1, "zoo"), ("coth", 2, "0"), ("sech", 3, "zoo")]],
    Accepted("other", _H + "test_values_at_odd_only_sign_unknown[sinh]", "sinh(I*pi*(k/2)) | Q.odd(k)",
             "(-1)**(k/2 + 3/2)*I", _HVAL + "; the exponent k/2 + 3/2 reads awkwardly"),
    Accepted("other", _H + "test_values_at_odd_only_sign_unknown[csch]", "csch(I*pi*(k/2)) | Q.odd(k)",
             "-(-1)**(1/2 - k/2)*I", _HVAL + "; the exponent 1/2 - k/2 reads awkwardly"),

    # --- inverse: interval rules v3 does not have (ours better) ---
    Accepted("extra", "test_inverse.py::test_acos_cos_needs_the_real_interval",
             "acos(cos(x)) | Q.ge(x, -pi/2) & Q.le(x, pi/2)", "Abs(x)", "exact: acos(cos x) = |x| on [-pi, pi]"),
    Accepted("extra", "test_inverse.py::test_acos_cos_needs_the_real_interval",
             "acos(sin(x)) | Q.ge(x, 0) & Q.le(x, pi)", "Abs(x - pi/2)",
             "exact: acos(sin x) = |x - pi/2| on [-pi/2, 3*pi/2]"),
    Accepted("extra", "test_inverse.py::test_bounds_spanning_more_than_one_branch_do_not_fire",
             "acos(cos(x)) | Q.le(x, pi) & Q.ge(x, -pi)", "Abs(x)",
             "exact: acos(cos x) = |x| on [-pi, pi] (one branch of acos(cos) with |.|; v3 splits it in two)"),
    Accepted("extra", "test_inverse.py::test_bounds_spanning_more_than_one_branch_do_not_fire",
             "acos(sin(x)) | Q.nonnegative(x) & Q.le(x, pi)", "Abs(x - pi/2)",
             "exact: acos(sin x) = |x - pi/2| on [-pi/2, 3*pi/2]"),
    Accepted("extra", "test_inverse.py::test_bounds_spanning_more_than_one_branch_do_not_fire",
             "asin(cos(x)) | Q.ge(x, pi) & Q.le(x, 2*pi)", "x - 3*pi/2",
             "exact: cos x = sin(x - 3*pi/2) and x - 3*pi/2 is in [-pi/2, pi/2]"),
    Accepted("extra", "test_inverse.py::test_bounds_spanning_more_than_one_branch_do_not_fire",
             "atan(cot(x)) | Q.gt(x, pi) & Q.lt(x, 2*pi)", "-x + 3*pi/2",
             "exact: cot x = tan(3*pi/2 - x) and 3*pi/2 - x is in (-pi/2, pi/2)"),
    Accepted("other", "test_inverse.py::test_even_inverse_by_sign[acosh-cosh]", "acosh(cosh(x)) | Q.zero(x)", "0",
             "same value: x is 0"),
    Accepted("other", "test_inverse.py::test_even_inverse_by_sign[asech-sech]", "asech(sech(x)) | Q.zero(x)", "0",
             "same value: x is 0"),

    # --- power_exp_log ---
    Accepted("extra", "test_power_exp_log.py::TestExp::test_unchanged", "exp(I*pi*n/2 + x) | Q.odd(n)",
             "(-1)**(n/2 + 3/2)*I*exp(x)", "exact: exp(I*pi*n/2) = I*(-1)**((n - 1)/2) for odd n; awkward exponent"),
    Accepted("other", "test_power_exp_log.py::TestLogOfPower::test_reciprocal", "log(1/x) | Q.zero(x)", "zoo",
             "same value: log(1/0) = log(zoo) = zoo = -log(0)"),
    Accepted("extra", "test_power_exp_log.py::TestLogOfPower::test_reciprocal_unchanged_for_infinite_argument",
             "log(1/x) | Q.infinite(x)", "zoo", "exact: 1/x is 0 for an infinite x, and log(0) is zoo"),
    Accepted("extra", "test_power_exp_log.py::TestLogOfProduct::test_unchanged", "log(2*x) | True", "log(x) + log(2)",
             "exact: a positive constant factor leaves arg unchanged (log(2*0) = zoo = log(0) + log(2))"),

    # --- complex_parts ---
    Accepted("other", "test_complex_parts.py::test_abs_product_splits_only_known_sign_factors", "Abs(x*y) | Q.zero(y)",
             "y*Abs(x)", "exact also for an infinite x (0*oo is nan on both sides); v3's 0 (and live mode's) is not",
             ("generated",)),
    *[Accepted("other", "test_complex_parts.py::test_abs_and_reim_of_literal_negative_power_with_nonzero_base", case,
               got, "exact for real x (x = 0: zoo on both sides); simpler than v3's form")
      for case, got in [("Abs(x**(-2)) | Q.nonzero(x) & Q.real(x)", "x**(-2)"), ("Abs(x**(-2)) | Q.real(x)", "x**(-2)"),
                        ("Abs(x**(-2)) | Q.real(x) & ~Q.zero(x)", "x**(-2)"),
                        ("re(x**(-3)) | Q.real(x) & ~Q.zero(x)", "x**(-3)"), ("re(x**(-3)) | Q.real(x)", "x**(-3)")]],
    Accepted("extra", "test_complex_parts.py::test_arg_scalar", "arg(x) | Q.zero(x)", "nan",
             "SymPy's arg(0) is nan (the zero row); v3 declines"),
    Accepted("extra", "test_complex_parts.py::test_arg_product_drops_positive_factors", "arg(x*y) | Q.negative(y)",
             "arg(-x)", "exact: arg(x*y) = arg(-x*|y|) = arg(-x) for y < 0"),
    Accepted("other", "test_complex_parts.py::test_conjugate_of_sums_and_products", "conjugate(x + y) | Q.real(y)",
             "y + conjugate(x)", "simpler: conjugate(y) = y for a real y"),
    Accepted("other", "test_complex_parts.py::test_conjugate_of_sums_and_products", "conjugate(x*y) | Q.real(x)",
             "x*conjugate(y)", "simpler: conjugate(x) = x for a real x"),

    # --- integer_funcs, minmax_deltas ---
    Accepted("extra", "test_integer_funcs.py::test_floor_of_infinite_is_not_a_gaussian_integer",
             "floor(x + floor(y)) | True", "floor(x) + floor(y)",
             "exact: floor(y) is a Gaussian integer or infinite, and an integer term leaves floor; "
             "numerically checked incl. infinite points"),
    Accepted("extra", "test_minmax_deltas.py::test_minmax_unknown_order_unchanged", "Max(x, y) | Q.positive_infinite(x)",
             "x", "exact: oo is the maximum of the extended reals"),

    # --- combinatorial: v3 questionable (wrong at infinity) ---
    Accepted("miss", "test_combinatorial.py::test_binomial_k_equals_n", "binomial(n, n) | ~Q.integer(n)", "binomial(n, n)",
             "v3 questionable: ~integer allows an infinite n, where binomial(oo, oo) is not 1"),
    Accepted("miss", "test_combinatorial.py::test_binomial_k_equals_n_minus_one", "binomial(n, n - 1) | ~Q.integer(n)",
             "binomial(n, n - 1)", "v3 questionable: ~integer allows an infinite n, where binomial(n, n - 1) is not n"),
    Accepted("miss", "test_combinatorial.py::test_rf_gamma_positive_x", "RisingFactorial(x, k) | ~Q.integer(x)",
             "RisingFactorial(x, k)", "v3 questionable: gamma(k + x)/gamma(x) is wrong when k + x is a pole or at infinity"),
]


def key(kind: str, source: str, case: str, got: str) -> tuple:
    return (kind, source, case, got)


def table(mode: str) -> dict[tuple, Accepted]:
    """The entries that apply in ``mode``, by :func:`key`."""
    return {key(a.kind, a.source, a.case, a.got): a for a in ACCEPTED if mode in a.modes}
