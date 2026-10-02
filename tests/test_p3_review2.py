"""Second-review test for #97 P3 (branch ``issue-97/p3-theory-scope`` at
738bf76, P3-fix1).  Expected to fail there; see ``reports/p3-review2.md``.
"""
from sympy import S, Symbol, symbols

from satassume import extensions as X
from satassume.engine import DictCache, Engine, INCONSISTENT
from satassume.formula import And, Implies, P

x, y = symbols("x y")


def test_the_sets_check_interprets_the_relation_atoms_of_its_extension_facts():
    """``docs/spec.md`` section 3 and ``Engine._build_context``: the set's
    check "assumes only the set's own glue", and ``Engine.verdict`` is the
    result of the complete check.  A set whose relation atoms come from an
    extension fact (in the scope since P3-fix1, ``scope.extension_atoms``)
    is its own glue too; but ``Session.assume_formula`` tests the set's
    glue syntactically, so the atoms stay queued and uninterpreted through
    the check, and an inconsistent set gets the verdict CONSISTENT (the
    lazy order at d474399, and every ``ask`` under the set, say
    inconsistent)."""
    X.register("big", Symbol)(lambda s: Implies(
        P("big", s), And(P("lt", (S.One, s)), P("lt", (s, S.Zero)))))
    try:
        e = Engine(cache=DictCache(), relevance=False)
        assert e.verdict(P("big", x)) is INCONSISTENT
        assert e.verdict(And(P("big", x), P("nonzero", y))) is INCONSISTENT
    finally:
        X.unregister("big")
