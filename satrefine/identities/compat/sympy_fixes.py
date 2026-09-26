"""SymPy workarounds the driver needs (expected to change with SymPy).

* :func:`rebuild`: ``acot``/``acoth`` rebuilt from refined children keep their
  value at 0 (issue #10, B8: SymPy's ``eval`` pulls a sign out of an argument
  that may be zero);
* :data:`EVAL_REFINE`: satrefine's copies of SymPy's ``Pow._eval_refine`` and
  ``exp._eval_refine``, which call SymPy's ``ask`` directly (A1).

Importing this module installs both (:data:`..core.hooks.rebuild`,
:data:`..core.hooks.eval_refine`);
:mod:`satrefine.identities` imports it.
"""
from __future__ import annotations

from typing import Any

from sympy import I, Pow, Q, S, acot, acoth, exp, pi
from sympy.core import Basic

from . import upstream as _upstream
from ..core import hooks


_SIGN_AT_ZERO = (acot, acoth)   # heads whose eval pulls a sign out of an argument that may be zero


def rebuild(func: Any, args: Any, assumptions: Any) -> Basic:
    """``func(*args)``, the node rebuilt from refined children, except that
    ``acot`` and ``acoth`` of a non-numeric argument that may be zero stay
    unevaluated (issue #10, B8).

    SymPy's ``acot.eval`` and ``acoth.eval`` pull a sign out of the argument
    (``acot(-z) -> -acot(z)``, and ``acoth(I*c) -> -I*acot(c)``), which is
    wrong at ``z = 0``: ``acot(0) = pi/2``, ``acoth(0) = I*pi/2``.  A refined
    child often has that shape (``Abs(z) -> -z`` under ``Q.nonpositive(z)``), so
    ``acot(Abs(z))`` would become ``-acot(z)``.  When ``ask`` proves the
    argument nonzero the evaluated form is correct and is kept."""
    if func in _SIGN_AT_ZERO and len(args) == 1 and not args[0].is_number:
        new = func(*args)
        if new.func is not func or new.args != tuple(args):
            try:
                nonzero = _upstream.ask(Q.zero(args[0]), assumptions) is False
            except (ValueError, TypeError, AssertionError):
                nonzero = False
            if not nonzero:
                return func(*args, evaluate=False)
        return new
    return func(*args)


def _pow_eval_refine(expr: Any, assumptions: Any) -> Any:
    """SymPy's ``Pow._eval_refine`` asking through :func:`.upstream.ask`
    (the selected backend, memoized for the call) instead of SymPy's ``ask``."""
    ask = _upstream.ask
    b, e = expr.as_base_exp()
    try:
        if ask(Q.integer(e), assumptions) and b.could_extract_minus_sign():
            if ask(Q.even(e), assumptions):
                return Pow(-b, e)
            elif ask(Q.odd(e), assumptions):
                return -Pow(-b, e)
    except ValueError:                       # inconsistent assumptions: the hook declines
        return None
    return None


def _exp_eval_refine(expr: Any, assumptions: Any) -> Any:
    """SymPy's ``exp._eval_refine`` asking through :func:`.upstream.ask`.
    Like SymPy's, it asks without the assumptions (it only reads the literal
    coefficient of ``pi*I``)."""
    ask = _upstream.ask
    arg = expr.args[0]
    if arg.is_Mul:
        Ioo = I*S.Infinity
        if arg in [Ioo, -Ioo]:
            return S.NaN
        coeff = arg.as_coefficient(pi*I)
        if coeff:
            try:
                if ask(Q.integer(2*coeff)):
                    if ask(Q.even(coeff)):
                        return S.One
                    elif ask(Q.odd(coeff)):
                        return S.NegativeOne
                    elif ask(Q.even(coeff + S.Half)):
                        return -I
                    elif ask(Q.odd(coeff + S.Half)):
                        return I
            except ValueError:
                return None
    return None


EVAL_REFINE = {Pow._eval_refine: _pow_eval_refine, exp._eval_refine: _exp_eval_refine}
"""satrefine's copies of SymPy's ``_eval_refine`` hooks that call ``ask``, by the
SymPy method they replace (a subclass overriding the hook keeps its own).  SymPy's
versions call SymPy's ``ask`` directly, past the backend and the per-call memo;
the copies behave the same with the selected backend's answers."""


hooks.rebuild = rebuild
hooks.eval_refine.update(EVAL_REFINE)
