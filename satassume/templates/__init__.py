"""Structural rule templates for :mod:`satassume`.

Importing this package registers every template module with
:data:`registry`; the engine then calls ``registry.facts_for(expr)`` for each
expression node it visits.  This package imports SymPy; the core
:mod:`satassume` modules do not.
"""
from . import atoms, core, functions  # noqa: F401  (registration side effects)
from .registry import TemplateRegistry, registry

__all__ = ['TemplateRegistry', 'registry']

_warm = False


def warm_up() -> None:
    """Build the patterns of the most common node shapes once per process
    (a few milliseconds), so no query pays for them.  Called by the engine
    on construction."""
    global _warm
    if _warm:
        return
    _warm = True
    from sympy import Abs, Dummy, Integer, Rational, S, Symbol, exp, log, sqrt
    from sympy.functions.elementary.trigonometric import acos, asin, atan, cos, sin, tan
    x, y, z = Symbol('x'), Symbol('y'), Symbol('z')
    p = Symbol('p', positive=True)
    for e in (x + y, x + y + z, x + 1, x - 1, x + 2, x*y, x*y*z, 2*x, -x, x/2, 3*x,
              x**2, x**3, x**y, x**-1, sqrt(x), x**S.Half, x**Rational(1, 3), 2**x,
              exp(x), log(x), Abs(x), sin(x), cos(x), tan(x), asin(x), acos(x), atan(x),
              x, p, Dummy('d'), Integer(0), Integer(1), Integer(2), Integer(-1), S.Half,
              S.Pi, S.Exp1, S.ImaginaryUnit, S.Infinity, S.NegativeInfinity):
        registry.clauses_for(e)


registry.warm_up = warm_up
