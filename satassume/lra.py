"""Linear real arithmetic (LRA) theory solver for satassume's DPLL(T) layer.

The solver implements :class:`satassume.theory.TheorySolver` (plus the
optional ``propagate``) for conjunctions of linear constraints over the
reals, with the general simplex of Dutertre and de Moura, "A Fast
Linear-Arithmetic Solver for DPLL(T)" (CAV 2006).  Arithmetic is exact
(:class:`fractions.Fraction`, and numbers with constants such as ``pi``,
``1/pi``, ``sqrt(2)`` from :mod:`satassume.constfield` where a payload has
them); strict bounds use delta-rationals ``q + d*delta``
for an infinitesimal ``delta > 0``.  Nothing here imports SymPy: terms are
opaque hashable keys, the SymPy boundary is :mod:`satassume.lra_adapter`.

Payloads
--------

``register_atom(v, payload)`` takes

* ``(terms, constant, strict, equality)``: the constraint
  ``sum(c*t for t, c in terms)  OP  constant`` where ``OP`` is ``==`` if
  ``equality`` else ``<`` if ``strict`` else ``<=``.  ``terms`` is a tuple of
  ``(term, coefficient)`` pairs (or a dict ``{term: coefficient}``);
  repeated terms are summed and zero coefficients dropped.  Coefficients
  and the constant are anything :class:`~fractions.Fraction` accepts.
* ``Negated(payload)``: the atom is the *negation* of ``payload`` (used for
  ``x != y``, i.e. solver variable ``v`` true means the equality is false).
* ``Integral(terms, offset)``: ``sum(c*t for t, c in terms) + offset`` is
  an integer (``terms`` as above).  Its negation is "not an integer".

Coefficients and constants may be :class:`satassume.constfield.Element`
numbers (``pi``, ``3*pi/2``, ``1/pi``); a payload of Fractions only costs
nothing extra (constant-free results stay Fractions).  With constants a
comparison can be undecidable (:class:`satassume.constfield.Undecided`:
a formal expression whose value is 0, ``sqrt(2)**2 - 2``, or one over the
size budget).  No comparison takes a default branch then: the theory
*gives up* (see "Giving up" in :mod:`satassume.theory`): it reports no
conflict, propagation or model from then on, which is incompleteness, not
unsoundness.  Rows drop a coefficient only when it is formally 0
(:func:`~satassume.constfield.formally_zero`), pivots and assignment
updates compute every new value before writing any, and integrality
never calls an Element integral or non-integral by default
(:func:`_is_int`).

A payload without terms is a *ground* atom: its truth value is fixed, the
theory reports ``[-lit]`` when it is asserted the wrong way and propagates
it as a unit.

Semantics: every term is a real variable, independent of all other terms
(a sound relaxation when terms are really e.g. ``x*y`` and ``x``).  The
negation of an order atom is the complementary order atom
(``not (s <= c)`` is ``s > c``), which is only right over the reals: the
caller registers an atom only when its terms are finite reals (the engine's
bridge clauses).  Disequalities (negated equalities) are decided exactly in
:meth:`LRATheory.check`.

Integrality
-----------

An ``Integral`` atom is kept as ``m*v + k`` in Z for the variable ``v`` of
its form (the term itself, or the slack of the form normalised as above,
``m`` the leading coefficient) and is not a bound.  It is checked in three
places, cheapest first:

* ``assert_lit`` and ``propagate``: the bounds of ``v`` itself, rounded
  (``m*v + k`` lies in ``[ceil(m*lo + k), floor(m*up + k)]``, with the
  floor/ceiling of a delta-rational, so ``v < 1`` gives ``v <= 0``): an
  asserted atom whose range holds no integer is a conflict, and so is a
  negated one whose ``v`` the bounds pin to a value where ``m*v + k`` is
  an integer; an unassigned atom is propagated in the same two cases;
* ``check``: branch and bound (Dutertre and de Moura, SRI-CSL-06-01,
  chapter 4) after the simplex: an asserted ``m*v + k`` in Z whose value
  ``n`` is not an integer splits into ``m*v + k <= floor(n)`` and
  ``>= floor(n) + 1`` (a negated one whose value is the integer ``n``
  into ``< n`` and ``> n``), each branch a ``push_level`` with bounds
  that have no literal; if both branches conflict, the conflict is the
  union of their explanations plus the integrality literal (the branch
  bounds drop out: they are the two cases of that literal).  At most
  :data:`BRANCH_BUDGET` branch nodes per ``check``; when the budget runs
  out, the check reports no conflict.

So integrality is sound but incomplete: a conflict is always valid, a
satisfiable check may be integrally infeasible (the budget), and the model
``check`` returns satisfies the bounds and disequalities but not
necessarily the integrality atoms.  satassume reads a definite answer only
from an unsatisfiable search; a satisfiable one gives None (or "the
assumptions are consistent"), never a definite answer.

How it works
------------

Every distinct linear form over two or more terms gets one *slack*
variable, keyed by the form normalised to leading coefficient ``1`` (so
``x + y <= 1``, ``2*y + 2*x >= 3`` and ``-x - y < 0`` share one slack); a
one-term constraint is a bound on the term itself.  Each atom is then a
bound on one variable: ``<=``, ``<``, ``>=``, ``>``, ``=`` or ``!=``.  The
tableau is sparse (``basic -> {nonbasic: coeff}`` plus column index sets)
and lives across levels: backtracking only restores bounds, since the
assignment still satisfies every row and the nonbasic variables stay
within the (looser) restored bounds.

Complexity (``k`` = number of rows containing a variable, ``m`` = rows):

* ``assert_lit``: O(k) for the bound, plus a simplex run if ``eager``.
* ``push_level``: O(1).  ``pop_level``: O(bound changes since the push).
* ``check``: simplex with Bland's rule (terminates), each pivot
  O(row length * rows touching the entering column); then O(n) to pick a
  concrete delta, plus two extra simplex runs per disequality that the
  first model violates.
* integrality: O(1) per asserted atom on a variable whose bound changes;
  ``check`` adds at most :data:`BRANCH_BUDGET` branchings (two simplex
  runs each) when an integrality atom is violated by the simplex point.
* ``propagate``: O(atoms on the variables whose bounds changed).
* ``register_atom``: O(length of the form * row length) for a new slack.
"""
from __future__ import annotations

