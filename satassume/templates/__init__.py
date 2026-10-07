"""Structural rule templates for :mod:`satassume`.

Importing this package registers every template module with
:data:`registry` (:mod:`.core` and :mod:`.functions` on first use, see
:meth:`TemplateRegistry.lazy`); the engine then calls ``registry.facts_for(expr)`` for each
expression node it visits.  This package imports SymPy; the core
:mod:`satassume` modules do not.
"""
from sympy.core.add import Add
from sympy.core.function import Function
from sympy.core.mul import Mul
from sympy.core.power import Pow

from . import atoms  # noqa: F401  (registration side effects)
from .registry import TemplateRegistry, registry

# the templates of sums, products and powers, and of functions, are
# imported when the first node of such a class is met (TemplateRegistry.lazy)
registry.lazy(__name__ + ".core", Add, Mul, Pow)
registry.lazy(__name__ + ".functions", Function)

__all__ = ['TemplateRegistry', 'registry']

_warm = False


def warm_up():
    # type: () -> None
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
