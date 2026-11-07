"""Planted: one raise inside each quiet handler's try block, on whichever backend. The zero means nothing without this."""
from unittest import mock
from sympy import Q, Symbol
from satassume import engine as E, sympy_api as A

x, y = Symbol("x"), Symbol("y")


def test_consistent_site():
    with mock.patch.object(A, "_formula", side_effect=ValueError("planted consistent")):
        assert A._consistent(Q.positive(x) & Q.negative(y), E.Engine()) is False


def test_build_context_site():
    with mock.patch.object(E.Engine, "_complete_check", side_effect=ValueError("planted context")):
        assert A._consistent(Q.positive(x) & Q.negative(y), E.Engine()) in (True, False)
