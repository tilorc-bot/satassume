"""Reusable harness for testing theory solvers against satassume's Solver.

Import from a test module with ``from theory_harness import ...`` (pytest
puts ``tests/`` on ``sys.path``).  Nothing here knows about LRA or EUF.

The pieces
----------

``TheoryCase(theory, atoms, clauses)``
    A solver with ``theory`` attached, ``atoms`` (``{var: payload}``)
    registered and ``clauses`` added.  ``case.solve()``, ``case.entails()``
    and ``case.implied()`` forward to the solver.

``check_solve(case, consistent, ...)`` / ``check_entails(...)`` /
``check_implied(...)``
    Run the query and compare it with brute force over every assignment of
    the case's variables.  ``consistent(assign)`` is supplied by the
    theory's tests: given ``{var: bool}`` for every registered atom it says
    whether that conjunction of theory literals is satisfiable in the
    theory (evaluate the constraints on a candidate model, run union-find,
    ...).  With ``complete=True`` the answer must equal brute force; with
    ``complete=False`` only definite answers are checked (an UNSAT or an
    entailment must be real; SAT may be spurious).  A SAT answer is always
    checked to satisfy the clauses and assumptions.

``Recorder(inner, solver=None)``
    Wraps any theory, forwards every call and records it in ``events``;
    ``check_protocol(recorder)`` verifies the solver-side guarantees of
    ``satassume/theory.py`` on the recorded trace, and the recorder checks
    live that ``check()`` only sees total assignments and that every
    conflict clause the theory returns is false under the solver's
    assignment.  Wrapping your theory in a Recorder in a fuzz test checks
    both sides of the protocol at once.

``ForbidTheory(forbidden, mode)``
    A dummy theory over plain variables: each set of literals in
    ``forbidden`` is theory-inconsistent.  ``mode`` is ``"eager"``
    (conflicts from ``assert_lit``), ``"lazy"`` (only from ``check``) or
    ``"propagate"`` (eager plus theory propagation).  ``ForbidTheory(())``
    is the always-consistent theory.

Brute force is exponential; keep cases at about 14 variables or fewer.
"""
from __future__ import annotations

import itertools
from typing import Any, Callable, Iterable

from satassume.solver import Solver


# ----------------------------------------------------------------------
# Building a case
# ----------------------------------------------------------------------

class TheoryCase:
    """A solver with one or more theories attached and atoms registered.

    ``theory`` is a theory or a list of ``(theory, atoms)`` pairs for
    several theories; ``atoms`` is ``{var: payload}`` (single theory).
    """

    def __init__(self, theory, atoms: dict[int, Any] | None = None,
                 clauses: Iterable[Iterable[int]] = (), nvars: int | None = None):
        pairs = theory if isinstance(theory, list) else [(theory, atoms or {})]
        self.solver = s = Solver()
        self.clauses = [list(c) for c in clauses]
        self.theories = [t for t, _ in pairs]
        self.atoms: dict[int, Any] = {}
        top = max([abs(l) for c in self.clauses for l in c] +
                  [v for _, a in pairs for v in a] + [nvars or 0, 0])
        self.nvars = top
        s.ensure_vars(top)
        for t, a in pairs:
            if isinstance(t, Recorder) and t.solver is None:
                t.solver = s
            s.attach_theory(t)
        for t, a in pairs:
            for v, payload in a.items():
                s.register_atom(t, v, payload)
                self.atoms[v] = payload
        for c in self.clauses:
            s.add_clause(c)

    def solve(self, assumptions=()) -> bool:
        return self.solver.solve(list(assumptions))

    def entails(self, lit: int, assumptions=()):
        return self.solver.entails(lit, list(assumptions))

    def implied(self, assumptions=()):
        return self.solver.implied(list(assumptions))


# ----------------------------------------------------------------------
# Brute force
# ----------------------------------------------------------------------

def _holds(lit, bits):
    return bits[abs(lit)] == (lit > 0)


