"""Integration checks written while verifying the DPLL(T) merge (af60a09).

They pin properties that span several agents' modules: import hygiene of
the SymPy-free core, the default adapter wiring, per-session ownership of
theories, the relations-off path, the adapters' number rules, and the
solver's root-unit reporting.
"""
import subprocess
import sys

import pytest
from sympy import Float, Function, Q, pi, symbols

from satassume import Engine
from satassume.solver import Solver
from satassume.sympy_api import ask, out_of_scope

r, s, t = symbols("r s t", real=True)
x, y = symbols("x y")
f = Function("f")


# ----------------------------------------------------------------------
# import hygiene
# ----------------------------------------------------------------------

@pytest.mark.parametrize("mod", ["solver", "theory", "lra", "euf", "relations", "engine"])
def test_core_modules_import_no_sympy(mod):
    code = f"import sys, satassume.{mod}; print('sympy' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         check=True)
    assert out.stdout.strip() == "False"


# ----------------------------------------------------------------------
# wiring
# ----------------------------------------------------------------------

def test_default_specs_are_guarded_lra_and_unguarded_euf():
    specs = [(sp.name, sp.guarded) for sp in Engine().relation_specs]
    assert specs == [("lra", True), ("euf", False)]


def test_relations_off_gives_old_behaviour_and_same_unary_answers():
    on, off = Engine(), Engine(relations=[])
    unary = [(Q.positive(r + 1), Q.positive(r)), (Q.even(x + 1), Q.odd(x)),
             (Q.real(x * y), Q.real(x) & Q.real(y)), (Q.positive(x), Q.real(x))]
    for p, a in unary:
        assert ask(p, a, engine=on) == ask(p, a, engine=off)
    assert ask(Q.positive(r), Q.gt(r, 0), engine=off) is None
    assert ask(Q.positive(r), Q.gt(r, 0), engine=on) is True


def test_each_context_session_owns_its_adapters_and_theories():
    eng = Engine()
    assert ask(Q.lt(r, t), Q.lt(r, s) & Q.lt(s, t), engine=eng) is True
    assert ask(Q.gt(r, 0), Q.gt(r, 1), engine=eng) is True
    sessions = [sess for sess, _ in eng._context_sessions.values()]
    assert len(sessions) == 2
    ads = [sess.relations.adapters for sess in sessions]
    for name in ("lra",):
        assert ads[0][name] is not ads[1][name]
        assert ads[0][name].theory is not ads[1][name].theory
    for sess in sessions:
        for th in sess.solver.theories():
            assert sum(th in other.solver.theories() for other in sessions) == 1


def test_theory_levels_match_the_solver_after_ask():
    # Between public calls the solver may hold assumption levels (also with
    # theories attached, see Solver._assume); every theory must then be at
    # the same level, and at 0 once the solver is back at root.
    eng = Engine()
    ask(Q.eq(f(r), f(s)), Q.le(r, s) & Q.le(s, r), engine=eng)
    ask(Q.lt(r, 3), Q.lt(r, s) & Q.lt(s, 2) & Q.ne(r, 0), engine=eng)
    held = 0
    for sess, _ in eng._context_sessions.values():
        solver = sess.solver
        held += bool(solver._trail_lim)
        for th in solver.theories():
            assert len(th._lims) == len(solver._trail_lim), th
        solver.propagate() if solver._held is None else solver._backtrack(0)
        for th in solver.theories():
            assert not th._lims, th
    assert held


def test_uninterpreted_assumption_is_none_and_not_cached():
    eng = Engine()
    assum = Q.gt(r, 0) & Q.lt(pi * r, 1)  # LRA refuses pi*r, EUF takes no lt
    assert ask(Q.positive(r), assum, engine=eng) is None
    assert ask(Q.positive(r), assum, engine=eng) is None
    assert not eng._context_sessions


