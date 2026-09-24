"""Simple rules for the imaginary part, ahead of the vendored handler.

``im(log(w)) = arg(w)``; ``im(u + v) = im(u) + im(v)``; ``im(c*w) = c*im(w)``
for real ``c``.  The identities in :mod:`.log` reduce their branch
bookkeeping through these; the vendored handler expands into real and
imaginary parts instead, which leaves ``arg(re(w) + I*im(w))`` that nothing
can refine.
"""
from __future__ import annotations

from sympy import Q, arg, im, log
from sympy.core import Add, Basic, Mul

from .. import _upstream
from .._upstream import handlers_dict


def refine_im(expr: Basic, assumptions) -> Basic | None:
    a = expr.args[0]
    if isinstance(a, log):
        return arg(a.args[0])
    if isinstance(a, Add):
        return Add(*[im(t) for t in a.args])
    if isinstance(a, Mul):
        real = [f for f in a.args if _upstream.ask(Q.real(f), assumptions)]
        if real and len(real) < len(a.args):
            return Mul(*real) * im(Mul(*[f for f in a.args if f not in real]))
    return _upstream.refine_im(expr, assumptions)


handlers_dict['im'] = refine_im
