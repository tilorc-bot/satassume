"""Incremental CDCL SAT solver in pure Python.

This is the propositional core of the assumptions engine.  It is a fairly
direct, MiniSat-flavoured CDCL solver:

* two watched literals per clause, iterative propagation;
* first-UIP conflict analysis with basic clause minimization and
  non-chronological backjumping;
* VSIDS variable activities kept in an indexed binary heap, phase saving;
* Luby restarts, simple activity-based deletion of learned clauses;
* MiniSat-style assumptions (the first decisions of a search) with a proper
  final-conflict analysis (:meth:`Solver.conflict`).

Literals are plain signed integers externally (``v`` / ``-v``, ``v >= 1``).
Internally a literal is encoded as ``2*v + (1 if negative else 0)`` so that
all per-literal data lives in flat lists indexed by literal and negation is
``lit ^ 1``.  Variable ``v`` of a literal is ``lit >> 1``.

Assignments are stored per *literal*: ``_val[lit]`` is ``True``, ``False`` or
``None``, with ``_val[lit ^ 1]`` always the complement.

The solver is always at decision level 0 between public calls.  Level-0
assignments are permanent facts entailed by the clause set (found by unit
propagation, by unit clauses, or as learned unit clauses).
"""
from __future__ import annotations

from collections.abc import Iterable


class Clause(list):
    """A clause: a list of internal literals plus an activity score.

    Watched literals are always at positions 0 and 1.  For a clause that is
    the reason of an assignment, the implied literal is at position 0.
    """

    __slots__ = ("act", "learnt")

    def __init__(self, lits, learnt=False):
        list.__init__(self, lits)
        self.learnt = learnt
        self.act = 0.0


def _luby(y: float, x: int) -> float:
    """The x-th element of the Luby restart sequence with base y."""
    size = 1
    seq = 0
    while size < x + 1:
        seq += 1
        size = 2 * size + 1
    while size - 1 != x:
        size = (size - 1) >> 1
        seq -= 1
        x = x % size
    return y ** seq


