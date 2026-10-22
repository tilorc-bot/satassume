"""Which template each function of a family of rows gets (#249).

The family modules (:mod:`.trig`) state rows only, as ``RULES`` (see
:mod:`._rows`).  This module compiles them and registers one template per
function: the unary template of its rows (:func:`.functions._unary`), or,
for a function of :data:`PI_MULTIPLE`, :func:`.functions._pi_trig`'s, which
adds the rules of ``f(pi*c*s)`` for a rational ``c``.  The templates are
attributed to this module, which ``templates/__init__.py`` declares for the
functions of :data:`FAMILIES` (``TemplateRegistry.lazy``).
"""
from __future__ import annotations

import importlib

from sympy import cos, sin

from ._rows import by_function, rules
from .functions import _pi_trig, _unary
from .registry import registry

#: the family modules of rows
FAMILIES = ("trig",)

#: the functions with rules for an argument pi*c*s, each with whether it
#: shifts like cos (cos(pi*c*s) == sin(pi*(c + 1/2)*s))
PI_MULTIPLE = ((sin, False), (cos, True))


def functions(family: str):
    """The functions the family's ``RULES`` state rows for, in order."""
    module = importlib.import_module(f"{__package__}.{family}")
    return tuple(fn for fn, _ in by_function(module.RULES))


for _family in FAMILIES:
    for _fn, _all in by_function(importlib.import_module(f"{__package__}.{_family}").RULES):
        _gen = rules(_fn, _all, __name__)
        _shift = dict(PI_MULTIPLE).get(_fn)
        if _shift is None:
            registry.register(_fn)(_unary(_fn.__name__, _gen))
        else:
            registry.register(_fn)(_pi_trig(_fn.__name__, _gen, _shift))
