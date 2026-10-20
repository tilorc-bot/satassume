"""A subclass that redefines a fact does not inherit the templates of the
class whose handler it overrides (#180 S10).

``sympy.printing.rust.float_floor`` is a ``floor`` whose
``_eval_is_integer`` returns False (Rust's ``floor`` returns a float); the
``floor`` template made ``float_floor(xr)`` an integer, and the Rust printer
printed ``3`` instead of ``3.0`` (test_rust::test_Functions,
::test_parenthesize_typecast).
"""
import pytest
from sympy import Float, Number, Q, Symbol, ceiling, floor
from sympy.printing.rust import float_ceiling, float_floor

from satassume import DictCache, Engine
from satassume.knowledge.templates.registry import (TemplateRegistry, own_facts,
                                                    registry)
from satassume.sympy_api import ask

xr = Symbol('xr', real=True)


@pytest.fixture
def eng():
    return Engine(cache=DictCache())


def test_reproducers(eng):
    # SymPy: False and None; the floor template gave True for both
    assert ask(Q.integer(float_floor(xr)), True, eng) is None
    assert ask(Q.integer(-3*float_floor(xr/3)), True, eng) is None
    assert ask(Q.integer(float_ceiling(xr)), True, eng) is None
    # floor and ceiling themselves keep their templates
    assert ask(Q.integer(floor(xr)), True, eng) is True
    assert ask(Q.integer(ceiling(xr)), True, eng) is True
    assert registry.templates_for(float_floor) == []


def test_constant_facts_follow_the_override(eng):
    # Float overrides Number's sign handlers; the template of Number reads
    # the constant's own facts (own_facts), so Float keeps it
    assert registry.templates_for(Float) == registry.templates_for(Number)
    assert getattr(registry.templates_for(Float)[0], '_satassume_own_facts')
    assert ask(Q.positive(Float(2.5)), True, eng) is True
    assert ask(Q.negative(Float(-2.5)), True, eng) is True


class Base:
    def _eval_is_integer(self):
        return True

    def _eval_is_polynomial(self, syms):
        return True


class Overrides(Base):
    def _eval_is_integer(self):
        return False


class Plain(Base):
    pass


class NotAFact(Base):
    def _eval_is_polynomial(self, syms):
        return False


class NewHandler(Base):
    def _eval_is_prime(self):
        return False


class Mixin:
    def _eval_is_integer(self):
        return False


class MixedIn(Mixin, Base):
    pass


class Below(Overrides):
    pass


def test_registry_rule():
    reg = TemplateRegistry()

    def structural(expr):
        return None

    @own_facts
    def own(expr):
        return None

    def mine(expr):
        return None

    reg.register(Base)(structural)
    reg.register(Base)(own)
    reg.register(Overrides)(mine)
    both = [structural, own]
    assert reg.templates_for(Base) == both
    assert reg.templates_for(Plain) == both
    # handlers that are no facts, or facts the base has no handler for
    assert reg.templates_for(NotAFact) == both
    assert reg.templates_for(NewHandler) == both
    # an override of a fact handler of the base, also through a mixin that
    # comes first in the MRO, or further up
    assert reg.templates_for(Overrides) == [mine, own]
    assert reg.templates_for(MixedIn) == [own]
    assert reg.templates_for(Below) == [mine, own]