class Solver:
    """Incremental CDCL SAT solver.  See the module docstring."""

    # Tunables (MiniSat defaults, mostly).
    _var_decay = 0.95
    _cla_decay = 0.999
    _restart_first = 100
    _restart_inc = 2.0
    _learnt_size_inc = 1.1
    _learnt_size_min = 1000

    def __init__(self):
        # Per-literal data; indices 0 and 1 are unused (variable 0 is not a var).
        self._val: list[bool | None] = [None, None]
        self._watches: list[list[Clause]] = [[], []]
        # Per-variable data; index 0 unused.
        self._level: list[int] = [0]
        self._reason: list[Clause | None] = [None]
        self._act: list[float] = [0.0]
        self._polarity: list[int] = [1]      # 1: last/default phase is negative
        self._hpos: list[int] = [-1]         # position in the activity heap, -1 if absent
        self._seen: list[int] = [0]
        self._heap: list[int] = []           # max-heap of variables keyed by activity
        self._trail: list[int] = []
        self._trail_lim: list[int] = []
        self._qhead = 0
        self._clauses: list[Clause] = []
        self._learnts: list[Clause] = []
        self._ok = True
        self._nvars = 0
        self._var_inc = 1.0
        self._cla_inc = 1.0
        self._max_learnts = 0.0
        self._assumptions: list[int] = []
        self._model: dict[int, bool] | None = None
        # Last model found by any solve; a cheap witness that a set of
        # assumptions is consistent.  Invalidated when clauses are added.
        self._witness: dict[int, bool] | None = None
        self._conflict: list[int] = []
        # Statistics.
        self._n_props = 0
        self._n_conflicts = 0
        self._n_decisions = 0
        self._n_learned = 0
        self._n_restarts = 0

    # ------------------------------------------------------------------
    # Variables and literal encoding
    # ------------------------------------------------------------------

    def new_var(self) -> int:
        """Allocate and return a fresh variable id (1-based)."""
        v = self._nvars + 1
        self._grow(v)
        return v

    def nvars(self) -> int:
        return self._nvars

    def _grow(self, v: int) -> None:
        """Make sure variables ``1..v`` exist."""
        n = self._nvars
        if v <= n:
            return
        val = self._val
        watches = self._watches
        for u in range(n + 1, v + 1):
            val.append(None)
            val.append(None)
            watches.append([])
            watches.append([])
            self._level.append(0)
            self._reason.append(None)
            self._act.append(0.0)
            self._polarity.append(1)
            self._hpos.append(-1)
            self._seen.append(0)
            self._heap_insert(u)
        self._nvars = v

    @staticmethod
    def _to_int(x: int) -> int:
        return 2 * x if x > 0 else 2 * (-x) + 1

    @staticmethod
    def _to_ext(l: int) -> int:
        return -(l >> 1) if l & 1 else (l >> 1)

    def _internal_lits(self, lits) -> list[int]:
        out = []
        maxv = 0
        for x in lits:
            x = int(x)
            if x == 0:
                raise ValueError("literal must be a nonzero integer")
            v = -x if x < 0 else x
            maxv = max(maxv, v)
            out.append(2 * v + 1 if x < 0 else 2 * v)
        if maxv > self._nvars:
            self._grow(maxv)
        return out

    # ------------------------------------------------------------------
    # Activity heap (indexed binary max-heap on variable activity)
    # ------------------------------------------------------------------

    def _heap_insert(self, v: int) -> None:
        hpos = self._hpos
        if hpos[v] >= 0:
            return
        heap = self._heap
        hpos[v] = len(heap)
        heap.append(v)
        self._heap_up(len(heap) - 1)

    def _heap_up(self, i: int) -> None:
        heap = self._heap
        hpos = self._hpos
        act = self._act
        v = heap[i]
        a = act[v]
        while i > 0:
            p = (i - 1) >> 1
            pv = heap[p]
            if act[pv] >= a:
                break
            heap[i] = pv
            hpos[pv] = i
            i = p
        heap[i] = v
        hpos[v] = i

    def _heap_down(self, i: int) -> None:
        heap = self._heap
        hpos = self._hpos
        act = self._act
        n = len(heap)
        v = heap[i]
        a = act[v]
        while True:
            c = 2 * i + 1
            if c >= n:
                break
            r = c + 1
            if r < n and act[heap[r]] > act[heap[c]]:
                c = r
            cv = heap[c]
            if act[cv] <= a:
                break
            heap[i] = cv
            hpos[cv] = i
            i = c
        heap[i] = v
        hpos[v] = i

    def _heap_pop(self) -> int:
        heap = self._heap
        hpos = self._hpos
        v = heap[0]
        last = heap.pop()
        hpos[v] = -1
        if heap:
            heap[0] = last
            hpos[last] = 0
            self._heap_down(0)
        return v

    def _bump_var(self, v: int) -> None:
        act = self._act
        a = act[v] + self._var_inc
        act[v] = a
        if a > 1e100:
            for u in range(1, self._nvars + 1):
                act[u] *= 1e-100
            self._var_inc *= 1e-100
        if self._hpos[v] >= 0:
            self._heap_up(self._hpos[v])

    def _bump_clause(self, c: Clause) -> None:
        c.act += self._cla_inc
        if c.act > 1e20:
            for d in self._learnts:
                d.act *= 1e-20
            self._cla_inc *= 1e-20

    # ------------------------------------------------------------------
    # Clause database
    # ------------------------------------------------------------------

    def add_clause(self, lits: Iterable[int]) -> bool:
        """Add a clause.  Returns False iff the formula is now UNSAT at root.

        Duplicate literals are merged, tautologies are dropped, literals
        false at root are removed and clauses satisfied at root are dropped.
        A unit clause is assigned and propagated immediately.
        """
        if not self._ok:
            return False
        if self._trail_lim:
            self._backtrack(0)
        raw = self._internal_lits(list(lits))
        val = self._val
        out: list[int] = []
        seen = set()
        for l in raw:
            if l in seen:
                continue
            if (l ^ 1) in seen:
                return True                     # tautology
            vl = val[l]
            if vl is True:
                return True                     # satisfied at root
            if vl is False:
                continue                        # false at root: drop literal
            seen.add(l)
            out.append(l)
        self._witness = None
        if not out:
            self._ok = False
            return False
        if len(out) == 1:
            l = out[0]
            val[l] = True
            val[l ^ 1] = False
            self._level[l >> 1] = 0
            self._reason[l >> 1] = None
            self._trail.append(l)
            if self._propagate() is not None:
                self._ok = False
                return False
            return True
        c = Clause(out)
        self._clauses.append(c)
        self._watches[out[0]].append(c)
        self._watches[out[1]].append(c)
        return True

    def add_pattern(self, pattern, base: int, nvars: int) -> bool:
        """Bulk-add ``pattern`` (clauses in internal encoding relative to
        variable 0) shifted so that pattern variable 0 becomes ``base``.

        The pattern must be tautology- and duplicate-free with no unit
        clauses (true for the rule base).  If any of the ``nvars`` target
        variables is already assigned at root the slow path is used, so the
        watch invariants always hold.
        """
        if not self._ok:
            return False
        if self._trail_lim:
            self._backtrack(0)
        top = base + nvars - 1
        if top > self._nvars:
            self._grow(top)
        val = self._val
        lo = 2 * base
        if any(val[l] is not None for l in range(lo, lo + 2 * nvars)):
            ok = True
            ext = self._to_ext
            for c in pattern:
                ok = self.add_clause([ext(l + lo) for l in c]) and ok
            return ok
        clauses = self._clauses
        watches = self._watches
        append = clauses.append
        for c in pattern:
            out = [l + lo for l in c]
            cl = Clause(out)
            append(cl)
            watches[out[0]].append(cl)
            watches[out[1]].append(cl)
        self._witness = None
        return True

    def propagate(self) -> bool:
        """Run unit propagation at root; False iff there is a root conflict."""
        if not self._ok:
            return False
        if self._trail_lim:
            self._backtrack(0)
        if self._propagate() is not None:
            self._ok = False
            return False
        return True

    # ------------------------------------------------------------------
    # Root-level queries
    # ------------------------------------------------------------------

    def value(self, lit: int) -> bool | None:
        """Truth value of ``lit`` at root level, or None if not fixed at root."""
        v = -lit if lit < 0 else lit
        if v == 0 or v > self._nvars:
            return None
        l = 2 * v + 1 if lit < 0 else 2 * v
        if self._trail_lim and self._level[v] > 0:
            return None
        return self._val[l]

    def root_trail(self) -> list[int]:
        """All literals assigned at root level, in assignment order."""
        trail = self._trail
        if self._trail_lim:
            trail = trail[: self._trail_lim[0]]
        ext = self._to_ext
        return [ext(l) for l in trail]

    def implied(self, assumptions: Iterable[int] = ()) -> list[int] | None:
        """Literals forced by unit propagation under ``assumptions``.

        Returns the list of *all* assigned literals (root facts, the
        assumptions and their consequences) or None if propagation runs into
        a conflict.  No search and no learning; the solver is left at root.
        """
        if not self._assume_propagate(assumptions):
            self._backtrack(0)
            return None
        ext = self._to_ext
        result = [ext(l) for l in self._trail]
        self._backtrack(0)
        return result

    def _assume_propagate(self, assumptions) -> bool:
        """Assume each literal at its own level and propagate.

        On success the solver is left in the assumed state (caller must
        backtrack).  Returns False on conflict or if the root is UNSAT.
        """
        if self._trail_lim:
            self._backtrack(0)
        if not self._ok:
            return False
        if self._propagate() is not None:
            self._ok = False
            return False
        lits = self._internal_lits(list(assumptions))
        val = self._val
        trail = self._trail
        trail_lim = self._trail_lim
        level = self._level
        reason = self._reason
        for l in lits:
            vl = val[l]
            if vl is True:
                continue
            if vl is False:
                return False
            trail_lim.append(len(trail))
            v = l >> 1
            val[l] = True
            val[l ^ 1] = False
            level[v] = len(trail_lim)
            reason[v] = None
            trail.append(l)
            if self._propagate() is not None:
                return False
        return True

    # ------------------------------------------------------------------
    # Propagation and backtracking
    # ------------------------------------------------------------------

    def _propagate(self) -> Clause | None:
        """Unit propagation from the current queue head.  Returns a
        conflicting clause or None."""
        val = self._val
        watches = self._watches
        trail = self._trail
        level = self._level
        reason = self._reason
        qhead = self._qhead
        dl = len(self._trail_lim)
        confl = None
        nprops = 0
        while qhead < len(trail):
            p = trail[qhead]
            qhead += 1
            nprops += 1
            fl = p ^ 1                          # this literal just became false
            ws = watches[fl]
            n = len(ws)
            if not n:
                continue
            i = 0
            j = 0
            while i < n:
                c = ws[i]
                i += 1
                # Make sure the false literal is c[1].
                if c[0] == fl:
                    c[0] = c[1]
                    c[1] = fl
                first = c[0]
                vf = val[first]
                if vf is True:
                    ws[j] = c
                    j += 1
                    continue
                # Look for a new literal to watch.
                k = 2
                m = len(c)
                while k < m:
                    l = c[k]
                    if val[l] is not False:
                        c[1] = l
                        c[k] = fl
                        watches[l].append(c)
                        break
                    k += 1
                else:
                    # Clause is unit or conflicting; keep watching fl.
                    ws[j] = c
                    j += 1
                    if vf is False:
                        confl = c
                        while i < n:
                            ws[j] = ws[i]
                            j += 1
                            i += 1
                        qhead = len(trail)
                    else:
                        v = first >> 1
                        val[first] = True
                        val[first ^ 1] = False
                        level[v] = dl
                        reason[v] = c
                        trail.append(first)
            del ws[j:]
        self._qhead = qhead
        self._n_props += nprops
        return confl

    def _backtrack(self, lvl: int) -> None:
        """Undo all assignments above decision level ``lvl``."""
        trail_lim = self._trail_lim
        if len(trail_lim) <= lvl:
            return
        trail = self._trail
        val = self._val
        pol = self._polarity
        hpos = self._hpos
        start = trail_lim[lvl]
        for i in range(len(trail) - 1, start - 1, -1):
            l = trail[i]
            v = l >> 1
            val[l] = None
            val[l ^ 1] = None
            pol[v] = l & 1
            if hpos[v] < 0:
                self._heap_insert(v)
        del trail[start:]
        self._qhead = start
        del trail_lim[lvl:]

    # ------------------------------------------------------------------
    # Conflict analysis
    # ------------------------------------------------------------------

    def _analyze(self, confl: Clause):
        """First-UIP analysis.  Returns ``(learnt, backtrack_level)`` with
        the asserting literal at ``learnt[0]`` and (if present) the literal
        of the backtrack level at ``learnt[1]``."""
        seen = self._seen
        level = self._level
        reason = self._reason
        trail = self._trail
        dl = len(self._trail_lim)
        learnt = [0]
        toclear = []
        path = 0
        p = -1
        index = len(trail) - 1
        while True:
            if confl.learnt:
                self._bump_clause(confl)
            for k in range(0 if p < 0 else 1, len(confl)):
                q = confl[k]
                v = q >> 1
                if not seen[v]:
                    lv = level[v]
                    if lv > 0:
                        seen[v] = 1
                        toclear.append(v)
                        self._bump_var(v)
                        if lv >= dl:
                            path += 1
                        else:
                            learnt.append(q)
            # Next literal on the current level to resolve on.
            while not seen[trail[index] >> 1]:
                index -= 1
            p = trail[index]
            index -= 1
            pv = p >> 1
            confl = reason[pv]
            seen[pv] = 0
            path -= 1
            if path == 0:
                break
        learnt[0] = p ^ 1

        # Basic clause minimization: drop literals whose reason clause is
        # entirely covered by other literals of the learnt clause.
        if len(learnt) > 1:
            j = 1
            for k in range(1, len(learnt)):
                q = learnt[k]
                r = reason[q >> 1]
                if r is None:
                    learnt[j] = q
                    j += 1
                    continue
                keep = False
                for m in range(1, len(r)):
                    u = r[m] >> 1
                    if not seen[u] and level[u] > 0:
                        keep = True
                        break
                if keep:
                    learnt[j] = q
                    j += 1
            del learnt[j:]
        for v in toclear:
            seen[v] = 0

        if len(learnt) == 1:
            return learnt, 0
        mi = 1
        ml = level[learnt[1] >> 1]
        for k in range(2, len(learnt)):
            lv = level[learnt[k] >> 1]
            if lv > ml:
                ml = lv
                mi = k
        learnt[1], learnt[mi] = learnt[mi], learnt[1]
        return learnt, ml

    def _analyze_final(self, p: int) -> None:
        """``p`` is an assumption that is false under the earlier
        assumptions.  Compute the subset of assumptions responsible."""
        out = [p]
        trail_lim = self._trail_lim
        if not trail_lim:
            self._conflict = out
            return
        seen = self._seen
        level = self._level
        reason = self._reason
        trail = self._trail
        seen[p >> 1] = 1
        for i in range(len(trail) - 1, trail_lim[0] - 1, -1):
            l = trail[i]
            v = l >> 1
            if seen[v]:
                r = reason[v]
                if r is None:
                    # A decision: every decision below the assumptions is
                    # itself an assumption.
                    if l != p:
                        out.append(l)
                else:
                    for k in range(1, len(r)):
                        u = r[k] >> 1
                        if level[u] > 0:
                            seen[u] = 1
                seen[v] = 0
        seen[p >> 1] = 0
        self._conflict = out

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _pick_branch(self) -> int:
        val = self._val
        heap = self._heap
        pol = self._polarity
        while heap:
            v = self._heap_pop()
            if val[2 * v] is None:
                return 2 * v + pol[v]
        return -1

    def _reduce_db(self) -> None:
        """Remove about half of the learned clauses with low activity."""
        learnts = self._learnts
        learnts.sort(key=lambda c: c.act)
        half = len(learnts) // 2
        reason = self._reason
        val = self._val
        keep = []
        dead = {}
        for i, c in enumerate(learnts):
            first = c[0]
            locked = val[first] is True and reason[first >> 1] is c
            if i < half and len(c) > 2 and not locked:
                dead[id(c)] = c
            else:
                keep.append(c)
        if dead:
            watches = self._watches
            for l in range(2, 2 * self._nvars + 2):
                ws = watches[l]
                if ws:
                    watches[l] = [c for c in ws if id(c) not in dead]
        self._learnts = keep
        self._max_learnts *= self._learnt_size_inc

    def _search(self, nof_conflicts: int) -> bool | None:
        """Search until a result or ``nof_conflicts`` conflicts (then None)."""
        val = self._val
        trail = self._trail
        trail_lim = self._trail_lim
        level = self._level
        reason = self._reason
        assumptions = self._assumptions
        conflict_c = 0
        while True:
            confl = self._propagate()
            if confl is not None:
                self._n_conflicts += 1
                conflict_c += 1
                if not trail_lim:
                    self._ok = False
                    return False
                learnt, bt = self._analyze(confl)
                self._backtrack(bt)
                self._n_learned += 1
                l0 = learnt[0]
                v0 = l0 >> 1
                if len(learnt) == 1:
                    val[l0] = True
                    val[l0 ^ 1] = False
                    level[v0] = 0
                    reason[v0] = None
                    trail.append(l0)
                else:
                    c = Clause(learnt, True)
                    self._bump_clause(c)
                    self._learnts.append(c)
                    self._watches[learnt[0]].append(c)
                    self._watches[learnt[1]].append(c)
                    val[l0] = True
                    val[l0 ^ 1] = False
                    level[v0] = len(trail_lim)
                    reason[v0] = c
                    trail.append(l0)
                self._var_inc /= self._var_decay
                self._cla_inc /= self._cla_decay
            else:
                if conflict_c >= nof_conflicts:
                    self._backtrack(0)
                    return None
                if len(self._learnts) - len(trail) >= self._max_learnts:
                    self._reduce_db()
                dl = len(trail_lim)
                nxt = -1
                while dl < len(assumptions):
                    p = assumptions[dl]
                    vp = val[p]
                    if vp is True:
                        trail_lim.append(len(trail))     # dummy level
                        dl += 1
                    elif vp is False:
                        self._analyze_final(p)
                        return False
                    else:
                        nxt = p
                        break
                if nxt < 0:
                    self._n_decisions += 1
                    nxt = self._pick_branch()
                    if nxt < 0:
                        return True                      # all assigned: model
                trail_lim.append(len(trail))
                v = nxt >> 1
                val[nxt] = True
                val[nxt ^ 1] = False
                level[v] = len(trail_lim)
                reason[v] = None
                trail.append(nxt)

    def solve(self, assumptions: Iterable[int] = ()) -> bool:
        """CDCL search under ``assumptions``.  True iff satisfiable.

        Learned clauses are kept (they never depend on the assumptions).
        After an unsatisfiable call :meth:`conflict` gives the assumptions
        responsible; after a satisfiable one :meth:`model` gives a model.
        """
        self._model = None
        self._conflict = []
        if self._trail_lim:
            self._backtrack(0)
        if not self._ok:
            return False
        if self._propagate() is not None:
            self._ok = False
            return False
        self._assumptions = self._internal_lits(list(assumptions))
        self._max_learnts = max(self._max_learnts, len(self._clauses) / 3.0,
                                float(self._learnt_size_min))
        status = None
        restarts = 0
        while status is None:
            budget = int(_luby(self._restart_inc, restarts) * self._restart_first)
            status = self._search(budget)
            restarts += 1
        self._n_restarts += restarts - 1
        if status:
            val = self._val
            self._model = {v: val[2 * v] for v in range(1, self._nvars + 1)}
            self._witness = self._model
        self._backtrack(0)
        self._assumptions = []
        return status

    def model(self) -> dict[int, bool] | None:
        """Model of the last successful :meth:`solve`, else None."""
        return dict(self._model) if self._model is not None else None

    def conflict(self) -> list[int]:
        """After an UNSAT :meth:`solve`: assumptions responsible for it.

        The returned literals are a subset of the assumptions that is by
        itself inconsistent with the formula (empty if the formula alone is
        unsatisfiable).
        """
        ext = self._to_ext
        return [ext(l) for l in self._conflict]

    def _witness_satisfies(self, assumptions: list[int]) -> bool:
        """Does the cached model satisfy every assumption?"""
        w = self._witness
        if w is None:
            return False
        for a in assumptions:
            b = w.get(-a if a < 0 else a)
            if b is not None and b != (a > 0):
                return False
        return True

    def entails(self, lit: int, assumptions: Iterable[int] = ()) -> bool | None:
        """True if ``lit`` is forced under ``assumptions``, False if ``-lit``
        is, None if neither.  Raises ValueError if the assumptions are
        themselves inconsistent with the formula.

        Unit propagation is tried first.  If it settles ``lit``, the answer
        is returned after making sure the assumptions are consistent: the
        model of the last successful solve is checked against them (free),
        and only if that fails is a search under the assumptions run (its
        model is then cached for the next queries).
        """
        assumptions = list(assumptions)
        if lit == 0:
            raise ValueError("literal must be a nonzero integer")
        # Cheap path: unit propagation only.
        if not self._assume_propagate(assumptions):
            self._backtrack(0)
            raise ValueError("inconsistent assumptions")
        v = -lit if lit < 0 else lit
        if v > self._nvars:
            self._grow(v)
        l = 2 * v + 1 if lit < 0 else 2 * v
        vl = self._val[l]
        self._backtrack(0)
        if vl is not None:
            if self._witness_satisfies(assumptions) or self.solve(assumptions):
                return vl
            raise ValueError("inconsistent assumptions")
        # Full search.
        if not self.solve(assumptions + [-lit]):
            if not self.solve(assumptions + [lit]):
                raise ValueError("inconsistent assumptions")
            return True
        if not self.solve(assumptions + [lit]):
            return False
        return None

    def stats(self) -> dict[str, int]:
        return {
            "propagations": self._n_props,
            "conflicts": self._n_conflicts,
            "decisions": self._n_decisions,
            "learned": self._n_learned,
            "restarts": self._n_restarts,
            "vars": self._nvars,
            "clauses": len(self._clauses),
            "learnts": len(self._learnts),
        }
