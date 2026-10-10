"""Layer 3 of :mod:`satassume`: the DPLL(T) theories.

Linear real arithmetic (:mod:`.lra`), equality with uninterpreted
functions (:mod:`.euf`), predicate transfer across equal terms
(:mod:`.transfer`) and the signs and ring/field memberships of sums and products
(:mod:`.sign`: SIGN and CLOSURE).  Hides how relation atoms are decided: each theory
implements the contract of :mod:`satassume.sat.theory` and is told its
atoms and terms by the layer above.  Which theories a session gets, how
SymPy relations become relation atoms and how those are linked to the
unary predicates is decided above, in :mod:`satassume.relations` and
:mod:`satassume.scope`.

May import :mod:`satassume.state`, :mod:`satassume.sat` and
:mod:`satassume.knowledge`.  The theories do not import each other (nor
this package's ``__init__``).

SymPy: each theory has a SymPy-free decision procedure and, where it
reads SymPy terms, an adapter module that does: ``lra/lra_adapter`` and
``lra/lra_bounds``, ``euf/euf_adapter``, ``sign/sign_adapter``.  :mod:`.transfer` works on atoms
only.  Adding a theory: docs/design.md, "Adding a theory".
"""
