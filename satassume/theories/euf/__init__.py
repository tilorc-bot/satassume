"""Equality with uninterpreted functions.

The congruence-closure theory (:mod:`.euf`, SymPy-free: terms are opaque
hashable objects) and its adapter from SymPy terms (:mod:`.euf_adapter`,
imports SymPy at module level).  Hides which SymPy terms are applications
(:func:`.euf_adapter.structural`) and how congruence is decided.

May import the layers below :mod:`satassume.theories`; not the other
theories.
"""
