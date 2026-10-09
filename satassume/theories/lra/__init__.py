"""Linear real arithmetic.  Hides exact arithmetic over symbolic constants.

SymPy-free core: the theory (:mod:`.lra`), its certificate for payloads
with constants (:mod:`.lra_cert`, imported by :mod:`.lra` only inside
functions, because only such payloads need it) and the field of closed
real constants it computes in (:mod:`.constfield`; its conversions from
and to SymPy import SymPy inside functions).

SymPy side: the adapter from SymPy relations (:mod:`.lra_adapter`) and
the rigorous bounds of SymPy constants (:mod:`.lra_bounds`).  Both import
SymPy at module level.  :mod:`.lra_bounds` (which also uses mpmath, inside
functions) is imported only inside functions, by :mod:`.constfield` and
:mod:`.lra_adapter`: only a query with such a constant needs it, and
:mod:`.constfield` must stay importable without SymPy.

May import the layers below :mod:`satassume.theories`; not the other
theories.
"""
