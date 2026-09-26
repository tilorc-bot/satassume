"""Refine handlers for the complex-part functions ``re``, ``im``, ``arg``,
``sign``, ``Abs`` and ``conjugate``, plus the conjugate-pair rule for
``Mul``.

Every rule below is an identity of complex arithmetic under the stated
precondition; nothing here relies on a symbol's own (old-style) assumptions,
only on answers of ``_upstream.ask`` for the ``assumptions`` argument.  A
rule that could not be proved for all finite values satisfying its
precondition, including ``0``, negative reals and the imaginary axis, was
left out (see the end of this docstring).  Every handler returns ``None``
when no rule applies and never rebuilds an expression that re-enters the
same handler unchanged.

Notation: ``a`` is the argument of the function, ``R`` a product of factors
proved real, ``P`` a product of factors proved positive.

``Abs(a)``
    * ``Q.zero(a)`` -> ``0``.
    * ``Q.nonnegative(a)`` or ``Q.positive(a)``, or ``Q.real(a)`` with
      ``Q.negative(a)`` refuted -> ``a``.
    * ``Q.nonpositive(a)`` or ``Q.negative(a)``, or ``Q.real(a)`` with
      ``Q.positive(a)`` refuted -> ``-a``.
    * ``Q.imaginary(a)`` with ``Q.positive(im(a))`` (also accepted in the
      form ``Q.positive(-I*a)``) -> ``-I*a``; with ``Q.negative(im(a))``
      -> ``I*a``.
    * ``Abs(exp(w))`` -> ``exp(re(w))`` (unconditional; ``re`` then refines).
    * ``Abs(conjugate(w))`` -> ``Abs(w)`` (unconditional).
    * ``Abs(b**e)``: with ``Q.real(b)``, ``e`` even -> ``b**e``; with
      ``Q.real(b)``, ``e`` integer -> ``Abs(b)**e``; with ``Q.real(e)`` (a
      literal ``2`` counts) and any ``b`` -> ``Abs(b)**e``, since
      ``|b**e| = |b|**e`` on the principal branch for every complex ``b``.
      Each of these also needs ``Q.nonnegative(e)`` (a literal or by asking)
      or ``~Q.zero(b)``, because ``Abs(0**e)`` is ``oo`` while ``Abs(0)**e``
      is ``zoo`` for negative ``e``.
    * ``Abs(f1*f2*...)`` (commutative) -> the factors whose ``Abs`` one of
      the rules above resolves are pulled out; the others stay under a
      single ``Abs``.  ``|xy| = |x||y|`` always, so the only precondition
      is that at least one factor resolves (otherwise the product is left
      alone).  ``Abs(I*x) -> Abs(x)`` is a special case (``Abs(I) = 1``).

``re(a)`` / ``im(a)``
    * ``Q.zero(a)`` -> ``0`` / ``0``; ``Q.real(a)`` -> ``a`` / ``0``;
      ``Q.imaginary(a)`` -> ``0`` / ``-I*a``.
    * ``re(conjugate(w))`` -> ``re(w)``, ``im(conjugate(w))`` -> ``-im(w)``.
    * ``re(exp(w))`` -> ``exp(re(w))*cos(im(w))``,
      ``im(exp(w))`` -> ``exp(re(w))*sin(im(w))`` (unconditional).
    * ``re(b**n)`` -> ``b**n``, ``im(b**n)`` -> ``0`` for ``Q.real(b)`` and
      integer ``n`` with ``Q.nonnegative(n)`` or ``~Q.zero(b)`` (``0**n`` is
      ``zoo`` for negative ``n``, whose parts are ``nan``).
    * sums split linearly (always valid).
    * products: every factor proved real is pulled out; every factor ``f``
      proved imaginary is pulled out as the real number ``-I*f`` and the
      ``I`` moves into the remaining product.  Fires only if at least one
      factor moved.
    * ``re(x**z)`` with ``Q.real(x) & Q.imaginary(z)`` falls through to
      ``None``: this handler never calls ``expand(complex=True)``, which is
      what makes the vendored handler recurse without bound.

``arg(a)``
    * ``Q.positive(a)`` -> ``0``; ``Q.negative(a)`` -> ``pi``.
    * ``Q.imaginary(a)`` with ``im(a)`` positive / negative -> ``pi/2`` /
      ``-pi/2``.
    * ``arg(P*w)`` -> ``arg(w)`` for factors ``P`` proved positive (a
      positive factor never moves the argument; ``0`` gives ``nan`` on both
      sides).  Negative or imaginary factors are NOT pulled out: ``arg(-w)``
      is ``arg(w) +- pi`` depending on the branch.
    * ``arg(exp(w))`` with ``w = r + I*t``, each summand proved real or
      imaginary, ``t`` therefore real: ``0`` when ``t == 0``; ``t`` when
      ``Q.positive(t + pi)`` and ``Q.nonpositive(t - pi)`` hold (a literal
      ``t`` is compared directly), i.e. ``t`` in ``(-pi, pi]``.  Without the
      range nothing fires: ``arg(exp(3*pi*I))`` is ``pi``, not ``3*pi``.
    * ``arg(conjugate(w))`` -> ``-arg(w)`` when ``~Q.extended_negative(w)``,
      ``Q.positive(re(w))``, ``Q.nonnegative(re(w))`` or ``~Q.zero(im(w))``
      holds: on the negative real axis both sides are ``pi`` (and ``-oo`` is
      why ``extended_negative`` is asked, not ``negative``).

``sign(a)``
    * ``Q.zero(a)`` -> ``0``; ``Q.positive(a)`` -> ``1``;
      ``Q.negative(a)`` -> ``-1``.
    * ``Q.imaginary(a)`` with ``im(a)`` positive / negative -> ``I`` / ``-I``.
    * ``sign(Abs(w))`` -> ``1`` for ``~Q.zero(w)`` (asked as ``~Q.zero``,
      not ``Q.nonzero``, which in SymPy implies real).
    * ``sign(exp(w))`` -> ``1`` for ``Q.real(w)``.
    * ``sign(f1*f2*...)`` (commutative): ``sign`` is multiplicative on the
      complex numbers, so factors whose sign one of the rules above
      resolves are pulled out; fires only if at least one factor resolves.

``conjugate(a)``
    * ``Q.zero(a)`` -> ``0``; ``Q.real(a)`` -> ``a``; ``Q.imaginary(a)``
      -> ``-a``; also ``a`` when ``a`` is an ``Abs``, ``re``, ``im`` or
      ``arg`` (real by construction).
    * ``conjugate(exp(w))`` -> ``exp(conjugate(w))`` (unconditional).
    * ``conjugate(b**e)`` -> ``conjugate(b)**e`` for integer ``e``;
      -> ``b**conjugate(e)`` for ``Q.positive(b)``.  Non-integer exponents
      with a general base are left alone (branch cut on the negative axis).
    * sums and commutative products split termwise / factorwise, but only
      when at least one term's ``conjugate`` resolves to something
      conjugate-free by the rules above.

``Mul``
    * ``w**e * conjugate(w)**e`` -> ``Abs(w)**(2*e)`` for integer ``e``
      (literal or ``Q.integer``), and ``w**m * conjugate(w)**n`` with literal
      integers ``m, n`` of the same sign -> ``Abs(w)**(2*k)`` times the
      leftover power, ``k = min(|m|, |n|)`` with that sign.  Only for
      commutative products; every other factor is left untouched and no
      other product rewriting is done.

Deliberately not implemented: ``Abs(x + y)`` (no identity), ``arg`` of a
product with negative/imaginary factors and ``arg(w**e)`` (branch cuts),
``arg(exp(I*t))`` without the range of ``t``, ``sign(w**e)``,
``conjugate(w**e)`` for non-integer ``e`` and general ``w``, ``Abs(x)**2 ->
x**2`` for merely complex ``x``, and ``re``/``im`` of powers with a
non-real base (would need ``expand(complex=True)``, the source of the
upstream recursion).
"""
from __future__ import annotations

