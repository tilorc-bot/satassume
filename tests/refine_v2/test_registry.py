"""The package registers exactly the 56 keys and honours the handler contract."""
from __future__ import annotations

import pkgutil

from sympy import Abs, Basic, Integer, Q, S, cos, sin, sqrt
from sympy.abc import n, x, y

import satrefine
from satrefine import handlers_v2
from satrefine.identities.compat import backend
from satrefine._upstream import handlers_dict
from satrefine.testing.harness import scripted_ask, use_ask

KEYS = sorted("""Abs Determinant DiracDelta FallingFactorial HadamardProduct Heaviside
Inverse KroneckerDelta MatAdd MatMul MatrixElement Max Min Mod Mul Pow Rem RisingFactorial
Trace Transpose acos acosh acoth acsch arg asech asin asinh atan atan2 atanh binomial
ceiling conjugate cos cosh cot coth csc csch exp factorial floor frac gamma im log re sec
sech sign sin sinc sinh tan tanh""".split())


def test_all_56_keys_registered():
    assert len(KEYS) == 56
    assert sorted(handlers_dict) == KEYS


def test_every_public_module_registers_something():
    import importlib
    for info in pkgutil.iter_modules(handlers_v2.__path__):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{handlers_v2.__name__}.{info.name}")
        assert any(handler is getattr(module, name) for name in dir(module)
                   for handler in handlers_dict.values()), info.name


def test_handlers_return_none_or_basic_never_python_numbers():
    probes = [
        (sin(x), Q.zero(x)), (cos(x), Q.zero(x)), (Abs(x), Q.positive(x)),
        (sqrt(x**2), True), (x**y, Q.zero(y)), (sin(x + n * S.Pi), Q.integer(n)),
    ]
    for expr, assumptions in probes:
        result = handlers_dict[expr.__class__.__name__](expr, assumptions)
        assert result is None or isinstance(result, Basic), (expr, result)
        assert not isinstance(result, (int, float, complex)) or isinstance(result, Integer)


def test_handlers_survive_an_ask_that_only_answers_none():
    """No handler may fire (or crash) when nothing is provable."""
    fake_ask, _ = scripted_ask([])
    probes = [
        sin(x + n * S.Pi), sqrt(x**2), Abs(x * y), x**y, (-1)**(x + y), sin(x) * Abs(x),
    ]
    with use_ask(fake_ask):
        for expr in probes:
            assert satrefine.refine(expr, Q.integer(n)) == expr


def test_relation_rules_do_not_fire_under_the_satassume_backend():
    from sympy import Max, asin
    with backend.using("satassume"):
        assert satrefine.refine(asin(sin(x)), Q.ge(x, -S.Pi / 2) & Q.le(x, S.Pi / 2)) == asin(sin(x))
        assert satrefine.refine(Max(x, y), Q.ge(x, y)) == Max(x, y)
    with backend.using("combined"):
        assert satrefine.refine(Max(x, y), Q.ge(x, y)) == x


def test_ask_is_reached_through_the_module_attribute():
    """Patching ``_upstream.ask`` must reach every handler."""
    fake_ask, log = scripted_ask([None, True])
    with use_ask(fake_ask):
        assert satrefine.refine(Abs(x), Q.positive(x)) == x
    assert [entry[0] for entry in log[:2]] == [Q.zero(x), Q.nonnegative(x)]