import math
from fractions import Fraction
from typing import Any, Hashable, Iterable, NamedTuple

from .constfield import Undecided, formally_zero, num

__all__ = ["LRATheory", "Negated", "Integral", "constraint", "BRANCH_BUDGET"]

_ZERO = Fraction(0)
_ONE = Fraction(1)

# bound kinds; _NEG maps a kind to the kind of the negated atom
_NEG = {"<=": ">", "<": ">=", ">=": "<", ">": "<=", "=": "!=", "!=": "="}
_FLIP = {"<=": ">=", "<": ">", ">=": "<=", ">": "<", "=": "=", "!=": "!="}

# trail entry tags
_LO, _UP, _ASG, _DIS, _INT = 0, 1, 2, 3, 4

#: branch-and-bound nodes (branchings) per ``check``; beyond it the check
#: reports no integrality conflict (incomplete, sound)
BRANCH_BUDGET = 16


class Negated(NamedTuple):
    """Payload wrapper: the registered atom is the negation of ``payload``."""
    payload: Any


class Integral(NamedTuple):
    """Payload: ``sum(c*t for t, c in terms) + offset`` is an integer."""
    terms: Any
    offset: Any = 0


def constraint(terms, op: str, rhs=0):
    """Convenience payload builder: ``sum(c*t) op rhs`` with ``op`` one of
    ``< <= > >= = == !=``.  ``>``/``>=`` are negated into ``<``/``<=``;
    ``!=`` gives ``Negated`` of the equality."""
    items = terms.items() if isinstance(terms, dict) else terms
    items = tuple((t, num(c)) for t, c in items)
    rhs = num(rhs)
    if op in (">", ">="):
        items = tuple((t, -c) for t, c in items)
        rhs = -rhs
        op = "<" if op == ">" else "<="
    if op == "<":
        return (items, rhs, True, False)
    if op == "<=":
        return (items, rhs, False, False)
    if op in ("=", "=="):
        return (items, rhs, False, True)
    if op == "!=":
        return Negated((items, rhs, False, True))
    raise ValueError(f"unknown operator {op!r}")


def _is_int(q) -> bool:
    """``q`` (a Fraction or an :class:`~satassume.constfield.Element`) is
    an integer.  An Element is False when its value is proven not to be an
    integer and raises Undecided otherwise, never True (its value may still
    be one, ``sqrt(2)**2``): so no Element is ever declared non-integral
    by default."""
    if type(q) is Fraction:
        return q.denominator == 1
    return q.is_integer()


