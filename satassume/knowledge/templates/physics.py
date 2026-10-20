"""Unit facts for ``Quantity`` of ``sympy.physics.units`` (#180, C-NOTMPL).

A ``Quantity`` (a unit such as ``meter`` or a physical constant such as
``speed_of_light``) is an atom that SymPy declares positive
(``Quantity._eval_is_positive`` is ``True``, the class has ``is_real`` and
``is_nonzero``): ``sqrt(meter**2) == meter``.  The closure gives real,
finite, nonzero, ... (``units``).

SymPy does not import ``sympy.physics`` itself, so this module is declared
with the class name (:meth:`TemplateRegistry.lazy`) and imported when the
first quantity is met.
"""
from __future__ import annotations

from sympy.physics.units.quantities import Quantity

from ._common import units
from .registry import registry


@registry.register(Quantity)
def quantity_units(expr):
    return units(('quantity',), lambda: [('positive', True)], expr)
