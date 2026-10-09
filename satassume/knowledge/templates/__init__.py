"""Structural rule templates for :mod:`satassume`.

Importing this package registers every template module with
:data:`registry` (:mod:`.core` and :mod:`.functions` on first use, see
:meth:`TemplateRegistry.lazy`); the engine then calls ``registry.facts_for(expr)`` for each
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

from . import atoms  # noqa: F401  (registration side effects)
from .registry import TemplateRegistry, registry

# the templates of sums, products and powers, and of functions, are
# imported when the first node of such a class is met (TemplateRegistry.lazy)
registry.lazy(__name__ + ".core", Add, Mul, Pow)
registry.lazy(__name__ + ".functions", Function)

__all__ = ['TemplateRegistry', 'registry']
