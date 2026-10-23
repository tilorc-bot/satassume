"""Structural rule templates for :mod:`satassume`.

Importing this package registers every template module with
:data:`registry` (:mod:`.core`, the families of rows through :mod:`.wiring`,
:mod:`.selection`, :mod:`.special`, :mod:`.rootof`,
:mod:`.nodes`, :mod:`.limits`, :mod:`.physics` and :mod:`.stats` on first use,
see :meth:`TemplateRegistry.lazy`); the engine then calls ``registry.facts_for(expr)`` for each
expression node it visits.

This package is where the knowledge about SymPy expression classes lives,
so it imports SymPy at module level (``_common``, ``registry`` and
``table`` themselves do not).  So do :mod:`satassume.knowledge.domain`,
the theories' adapters and :mod:`satassume.sympy_api`; every other module
of :mod:`satassume` is importable without SymPy, and the engine imports
this package only inside functions (docs/design.md, "Where SymPy is
imported"; ``tests/test_layering.py``).
"""
from sympy.core.add import Add
from sympy.core.basic import Basic
from sympy.core.function import Application
from sympy.core.mod import Mod
from sympy.core.mul import Mul
from sympy.core.power import Pow
from sympy.core.singleton import S
from sympy.functions.elementary.exponential import LambertW, exp, exp_polar, log
from sympy.functions.combinatorial.factorials import (
    FallingFactorial,
    RisingFactorial,
    binomial,
    factorial,
    factorial2,
    subfactorial,
)
from sympy.functions.combinatorial.numbers import andre, catalan, genocchi, partition
from sympy.functions.elementary.complexes import (
    Abs, conjugate, im, polar_lift, principal_branch, re, sign,
)
from sympy.functions.elementary.integers import RoundFunction, ceiling, floor
from sympy.functions.elementary.miscellaneous import MinMaxBase
from sympy.functions.elementary.piecewise import Piecewise
from sympy.functions.elementary.hyperbolic import (
    acosh, acoth, acsch, asech, asinh, atanh, cosh, coth, csch, sech, sinh, tanh,
)
from sympy.functions.elementary.trigonometric import (
    acos, acot, acsc, asec, asin, atan, cos, cot, csc, sec, sin, tan,
)
from sympy.functions.special.bessel import (
    airyai,
    airyaiprime,
    airybi,
    airybiprime,
    besseli,
    besselj,
    besselk,
    bessely,
)
from sympy.functions.special.beta_functions import beta, betainc, betainc_regularized
from sympy.functions.special.error_functions import (
    Chi,
    Ci,
    Ei,
    Li,
    Shi,
    Si,
    erf,
    erf2,
    erfc,
    erfcinv,
    erfi,
    erfinv,
    expint,
    fresnelc,
    fresnels,
    li,
)
from sympy.functions.special.gamma_functions import (
    digamma,
    gamma,
    loggamma,
    lowergamma,
    multigamma,
    polygamma,
    trigamma,
    uppergamma,
)
from sympy.functions.special.zeta_functions import dirichlet_eta, polylog, zeta
from sympy.polys.rootoftools import ComplexRootOf
from sympy.calculus.accumulationbounds import AccumulationBounds
from sympy.tensor.indexed import Idx
from sympy.concrete.products import Product
from sympy.concrete.summations import Sum
from sympy.integrals.integrals import Integral

from . import atoms  # noqa: F401  (registration side effects)
from .registry import TemplateRegistry, registry

