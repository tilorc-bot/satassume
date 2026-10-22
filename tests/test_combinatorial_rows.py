"""The rules of ``factorial2``, ``subfactorial``, ``catalan``, ``andre``,
``partition``, ``genocchi``, ``RisingFactorial``, ``FallingFactorial`` and
``binomial``, written as ``for_all`` statements
(``templates/combinatorial.py``, compiled by ``templates/wiring.py``,
#249), against the generators they replace
(``tests/_legacy_combinatorial_rules.py``, verbatim from d149951).

The comparison is ``tests/_rows_equivalence.py``'s: the rows and the
legacy generators plus :data:`ADDED` entail each other on every node of
its corpus (the functions of two arguments on every pair of arguments),
though the clauses differ.  Both sides get the hooks of ``wiring.py``: the
facts of the value at a constant integer argument
(``wiring.VALUE_AT_INTEGER``) and ``genocchi``'s rules about ``n/2``
(``wiring.HALF_ARGUMENT``), which are not rows.  Rows of the legacy
generators the rows leave out because the rule base and the other rows
imply them: ``subfactorial``'s ``integer & nonnegative -> integer`` (the
parity rows: an even or odd value), ``factorial2``'s ``odd -> ~zero`` (not
even there, and 0 is even), and ``partition``'s ``integer ->
nonnegative`` (0 at a negative integer, positive at a nonnegative one).
:data:`ADDED` are the facts the rows give that the legacy rules did not,
each with its argument; a test checks that each is new.
"""
import os
import subprocess
import sys

import pytest

pytest.importorskip("sympy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _legacy_combinatorial_rules as legacy  # noqa: E402
import _rows_equivalence as eq  # noqa: E402
from sympy import (  # noqa: E402
    FallingFactorial, Integer, Q, RisingFactorial, Symbol, andre, binomial, catalan, factorial2,
    genocchi, partition, subfactorial,
)

from satassume.knowledge.templates import _common, wiring  # noqa: E402

HEADS = (factorial2, subfactorial, catalan, andre, partition, genocchi,
         RisingFactorial, FallingFactorial, binomial)

#: facts the rows give and the legacy rules did not
ADDED = {}


def _shifts(gen, *shifts):
    """``gen`` with the terms ``x + c`` its slots 2, 3, ... are (the legacy
    ``slots=``), which ``wiring.template`` takes from ``gen.shifts``."""
    def shifted_gen(R, c):
        gen(R, c)
    shifted_gen.shifts = shifts
    return shifted_gen


def _nary(gen, arity):
    """``gen`` as ``functions.nary`` called it, with the number of
    arguments, which ``wiring.template`` takes from ``gen.arity``."""
    def nary_gen(R, c):
        gen(R, arity)
    nary_gen.arity = arity
    return nary_gen


LEGACY_GEN = {
    factorial2: _shifts(legacy._factorial2, 1, 3),
    subfactorial: legacy._subfactorial,
    catalan: _shifts(legacy._catalan, -3),
    andre: legacy._andre,
    partition: legacy._partition,
    # slot 3, n/2, is added by wiring.HALF_ARGUMENT
    genocchi: _shifts(legacy._genocchi, -1),
    RisingFactorial: _nary(lambda R, n: legacy._rising_falling(R, n, True), 2),
    FallingFactorial: _nary(lambda R, n: legacy._rising_falling(R, n, False), 2),
    binomial: _nary(legacy._binomial, 2),
}


def test_rows_entail_exactly_the_legacy_rules_and_the_added_facts():
    new = eq.check_rows_entail_exactly(HEADS, "combinatorial", LEGACY_GEN, ADDED)
    # the slots x + 1 and x + 3 of factorial2, x - 1 and n/2 of genocchi
    n = Symbol('x')
    objs = {type(e): c.objs for e, (cs, _) in new.items() if e.args == (n,) for c in cs}
    assert objs[factorial2] == (n, factorial2(n), n + 1, n + 3)
    assert objs[genocchi] == (n, genocchi(n), n - 1, n/2)
    assert objs[catalan] == (n, catalan(n), n - 3)
    # the facts of the value at a constant integer argument: a second block
    assert all(len(cs) == 2 for e, (cs, _) in new.items()
               if e.args == (Integer(2),) and type(e) in wiring.VALUE_AT_INTEGER)


def test_each_added_fact_is_new():
    eq.check_added_are_new(LEGACY_GEN, ADDED)


def test_genocchi_has_the_sign_of_the_parity_of_half_the_argument():
    # G_2k has the sign (-1)**k (wiring.HALF_ARGUMENT): its rules are in
    # the template of the rows, in the slot after x - 1
    n = Symbol('n')
    _common._CACHE.clear()
    templates = eq.rows_templates((genocchi,), "combinatorial")
    [c], _ = eq.compiled(templates, genocchi(n, evaluate=False))
    assert c.objs[3] == n/2
    _common._CACHE.clear()


def test_combinatorial_is_compiled_on_its_own_first_use():
    code = """
import sys
from sympy import (FallingFactorial, Q, RisingFactorial, Symbol, andre, binomial, catalan,
                   factorial2, genocchi, partition, subfactorial)
from satassume.knowledge.templates.registry import registry
from satassume.sympy_api import ask
COMB = "satassume.knowledge.templates.combinatorial"
INTEGER = "satassume.knowledge.templates.integer_funcs"
WIRING = "satassume.knowledge.templates.wiring"
n, k = Symbol('n'), Symbol('k')
assert ask(Q.integer(catalan(n)), Q.integer(n) & Q.nonnegative(n)) is True
pending = {m for _, m in registry._lazy}
assert WIRING + ":combinatorial" not in pending and WIRING + ":integer_funcs" in pending
# the rows are read compiled: no family module is imported
assert COMB not in sys.modules and INTEGER not in sys.modules
for h in (factorial2, subfactorial, catalan, andre, partition, genocchi,
          RisingFactorial, FallingFactorial, binomial):
    assert [t.__module__ for t in registry._by_class[h]] == [WIRING + ":combinatorial"]
assert ask(Q.composite(catalan(n)), Q.integer(n) & Q.positive(n - 3)) is True
assert ask(Q.zero(binomial(n, k)), Q.integer(k) & Q.negative(k)) is True
assert ask(Q.negative(genocchi(n)), Q.even(n) & Q.positive(n) & Q.odd(n/2)) is True
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