def test_readme_usage_example():
    # README: "ask(Q.positive(y), Q.gt(y, 0))  # None"; still None, but now
    # because y may be non-real (the LRA guard), not because relations are
    # out of scope.  out_of_scope keeps reporting the category.
    assert ask(Q.positive(y), Q.gt(y, 0)) is None
    assert out_of_scope(Q.positive(y), Q.gt(y, 0)) == "relation"
    assert ask(Q.positive(y), Q.gt(y, 0) & Q.real(y)) is True


def test_sharing_example_needs_real_arguments():
    # the design note's section 5.4 example; with plain symbols the guard
    # keeps LRA out, so sharing cannot fire
    assert ask(Q.eq(f(r), f(s)), (r <= s) & (s <= r)) is True
    assert ask(Q.eq(f(x), f(y)), (x <= y) & (y <= x)) is None


# ----------------------------------------------------------------------
# the adapters' number rules
# ----------------------------------------------------------------------

def test_float_is_uninterpreted_by_lra_and_opaque_to_euf():
    from satassume.euf_adapter import EUFAdapter
    from satassume.lra_adapter import to_constraint
    assert to_constraint(Q.lt(r, Float(0.5))) is None
    assert EUFAdapter.parse(Q.eq(x, Float(1.0))) is not None
    # opaque, not a distinct value: Eq(x, 1.0) must not refute Eq(x, 1)
    assert ask(Q.eq(x, 1), Q.eq(x, Float(1.0))) is not False
    assert ask(Q.ne(x, 1), Q.eq(x, Float(1.0))) is not True
    # rationals are distinct values
    assert ask(Q.eq(x, 2), Q.eq(x, 1)) is False


def test_non_real_and_infinite_arguments_stay_undecided():
    from sympy import I, oo
    assert ask(Q.lt(I, 1)) is None
    assert ask(Q.lt(r, oo)) is None           # LRA refuses oo (SymPy: True)
    assert ask(Q.le(x, y), Q.gt(x, y)) is False   # <= is the complement of reversed <
    assert ask(Q.lt(x, y), Q.lt(x, 0) & Q.lt(0, y)) is None   # x, y may be non-real


# ----------------------------------------------------------------------
# solver reporting
# ----------------------------------------------------------------------

class _Log:
    def __init__(self):
        self.log = []

    def register_atom(self, v, p):
        self.log.append(("reg", v))

    def assert_lit(self, lit):
        self.log.append(("assert", lit))

    def check(self):
        return None

    def push_level(self):
        self.log.append("push")

    def pop_level(self):
        self.log.append("pop")


def test_root_unit_from_add_clause_is_reported_once_by_next_propagate():
    sv, th = Solver(), _Log()
    sv.attach_theory(th)
    sv.register_atom(th, 1, None)
    sv.add_clause([1])
    assert ("assert", 1) not in th.log        # lazy: add_clause does not report
    sv.register_atom(th, 2, None)
    # NB: the design note (section 2, item 3) says register_atom reports
    # pending root units; it does not, only the next propagating call does.
    assert ("assert", 1) not in th.log
    assert sv.propagate()
    assert sv.solve()
    assert sv.implied([2]) is not None
    assert th.log.count(("assert", 1)) == 1


def test_register_atom_on_var_already_reported_at_root_asserts_at_once():
    sv, th = Solver(), _Log()
    sv.attach_theory(th)
    sv.ensure_vars(2)
    sv.register_atom(th, 1, None)
    sv.add_clause([2])
    sv.add_clause([-1])
    assert sv.propagate()                      # cursor now past both units
    th2 = _Log()
    sv.attach_theory(th2)
    sv.register_atom(th2, 1, None)
    assert th2.log == [("reg", 1), ("assert", -1)]


def test_lra_adapter_refuses_a_second_solver():
    from satassume.lra_adapter import LRAAdapter
    ad = LRAAdapter()
    s1, s2 = Solver(), Solver()
    s1.ensure_vars(2)
    s2.ensure_vars(2)
    ad.register(s1, 1, Q.lt(r, 0))
    with pytest.raises(ValueError):
        ad.register(s2, 2, Q.gt(r, 1))
