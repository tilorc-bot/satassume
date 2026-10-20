"""Structural rule templates for :mod:`satassume`.

Importing this package registers every template module with
:data:`registry` (:mod:`.core`, :mod:`.functions`, :mod:`.selection`,
:mod:`.combinatorial`, :mod:`.special`, :mod:`.cfunctions`, :mod:`.rootof`,
:mod:`.nodes`, :mod:`.physics` and :mod:`.stats` on first use,
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
from sympy.core.function import Function
from sympy.core.mul import Mul
from sympy.core.power import Pow
from sympy.functions.elementary.exponential import LambertW
from sympy.functions.combinatorial.factorials import (
    FallingFactorial,
    RisingFactorial,
    binomial,
    factorial2,
    subfactorial,
)
from sympy.functions.combinatorial.numbers import andre, catalan, genocchi, partition
from sympy.functions.elementary.miscellaneous import MinMaxBase
from sympy.functions.elementary.piecewise import Piecewise
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

from . import atoms  # noqa: F401  (registration side effects)
from .registry import TemplateRegistry, registry

# the templates of sums, products and powers, and of functions, are
# imported when the first node of such a class is met (TemplateRegistry.lazy)
registry.lazy(__name__ + ".core", Add, Mul, Pow)
registry.lazy(__name__ + ".functions", Function)
registry.lazy(__name__ + ".rootof", ComplexRootOf)
registry.lazy(__name__ + ".selection", MinMaxBase, Piecewise)
registry.lazy(__name__ + ".combinatorial", factorial2, subfactorial, RisingFactorial,
              FallingFactorial, binomial, catalan, andre, genocchi, partition)
registry.lazy(__name__ + ".special", gamma, loggamma, polygamma, digamma, trigamma, multigamma,
              lowergamma, uppergamma, erf, erfc, erfi, erf2, erfinv, erfcinv, Ei, expint, li, Li,
              Si, Ci, Shi, Chi, fresnels, fresnelc, beta, betainc, betainc_regularized, LambertW,
              zeta, dirichlet_eta, polylog, airyai, airybi, airyaiprime, airybiprime, besselj,
              bessely, besseli, besselk,
              # new in SymPy 1.15: declared by name
              "sympy.functions.special.error_functions:owens_t")
# sympy.codegen is not imported by SymPy itself: declared by name
registry.lazy(__name__ + ".cfunctions", "sympy.codegen.cfunctions:expm1",
              "sympy.codegen.cfunctions:log1p")
# sympy.physics and sympy.stats neither
registry.lazy(__name__ + ".physics", "sympy.physics.units.quantities:Quantity")
registry.lazy(__name__ + ".stats", "sympy.stats.rv:RandomSymbol")
registry.lazy(__name__ + ".nodes", AccumulationBounds, Idx)

__all__ = ['TemplateRegistry', 'registry']
