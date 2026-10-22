"""Which template each function of a family of rows gets (#249).

The family modules (:mod:`.trig`, :mod:`.hyperbolic`) state rows only, as
``RULES`` (see :mod:`._rows`).  :func:`load` compiles a family's rows and
registers one template per function (:func:`template`): the unary template
of its rows (:func:`.functions._unary`), or, for a function of
:data:`PI_MULTIPLE` or :data:`I_PI_MULTIPLE`, :func:`.functions._pi_trig`'s,
which adds the rules of ``f(pi*c*s)`` for a rational ``c``.
``templates/__init__.py`` declares each family as ``"<this
module>:<family>"`` for its functions (``TemplateRegistry.lazy``), so a
family is compiled on the first use of one of its functions, and its
templates are attributed to that name.
"""
from __future__ import annotations

import importlib

from sympy import cos, cosh, sin

from ._rows import by_function, rules
from .core import ipi_split
from .functions import _cosh_shift, _pi_trig, _unary
from .registry import registry

#: the functions with rules for an argument pi*c*s, each with whether it
#: shifts like cos (cos(pi*c*s) == sin(pi*(c + 1/2)*s))
PI_MULTIPLE = ((sin, False), (cos, True))

#: the functions with rules for an argument I*pi*c*s (cosh(I*pi*c*s) ==
#: cos(pi*c*s)) and r + I*pi*c*s for an integer c (functions._cosh_shift)
I_PI_MULTIPLE = (cosh,)


def functions(family: str):
    """The functions the family's ``RULES`` state rows for, in order."""
    module = importlib.import_module(f"{__package__}.{family}")
    return tuple(fn for fn, _ in by_function(module.RULES))


def template(fn, gen):
    """The template of ``fn`` whose rules ``gen`` (the compiled rows) gives."""
    shift = dict(PI_MULTIPLE).get(fn)
    if shift is not None:
        return _pi_trig(fn.__name__, gen, shift)
    if fn in I_PI_MULTIPLE:
        return _pi_trig(fn.__name__, gen, True, ipi_split, _cosh_shift(gen))
    return _unary(fn.__name__, gen)


def load(family: str) -> None:
    """Register the templates of the family's rows (``TemplateRegistry.lazy``)."""
    name = f"{__name__}:{family}"
    for fn, all_rows in by_function(importlib.import_module(f"{__package__}.{family}").RULES):
        registry.register(fn)(template(fn, rules(fn, all_rows, name)))