# the templates of sums, products and powers, and of functions, are
# imported when the first node of such a class is met (TemplateRegistry.lazy)
registry.lazy(__name__ + ".core", Add, Mul, Pow)
#: the families of rows (.wiring), each with the functions it states rows
#: for: a family is compiled on the first use of one of its functions
ROW_FAMILIES = (
    ("trig", (sin, cos, tan, cot, sec, csc)),
    ("hyperbolic", (sinh, cosh, tanh, coth, sech, csch)),
    ("inverse", (asin, acos, asinh, acosh, atanh, acoth, asech, acsch, asec, acsc, atan, acot)),
    ("error_functions", (erf, erfc, erfi, Si, Shi, fresnels, fresnelc, erf2, Ei, Ci, Chi, li, Li,
                         erfinv, erfcinv,
                         # new in SymPy 1.15: declared by name
                         "sympy.functions.special.error_functions:owens_t",
                         expint)),
    ("exp_log", (exp, log)),
    ("complex_parts", (Abs, re, im, sign, conjugate)),
    ("integer_funcs", (RoundFunction, floor, ceiling, factorial, Mod)),
    ("polar", (exp_polar, polar_lift, principal_branch)),
    ("zeta_functions", (zeta, dirichlet_eta, polylog)),
    ("lambertw", (LambertW,)),
    ("bessel", (airyai, airybi, airyaiprime, airybiprime, besselj, bessely, besseli, besselk)),
    ("gamma_functions", (gamma, digamma, trigamma, polygamma, loggamma, lowergamma, uppergamma)),
    ("beta_functions", (beta, betainc, betainc_regularized)),
    ("combinatorial", (catalan, andre, genocchi, partition, factorial2, subfactorial,
                       RisingFactorial, FallingFactorial, binomial)),
    # sympy.codegen is not imported by SymPy itself: declared by name
    ("cfunctions", ("sympy.codegen.cfunctions:expm1", "sympy.codegen.cfunctions:log1p")),
)
for _family, _functions in ROW_FAMILIES:
    registry.lazy(f"{__name__}.wiring:{_family}", *_functions)
registry.lazy(__name__ + ".rootof", ComplexRootOf)
registry.lazy(__name__ + ".selection", MinMaxBase, Piecewise)
registry.lazy(__name__ + ".special", multigamma)
# sympy.physics and sympy.stats are not imported by SymPy itself either
registry.lazy(__name__ + ".physics", "sympy.physics.units.quantities:Quantity")
registry.lazy(__name__ + ".stats", "sympy.stats.rv:RandomSymbol")
registry.lazy(__name__ + ".nodes", AccumulationBounds, Idx)
registry.lazy(__name__ + ".limits", Sum, Product, Integral)


_SPECIAL = (S.NaN, S.Infinity, S.NegativeInfinity, S.ComplexInfinity)


def _may_be_nan(a) -> bool:
    """``a`` is ``nan``, or holds an explicit ``nan`` or infinity in a part
    that carries a value, so that it may evaluate to nan: arithmetic
    (``oo - oo``, ``0*oo``, ``x + oo`` at ``x = -oo``), a function
    application (``Abs(nan)``), and every other node whose arguments feed
    its value -- ``Subs(nan, x, 1)``, ``Subs(x, x, nan)``,
    ``Limit(nan, x, 0)``, ``UnevaluatedExpr(nan)``, an integral or a sum
    over ``(-oo, oo)`` (``Integral(x, (x, -oo, oo))`` is nan), a
    ``Piecewise`` branch value, and a condition too: a ``Piecewise``
    without a ``True`` branch is nan where no condition holds, so a
    condition holding ``oo - oo`` may leave no value (#236 review).  Only
    the arguments of an atom (the range of an ``Idx``) are labels, not
    followed (#235 review; re-review R1)."""
    if a is S.NaN:
        return True
    if not isinstance(a, Basic) or a.is_Atom:
        return False
    return any(any(b is c for c in _SPECIAL) or _may_be_nan(b) for b in a.args)


def _applied_to_nan(expr) -> bool:
    """A function applied to ``nan``, or to an argument that may evaluate
    to nan (:func:`_may_be_nan`): SymPy's functions return nan before any
    identity a template states (``rf(nan, 0)``, ``owens_t(nan, 0)``,
    ``zeta(1, nan)``, ``Abs(nan)``, ``sign(nan)``), and no predicate holds
    of nan, so no template fact is claimed (#180 final review F3; #231:
    ``Abs(oo - oo)`` is not extended_positive, although ``oo - oo`` is not
    zero).  An argument that is nan only at some values of its symbols
    (``Abs(x + y)`` at ``x = oo, y = -oo``) is not detected."""
    return isinstance(expr, Application) and any(_may_be_nan(a) for a in expr.args)


registry.opaque = _applied_to_nan

__all__ = ['TemplateRegistry', 'registry']