def _floor(q, d) -> int:
    """The largest integer ``<= q + d*delta`` for every small ``delta > 0``."""
    if _is_int(q):
        return q.numerator - 1 if d < 0 else q.numerator
    return math.floor(q)


def _ceil(q, d) -> int:
    """The smallest integer ``>= q + d*delta`` for every small ``delta > 0``."""
    if _is_int(q):
        return q.numerator + 1 if d > 0 else q.numerator
    return math.ceil(q)


def _dedupe(lits: Iterable[int]) -> list[int]:
    out: list[int] = []
    seen = set()
    for l in lits:
        if l and l not in seen:
            seen.add(l)
            out.append(l)
    return out


class LRATheory:
    """Simplex-based LRA theory solver (see the module docstring).

    ``eager=True`` (default) runs the simplex inside every ``assert_lit`` of
    a bound, so conflicts are found as early as possible (and ``implied``
    sees them); ``eager=False`` only checks bound-against-bound there and
    leaves the simplex to :meth:`check`.
    """

    def __init__(self, eager: bool = True) -> None:
        self.eager = eager
        #: set when an undecidable comparison made the theory give up
        self.gave_up = False
        # variables: index -> term key (None for slack variables)
        self._key: list[Hashable | None] = []
        self._var_of: dict[Hashable, int] = {}
        self._slack_of: dict[tuple, int] = {}
        # bounds: (q, d) delta-rational or None, and the literal that set it
        self._lo: list[tuple | None] = []
        self._up: list[tuple | None] = []
        self._lo_r: list[int] = []
        self._up_r: list[int] = []
        # assignment
        self._vq: list[Fraction] = []
        self._vd: list[Fraction] = []
        # tableau: basic var -> {nonbasic var: coeff}; column sets
        self._rows: dict[int, dict[int, Fraction]] = {}
        self._cols: list[set[int]] = []
        # atoms: solver var -> (lra var, kind, value) ; ground atoms separately
        self._atoms: dict[int, tuple[int, str, Fraction]] = {}
        self._ground: dict[int, bool] = {}
        self._atoms_on: list[list[int]] = []
        self._assigned: dict[int, bool] = {}
        # asserted disequalities (var, value, literal)
        self._diseqs: list[tuple[int, Fraction, int]] = []
        # integrality atoms: solver var -> (lra var, m, k) for m*v + k in Z;
        # lra var -> those solver vars; the asserted ones (var, m, k, literal)
        self._ints: dict[int, tuple[int, Fraction, Fraction]] = {}
        self._ints_on: dict[int, list[int]] = {}
        self._int_lits: list[tuple[int, Fraction, Fraction, int]] = []
        # undo trail and level marks
        self._trail: list[tuple] = []
        self._lims: list[int] = []
        # propagation work list
        self._dirty: set[int] = set()
        self._pending_ground: list[int] = []
        self.stats = {"pivots": 0, "checks": 0, "conflicts": 0,
                      "propagations": 0, "branches": 0, "gave_up": 0}

    # ------------------------------------------------------------------
    # registration
    # ------------------------------------------------------------------

    def _new_var(self, key: Hashable | None) -> int:
        v = len(self._key)
        self._key.append(key)
        self._lo.append(None)
        self._up.append(None)
        self._lo_r.append(0)
        self._up_r.append(0)
        self._vq.append(_ZERO)
        self._vd.append(_ZERO)
        self._cols.append(set())
        self._atoms_on.append([])
        if key is not None:
            self._var_of[key] = v
        return v

    def _term_var(self, key: Hashable) -> int:
        v = self._var_of.get(key)
        return self._new_var(key) if v is None else v

    def _slack(self, form: tuple[tuple[int, Fraction], ...]) -> int:
        s = self._slack_of.get(form)
        if s is not None:
            return s
        rows = self._rows
        row: dict[int, Fraction] = {}
        for v, c in form:
            r = rows.get(v)
            if r is None:
                row[v] = row.get(v, _ZERO) + c
            else:
                for k, a in r.items():
                    row[k] = row.get(k, _ZERO) + c * a
        row = {k: a for k, a in row.items() if not formally_zero(a)}
        vq = vd = _ZERO
        for k, a in row.items():
            vq += a * self._vq[k]
            vd += a * self._vd[k]
        s = self._new_var(None)                 # arithmetic done: commit
        self._slack_of[form] = s
        for k in row:
            self._cols[k].add(s)
        self._vq[s] = vq
        self._vd[s] = vd
        rows[s] = row
        return s

    # ------------------------------------------------------------------
    # the theory boundary: Undecided -> give up
    # ------------------------------------------------------------------
    #
    # With constants in the coefficients (satassume.constfield) a sign, a
    # comparison or a floor can be undecidable (Undecided, or TooLarge for
    # the size budget).  No comparison here has a default branch for that:
    # the exception leaves the method, and the theory gives up
    # (satassume.theory, "Giving up"): it reports nothing more (no
    # conflict, no propagation, None from check), whatever state the
    # interrupted call left is never read again, and the engine discards
    # the session after the query.  Conflicts and propagations reported
    # before stay valid, so answers stay sound (only less complete).
    # propagate alone skips an implication it cannot decide and goes on
    # (propagation is optional).

    def _give_up(self) -> None:
        self.gave_up = True
        self.stats["gave_up"] += 1

    def register_atom(self, literal: int, payload: Any) -> None:
        if self.gave_up:
            return
        try:
            self._register_atom(literal, payload)
        except Undecided:
            self._give_up()

    def assert_lit(self, literal: int):
        if self.gave_up:
            return None
        try:
            return self._assert_lit(literal)
        except Undecided:
            self._give_up()
            return None

    def check(self):
        if self.gave_up:
            return None
        try:
            return self._check()
        except Undecided:
            self._give_up()
            return None

    def propagate(self):
        if self.gave_up:
            return []
        try:
            return self._propagate()
        except Undecided:
            self._give_up()
            return []

    def _register_atom(self, literal: int, payload: Any) -> None:
        if literal <= 0:
            raise ValueError("register_atom takes a positive literal")
        if literal in self._atoms or literal in self._ground \
                or literal in self._ints:
            raise ValueError(f"literal {literal} registered twice")
        if isinstance(payload, Integral):
            self._register_integral(literal, payload)
            return
        negated = False
        while isinstance(payload, Negated):
            negated = not negated
            payload = payload.payload
        terms, constant, strict, equality = payload
        lin = self._lin(terms)
        k = num(constant)
        kind = "=" if equality else "<" if strict else "<="
        if negated:
            kind = _NEG[kind]
        if not lin:
            truth = {"=": 0 == k, "!=": 0 != k, "<": 0 < k, "<=": 0 <= k,
                     ">": 0 > k, ">=": 0 >= k}[kind]
            self._ground[literal] = truth
            self._pending_ground.append(literal)
            return
        v, c = self._var_of_form(lin)
        bound = k / c
        if c < 0:
            kind = _FLIP[kind]
        self._atoms[literal] = (v, kind, bound)
        self._atoms_on[v].append(literal)
        self._dirty.add(v)

    def _lin(self, terms) -> dict:
        """``{term: coefficient}`` of a payload's terms, repeated terms
        summed and zeros dropped; every term gets a variable (also one with
        coefficient 0, so that it has a model value)."""
        items = terms.items() if isinstance(terms, dict) else terms
        lin: dict[Hashable, Fraction] = {}
        for t, c in items:
            lin[t] = lin.get(t, _ZERO) + num(c)
        for t in lin:
            self._term_var(t)
        # a formal zero test (sparsity): a coefficient whose value is 0
        # without being formally 0 stays, and any use of its sign aborts
        return {t: c for t, c in lin.items() if not formally_zero(c)}

    def _var_of_form(self, lin: dict) -> tuple[int, Fraction]:
        """``(v, c)`` with ``sum(a*t) == c*v`` for the non-empty form
        ``lin``: the term's variable, or the slack of the form normalised to
        leading coefficient 1."""
        vs = sorted((self._term_var(t), c) for t, c in lin.items())
        if len(vs) == 1:
            return vs[0]
        c = vs[0][1]
        return self._slack(tuple((w, a / c) for w, a in vs)), c

    def _register_integral(self, literal: int, payload: Integral) -> None:
        lin = self._lin(payload.terms)
        k = num(payload.offset)
        if not lin:
            self._ground[literal] = _is_int(k)
            self._pending_ground.append(literal)
            return
        v, m = self._var_of_form(lin)
        k -= math.floor(k)
        if type(m) is Fraction and m == 1 and type(k) is Fraction and not k:
            m, k = _ONE, _ZERO                  # "v in Z": the fast path
        self._ints[literal] = (v, m, k)
        self._ints_on.setdefault(v, []).append(literal)
        self._dirty.add(v)

    # ------------------------------------------------------------------
    # levels
    # ------------------------------------------------------------------

    def push_level(self) -> None:
        if not self.gave_up:
            self._lims.append(len(self._trail))

    def pop_level(self) -> None:
        # after giving up (possibly inside an internal level of check) the
        # state is never read again: levels need no bookkeeping
        if not self.gave_up:
            self._undo_to(self._lims.pop())

    def _undo_to(self, n: int) -> None:
        trail = self._trail
        while len(trail) > n:
            e = trail.pop()
            tag = e[0]
            if tag == _LO:
                self._lo[e[1]] = e[2]
                self._lo_r[e[1]] = e[3]
            elif tag == _UP:
                self._up[e[1]] = e[2]
                self._up_r[e[1]] = e[3]
            elif tag == _ASG:
                del self._assigned[e[1]]
            elif tag == _DIS:
                self._diseqs.pop()
            else:
                self._int_lits.pop()

    # ------------------------------------------------------------------
    # asserting
    # ------------------------------------------------------------------

    def _assert_lit(self, literal: int):
        a = abs(literal)
        atom = self._atoms.get(a)
        if atom is None:
            it = self._ints.get(a)
            if it is not None:
                return self._assert_integral(literal, it)
            truth = self._ground.get(a)
            if truth is None:
                return None
            self._assigned[a] = literal > 0
            self._trail.append((_ASG, a))
            if truth != (literal > 0):
                self.stats["conflicts"] += 1
                return (False, [-literal])
            return None
        self._assigned[a] = literal > 0
        self._trail.append((_ASG, a))
        v, kind, c = atom
        if literal < 0:
            kind = _NEG[kind]
        conflict = self._assert_kind(v, kind, c, literal)
        if conflict is None and self._int_lits and v in self._ints_on:
            conflict = self._int_bounds(v)
        if conflict is None and self.eager and kind != "!=":
            conflict = self._simplex()
        if conflict is not None:
            self.stats["conflicts"] += 1
            return (False, conflict)
        return None

    def _assert_kind(self, v: int, kind: str, c: Fraction, lit: int):
        if kind == "<=":
            return self._set_upper(v, (c, _ZERO), lit)
        if kind == "<":
            return self._set_upper(v, (c, -_ONE), lit)
        if kind == ">=":
            return self._set_lower(v, (c, _ZERO), lit)
        if kind == ">":
            return self._set_lower(v, (c, _ONE), lit)
        if kind == "=":
            return (self._set_upper(v, (c, _ZERO), lit)
                    or self._set_lower(v, (c, _ZERO), lit))
        # disequality: record; cheap eager test when the bounds pin v to c
        self._diseqs.append((v, c, lit))
        self._trail.append((_DIS,))
        lo, up = self._lo[v], self._up[v]
        if lo is not None and lo == up == (c, _ZERO):
            return _dedupe([-lit, -self._lo_r[v], -self._up_r[v]])
        return None

    def _set_upper(self, v: int, b: tuple, lit: int):
        up = self._up[v]
        if up is not None and up <= b:
            return None
        lo = self._lo[v]
        if lo is not None and b < lo:
            return _dedupe([-lit, -self._lo_r[v]])
        self._trail.append((_UP, v, up, self._up_r[v]))
        self._up[v] = b
        self._up_r[v] = lit
        self._dirty.add(v)
        if v not in self._rows and (self._vq[v], self._vd[v]) > b:
            self._update(v, b)
        return None

    def _set_lower(self, v: int, b: tuple, lit: int):
        lo = self._lo[v]
        if lo is not None and lo >= b:
            return None
        up = self._up[v]
        if up is not None and b > up:
            return _dedupe([-lit, -self._up_r[v]])
        self._trail.append((_LO, v, lo, self._lo_r[v]))
        self._lo[v] = b
        self._lo_r[v] = lit
        self._dirty.add(v)
        if v not in self._rows and (self._vq[v], self._vd[v]) < b:
            self._update(v, b)
        return None

    def _update(self, v: int, b: tuple) -> None:
        """Move nonbasic ``v`` to value ``b``, keeping every row satisfied
        (computed first, then written: see :meth:`_pivot`)."""
        dq = b[0] - self._vq[v]
        dd = b[1] - self._vd[v]
        vq, vd, rows = self._vq, self._vd, self._rows
        new = [(r, vq[r] + a * dq, vd[r] + a * dd)
               for r, a in ((r, rows[r][v]) for r in self._cols[v])]
        for r, q, d in new:
            vq[r] = q
            vd[r] = d
        vq[v] = b[0]
        vd[v] = b[1]

    # ------------------------------------------------------------------
    # integrality
    # ------------------------------------------------------------------

    def _assert_integral(self, literal: int, it: tuple):
        """Assert ``m*v + k`` in Z (``literal > 0``) or not in Z."""
        self._assigned[abs(literal)] = literal > 0
        self._trail.append((_ASG, abs(literal)))
        v, m, k = it
        self._int_lits.append((v, m, k, literal))
        self._trail.append((_INT,))
        r = self._int_verdict(v, m, k)
        if r is not None and r[0] != (literal > 0):
            self.stats["conflicts"] += 1
            return (False, _dedupe([-literal] + [-l for l in r[1]]))
        return None

    def _int_verdict(self, v: int, m: Fraction, k: Fraction):
        """Truth of ``m*v + k`` in Z implied by the bounds of ``v`` itself:
        False if the rounded range of ``m*v + k`` holds no integer, True if
        the bounds pin ``v`` to a value where it is an integer, else None;
        with the literals of the bounds used."""
        lo, up = self._lo[v], self._up[v]
        if lo is None or up is None:
            return None
        why = [self._lo_r[v], self._up_r[v]]
        if m is _ONE and k is _ZERO:
            a, b = lo, up
        else:
            a = (m * lo[0] + k, m * lo[1])
            b = (m * up[0] + k, m * up[1])
            if m < 0:
                a, b = b, a
        if lo == up:                            # pinned: d == 0 here
            return (_is_int(a[0]), why)
        if _ceil(*a) > _floor(*b):
            return (False, why)
        return None

    def _int_bounds(self, v: int):
        """A conflict between the bounds of ``v`` and an asserted
        integrality literal on ``v``, or None."""
        for w, m, k, lit in self._int_lits:
            if w == v:
                r = self._int_verdict(v, m, k)
                if r is not None and r[0] != (lit > 0):
                    return _dedupe([-lit] + [-l for l in r[1]])
        return None

    def _branch(self, budget: list[int]):
        """Branch and bound from a feasible simplex point: a conflict
        clause, or None (a point that satisfies every asserted integrality
        literal, or ``budget[0]`` branchings spent).  Leaves the bounds as
        it found them; the assignment then satisfies them (as after a
        pop)."""
        vq, vd = self._vq, self._vd
        for v, m, k, lit in self._int_lits:
            if m is _ONE and k is _ZERO:
                nq, nd = vq[v], vd[v]
            else:
                nq, nd = m * vq[v] + k, m * vd[v]
            integral = not nd and _is_int(nq)
            if lit > 0 and not integral:        # n <= floor(n) or n >= floor(n) + 1
                f = _floor(nq, nd)
                cases = (("<=", f), (">=", f + 1))
                break
            if lit < 0 and integral:            # n < value or n > value
                # first the side v can move to (v often sits at a bound)
                down = self._lo[v] != (vq[v], _ZERO)
                cases = (("<", nq), (">", nq)) if down == (m > 0) \
                    else ((">", nq), ("<", nq))
                break
        else:
            return None
        if budget[0] <= 0:
            return None
        budget[0] -= 1
        self.stats["branches"] += 1
        expl = [-lit]
        for kind, n in cases:
            if m < 0:
                kind = _FLIP[kind]
            self.push_level()
            r = self._assert_kind(v, kind, (n - k) / m, 0)   # no literal
            if r is None:
                r = self._simplex()
                if r is None:
                    r = self._branch(budget)
            self.pop_level()
            if r is None:
                return None
            expl.extend(r)
        return _dedupe(expl)

    # ------------------------------------------------------------------
    # simplex
    # ------------------------------------------------------------------

    def _simplex(self):
        """Restore feasibility; None or a conflict clause (Bland's rule)."""
        rows, lo, up, vq, vd = self._rows, self._lo, self._up, self._vq, self._vd
        while True:
            leave = -1
            below = False
            for b in rows:
                if leave != -1 and b > leave:
                    continue
                l = lo[b]
                if l is not None and (vq[b], vd[b]) < l:
                    leave, below = b, True
                    continue
                u = up[b]
                if u is not None and (vq[b], vd[b]) > u:
                    leave, below = b, False
            if leave == -1:
                return None
            b = leave
            row = rows[b]
            enter = -1
            for j, a in row.items():
                if enter != -1 and j > enter:
                    continue
                inc = (a > 0) == below          # need x_j to increase?
                if inc:
                    u = up[j]
                    if u is None or (vq[j], vd[j]) < u:
                        enter = j
                else:
                    l = lo[j]
                    if l is None or (vq[j], vd[j]) > l:
                        enter = j
            if enter == -1:
                if below:
                    expl = [-self._lo_r[b]]
                    for j, a in row.items():
                        expl.append(-(self._up_r[j] if a > 0 else self._lo_r[j]))
                else:
                    expl = [-self._up_r[b]]
                    for j, a in row.items():
                        expl.append(-(self._lo_r[j] if a > 0 else self._up_r[j]))
                return _dedupe(expl)
            self._pivot_and_update(b, enter, lo[b] if below else up[b])

    def _pivot_and_update(self, b: int, j: int, target: tuple) -> None:
        rows, cols, vq, vd = self._rows, self._cols, self._vq, self._vd
        a = rows[b][j]
        tq = (target[0] - vq[b]) / a
        td = (target[1] - vd[b]) / a
        new = [(k, vq[k] + ak * tq, vd[k] + ak * td)
               for k, ak in ((k, rows[k][j]) for k in cols[j] if k != b)]
        new.append((j, vq[j] + tq, vd[j] + td))
        self._pivot(b, j)                        # may raise before writing
        vq[b], vd[b] = target
        for k, q, d in new:
            vq[k] = q
            vd[k] = d

    def _pivot(self, b: int, j: int) -> None:
        """Make ``j`` basic in place of ``b`` (``b`` becomes nonbasic).

        All arithmetic (which can raise for numbers with constants: a
        size budget, see :mod:`satassume.constfield`) is done before the
        tableau is written, so the tableau is never left half pivoted."""
        self.stats["pivots"] += 1
        rows, cols = self._rows, self._cols
        row = rows[b]
        a = row[j]
        inv = _ONE / a
        newrow = {b: inv}
        for k, c in row.items():
            if k != j:
                newrow[k] = -c * inv
        cj = cols[j]
        updates = []
        for r in cj:
            if r == b:
                continue
            rr = rows[r]
            f = rr[j]
            updates.append((r, [(k, rr.get(k, _ZERO) + f * c) for k, c in newrow.items()]))
        # commit
        del rows[b]
        for k in row:
            if k != j:
                cols[k].discard(b)
        for r, new in updates:
            rr = rows[r]
            del rr[j]
            for k, nv in new:
                if not formally_zero(nv):
                    if k not in rr:
                        cols[k].add(r)
                    rr[k] = nv
                elif k in rr:
                    del rr[k]
                    cols[k].discard(r)
        cols[j] = set()
        rows[j] = newrow
        for k in newrow:
            cols[k].add(j)

    # ------------------------------------------------------------------
    # models
    # ------------------------------------------------------------------

    def _concrete(self) -> list[Fraction]:
        """Values of all variables with delta replaced by a small rational
        that satisfies every current bound."""
        vq, vd, lo, up = self._vq, self._vd, self._lo, self._up
        delta = _ONE
        for v in range(len(vq)):
            q, d = vq[v], vd[v]
            l = lo[v]
            if l is not None and l[1] > d and q > l[0]:
                delta = min(delta, (q - l[0]) / (l[1] - d))
            u = up[v]
            if u is not None and u[1] < d and q < u[0]:
                delta = min(delta, (u[0] - q) / (d - u[1]))
        return [q + delta * d for q, d in zip(vq, vd)]

    def _model(self, point: list[Fraction]) -> dict:
        return {k: point[v] for v, k in enumerate(self._key) if k is not None}

    def _check(self):
        self.stats["checks"] += 1
        conflict = self._simplex()
        if conflict is None and self._int_lits:
            conflict = self._branch([BRANCH_BUDGET])
        if conflict is not None:
            self.stats["conflicts"] += 1
            return (False, conflict)
        p0 = self._concrete()
        diseqs = self._diseqs
        if all(p0[v] != c for v, c, _ in diseqs):
            return (True, self._model(p0))
        # Some disequalities are violated by p0.  The feasible set P is
        # convex, so P minus the hyperplanes is empty iff P lies inside one
        # of them.  For each violated s != c find a point of P off the
        # hyperplane (s < c or s > c); if neither exists, the bounds force
        # s = c: conflict.  Otherwise combine the points generically.
        points = [p0]
        for v, c, lit in diseqs:
            if any(p[v] != c for p in points):
                continue
            expl: list[int] = []
            found = None
            for kind in ("<", ">"):
                self.push_level()
                r = self._assert_kind(v, kind, c, 0)
                if r is None:
                    r = self._simplex()
                if r is None:
                    found = self._concrete()
                self.pop_level()
                if found is not None:
                    break
                expl.extend(r)
            if found is None:
                self.stats["conflicts"] += 1
                return (False, _dedupe([-lit] + expl))
            points.append(found)
        n = len(points)
        t = 1
        while True:
            w = [Fraction(t) ** i for i in range(n)]
            total = sum(w)
            p = [sum(wi * pt[v] for wi, pt in zip(w, points)) / total
                 for v in range(len(p0))]
            if all(p[v] != c for v, c, _ in diseqs):
                return (True, self._model(p))
            t += 1

    # ------------------------------------------------------------------
    # propagation
    # ------------------------------------------------------------------

    def _propagate(self):
        out = []
        assigned = self._assigned
        if self._pending_ground:
            for a in self._pending_ground:
                if a not in assigned:
                    lit = a if self._ground[a] else -a
                    out.append((lit, [lit]))
            self._pending_ground = []
        if not self._dirty:
            return out
        ints_on = self._ints_on
        for v in self._dirty:
            if self._lo[v] is None and self._up[v] is None:
                continue
            for a in self._atoms_on[v]:
                if a in assigned:
                    continue
                _, kind, c = self._atoms[a]
                try:
                    val = self._implied(v, kind, c)
                except Undecided:
                    continue                    # optional: skip, never guess
                if val is None:
                    continue
                lit = a if val[0] else -a
                out.append((lit, _dedupe([lit] + [-r for r in val[1]])))
            for a in ints_on.get(v, ()):
                if a in assigned:
                    continue
                try:
                    val = self._int_verdict(*self._ints[a])
                except Undecided:
                    continue
                if val is not None:
                    lit = a if val[0] else -a
                    out.append((lit, _dedupe([lit] + [-r for r in val[1]])))
        self._dirty = set()
        self.stats["propagations"] += len(out)
        return out

    def _implied(self, v, kind, c):
        """Truth of atom ``v kind c`` implied by the current bounds of
        ``v``: None, or ``(value, bound literals used)``."""
        l, u = self._lo[v], self._up[v]
        c0 = (c, _ZERO)
        if kind == "!=":
            r = self._implied(v, "=", c)
            return None if r is None else (not r[0], r[1])
        if kind == "=":
            if l is not None and l > c0:
                return (False, [self._lo_r[v]])
            if u is not None and u < c0:
                return (False, [self._up_r[v]])
            if l == c0 and u == c0:
                return (True, [self._lo_r[v], self._up_r[v]])
            return None
        if kind == "<=":
            t = u is not None and u <= c0
            f = l is not None and l > c0
        elif kind == "<":
            t = u is not None and u < c0
            f = l is not None and l >= c0
        elif kind == ">=":
            t = l is not None and l >= c0
            f = u is not None and u < c0
        else:  # ">"
            t = l is not None and l > c0
            f = u is not None and u <= c0
        if t:
            return (True, [self._up_r[v] if kind[0] == "<" else self._lo_r[v]])
        if f:
            return (False, [self._lo_r[v] if kind[0] == "<" else self._up_r[v]])
        return None

    def __repr__(self) -> str:
        return (f"LRATheory({len(self._key)} vars, {len(self._rows)} rows, "
                f"{len(self._atoms)} atoms, level {len(self._lims)})")
