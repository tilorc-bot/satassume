"""Per-family generation settings (offline), kept out of the family modules so
that importing a family imports nothing offline: the assumption profiles the
generator tries per variable where a family needs more than the default
:data:`.specialize.CATALOG`, the extra points generated rules are checked at,
and the families without a generated table.
"""
from __future__ import annotations

from sympy import Q, S

from .specialize import CATALOG, Literal

CATALOGS: dict = {
    "power_exp_log": {None: CATALOG + [lambda v: ~Q.zero(v)],       # the log rows' domains speak of b != 0
                      "e": CATALOG + [Literal(-1), Literal(2)]},     # log(1/b), log(b**2)
    "inverse": CATALOG + [Q.extended_real],   # asinh/atanh/acoth of their functions hold at +-oo
}
"""``family -> catalog``: a list (every variable) or a dict ``{variable name: list}``
with ``None`` as the default key (see :data:`.specialize.CATALOG`)."""

EDGE_POINTS: dict = {
    "integer_funcs": (S(2), S(-2)),   # Rem(1, 2) has 2*a/b odd
    "inverse": (S.Infinity, S.NegativeInfinity),   # rows over the extended reals (acsch(csch(oo)) = zoo)
}
"""``family -> points``: values every generated rule of the family is checked at, in
addition to :data:`.verify.EDGE_POINTS` (the family's branch-cut points)."""

NOT_GENERATED: frozenset = frozenset({
    "minmax_deltas",   # a definition is decided in about 2 ms live
})
"""Families with identity rows but no generated table (definitions that are cheap to
evaluate live and have no bookkeeping to collapse)."""
