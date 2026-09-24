"""``log`` from two facts and two exponential forms.

The facts: ``log`` inverts ``exp`` up to the principal branch, and the
complex logarithm is the real logarithm of the modulus plus ``I`` times the
argument.  The exponential forms are not about ``log``: a power is
``exp(e*log(b))`` and a product is ``exp(log(p) + log(r))``.  Composing the
first fact with each form (see :func:`._engine.derive`) gives the rows for
``log(b**e)`` and ``log(p*r)``; the negated-pair product rule follows from
the product row and the second fact, so it is not written.

Every conditional rule of the procedural handlers is one of these rows with
its bookkeeping collapsed under an assumption profile; see
``tools/refine_specialize.py`` for that table.
"""
from __future__ import annotations

from sympy import Abs, I, Q, arg, exp, log, symbols, true

from .._upstream import handlers_dict
from ._engine import Row, derive, identity_handler, principal

z, b, e, p, r, x = symbols('z b e p r x')

FACTS: list[Row] = [   # (lhs, rhs, domain): lhs == rhs wherever the domain holds
    (log(exp(z)), principal(z),            true),
    (log(x),      log(Abs(x)) + I*arg(x),  ~Q.zero(x)),
]

EXP_FORMS: list[Row] = [   # (L, W, domain): L == exp(W) wherever the domain holds
    (b**e, e*log(b),         ~Q.zero(b)),
    (p*r,  log(p) + log(r),  ~Q.zero(p) & ~Q.zero(r)),
]

IDENTITIES: list[Row] = derive(FACTS, EXP_FORMS)
LOG_FACTS = FACTS   # older name

refine_log = identity_handler(IDENTITIES)

handlers_dict['log'] = refine_log
