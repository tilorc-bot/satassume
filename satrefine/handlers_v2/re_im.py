"""Handlers for the real and imaginary parts ``re`` and ``im``.

Rules:

R1  ``re(x) -> x`` and ``im(x) -> 0`` when ``x`` is real.
R2  ``re(x) -> 0`` and ``im(x) -> -I*x`` when ``x`` is imaginary.
R3  Otherwise ``x`` is expanded with ``expand(complex=True)`` and the
    expansion refined; the result is kept only if it changed.  This is the
    vendored SymPy logic (:func:`satrefine._upstream.refine_re` and
    ``refine_im``), which is sound: every step is an identity.
"""
from __future__ import annotations

from .. import _upstream
from .._upstream import handlers_dict

refine_re = _upstream.refine_re
refine_im = _upstream.refine_im

handlers_dict['re'] = refine_re
handlers_dict['im'] = refine_im
