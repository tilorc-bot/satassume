"""Layer 2 of :mod:`satassume`: what is known about predicates and terms.

The unary predicate vocabulary and its rule base (:mod:`.rules`), the
structural templates per expression class (:mod:`.templates`), the user
extensions (:mod:`.extensions`), the domain all of these hold on
(:mod:`.domain`) and their encoding as clauses (:mod:`.compile`).  Hides
the knowledge and its clause encoding: the layers above ask for facts and
clauses, never for how a rule is written down.

May import :mod:`satassume.state` and :mod:`satassume.sat`.

SymPy: :mod:`.rules`, :mod:`.compile` and :mod:`.extensions` are about
predicates and atoms and never import SymPy.  :mod:`.templates` (the
knowledge per SymPy expression class) and :mod:`.domain` (which SymPy
terms are commutative scalars) are where SymPy classes are read, and
import it at module level; the engine imports both only inside
functions, so ``import satassume`` stays SymPy-free.
"""
