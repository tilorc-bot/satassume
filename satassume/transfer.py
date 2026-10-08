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

The atoms are registered *lazy* (``Solver.register_atom(..., mention=False)``):
they do not mention their variables, so the rule block writes its
implications above root only to variables something else mentions (a
clause, an assumption, the query, another theory), and the search does not
decide the rest.  No transfer is lost by that: every literal of a block
that the block did not imply itself (a decision, an assumption, a clause's
or a theory's propagation) is on the trail and reported here, so it reaches
every atom of its predicate in the class; each equal term's block then
asserts the same literals and its closure implies what the first block's
does (the closure is exact), writing it where mentioned.  A class's atoms of
one predicate are therefore all assigned alike or all unassigned; the
latter are completed per block from the same assigned values, alike, except
on a *partial* node (only some of its variables atoms), which ``decide``
settles before the final check.

The theory keeps no derived state: what it propagates is recomputed from
the current EUF classes and its own assignment, so EUF's undo needs no
hook, and ``pop_level`` only forgets the values asserted above the level.

Soundness: ``Q.eq(a, b)`` is equality of values, and every predicate of the
vocabulary is a property of a value, so ``a = b`` and ``P(a)`` give
``P(b)``.  Ordering relations are not transferred (they are LRA's), and
equalities LRA derives from inequalities are not handed to EUF.

Switched on per query: the session guards the theory with a selector
variable (:meth:`TransferTheory.guard`), registered as one of its atoms.
While the selector is not true the theory propagates, checks and decides
nothing; every reason and conflict clause it returns ends with the
negated selector, so a clause learnt from it is inert wherever the
selector is not assumed; when the selector turns true at some level every
class with two or more members is rescanned, and popping that level
switches the theory off again.

Terms are switched too (:meth:`TransferTheory.switch`): a term whose
candidacy comes from equality atoms (a side of one) takes part only while
one of its two enable variables is true, all its predicates with the
*full* one, ``polar`` alone with the *polar* one (it is then a partial
node, see ``decide``).  The session makes those variables true exactly in
the queries whose atoms make the term a side (see
``Relations._apply_role``); every lemma that uses a switched term carries
the negation of the enable variable it used.  Terms not switched (numbers,
congruent applications) always take part.

The session glue (which terms EUF sees, when the theory is engaged and
which queries assume its selector) is in
:class:`satassume.relations.Relations`.
"""
from __future__ import annotations

from .rules import BASIS_INDEX

__all__ = ["TransferTheory"]

_POLAR = BASIS_INDEX["polar"]
_POLAR_ONLY = frozenset({_POLAR})


class TransferTheory:
    """Unary facts shared across the congruence classes of one
    :class:`satassume.euf.EUFTheory`."""

    def __init__(self, euf):
        self.euf = euf
        #: the selector guarding every lemma (see :meth:`guard`); None:
        #: always on
        self.sel: int | None = None
        self.enabled = True
        self._ehist: list[tuple[int, bool]] = []   # (level, previous enabled)
        self._rescan = False
        self._atoms: dict[int, tuple] = {}       # var -> (term, pred)
        self._by_term: dict[int, dict] = {}      # term -> {pred: [var, ...]}
        self._val: dict[int, bool] = {}          # var -> asserted value
        self._trail: list[int] = []
        self._lims: list[int] = []
        self._dirty: list[int] = []              # terms whose class needs a look
        self._dirty_p: list[int] = []            # asserted vars to spread
        self._fixed: dict[int, dict] = {}        # term -> {pred: value} (numbers)
        #: term -> predicates with an atom of a *partial* node of the term
        #: (payload ``(term, pred, True)``: not every variable of the node's
        #: block is an atom), see ``decide``
        self._pterms: dict[int, set] = {}
        #: representatives of classes that had two or more members when
        #: noted (for ``decide``; stale entries are dropped there)
        self._multi: list[int] = [r for r, ms in enumerate(euf._members)
                                  if len(ms) > 1 and euf._repr[r] == r]
        #: switched terms (:meth:`switch`): term -> (full var, polar var),
        #: 0 for none; and enable variable -> (term, kind: 2 full, 1 polar)
        self._sw: dict[int, tuple] = {}
        self._onv: dict[int, tuple] = {}
        self._on: dict[int, bool] = {}           # enable var -> asserted value
        self._otrail: list[int] = []
        self._olims: list[int] = []
        euf.on_merge = self._merged
        self.stats = {"propagated": 0, "conflicts": 0}

    def guard(self, sel: int) -> None:
        """Make every lemma conditional on the selector variable ``sel``,
        which the caller registers as an atom of this theory: while ``sel``
        is not assigned true the theory propagates, checks and decides
        nothing; every reason and conflict clause it returns carries
        ``-sel``; when ``sel`` turns true at some level every class is
        looked at again, and when that level is popped the theory is off
        again.  A clause the solver learns from a lemma therefore keeps
        ``-sel`` and is inert where ``sel`` is not assumed."""
        self.sel = sel
        self.enabled = False

    def switch(self, term: int, full: int, polar: int) -> list:
        """Make ``term``'s atoms take part only while ``full`` (all of them)
        or ``polar`` (its ``polar`` atom alone) is true; 0 for none.  May be
        called again with new variables for a term.  Returns the variables
        new to the theory, which the caller registers as atoms of it (any
        payload)."""
        old = self._sw.get(term, (0, 0))
        new = []
        for v, k in ((full, 2), (polar, 1)):
            if v and v not in self._onv:
                self._onv[v] = (term, k)
                new.append(v)
        self._sw[term] = (full or old[0], polar or old[1])
        self._dirty.append(term)
        return new

    def unswitch(self, term: int) -> None:
        """``term`` takes part always from now on (a candidate for another
        reason, see ``Relations.sync_transfer``)."""
        if self._sw.pop(term, None) is not None:
            self._dirty.append(term)

    def _kind(self, m: int) -> int:
        """2: every predicate of term ``m`` takes part, 1: ``polar`` only,
        0: none (see :meth:`switch`)."""
        sw = self._sw.get(m)
        if sw is None:
            return 2
        on = self._on
        if sw[0] and on.get(sw[0]):
            return 2
        if sw[1] and on.get(sw[1]):
            return 1
        return 0

    def _why(self, m: int, k: int) -> list:
        """The negated enable variable term ``m`` takes part by (kind ``k``),
        for a lemma: [] if ``m`` is not switched."""
        sw = self._sw.get(m)
        if sw is None:
            return []
        return [-sw[0]] if k == 2 else [-sw[1]]

    # ------------------------------------------------------------------
    def _merged(self, ra: int, rb: int) -> None:
        self._dirty.append(rb)
        self._multi.append(rb)

    def register_atom(self, literal: int, payload) -> None:
        if literal == self.sel or literal in self._onv:
            return
        if literal <= 0 or literal in self._atoms:
            raise ValueError(f"bad or repeated atom variable {literal}")
        term, pred = payload[0], payload[1]
        self._atoms[literal] = (term, pred)
        if len(payload) > 2 and payload[2]:
            ps = self._pterms.get(term)
            if ps is None:
                self._pterms[term] = {pred}
            else:
                ps.add(pred)
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
        if v == self.sel:
            on = literal > 0
            if on != self.enabled:
                self._ehist.append((len(self._lims), self.enabled))
                self.enabled = on
                if on:
                    self._rescan = True
            return None
        o = self._onv.get(v)
        if o is not None:
            self._on[v] = literal > 0
            if self._olims:
                self._otrail.append(v)
            if literal > 0:
                self._dirty.append(o[0])
            return None
        a = self._atoms.get(v)
        if a is None:
            return None
        self._val[v] = literal > 0
        if self._lims:
            self._trail.append(v)
        euf = self.euf
        if len(euf._members[euf._repr[a[0]]]) > 1:
            self._dirty_p.append(v)
        return None

    # ------------------------------------------------------------------
    def set_fixed(self, term: int, facts) -> None:
        """Give ``term`` fixed, context-free facts ``[(pred, value), ...]``
        (a number's, see ``Relations._transfer_terms``) without a variable:
        every term EUF puts into its class gets them, with reasons made of
        the explanation of the equality alone (the facts are axioms of the
        theory).  Called at root."""
        if term in self._fixed:
            return
        self._fixed[term] = dict(facts)
        self._dirty.append(term)

    def _explain(self, a: int, b: int, memo: dict) -> list:
        if a == b:
            return []
        e = memo.get((a, b))
        if e is None:
            e = memo[(a, b)] = [-l for l in self.euf.explain(a, b)]
        return e

    def _members_on(self, members, p=None):
        """``(term, {pred: vars}, kind)`` for the members of a class that
        take part (see :meth:`switch`); a member with ``polar`` only is
        given its ``polar`` atoms alone."""
        by_term, sw = self._by_term, self._sw
        out = []
        for m in members:
            d = by_term.get(m)
            if not d:
                continue
            if sw and m in sw:
                k = self._kind(m)
                if k == 0:
                    continue
                if k == 1:
                    vs = d.get(_POLAR)
                    if vs is None:
                        continue
                    d = {_POLAR: vs}
                out.append((m, d, k))
            else:
                out.append((m, d, 2))
        return out

    def _scan(self, r: int, out: list) -> None:
        """Append to ``out`` the transfers the class of representative
        ``r`` implies (including ones whose literal is already false:
        conflicts)."""
        euf = self.euf
        members = euf._members[r]
        if len(members) < 2:
            return
        fixed = self._fixed
        ds = self._members_on(members)
        fs = [(m, f) for m in members if (f := fixed.get(m))] if fixed else []
        if not ds or (len(ds) < 2 and not fs
                      and all(len(vs) < 2 for vs in ds[0][1].values())):
            return
        per: dict = {}
        for m, d, k in ds:
            for p, vs in d.items():
                lst = per.get(p)
                if lst is None:
                    per[p] = [(m, vs, k)]
                else:
                    lst.append((m, vs, k))
        val = self._val
        sw = self._sw
        memo: dict = {}
        for p, lst in per.items():
            wit = None
            for m, f in fs:
                b = f.get(p)
                if b is not None:
                    wit = (m, 0, b, 2)
                    break
            if wit is None:
                if len(lst) < 2 and len(lst[0][1]) < 2:
                    continue
                for m, vs, k in lst:
                    for v in vs:
                        b = val.get(v)
                        if b is not None:
                            wit = (m, v, b, k)
                            break
                    if wit is not None:
                        break
                if wit is None:
                    continue
            wm, wv, wb, wk = wit
            head = [-wv if wb else wv] if wv else []   # the negated witness
            if sw:
                head += self._why(wm, wk)
            for m, vs, k in lst:
                tail = None
                for v in vs:
                    if v == wv or val.get(v) is wb:
                        continue
                    if tail is None:
                        tail = self._explain(wm, m, memo)
                        if sw and m != wm:
                            tail = tail + self._why(m, k)
                    lit = v if wb else -v
                    out.append((lit, [lit] + head + tail))

    def _spread(self, v: int, out: list) -> None:
        """Append the transfers of asserted variable ``v``'s value to the
        other variables of its predicate in its class (and the conflict with
        a fixed fact of the class, if any)."""
        wb = self._val.get(v)
        if wb is None:
            return
        wm, p = self._atoms[v]
        sw = self._sw
        wneg = [-v if wb else v]
        if sw and wm in sw:
            k = self._kind(wm)
            if k == 0 or (k == 1 and p != _POLAR):
                return
            wneg += self._why(wm, k)
        euf = self.euf
        members = euf._members[euf._repr[wm]]
        by_term, val, fixed = self._by_term, self._val, self._fixed
        memo: dict = {}
        for m in members:
            if fixed:
                f = fixed.get(m)
                if f is not None:
                    b = f.get(p)
                    if b is not None and b != wb:
                        lit = v if b else -v          # false: a conflict
                        out.append((lit, [lit] + wneg[1:] + self._explain(m, wm, memo)))
                        return
            d = by_term.get(m)
            if d is None:
                continue
            vs = d.get(p)
            if vs is None:
                continue
            whym = ()
            if sw and m in sw and m != wm:
                k = self._kind(m)
                if k == 0 or (k == 1 and p != _POLAR):
                    continue
                whym = self._why(m, k)
            for u in vs:
                if u == v or val.get(u) is wb:
                    continue
                lit = u if wb else -u
                out.append((lit, [lit] + wneg + self._explain(wm, m, memo) + list(whym)))

    def _classes(self) -> list:
        """The representatives of the classes with two or more members
        (each once), from ``_multi``, which is pruned to them: a class
        that is a singleton now stays one until a merge notes it again
        (backtracking only splits classes)."""
        euf = self.euf
        rep, members = euf._repr, euf._members
        keep, reps, kept, seen = [], [], set(), set()
        for r0 in self._multi:
            r = rep[r0]
            if len(members[r]) > 1:
                if r0 not in kept:
                    kept.add(r0)
                    keep.append(r0)
                if r not in seen:
                    seen.add(r)
                    reps.append(r)
        self._multi = keep
        return reps

    def propagate(self):
        dirty, dirty_p = self._dirty, self._dirty_p
        if not self.enabled:
            dirty.clear()
            dirty_p.clear()
            return []
        if self._rescan:
            # switched on: every class with two or more members once (what
            # was queued while off was dropped; a singleton transfers
            # nothing)
            self._rescan = False
            dirty.extend(self._classes())
        if not dirty and not dirty_p:
            return []
        rep = self.euf._repr
        seen = set()
        out: list = []
        for t in dirty:
            r = rep[t]
            if r not in seen:
                seen.add(r)
                self._scan(r, out)
        for v in dirty_p:
            if rep[self._atoms[v][0]] not in seen:
                self._spread(v, out)
        dirty.clear()
        dirty_p.clear()
        self.stats["propagated"] += len(out)
        if self.sel is not None:
            g = -self.sel
            for _, why in out:
                why.append(g)
        return out

    def check(self):
        if not self.enabled:
            return None
        out: list = []
        for r in self._classes():
            self._scan(r, out)
        val = self._val
        for lit, why in out:
            b = val.get(-lit if lit < 0 else lit)
            if b is not None and b != (lit > 0):
                self.stats["conflicts"] += 1
                if self.sel is not None:
                    why.append(-self.sel)
                return (False, why)
        return None

    def decide(self):
        """A variable to decide, or None: the solver asks at an assignment
        total but for lazy variables (see ``Solver.register_atom(...,
        mention=False)``).

        After propagation the atoms of a predicate in one class are either
        all assigned alike or all unassigned (no witness).  All unassigned
        is consistent, and the stored model completes each lazy block
        variable from a model of its block containing the block's assigned
        values (``Solver._fill``, a function of those values).  Two nodes
        whose block variables are all atoms have the same assigned values
        in one class, so they are completed alike.  A *partial* node (only
        some of its variables are atoms: a link-only side, a rational
        number's basis, a switched term with ``polar`` alone on) may be
        completed differently from an equal term on an atom they share;
        such an atom, unassigned with another atom of its predicate in the
        class, is decided here, and propagation gives the rest the same
        value.  Only the atoms that take part count (see :meth:`switch`).

        Only classes noted by a merge are looked at (``_multi``)."""
        if not self._multi or not (self._pterms or self._sw) or not self.enabled:
            return None
        pterms = self._pterms
        members = self.euf._members
        val = self._val
        for r in self._classes():
            ds = self._members_on(members[r])
            preds = None
            for m, d, k in ds:
                ps = _POLAR_ONLY if k == 1 else pterms.get(m)
                if ps is not None:
                    preds = ps if preds is None else preds | ps
            if preds is None:
                continue
            for p in preds:
                first = None
                n = 0
                for m, d, k in ds:
                    vs = d.get(p)
                    if vs is None:
                        continue
                    for v in vs:
                        if v in val:
                            break
                    else:
                        if first is None:
                            first = vs[0]
                        n += len(vs)
                        continue
                    break
                else:
                    if n > 1:
                        return first
        return None

    def push_level(self) -> None:
        self._lims.append(len(self._trail))
        self._olims.append(len(self._otrail))

    def pop_level(self) -> None:
        lim = self._lims.pop()
        trail, val = self._trail, self._val
        while len(trail) > lim:
            del val[trail.pop()]
        lim = self._olims.pop()
        trail, on = self._otrail, self._on
        while len(trail) > lim:
            del on[trail.pop()]
        eh = self._ehist
        n = len(self._lims)
        while eh and eh[-1][0] > n:
            self.enabled = eh.pop()[1]

    # ------------------------------------------------------------------
    def level(self) -> int:
        return len(self._lims)

    def __repr__(self) -> str:
        return (f"<TransferTheory {len(self._atoms)} atoms over "
                f"{len(self._by_term)} terms, level {len(self._lims)}>")
