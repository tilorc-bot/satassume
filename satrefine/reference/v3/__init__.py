"""Refine handlers, third implementation: one module per handler family,
each written by a separate agent that never saw the other implementations.

The reference the identity handlers are measured against: the battery
(``tests/refine_identities/battery_v3.py``) was captured from it, and the
scoreboard and the differential compare with it.  It was
``satrefine/handlers_v3`` until phase 3.

Select with ``SATREFINE_HANDLERS=handlers_v3`` (:mod:`satrefine.handlers_v3`
is an alias of this package).  Every public module in this package is
imported by :mod:`satrefine` and registers its keys into
``satrefine.identities.compat.upstream.handlers_dict`` at import time.
Shared helpers live in :mod:`satrefine.reference.v3._common`.

Families and their modules:

``power_exp_log``   Pow, exp, log
``inverse``         asin, acos, atan, atan2, asinh, acosh, atanh, acoth, asech, acsch
``complex_parts``   re, im, arg, sign, Abs, conjugate, Mul
``trig``            sin, cos, tan, cot, sec, csc, sinc
``hyperbolic``      sinh, cosh, tanh, coth, sech, csch
``integer_funcs``   floor, ceiling, frac, Mod, Rem
``combinatorial``   factorial, binomial, RisingFactorial, FallingFactorial, gamma
``minmax_deltas``   Min, Max, DiracDelta, KroneckerDelta, Heaviside
``matrices``        Determinant, HadamardProduct, Inverse, MatAdd, MatMul, MatrixElement, Trace, Transpose
"""
