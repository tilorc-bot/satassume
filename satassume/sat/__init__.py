"""Layer 1 of :mod:`satassume`: propositional logic and CDCL search.

Formulas over atoms (:mod:`.formula`), the incremental CDCL solver
(:mod:`.solver`) and the DPLL(T) contract a theory implements
(:mod:`.theory`).  Hides the search: how clauses, assumptions and theory
lemmas are decided, independent of what the atoms mean.  No predicate
vocabulary here.

May import :mod:`satassume.state` only.  No SymPy, not even inside
functions: atoms are opaque hashable objects.
"""