def brute_models(case: TheoryCase, consistent: Callable[[dict], bool],
                 assumptions=()) -> list[dict[int, bool]]:
    """Every assignment of ``1..case.nvars`` satisfying the clauses and the
    assumptions whose atom part is theory-consistent."""
    n = case.nvars
    atom_vars = sorted(case.atoms)
    memo: dict[tuple, bool] = {}
    out = []
    for t in itertools.product((False, True), repeat=n):
        bits = dict(zip(range(1, n + 1), t))
        if not all(any(_holds(l, bits) for l in c) for c in case.clauses):
            continue
        if not all(_holds(a, bits) for a in assumptions):
            continue
        key = tuple(bits[v] for v in atom_vars)
        ok = memo.get(key)
        if ok is None:
            ok = memo[key] = bool(consistent({v: bits[v] for v in atom_vars}))
        if ok:
            out.append(bits)
    return out


def check_solve(case: TheoryCase, consistent, assumptions=(), complete=True) -> bool:
    """Solve under ``assumptions`` and compare with brute force."""
    r = case.solve(assumptions)
    models = brute_models(case, consistent, assumptions)
    if r:
        m = case.solver.model()
        assert m is not None
        for c in case.clauses:
            assert any(_holds(l, m) for l in c), ("model violates clause", c)
        for a in assumptions:
            assert _holds(a, m), ("model violates assumption", a)
        if complete:
            assert models, "solver says SAT, brute force says UNSAT"
            assert consistent({v: m[v] for v in case.atoms}), \
                "solver model is theory-inconsistent"
    else:
        assert not models, ("solver says UNSAT, brute force found", models[0])
    return r


def check_entails(case: TheoryCase, consistent, lit: int, assumptions=(),
                  complete=True):
    """``entails(lit, assumptions)`` against brute force (ValueError iff
    the assumptions are inconsistent)."""
    models = brute_models(case, consistent, assumptions)
    try:
        r = case.entails(lit, assumptions)
    except ValueError:
        assert not models, "entails raised, but the assumptions are consistent"
        return "inconsistent"
    if not models:
        assert not complete, "entails answered on inconsistent assumptions"
        return r
    pos = all(_holds(lit, m) for m in models)
    neg = all(not _holds(lit, m) for m in models)
    expected = True if pos else False if neg else None
    if r is not None or complete:
        assert r == expected, (lit, assumptions, r, expected)
    return r


def check_implied(case: TheoryCase, consistent, assumptions=()):
    """``implied`` must only return literals true in every model (None only
    if there is no model)."""
    models = brute_models(case, consistent, assumptions)
    r = case.implied(assumptions)
    if r is None:
        assert not models, "implied found a conflict on consistent assumptions"
        return r
    for l in r:
        assert all(_holds(l, m) for m in models), ("implied literal not entailed", l)
    return r


# ----------------------------------------------------------------------
# Recording and protocol checking
# ----------------------------------------------------------------------

class Recorder:
    """Forwards to ``inner`` (a theory) and records every call.

    ``events`` holds tuples: ``("register", var)``, ``("push",)``,
    ``("pop",)``, ``("assert", lit, result)``, ``("check", result)``,
    ``("propagate", implied_pairs)``.  ``result`` is what the inner theory
    returned.
    """

    def __init__(self, inner, solver: Solver | None = None):
        self.inner = inner
        self.solver = solver
        self.events: list[tuple] = []
        self.registered: set[int] = set()
        if hasattr(inner, "propagate"):
            self.propagate = self._propagate

    def register_atom(self, literal, payload):
        self.events.append(("register", literal))
        self.registered.add(literal)
        return self.inner.register_atom(literal, payload)

    def push_level(self):
        self.events.append(("push",))
        self.inner.push_level()

    def pop_level(self):
        self.events.append(("pop",))
        self.inner.pop_level()

    def _false(self, lit):
        s = self.solver
        v = abs(lit)
        val = s._val[2 * v + (1 if lit < 0 else 0)]
        return val is False

    def _check_clause(self, r, what):
        if r is not None and r[0] is False and self.solver is not None:
            assert r[1], f"{what}: empty conflict clause"
            for l in r[1]:
                assert self._false(l), f"{what}: conflict literal {l} is not false"

    def assert_lit(self, literal):
        r = self.inner.assert_lit(literal)
        self.events.append(("assert", literal, r))
        self._check_clause(r, "assert_lit")
        return r

    def check(self):
        s = self.solver
        if s is not None:
            assert all(s._val[2 * v] is not None for v in range(1, s.nvars() + 1)), \
                "check() called on a partial assignment"
        r = self.inner.check()
        self.events.append(("check", r))
        self._check_clause(r, "check")
        return r

    def _propagate(self):
        out = list(self.inner.propagate())
        self.events.append(("propagate", out))
        return out

    def mark(self, label):
        """Insert a marker (e.g. between public calls), with the solver's
        decision level at that moment (held assumption levels stay on the
        trail between public calls, see ``Solver._assume``)."""
        s = self.solver
        self.events.append(("mark", label, len(s._trail_lim) if s is not None else 0))