from typing import Any

from sympy import Add, Mul, S
from sympy.assumptions import Q
from sympy.core.basic import Basic
from sympy.core.expr import Expr
from sympy.core.numbers import ImaginaryUnit
from sympy.functions.elementary.complexes import Abs, arg, conjugate, im, re, sign
from sympy.functions.elementary.exponential import exp
from sympy.functions.elementary.trigonometric import cos, sin

from ...identities.compat import upstream as _upstream
from ...identities.compat.upstream import handlers_dict
from ._common import is_integer, parity

I = S.ImaginaryUnit
pi = S.Pi


# --------------------------------------------------------------------------
# asking helpers
# --------------------------------------------------------------------------

def _true(proposition: Basic, assumptions: Any) -> bool:
    """``True`` only when the backend proves ``proposition``."""
    return _upstream.ask(proposition, assumptions) is True


def _false(proposition: Basic, assumptions: Any) -> bool:
    """``True`` only when the backend refutes ``proposition``."""
    return _upstream.ask(proposition, assumptions) is False


def _is_real(a: Expr, assumptions: Any) -> bool:
    return _true(Q.real(a), assumptions)


def _is_imaginary(a: Expr, assumptions: Any) -> bool:
    return _true(Q.imaginary(a), assumptions)


def _is_nonzero(a: Expr, assumptions: Any) -> bool:
    """``a != 0`` in the complex sense (``Q.nonzero`` would imply real)."""
    return _true(~Q.zero(a), assumptions) or _true(Q.nonzero(a), assumptions)


