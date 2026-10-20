"""Templates for classes that had none (#180 C-NOTMPL, part C: ``Quantity``).

A ``Quantity`` of ``sympy.physics.units`` (a unit or a physical constant)
is positive under SymPy's definition (``Quantity._eval_is_positive``).  A
node of the class got no facts before, so ``sqrt(meter**2)`` did not
simplify and ``2 > meter*sqrt(second**2/meter**2)/second`` was undecided
(the physics/units, physics/optics and solveset ``test_units`` tests of
#180).
"""
import pytest
from sympy import Abs, Symbol, sqrt
from sympy.physics.units import centimeter, gram, kilogram, meter, second, speed_of_light
from sympy.physics.units.quantities import PhysicalConstant, Quantity

from satassume import DictCache, Engine

x = Symbol('x')


def fresh():
    return Engine(cache=DictCache())


@pytest.mark.parametrize("q", [meter, kilogram, speed_of_light, Quantity('qq'),
                               PhysicalConstant('pc')])
def test_quantity_is_positive(q):
    eng = fresh()
    for pred, expected in (('positive', True), ('real', True), ('finite', True),
                           ('nonzero', True), ('zero', False), ('negative', False),
                           ('imaginary', False), ('commutative', True)):
        assert eng.is_(q, pred) is expected, (q, pred)
        assert getattr(q, 'is_' + pred) is expected
    for pred in ('integer', 'rational', 'algebraic'):
        assert eng.is_(q, pred) is None


@pytest.mark.parametrize("expr, pred, expected", [
    # test_quantities: sqrt(meter**2) == meter, Abs(meter) == meter
    (meter**2, 'positive', True),
    (Abs(meter) - meter, 'zero', True),
    # test_utils (optics): 2 > meter*sqrt(second**2/meter**2)/second
    (meter*sqrt(second**2/meter**2)/second, 'positive', True),
    (sqrt(centimeter**3*gram)/second, 'positive', True),
    (meter - 2*meter, 'negative', True),
    (meter*x, 'positive', None),
])
def test_reproducers(expr, pred, expected):
    assert fresh().is_(expr, pred) is expected