def check_protocol(rec: Recorder, final_level_zero=True) -> dict:
    """Verify the solver-side guarantees on a recorded trace.

    * pushes and pops balance, the level never goes negative, and at any
      ``mark`` and at the end the theory's level equals the solver's
      decision level (0, or the held assumption levels; 0 without a solver);
    * only registered variables are asserted, and a variable is asserted at
      most once until a pop undoes it;
    * after a conflict (from ``assert_lit`` or ``check``) no ``assert``,
      ``check`` or ``propagate`` comes before a ``pop``; a conflict at level
      0 ends all ``assert``/``check`` calls;
    * ``check`` sees every variable registered so far asserted;
    * ``propagate`` is not called after a conflict.

    Returns counts of the event kinds.
    """
    level = 0
    reg: set = set()                     # registered so far in the trace
    alive: dict[int, int] = {}          # var -> level it was asserted at
    blocked = False                      # conflict seen, awaiting pop
    dead = False                         # conflict at level 0
    counts: dict[str, int] = {}
    for e in rec.events:
        kind = e[0]
        counts[kind] = counts.get(kind, 0) + 1
        if kind == "mark":
            want = e[2] if len(e) > 2 else 0
            assert level == want, f"level {level} at marker {e[1]}, solver at {want}"
            continue
        if kind == "register":
            reg.add(e[1])
            assert level == 0, "register_atom above level 0"
            continue
        if kind == "push":
            assert not dead
            level += 1
            continue
        if kind == "pop":
            assert level > 0, "pop_level at level 0"
            for v in [v for v, lv in alive.items() if lv == level]:
                del alive[v]
            level -= 1
            blocked = False
            continue
        assert not dead, f"{kind} after a root-level conflict"
        assert not blocked, f"{kind} after a conflict, before backtracking"
        if kind == "assert":
            lit, r = e[1], e[2]
            v = abs(lit)
            assert v in reg, f"assert_lit({lit}) of an unregistered variable"
            assert v not in alive, f"variable {v} asserted twice"
            alive[v] = level
            conflict = r is not None and r[0] is False
        elif kind == "check":
            missing = reg - set(alive)
            assert not missing, f"check() before asserting {sorted(missing)}"
            r = e[1]
            conflict = r is not None and r[0] is False
        else:  # propagate
            conflict = False
        if conflict:
            if level == 0:
                dead = True
            else:
                blocked = True
    if final_level_zero:
        s = getattr(rec, "solver", None)
        want = len(s._trail_lim) if s is not None else 0
        assert level == want, f"trace ends at level {level}, solver at {want}"
    return counts


# ----------------------------------------------------------------------
# Dummy theories
# ----------------------------------------------------------------------