def _is_nonnegative(a: Expr, assumptions: Any) -> bool:
    if a.is_Number:
        return bool(a.is_nonnegative)
    return (_true(Q.nonnegative(a), assumptions) or _true(Q.positive(a), assumptions)
            or (_is_real(a, assumptions) and _false(Q.negative(a), assumptions)))


def _is_nonpositive(a: Expr, assumptions: Any) -> bool:
    if a.is_Number:
        return bool(a.is_nonpositive)
    return (_true(Q.nonpositive(a), assumptions) or _true(Q.negative(a), assumptions)
            or (_is_real(a, assumptions) and _false(Q.positive(a), assumptions)))


def _imaginary_sign(a: Expr, assumptions: Any) -> int | None:
    """``1``/``-1`` when ``a`` is proved imaginary with ``im(a)`` of known
    sign, else ``None``.

    The sign is asked both as ``Q.positive(im(a))`` (which is how a user
    naturally states it; ``im`` may auto-evaluate) and as
    ``Q.positive(-I*a)``, the same number written without ``im``.
    """
    if not _is_imaginary(a, assumptions):
        return None
    candidates = {im(a), -I * a}
    for cand in candidates:
        if _true(Q.positive(cand), assumptions):
            return 1
    for cand in candidates:
        if _true(Q.negative(cand), assumptions):
            return -1
    return None


def _exponent_safe(base: Expr, e: Expr, assumptions: Any) -> bool:
    """Whether ``base**e`` cannot be ``0**negative`` (``zoo``).

    A literal nonnegative ``e`` settles it; a literal negative ``e`` (as in
    an unevaluated ``Abs(Pow(x, -3))``) still counts as safe when the base
    is proved nonzero, as the module docstring promises.
    """
    return _is_nonnegative(e, assumptions) or _is_nonzero(base, assumptions)


# --------------------------------------------------------------------------
# Abs
# --------------------------------------------------------------------------

def _abs_scalar(a: Expr, assumptions: Any) -> Expr | None:
    """The rules for ``Abs(a)`` other than the product split."""
    if _true(Q.zero(a), assumptions):
        return S.Zero
    if _is_nonnegative(a, assumptions):
        return a
    if _is_nonpositive(a, assumptions):
        return -a
    s = _imaginary_sign(a, assumptions)
    if s == 1:
        return -I * a
    if s == -1:
        return I * a
    if isinstance(a, exp):
        return exp(re(a.args[0]))
    if isinstance(a, conjugate):
        return Abs(a.args[0])
    if a.is_Pow:
        base, e = a.as_base_exp()
        if not _exponent_safe(base, e, assumptions):
            return None
        if _is_real(base, assumptions):
            if parity(e, assumptions) == "even":
                return base ** e
            if is_integer(e, assumptions):
                return Abs(base) ** e
        if _is_real(e, assumptions):
            return Abs(base) ** e
    return None


def refine_Abs(expr: Basic, assumptions: Any) -> Expr | None:
    """Handler for ``Abs``; see the module docstring."""
    a = expr.args[0]
    result = _abs_scalar(a, assumptions)
    if result is not None:
        return result
    if a.is_Mul and a.is_commutative:
        outside: list[Expr] = []
        inside: list[Expr] = []
        for f in a.args:
            fa = Abs(f)
            if not fa.has(Abs):
                outside.append(fa)       # e.g. Abs(I) == 1, Abs(exp(w)) == exp(re(w))
                continue
            r = _abs_scalar(fa.args[0], assumptions) if isinstance(fa, Abs) else None
            if r is None:
                inside.append(f)
            else:
                outside.append(r)
        if not outside:
            return None
        new = Mul(*outside)
        if inside:
            new = new * Abs(Mul(*inside))
        return None if new == expr else new
    return None


# --------------------------------------------------------------------------
# re / im
# --------------------------------------------------------------------------

