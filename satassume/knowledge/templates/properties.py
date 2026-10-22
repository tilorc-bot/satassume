"""Properties of functions: the rows each gives, and the functions that have it (#249).

Each property is a theorem-shaped fact about a function ``f`` (entire,
real on the real line, ...) and gives rows about ``f(x)``; it is followed
by the tuple of the functions that have it.  A function's rules are the
rows of its properties (:func:`rows_of`), then its signature and its own
rows in the module of its family (``trig.py``).  Only functions whose
rules are written this way are listed; the others are still in
``functions.py`` and ``special.py``.

Values at the special points follow SymPy's conventions: ``zoo`` at a pole,
no claim at an infinite argument (``sin(oo)`` is ``AccumBounds``; ``real``
and ``complex`` imply ``finite``).
"""
from __future__ import annotations

from sympy import Q, cos, cot, csc, sec, sin, tan

from ._rows import Rows, rows, x


def closed(f, *preds) -> Rows:
    """``f`` maps each set ``P`` into itself: ``P(x) -> P(f(x))``."""
    return rows(*(P(x) >> P(f(x)) for P in preds))


def _property(fn):
    """A property: its rows carry its name."""
    def prop(f) -> Rows:
        return fn(f).labelled(fn.__name__)
    prop.__name__ = prop.__qualname__ = fn.__name__
    prop.__doc__ = fn.__doc__
    return prop


@_property
def entire(f):
    """No poles: finite at every finite point."""
    return closed(f, Q.finite, Q.complex)


ENTIRE = (sin, cos)


@_property
def real_meromorphic(f):
    """``f(conj z) == conj f(z)``, and a number or ``zoo`` (at a pole) at
    every finite point: a real argument gives a real value or ``zoo``."""
    return ((Q.finite(f(x)) >> closed(f, Q.real, Q.complex))
            + rows(Q.real(x) >> ~Q.imaginary(f(x))))


REAL_MEROMORPHIC = (tan, cot, sec, csc)


@_property
def nonvanishing(f):
    """``1/f`` is entire: ``f`` is never 0 at a finite point."""
    return rows(Q.complex(x) >> ~Q.zero(f(x)))


NONVANISHING = (sec, csc)


@_property
def imaginary_axis(f):
    """``f`` maps the imaginary axis, 0 excluded, into itself: ``sin(I*t) ==
    I*sinh(t)``, ``tan(I*t) == I*tanh(t)``, ``cot(I*t) == -I*coth(t)``,
    ``csc(I*t) == -I*csch(t)``, finite and nonzero for real ``t != 0``."""
    return closed(f, Q.imaginary)


IMAGINARY_AXIS = (sin, tan, cot, csc)


@_property
def lindemann(f):
    """``f(a)`` is ``R(exp(I*a))`` for a nonconstant rational ``R`` with
    algebraic coefficients, with no pole at an algebraic ``a != 0``: a value
    ``b`` algebraic there would make ``exp(I*a)`` a root of ``R - b``,
    algebraic, against Lindemann-Weierstrass."""
    return rows((Q.algebraic(x) & ~Q.zero(x)) >> Q.transcendental(f(x)))


LINDEMANN = (sin, cos, tan, cot, sec, csc)


PROPERTIES = (
    (entire, ENTIRE),
    (real_meromorphic, REAL_MEROMORPHIC),
    (nonvanishing, NONVANISHING),
    (imaginary_axis, IMAGINARY_AXIS),
    (lindemann, LINDEMANN),
)


def rows_of(f) -> Rows:
    """The rows of the properties ``f`` has."""
    out = Rows()
    for prop, members in PROPERTIES:
        if f in members:
            out = out + prop(f)
    return out