class ForbidTheory:
    """Each element of ``forbidden`` (an iterable of literals) is a
    theory-inconsistent conjunction.  Payloads are ignored.

    ``mode``: ``"eager"`` reports conflicts from ``assert_lit``, ``"lazy"``
    only from ``check``, ``"propagate"`` is eager and also propagates the
    last literal of a forbidden set once all others hold.
    """

    def __init__(self, forbidden=(), mode="eager"):
        assert mode in ("eager", "lazy", "propagate")
        self.forbidden = [frozenset(f) for f in forbidden]
        self.mode = mode
        self.trail: list[int] = []
        self.lims: list[int] = []
        self.atoms: dict[int, Any] = {}
        if mode == "propagate":
            self.propagate = self._propagate

    def consistent(self, assign: dict[int, bool]) -> bool:
        """Brute-force oracle for :func:`check_solve` and friends."""
        true = {v if b else -v for v, b in assign.items()}
        return not any(f <= true for f in self.forbidden)

    def register_atom(self, literal, payload):
        assert literal > 0 and literal not in self.atoms
        self.atoms[literal] = payload

    def push_level(self):
        self.lims.append(len(self.trail))

    def pop_level(self):
        del self.trail[self.lims.pop():]

    def _violated(self):
        true = set(self.trail)
        for f in self.forbidden:
            if f <= true:
                return (False, sorted(-l for l in f))
        return None

    def assert_lit(self, literal):
        if abs(literal) not in self.atoms:
            return None
        self.trail.append(literal)
        if self.mode == "lazy":
            return None
        return self._violated()

    def check(self):
        r = self._violated()
        return r if r is not None else (True, sorted(self.trail))

    def _propagate(self):
        true = set(self.trail)
        out = []
        for f in self.forbidden:
            rest = f - true
            if len(rest) == 1:
                (last,) = rest
                if -last not in true:
                    out.append((-last, sorted(-l for l in f)))
        return out


# ----------------------------------------------------------------------
# Dummy relation adapters (stand-ins for LRA and EUF in engine tests)
# ----------------------------------------------------------------------

class _TrailTheory:
    """Shared plumbing: a trail of asserted literals with level marks; a
    conflict clause is the negation of everything asserted (valid whenever
    the asserted set is inconsistent, so always sound, just weak)."""

    def __init__(self):
        self.atoms: dict = {}
        self.trail: list = []
        self.lims: list = []

    def register_atom(self, literal, payload):
        self.atoms[literal] = payload

    def push_level(self):
        self.lims.append(len(self.trail))

    def pop_level(self):
        del self.trail[self.lims.pop():]

    def assert_lit(self, literal):
        if abs(literal) in self.atoms:
            self.trail.append(literal)
        return None

    def check(self):
        if self.consistent([(self.atoms[abs(l)], l > 0) for l in self.trail]):
            return (True, None)
        return (False, [-l for l in self.trail])


class OrderTheory(_TrailTheory):
    """Dense order over terms and rational constants: payloads
    ``(rel, a, b)`` with ``rel`` in ``lt le eq``.  Complete for these
    atoms (no arithmetic)."""

    @staticmethod
    def consistent(lits) -> bool:
        from sympy import Rational
        edges = []          # (a, b, strict): a <= b, or a < b if strict
        diseq = []
        nodes = set()
        for (rel, a, b), val in lits:
            nodes.update((a, b))
            if rel == "lt":
                edges.append((a, b, True) if val else (b, a, False))
            elif rel == "le":
                edges.append((a, b, False) if val else (b, a, True))
            elif val:
                edges += [(a, b, False), (b, a, False)]
            else:
                diseq.append((a, b))
        nums = sorted((n for n in nodes if isinstance(n, Rational)), key=float)
        for i in range(len(nums) - 1):
            if nums[i] != nums[i + 1]:
                edges.append((nums[i], nums[i + 1], True))
        # reach[a][b] = None | False (<=) | True (<)
        nodes = list(nodes)
        reach = {a: {} for a in nodes}
        for a, b, st in edges:
            reach[a][b] = reach[a].get(b, False) or st
        for k in nodes:
            for i in nodes:
                ik = reach[i].get(k)
                if ik is None:
                    continue
                for j, kj in list(reach[k].items()):
                    st = ik or kj
                    if reach[i].get(j) is None or (st and not reach[i][j]):
                        reach[i][j] = st
        if any(reach[a].get(a) for a in nodes):
            return False
        for a, b in diseq:
            if a == b or (reach[a].get(b) is not None and reach[b].get(a) is not None):
                return False
        return True