def _reim(expr: Basic, assumptions: Any, want_re: bool) -> Expr | None:
    a = expr.args[0]
    func = re if want_re else im
    if _true(Q.zero(a), assumptions):
        return S.Zero
    if _is_real(a, assumptions):
        return a if want_re else S.Zero
    if _is_imaginary(a, assumptions):
        return S.Zero if want_re else -I * a
    new: Expr | None = None
    if isinstance(a, conjugate):
        w = a.args[0]
        new = re(w) if want_re else -im(w)
    elif isinstance(a, exp):
        w = a.args[0]
        new = exp(re(w)) * (cos(im(w)) if want_re else sin(im(w)))
    elif a.is_Pow:
        base, e = a.as_base_exp()
        if (_is_real(base, assumptions) and is_integer(e, assumptions)
                and _exponent_safe(base, e, assumptions)):
            return a if want_re else S.Zero
        return None
    elif a.is_Add:
        new = Add(*[func(t) for t in a.args])
    elif a.is_Mul and a.is_commutative:
        real_factors: list[Expr] = []
        rest: list[Expr] = []
        count_i = 0
        for f in a.args:
            if isinstance(f, ImaginaryUnit):
                count_i += 1
            elif _is_real(f, assumptions):
                real_factors.append(f)
            elif _is_imaginary(f, assumptions):
                real_factors.append(-I * f)
                count_i += 1
            else:
                rest.append(f)
        if not real_factors:
            return None
        new = Mul(*real_factors) * func(Mul(*rest) * I ** count_i)
    if new is None or new == expr:
        return None
    return new


def refine_re(expr: Basic, assumptions: Any) -> Expr | None:
    """Handler for ``re``; see the module docstring."""
    return _reim(expr, assumptions, want_re=True)


def refine_im(expr: Basic, assumptions: Any) -> Expr | None:
    """Handler for ``im``; see the module docstring."""
    return _reim(expr, assumptions, want_re=False)


# --------------------------------------------------------------------------
# arg
# --------------------------------------------------------------------------

def _not_negative_real(w: Expr, assumptions: Any) -> bool:
    """``w`` is provably off the closed negative real axis (``-oo`` included)."""
    return (_true(~Q.extended_negative(w), assumptions)
            or _true(Q.positive(re(w)), assumptions)
            or _true(Q.nonnegative(re(w)), assumptions)
            or _is_nonzero(im(w), assumptions))


def _in_principal_range(t: Expr, assumptions: Any) -> bool:
    """``-pi < t <= pi`` for the real expression ``t``."""
    if t.is_number:
        lower = (t + pi).is_positive
        upper = (t - pi).is_nonpositive
        return bool(lower) and bool(upper)
    return (_true(Q.positive(t + pi), assumptions)
            and _true(Q.nonpositive(t - pi), assumptions))


def refine_arg(expr: Basic, assumptions: Any) -> Expr | None:
    """Handler for ``arg``; see the module docstring."""
    a = expr.args[0]
    if _true(Q.positive(a), assumptions):
        return S.Zero
    if _true(Q.negative(a), assumptions):
        return pi
    s = _imaginary_sign(a, assumptions)
    if s == 1:
        return pi / 2
    if s == -1:
        return -pi / 2
    if isinstance(a, conjugate):
        w = a.args[0]
        if _not_negative_real(w, assumptions):
            return -arg(w)
        return None
    if isinstance(a, exp):
        imag_terms: list[Expr] = []
        for term in Add.make_args(a.args[0]):
            if _is_real(term, assumptions):
                continue
            if _is_imaginary(term, assumptions):
                imag_terms.append(term)
                continue
            return None
        t = -I * Add(*imag_terms)
        if t == 0:
            return S.Zero
        if _in_principal_range(t, assumptions):
            return t
        return None
    if a.is_Mul and a.is_commutative:
        rest = [f for f in a.args if not _true(Q.positive(f), assumptions)]
        if len(rest) == len(a.args):
            return None
        if not rest:
            return S.Zero
        new = arg(Mul(*rest))
        return None if new == expr else new
    return None


# --------------------------------------------------------------------------
# sign
# --------------------------------------------------------------------------

def _sign_scalar(a: Expr, assumptions: Any) -> Expr | None:
    if _true(Q.zero(a), assumptions):
        return S.Zero
    if _true(Q.positive(a), assumptions):
        return S.One
    if _true(Q.negative(a), assumptions):
        return S.NegativeOne
    s = _imaginary_sign(a, assumptions)
    if s == 1:
        return I
    if s == -1:
        return -I
    if isinstance(a, Abs) and _is_nonzero(a.args[0], assumptions):
        return S.One
    if isinstance(a, exp) and _is_real(a.args[0], assumptions):
        return S.One
    return None


