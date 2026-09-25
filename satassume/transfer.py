"""Predicate transfer across equal terms: facts shared between equal expressions.

:class:`TransferTheory` is a propagating theory (contract in
:mod:`satassume.theory`) that closes the gap :mod:`satassume.euf` leaves
out: *substitution of equals into unary predicates*.  Whenever the EUF
theory of a session has two terms ``a`` and ``b`` in one congruence class
(from equality atoms, transitivity, congruence ``f(x) = f(y)`` from
``x = y``, or a number: ``x = 2`` puts ``x`` in the class of the value
``2``), every predicate ``P`` of the vocabulary holds for ``a`` iff it
holds for ``b``.  The theory enforces exactly the clauses

    eq(a, b) -> (P(a) <-> P(b))

for every pair of terms and every predicate, without materializing them:

* its atoms are the predicate variables of the session's node blocks
  (``payload = (term, predicate index)``, the term being the EUF term of
  the node's expression, see ``EUFAdapter.node_term``);
* ``assert_lit`` records the value; a term whose class has another member
  is queued, and so is the new representative of every EUF union
  (``EUFTheory.on_merge``);
* ``propagate`` looks at each queued class once: per predicate, the first
  assigned variable in the class is the *witness*; every other variable
  of that predicate in the class gets the witness's value, with the reason

      [P(b), ~P(a)] + [~l for l in euf.explain(a, b)]

  (all literals but the first are false: ``P(a)`` and the explanation
  literals are asserted).  A variable already assigned the opposite value
  makes that clause a conflict, which the solver handles as such;
* ``check`` rescans every class (the eager path finds everything; this is
  the completeness backstop the contract asks for at a total assignment).

The theory keeps no derived state: what it propagates is recomputed from
the current EUF classes and its own assignment, so EUF's undo needs no
hook, and ``pop_level`` only forgets the values asserted above the level.

Soundness: ``Q.eq(a, b)`` is equality of values, and every predicate of the
vocabulary is a property of a value, so ``a = b`` and ``P(a)`` give
``P(b)``.  Ordering relations are not transferred (they are LRA's), and
equalities LRA derives from inequalities are not handed to EUF.

The session glue (which terms EUF sees, when the theory is engaged) is in
:class:`satassume.relations.Relations`.
"""
from __future__ import annotations

__all__ = ["TransferTheory"]


class TransferTheory:
    """Unary facts shared across the congruence classes of one
    :class:`satassume.euf.EUFTheory`."""

    def __init__(self, euf):
        self.euf = euf
        self._atoms: dict[int, tuple] = {}       # var -> (term, pred)
        self._by_term: dict[int, dict] = {}      # term -> {pred: [var, ...]}
        self._val: dict[int, bool] = {}          # var -> asserted value
        self._trail: list[int] = []
        self._lims: list[int] = []
        self._dirty: list[int] = []              # terms whose class needs a look
        euf.on_merge = self._merged
        self.stats = {"propagated": 0, "conflicts": 0}

    # ------------------------------------------------------------------
    def _merged(self, ra: int, rb: int) -> None:
        self._dirty.append(rb)

    def register_atom(self, literal: int, payload) -> None:
        if literal <= 0 or literal in self._atoms:
            raise ValueError(f"bad or repeated atom variable {literal}")
        term, pred = payload
        self._atoms[literal] = (term, pred)
        d = self._by_term.get(term)
        if d is None:
            d = self._by_term[term] = {}
        vs = d.get(pred)
        if vs is None:
            d[pred] = [literal]
        else:
            vs.append(literal)
        self._dirty.append(term)

    def assert_lit(self, literal: int):
        v = -literal if literal < 0 else literal
        a = self._atoms.get(v)
        if a is None:
            return None
        self._val[v] = literal > 0
        if self._lims:
            self._trail.append(v)
        euf = self.euf
        if len(euf._members[euf._repr[a[0]]]) > 1:
            self._dirty.append(a[0])
        return None

    # ------------------------------------------------------------------
    def _scan(self, r: int, out: list) -> None:
        """Append to ``out`` the transfers the class of representative
        ``r`` implies (including ones whose literal is already false:
        conflicts)."""
        euf = self.euf
        members = euf._members[r]
        if len(members) < 2:
            return
        by_term = self._by_term
        per: dict = {}
        for m in members:
            d = by_term.get(m)
            if d:
                for p, vs in d.items():
                    lst = per.get(p)
                    if lst is None:
                        per[p] = [(m, vs)]
                    else:
                        lst.append((m, vs))
        if not per:
            return
        val = self._val
        expl: dict = {}
        for lst in per.values():
            if len(lst) < 2 and len(lst[0][1]) < 2:
                continue
            wit = None
            for m, vs in lst:
                for v in vs:
                    b = val.get(v)
                    if b is not None:
                        wit = (m, v, b)
                        break
                if wit is not None:
                    break
            if wit is None:
                continue
            wm, wv, wb = wit
            wneg = -wv if wb else wv          # the negated witness literal
            for m, vs in lst:
                for v in vs:
                    if v == wv or val.get(v) is wb:
                        continue
                    lit = v if wb else -v
                    key = (wm, m)
                    e = expl.get(key)
                    if e is None:
                        e = expl[key] = [-l for l in euf.explain(wm, m)] if wm != m else []
                    out.append((lit, [lit, wneg] + e))

    def propagate(self):
        dirty = self._dirty
        if not dirty:
            return []
        rep = self.euf._repr
        seen = set()
        out: list = []
        for t in dirty:
            r = rep[t]
            if r not in seen:
                seen.add(r)
                self._scan(r, out)
        dirty.clear()
        self.stats["propagated"] += len(out)
        return out

    def check(self):
        rep = self.euf._repr
        seen = set()
        out: list = []
        for t in self._by_term:
            r = rep[t]
            if r not in seen:
                seen.add(r)
                self._scan(r, out)
        val = self._val
        for lit, why in out:
            b = val.get(-lit if lit < 0 else lit)
            if b is not None and b != (lit > 0):
                self.stats["conflicts"] += 1
                return (False, why)
        return None

    def push_level(self) -> None:
        self._lims.append(len(self._trail))

    def pop_level(self) -> None:
        lim = self._lims.pop()
        trail, val = self._trail, self._val
        while len(trail) > lim:
            del val[trail.pop()]

    # ------------------------------------------------------------------
    def level(self) -> int:
        return len(self._lims)

    def __repr__(self) -> str:
        return (f"<TransferTheory {len(self._atoms)} atoms over "
                f"{len(self._by_term)} terms, level {len(self._lims)}>")
