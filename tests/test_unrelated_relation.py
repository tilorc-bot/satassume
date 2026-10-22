"""An unrelated relation in the assumptions (#261).

A relation atom anywhere in ``(p, A)`` starts the relation glue for the
whole set (spec section 3): the set is certified by one verdict whose
session links every vocabulary argument (``sympy_api._relevant``,
``satassume.relations``, "Links to the unary vocabulary").  A set without
one is certified per component, with no glue.  The glue knows more than
the rule base: clause 2 of an ``lt`` atom (an ``oo`` summand pushes its
side) refutes the link atom ``0 < y - oo``, which the templates
deliberately leave open (``test_infinite_sums.py``,
``test_extended_real_sum_keeps_its_sign_undecided``), and LRA bounds
``k - x + 1``, which the sum templates do not.

So a fresh-symbol relation such as ``a > b`` can make an *inconsistent* set
raise where it answered before, in the engine and in ``ask_ref`` alike.
That is allowed: I2's oracle (harness/INVARIANTS.md) compares answers
only under a consistent set and never counts an inconsistency report.
Under a consistent set the relation changes nothing.
"""
import pytest
from sympy import Dummy, E, Q, oo, sqrt, symbols

from harness import reffuzz as R
from satassume.engine import Engine
from satassume.ref import ask_ref
from satassume.sympy_api import ask

w, x, y, z, k = symbols("w x y z k")
a, b = Dummy("a"), Dummy("b")

#: satisfiable over symbols no query or set below mentions (a = 2, b = 1)
PADS = (a > b, a <= 3, Q.eq(a, b + 1), Q.ne(a, 0) & Q.lt(b, a))


def eng(p, A):
    try:
        return ask(p, A, Engine())
    except ValueError:
        return "ValueError"


def ref(p, A):
    try:
        return ask_ref(p, A)
    except ValueError:
        return "ValueError"


# Each set is inconsistent.  For a value v of y: v finite real gives
# y + oo = oo and y - oo = -oo; v = oo gives oo and nan; v = -oo gives nan
# and -oo; any other v (finite non-real, zoo, an infinity off the real axis)
# gives a sum that is no extended real.  So y + oo is never an extended
# negative (A1: extended_nonzero and not extended_nonnegative) and y - oo
# never an extended positive (A2).  A3: k <= -1 and x >= 1 are integers, so
# k - x + 1 <= -1 is not zero.
A1 = Q.extended_nonzero(y + oo) & ~Q.extended_nonnegative(y + oo)
A2 = Q.extended_nonnegative(y - oo) & Q.extended_positive(y - oo)
A3 = Q.integer(k) & Q.integer(x) & Q.negative(k) & Q.positive(x) & Q.zero(k - x + 1)


@pytest.mark.parametrize("p, A, before", [
    # the #261 reproducers
    (Q.finite(w) & ~Q.negative(y + oo), A1, None),
    (Q.nonpositive(E) & Q.lt(sqrt(x), z), A2, False),
    (Q.positive(y), A2, False),
    # the same channel without an infinity: LRA bounds the sum
    (Q.positive(x), A3, True),
    (Q.finite(w) & Q.positive(x), A3, None),
])
def test_inconsistent_sets_raise_with_a_relation(p, A, before):
    # without a relation the set's check misses the inconsistency; with one
    # it is found, as the spec (ask_ref) finds it
    assert eng(p, A) == before
    for pad in PADS:
        assert eng(p, A & pad) == "ValueError"
        assert ref(p, A & pad) == "ValueError"


@pytest.mark.parametrize("p, a_, eng_, ref_, why", R.KNOWN,
                         ids=[str(i) for i in range(len(R.KNOWN))])
def test_known_sets_padded(p, a_, eng_, ref_, why):
    """I2 over the KNOWN sets of ``harness/reffuzz.py`` (all inconsistent):
    a fresh relation keeps the engine's answer or makes it an inconsistency
    report that the spec gives too."""
    P, A = R.parse(p), R.parse(a_)
    assert str(eng(P, A)) == eng_       # KNOWN records answers as strings
    for pad in PADS:
        e = str(eng(P, A & pad))
        assert e == eng_ or (e == "ValueError" and ref(P, A & pad) == "ValueError"), pad


# Consistent sets around the reproducers, each with a witness: y = 0
# (y - oo = -oo, an extended real, infinite, nonzero, negative), y = I
# (I - oo is infinite and no extended real, so not an extended negative),
# and k = -1, x = 1 (k + x = 0).
@pytest.mark.parametrize("A", [
    Q.extended_real(y - oo),
    Q.infinite(y - oo),
    Q.extended_nonzero(y - oo),
    Q.extended_real(y) & Q.infinite(y - oo),
    Q.infinite(y - oo) & ~Q.extended_negative(y - oo),
    Q.extended_real(y + oo) & Q.extended_nonzero(y + oo),
    Q.integer(k) & Q.integer(x) & Q.negative(k) & Q.positive(x) & Q.zero(k + x),
])
@pytest.mark.parametrize("p", [
    Q.positive(y),
    Q.extended_real(y),
    Q.extended_nonnegative(y - oo),
    Q.negative_infinite(y - oo),
    Q.finite(w) & ~Q.negative(y + oo),
    Q.positive(x),
    Q.finite(w) & Q.positive(x),
    Q.nonpositive(E) & Q.lt(sqrt(x), z),
])
def test_consistent_sets_keep_their_answers(p, A):
    before = eng(p, A)
    assert before != "ValueError"
    for pad in PADS:
        assert eng(p, A & pad) == before, pad
