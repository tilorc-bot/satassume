"""The theory scope of a query is a pure function of its syntax
(``satassume.scope.theory_scope``, #97 P3), and a session is built with it:
the relation glue and predicate transfer exist from construction iff the
scope says so, and no path of ``Engine.ask`` switches either on later."""
import pytest
from sympy import Function, Q, S, pi, sqrt, symbols

from satassume.engine import DictCache, Engine
from satassume.formula import And, Not, Or, P
from satassume.scope import (EMPTY, Scope, affine_pair, linked_terms, theory_scope,
                             transfer_wanted)
from satassume.sympy_api import _formula, ask

x, y, z = symbols("x y z")
f = Function("f")


def F(expr):
    return _formula(expr, True, True)


def eng():
    return Engine(cache=DictCache(), relevance=False)


# -- the pure function ----------------------------------------------------------

def test_empty_without_relations_or_sum_pairs():
    assert theory_scope(None, None) is EMPTY
    assert theory_scope(F(Q.positive(x)), F(Q.negative(y))) is EMPTY
    # one sum, or two sums over disjoint symbols: no pair
    assert theory_scope(F(Q.positive(x - 1)), F(Q.positive(x - 1))) is EMPTY
    assert theory_scope(F(Q.positive(x - 1)), F(Q.negative(y - 1))) is EMPTY
    # a sum without symbols is no pair with anything
    assert theory_scope(F(Q.positive(pi + 1)), F(Q.positive(pi - x))) is EMPTY


def test_glue_from_a_relation_atom_on_either_side():
    a, p = F(Q.lt(x, 1)), F(Q.positive(y))
    s = theory_scope(a, p)
    assert s == Scope(True, False, frozenset({x, y}))
    assert theory_scope(p, a) == s
    assert theory_scope(None, a).linked_terms == frozenset({x})
    # a negated or disjoined relation counts the same (atoms, not polarity)
    assert theory_scope(F(Q.positive(y) | ~Q.lt(x, 1)), None).glue


def test_glue_from_a_sign_on_sum_pair_across_both_formulas():
    a, p = F(Q.positive(x - 1)), F(Q.negative(1 - x))
    assert theory_scope(a, p) == Scope(True, False, frozenset({x - 1, 1 - x}))
    assert theory_scope(And(a, p), None).glue and theory_scope(None, And(a, p)).glue
    # the pair needs sign predicates on Add nodes sharing a symbol
    assert not theory_scope(F(Q.real(x - 1)), F(Q.positive(1 - x))).glue
    assert not theory_scope(F(Q.positive(2 * x)), F(Q.positive(x + 1))).glue
    assert theory_scope(F(Q.nonzero(x + y)), F(Q.extended_nonnegative(y - z))).glue


def test_transfer_from_an_equality_or_a_trichotomy_pair():
    assert theory_scope(F(Q.eq(x, 2)), None) == Scope(True, True, frozenset({x}))
    assert theory_scope(None, F(Q.ne(x, y))).transfer          # ne is ~eq
    assert not theory_scope(F(Q.lt(0, x)), F(Q.positive(y))).transfer
    # an order atom and its reverse make an equality (Relations._trichotomy)
    assert theory_scope(F(Q.le(x, y)), F(Q.ge(x, y))).transfer
    assert theory_scope(F(Q.lt(x, y)), F(Q.gt(x, y))).transfer
    assert not theory_scope(F(Q.lt(x, y)), F(Q.lt(y, z))).transfer
    # transfer implies glue; never from a sum pair alone
    s = theory_scope(F(Q.positive(x - 1)), F(Q.negative(1 - x)))
    assert s.glue and not s.transfer


def test_linked_terms_are_arguments_and_sides_without_numbers():
    a = F(Q.eq(x + 1, 2) & Q.positive(sqrt(2)) & Q.positive(f(x)) & Q.lt(pi, 4))
    s = theory_scope(a, F(Q.zero(y)))
    assert s.linked_terms == frozenset({x + 1, f(x), y})
    assert linked_terms(()) == frozenset()


def test_helpers_are_syntactic():
    atoms = (P("lt", (x, y)), P("lt", (y, x)))
    assert transfer_wanted(atoms) and not transfer_wanted(atoms[:1])
    assert affine_pair((P("positive", x - 1), P("negative", 1 - x)))
    assert not affine_pair((P("positive", x - 1), P("negative", x - 1)))


# -- the session is built with it ------------------------------------------------

def _session(e, p, a):
    """The session ``Engine.ask`` builds for ``p`` under ``a`` (#97 P1),
    built the same way and kept for inspection."""
    q = _formula(p, True)
    s, lits = e._build_context(F(a), q)
    e._ask(s, lits, q, True)
    return s


