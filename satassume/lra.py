"""Linear real arithmetic (LRA) theory solver for satassume's DPLL(T) layer.

The solver implements :class:`satassume.theory.TheorySolver` (plus the
optional ``propagate``) for conjunctions of linear constraints over the
reals, with the general simplex of Dutertre and de Moura, "A Fast
Linear-Arithmetic Solver for DPLL(T)" (CAV 2006).  Arithmetic is exact
(:class:`fractions.Fraction`); strict bounds use delta-rationals ``q + d*delta``
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
* ``propagate``: O(atoms on the variables whose bounds changed).
* ``register_atom``: O(length of the form * row length) for a new slack.
"""
from __future__ import annotations

from fractions import Fraction
from typing import Any, Hashable, Iterable, NamedTuple

__all__ = ["LRATheory", "Negated", "constraint"]

_ZERO = Fraction(0)
_ONE = Fraction(1)

# bound kinds; _NEG maps a kind to the kind of the negated atom
_NEG = {"<=": ">", "<": ">=", ">=": "<", ">": "<=", "=": "!=", "!=": "="}
_FLIP = {"<=": ">=", "<": ">", ">=": "<=", ">": "<", "=": "=", "!=": "!="}

# trail entry tags
_LO, _UP, _ASG, _DIS = 0, 1, 2, 3


class Negated(NamedTuple):
    """Payload wrapper: the registered atom is the negation of ``payload``."""
    payload: Any


def constraint(terms, op: str, rhs=0):
    """Convenience payload builder: ``sum(c*t) op rhs`` with ``op`` one of
    ``< <= > >= = == !=``.  ``>``/``>=`` are negated into ``<``/``<=``;
    ``!=`` gives ``Negated`` of the equality."""
    items = terms.items() if isinstance(terms, dict) else terms
    items = tuple((t, Fraction(c)) for t, c in items)
    rhs = Fraction(rhs)
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
        # undo trail and level marks
        self._trail: list[tuple] = []
        self._lims: list[int] = []
        # propagation work list
        self._dirty: set[int] = set()
        self._pending_ground: list[int] = []
        self.stats = {"pivots": 0, "checks": 0, "conflicts": 0,
                      "propagations": 0}

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
        row = {k: a for k, a in row.items() if a}
        s = self._new_var(None)
        self._slack_of[form] = s
        vq = vd = _ZERO
        for k, a in row.items():
            vq += a * self._vq[k]
            vd += a * self._vd[k]
            self._cols[k].add(s)
        self._vq[s] = vq
        self._vd[s] = vd
        rows[s] = row
        return s

    def register_atom(self, literal: int, payload: Any) -> None:
        if literal <= 0:
            raise ValueError("register_atom takes a positive literal")
        if literal in self._atoms or literal in self._ground:
            raise ValueError(f"literal {literal} registered twice")
        negated = False
        while isinstance(payload, Negated):
            negated = not negated
            payload = payload.payload
        terms, constant, strict, equality = payload
        items = terms.items() if isinstance(terms, dict) else terms
        lin: dict[Hashable, Fraction] = {}
        for t, c in items:
            lin[t] = lin.get(t, _ZERO) + Fraction(c)
        for t in lin:                   # every term gets a model value,
            self._term_var(t)           # also one with coefficient 0
        lin = {t: c for t, c in lin.items() if c}
        k = Fraction(constant)
        kind = "=" if equality else "<" if strict else "<="
        if negated:
            kind = _NEG[kind]
        if not lin:
            truth = {"=": 0 == k, "!=": 0 != k, "<": 0 < k, "<=": 0 <= k,
                     ">": 0 > k, ">=": 0 >= k}[kind]
            self._ground[literal] = truth
            self._pending_ground.append(literal)
            return
        vs = sorted((self._term_var(t), c) for t, c in lin.items())
        if len(vs) == 1:
            (v, c), = vs
        else:
            c = vs[0][1]
            form = tuple((w, a / c) for w, a in vs)
            v = self._slack(form)
        bound = k / c
        if c < 0:
            kind = _FLIP[kind]
        self._atoms[literal] = (v, kind, bound)
        self._atoms_on[v].append(literal)
        self._dirty.add(v)

    # ------------------------------------------------------------------
    # levels
    # ------------------------------------------------------------------

    def push_level(self) -> None:
        self._lims.append(len(self._trail))

    def pop_level(self) -> None:
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
            else:
                self._diseqs.pop()

    # ------------------------------------------------------------------
    # asserting
    # ------------------------------------------------------------------

    def assert_lit(self, literal: int):
        a = abs(literal)
        atom = self._atoms.get(a)
        if atom is None:
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
        """Move nonbasic ``v`` to value ``b``, keeping every row satisfied."""
        dq = b[0] - self._vq[v]
        dd = b[1] - self._vd[v]
        vq, vd, rows = self._vq, self._vd, self._rows
        for r in self._cols[v]:
            a = rows[r][v]
            vq[r] += a * dq
            vd[r] += a * dd
        vq[v] = b[0]
        vd[v] = b[1]

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
        vq[b], vd[b] = target
        vq[j] += tq
        vd[j] += td
        for k in cols[j]:
            if k != b:
                ak = rows[k][j]
                vq[k] += ak * tq
                vd[k] += ak * td
        self._pivot(b, j)

    def _pivot(self, b: int, j: int) -> None:
        """Make ``j`` basic in place of ``b`` (``b`` becomes nonbasic)."""
        self.stats["pivots"] += 1
        rows, cols = self._rows, self._cols
        row = rows.pop(b)
        a = row.pop(j)
        inv = _ONE / a
        newrow = {b: inv}
        for k, c in row.items():
            cols[k].discard(b)
            newrow[k] = -c * inv
        cj = cols[j]
        cj.discard(b)
        for r in cj:
            rr = rows[r]
            f = rr.pop(j)
            for k, c in newrow.items():
                nv = rr.get(k, _ZERO) + f * c
                if nv:
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

    def check(self):
        self.stats["checks"] += 1
        conflict = self._simplex()
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

    def propagate(self):
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
        for v in self._dirty:
            if self._lo[v] is None and self._up[v] is None:
                continue
            for a in self._atoms_on[v]:
                if a in assigned:
                    continue
                _, kind, c = self._atoms[a]
                val = self._implied(v, kind, c)
                if val is None:
                    continue
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