class UFTheory(_TrailTheory):
    """Equality with uninterpreted functions: payloads ``(a, b)`` over SymPy
    terms; applications of undefined functions are congruent; distinct
    rational constants are distinct."""

    @staticmethod
    def consistent(lits) -> bool:
        from sympy import Rational
        from sympy.core.function import AppliedUndef
        terms = set()

        def add(t):
            if t in terms:
                return
            terms.add(t)
            if isinstance(t, AppliedUndef):
                for a in t.args:
                    add(a)
        for (a, b), _ in lits:
            add(a)
            add(b)
        parent = {t: t for t in terms}

        def find(t):
            while parent[t] != t:
                t = parent[t]
            return t
        for (a, b), val in lits:
            if val:
                parent[find(a)] = find(b)
        apps = [t for t in terms if isinstance(t, AppliedUndef)]
        changed = True
        while changed:
            changed = False
            for i, s in enumerate(apps):
                for t in apps[i + 1:]:
                    if s.func == t.func and len(s.args) == len(t.args) and \
                            find(s) != find(t) and \
                            all(find(x) == find(y) for x, y in zip(s.args, t.args)):
                        parent[find(s)] = find(t)
                        changed = True
        nums = [t for t in terms if isinstance(t, Rational)]
        for i, x in enumerate(nums):
            for y in nums[i + 1:]:
                if x != y and find(x) == find(y):
                    return False
        return all(find(a) != find(b) for (a, b), val in lits if not val)


class _DummyAdapter:
    theory_class: type = _TrailTheory

    def __init__(self):
        self.theory = self.theory_class()
        self.attached = False
        self.known: set = set()

    def register(self, solver, var, atom) -> bool:
        payload = self.interpret(atom)
        if payload is None:
            return False
        if not self.attached:
            solver.attach_theory(self.theory)
            self.attached = True
        solver.register_atom(self.theory, var, payload)
        self.known.update(self.terms(atom) or ())
        return True

    def shared_terms(self) -> set:
        return set(self.known)


class OrderAdapter(_DummyAdapter):
    """Guarded stand-in for LRA: ``Q.lt/le/eq`` between symbols and
    rational numbers."""
    theory_class = OrderTheory

    @staticmethod
    def _ok(e):
        return e.is_Symbol or e.is_Rational

    def interpret(self, atom):
        a, b = atom.arguments
        if not (self._ok(a) and self._ok(b)):
            return None
        return (str(atom.function.name), a, b)

    def terms(self, atom):
        return [e for e in atom.arguments if e.is_Symbol]


class UFAdapter(_DummyAdapter):
    """Unguarded stand-in for EUF: ``Q.eq`` between symbols, rational
    numbers and applications of undefined functions of those."""
    theory_class = UFTheory

    @staticmethod
    def _ok(e):
        from sympy.core.function import AppliedUndef
        if e.is_Symbol or e.is_Rational:
            return True
        return isinstance(e, AppliedUndef) and all(UFAdapter._ok(a) for a in e.args)

    def interpret(self, atom):
        if atom.function.name != "eq":
            return None
        a, b = atom.arguments
        if not (self._ok(a) and self._ok(b)):
            return None
        return (a, b)

    def terms(self, atom):
        from sympy.core.function import AppliedUndef
        out = []

        def walk(e):
            if not e.is_Rational:
                out.append(e)
            if isinstance(e, AppliedUndef):
                for a in e.args:
                    walk(a)
        for e in atom.arguments:
            walk(e)
        return out


def dummy_specs(order=True, uf=True):
    """Adapter specs for an :class:`~satassume.engine.Engine` using the
    dummy theories."""
    from satassume.relations import AdapterSpec
    specs = []
    if order:
        specs.append(AdapterSpec("order", OrderAdapter, True))
    if uf:
        specs.append(AdapterSpec("uf", UFAdapter, False))
    return specs


def relation_engine(specs=None):
    """A fresh engine (private caches) with the given relation adapter
    specs; default: the real ones (``satassume.relations.default_specs``)."""
    from satassume import Engine
    from satassume.engine import DictCache
    return Engine(cache=DictCache(), relations=specs)


def ask_with(engine, proposition, assumptions=True):
    """``satassume.sympy_api.ask`` on ``engine``; ``"inconsistent"`` if it
    raises ValueError (inconsistent assumptions)."""
    from satassume.sympy_api import ask
    try:
        return ask(proposition, assumptions, engine=engine)
    except ValueError:
        return "inconsistent"
