"""Per-family generation settings (offline): the assumption profiles the
generator tries per variable, where a family needs more than the default
:data:`.specialize.CATALOG`.  (Moved out of the family modules so that importing
a family imports nothing offline; step 3 of issue #13 moves the other
generation settings, ``EDGE_POINTS`` and ``SPECIALIZE``, here too.)
"""
from __future__ import annotations

from sympy import Q

from .specialize import CATALOG, Literal

CATALOGS: dict = {
    "power_exp_log": {None: CATALOG + [lambda v: ~Q.zero(v)],       # the log rows' domains speak of b != 0
                      "e": CATALOG + [Literal(-1), Literal(2)]},     # log(1/b), log(b**2)
}
"""``family -> catalog``: a list (every variable) or a dict ``{variable name: list}``
with ``None`` as the default key (see :data:`.specialize.CATALOG`)."""