def test_glue_and_transfer_exist_from_construction():
    e = eng()
    # a unary query under a unary set: no glue at all
    s = _session(e, Q.positive(x), Q.positive(y))
    assert s.scope is EMPTY and s.relations is None and s.xfer is None
    # a relation in the query: the glue exists before the set is compiled,
    # and links the set's terms as a fresh engine for the query does
    s = _session(e, Q.lt(0, x), Q.positive(y))
    assert s.scope.glue and s.relations is not None and s.relations.active
    assert y in s.relations.linked and x in s.relations.linked
    assert s.xfer is None
    # an equality: transfer engaged at construction
    s = _session(e, Q.prime(x), Q.eq(x, 2))
    assert s.scope.transfer and s.xfer is not None
    assert s.relations.xfer_sel is not None
    # the trichotomy pair, split over set and query
    s = _session(e, Q.ge(x, y), Q.le(x, y))
    assert s.scope.transfer and s.xfer is not None
    assert e.stats["scope_misses"] == 0


def test_no_lazy_engagement_on_the_ask_path():
    """Every query answered through ``Engine.ask`` (contextual, context-free,
    custom and relation atoms) runs in a session whose scope covered it:
    the fallback paths (glue at the first relation atom, transfer at the
    first user equality) are never taken."""
    e = eng()
    cases = [
        (Q.positive(x), None), (Q.lt(0, x), None), (Q.eq(x, 2), None),
        (Q.positive(x + 1), Q.positive(x - 1) & Q.negative(1 - x)),
        (Q.negative(1 - x), Q.positive(x - 1)),
        (Q.prime(x), Q.eq(x, 2)), (Q.positive(f(x)), Q.zero(x) & Q.positive(f(0))),
        (Q.positive(y), Q.lt(x, y) & Q.positive(x)), (Q.ge(x, y), Q.le(x, y)),
        (Q.zero(x - y), Q.nonnegative(x - y) & Q.nonpositive(x - y)),
        (Q.lt(x, 3), Q.lt(x, 1) | Q.lt(x, 2)), (Q.ne(x, y), Q.positive(x) & Q.negative(y)),
    ]
    for p, a in cases:
        ask(p, a, e)
    assert e.stats["scope_misses"] == 0
    assert e.stats["queries"] >= len(cases)


def test_scope_outside_the_query_is_counted():
    """A session built for the set alone and then asked a relation takes
    the fallback and is counted (the harness and tests do this)."""
    e = eng()
    s, lits = e._build_context(F(Q.positive(y)))
    assert s.relations is None
    e._ask(s, lits, _formula(Q.lt(0, x), True), True)
    assert s.relations is not None and e.stats["scope_misses"] == 1
    s, lits = e._build_context(F(Q.lt(0, y)))
    assert s.relations is not None and s.xfer is None
    e._ask(s, lits, _formula(Q.eq(x, 2), True), True)
    assert s.xfer is not None and e.stats["scope_misses"] == 2


def test_answers_agree_with_the_lazy_order():
    """The scope at construction answers what the lazily switched-on glue
    answered (the observers of harness/lazy.py: linear relatives of the
    set's terms, congruent applications)."""
    e = eng()
    assert ask(Q.positive(x + y), Q.positive(x + y - 1) & Q.real(x) & Q.real(y), e) is True
    assert ask(Q.positive(x - 3), Q.positive(x - pi), e) is True
    assert ask(Q.zero(x - y), Q.nonnegative(x - y) & Q.nonnegative(y - x) & Q.real(x)
               & Q.real(y), e) is True
    assert ask(Q.positive(f(x)), Q.eq(x, 0) & Q.positive(f(0)), e) is True
    assert ask(Q.prime(x), Q.eq(x, 2), e) is True
    assert ask(Q.eq(x, y), Q.le(x, y) & Q.ge(x, y), e) is True
    with pytest.raises(ValueError):          # inconsistent assumptions
        ask(Q.positive(x), Q.positive(x + y - 1) & Q.negative(x + y) & Q.real(x) & Q.real(y), e)


def test_relevance_uses_the_scope_for_sum_pairs():
    """``_relevant`` treats a set whose sign atoms on sums start the glue
    like a relational one (the whole set's verdict decides raising)."""
    from sympy import besselj
    bj = lambda t: besselj(1, t)
    e = Engine(cache=DictCache(), relevance=True)
    a = (Q.zero(x) & Q.zero(y) & Q.zero(bj(y)) & Q.nonzero(bj(x)) & Q.positive(z - 1)
         & Q.negative(z - 3))
    with pytest.raises(ValueError):
        ask(Q.positive(z), a, e)
    assert ask(Q.zero(bj(x)), Q.zero(x) & Q.zero(y) & Q.zero(bj(y)), e) in (None, True)