def refine_sign(expr: Basic, assumptions: Any) -> Expr | None:
    """Handler for ``sign``; see the module docstring."""
    a = expr.args[0]
    result = _sign_scalar(a, assumptions)
    if result is not None:
        return result
    if a.is_Mul and a.is_commutative:
        outside: list[Expr] = []
        inside: list[Expr] = []
        for f in a.args:
            r = _sign_scalar(f, assumptions)
            if r is None:
                inside.append(f)
            elif r == 0:
                return S.Zero
            else:
                outside.append(r)
        if not outside:
            return None
        new = Mul(*outside)
        if inside:
            new = new * sign(Mul(*inside))
        return None if new == expr else new
    return None


# --------------------------------------------------------------------------
# conjugate
# --------------------------------------------------------------------------

def _conjugate_scalar(a: Expr, assumptions: Any) -> Expr | None:
    """Rules that make ``conjugate(a)`` conjugate-free or push it inward."""
    if _true(Q.zero(a), assumptions):
        return S.Zero
    if _is_real(a, assumptions) or isinstance(a, (Abs, re, im, arg)):
        return a
    if _is_imaginary(a, assumptions):
        return -a
    if isinstance(a, exp):
        return exp(conjugate(a.args[0]))
    if a.is_Pow:
        base, e = a.as_base_exp()
        if is_integer(e, assumptions):
            return conjugate(base) ** e
        if _true(Q.positive(base), assumptions):
            return base ** conjugate(e)
    return None


def refine_conjugate(expr: Basic, assumptions: Any) -> Expr | None:
    """Handler for ``conjugate``; see the module docstring."""
    a = expr.args[0]
    result = _conjugate_scalar(a, assumptions)
    if result is not None:
        return None if result == expr else result
    if a.is_Add or (a.is_Mul and a.is_commutative):
        parts: list[Expr] = []
        progress = False
        for t in a.args:
            c = conjugate(t)
            if isinstance(c, conjugate):
                r = _conjugate_scalar(c.args[0], assumptions)
                if r is not None:
                    c = r
                    progress = True
            else:
                progress = True
            parts.append(c)
        if not progress:
            return None
        new = a.func(*parts)
        return None if new == expr else new
    return None


# --------------------------------------------------------------------------
# Mul: w**e * conjugate(w)**e -> Abs(w)**(2*e)
# --------------------------------------------------------------------------

def _same_sign_integers(m: Expr, n: Expr) -> Expr | None:
    """``k`` with ``|k| = min(|m|, |n|)`` and the common sign, for literal
    integers ``m, n`` of the same sign; else ``None``."""
    if not (m.is_Integer and n.is_Integer):
        return None
    if m > 0 and n > 0:
        return min(m, n)
    if m < 0 and n < 0:
        return max(m, n)
    return None


def refine_Mul(expr: Basic, assumptions: Any) -> Expr | None:
    """Handler for ``Mul``: only the conjugate-pair rule, see the module
    docstring."""
    if not expr.is_commutative:
        return None
    args = list(expr.args)
    bases: list[tuple[Expr, Expr]] = [f.as_base_exp() for f in args]
    used = [False] * len(args)
    out: list[Expr] = []
    changed = False
    for i, (b, e) in enumerate(bases):
        if used[i]:
            continue
        used[i] = True
        if b.is_Number:
            out.append(args[i])
            continue
        cb = conjugate(b)
        partner = None
        if cb != b:
            for j in range(i + 1, len(args)):
                if not used[j] and bases[j][0] == cb:
                    partner = j
                    break
        if partner is None:
            out.append(args[i])
            continue
        e2 = bases[partner][1]
        w = b.args[0] if isinstance(b, conjugate) else b
        if e == e2 and is_integer(e, assumptions):
            used[partner] = True
            out.append(Abs(w) ** (2 * e))
            changed = True
            continue
        k = _same_sign_integers(e, e2)
        if k is None:
            out.append(args[i])
            continue
        used[partner] = True
        out.append(Abs(w) ** (2 * k))
        if e != k:
            out.append(b ** (e - k))
        if e2 != k:
            out.append(cb ** (e2 - k))
        changed = True
    if not changed:
        return None
    new = Mul(*out)
    return None if new == expr else new


handlers_dict['Abs'] = refine_Abs
handlers_dict['re'] = refine_re
handlers_dict['im'] = refine_im
handlers_dict['arg'] = refine_arg
handlers_dict['sign'] = refine_sign
handlers_dict['conjugate'] = refine_conjugate
handlers_dict['Mul'] = refine_Mul
