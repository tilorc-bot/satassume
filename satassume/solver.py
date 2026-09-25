"""Incremental CDCL SAT solver in pure Python.

This is the propositional core of the assumptions engine.  It is a fairly
direct, MiniSat-flavoured CDCL solver:

* two watched literals per clause, iterative propagation;
* first-UIP conflict analysis with basic clause minimization and
  non-chronological backjumping;
* VSIDS variable activities kept in an indexed binary heap, phase saving;
* Luby restarts, simple activity-based deletion of learned clauses;
* MiniSat-style assumptions (the first decisions of a search) with a proper
  final-conflict analysis (:meth:`Solver.conflict`);
* optional theory solvers (DPLL(T), :meth:`Solver.attach_theory`, contract
  in :mod:`satassume.theory`); without one every hook is skipped after a
  single attribute test.

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

    ``learnt`` and ``act`` are class-level defaults so that constructing a
    clause is a plain (C-level) list construction; learnt clauses set both
    on the instance.
    """

    learnt = False
    act = 0.0


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
        # Version of the clause database (problem and learnt clauses and
        # theory atoms); bumped by every change that can alter what
        # propagation derives.  Together with the length of the root trail
        # it keys the cache of :meth:`_assume` below.
        self._stamp = 0
        # Last propagation under assumptions: ``(key, trail)`` with
        # ``key = (assumptions, stamp, root trail length)`` and ``trail``
        # the internal trail it reached (None on conflict).
        self._acache: tuple | None = None
        self._conflict: list[int] = []
        # Statistics.
        self._n_props = 0
        self._n_conflicts = 0
        self._n_decisions = 0
        self._n_learned = 0
        self._n_restarts = 0
        # Theories (see satassume/theory.py).  ``_theories`` is the guard of
        # every hook: the no-theory path pays one attribute test per call.
        self._theories: list = []
        self._tmap: dict[int, list] = {}     # variable -> theories that registered it
        self._thead = 0                      # trail entries before it were reported
        self._tprops: list = []              # bound ``propagate`` methods
        self._tmodels: list | None = None

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
        k = v - n
        self._val.extend([None] * (2 * k))
        self._watches.extend([] for _ in range(2 * k))
        self._level.extend([0] * k)
        self._reason.extend([None] * k)
        self._act.extend([0.0] * k)
        self._polarity.extend([1] * k)
        self._seen.extend([0] * k)
        # New variables have activity 0, the minimum: appending them keeps
        # the max-heap property.
        heap = self._heap
        start = len(heap)
        self._hpos.extend(range(start, start + k))
        heap.extend(range(n + 1, v + 1))
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
        self._stamp += 1
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

    def add_clauses(self, clauses) -> bool:
        """Bulk-add clauses of external literals.  Returns False iff the
        formula is now UNSAT at root.

        Clauses whose literals are all unassigned at root are inserted
        directly (they must be duplicate- and tautology-free, which is true
        for template patterns); any other clause goes through
        :meth:`add_clause`.  Unit clauses are assigned but not propagated:
        the caller propagates once at the end (:meth:`propagate`).
        """
        if not self._ok:
            return False
        if self._trail_lim:
            self._backtrack(0)
        val = self._val
        watches = self._watches
        cls = self._clauses
        level = self._level
        reason = self._reason
        trail = self._trail
        nv = self._nvars
        for lits in clauses:
            if len(lits) == 1:
                x = lits[0]
                v = x if x > 0 else -x
                if v > nv:
                    self._grow(v)
                    nv = self._nvars
                l = 2 * v + 1 if x < 0 else 2 * v
                vl = val[l]
                if vl is True:
                    continue
                if vl is False:
                    self._ok = False
                    return False
                val[l] = True
                val[l ^ 1] = False
                level[v] = 0
                reason[v] = None
                trail.append(l)
                continue
            out = []
            for x in lits:
                v = x if x > 0 else -x
                if v > nv:
                    self._grow(v)
                    nv = self._nvars
                l = 2 * v + 1 if x < 0 else 2 * v
                if val[l] is not None:
                    out = None
                    break
                out.append(l)
            if out is None:
                if not self.add_clause(lits):
                    return False
                nv = self._nvars
                continue
            c = Clause(out)
            cls.append(c)
            watches[out[0]].append(c)
            watches[out[1]].append(c)
        self._witness = None
        self._stamp += 1
        return True

    def ensure_vars(self, v: int) -> None:
        """Make sure variables ``1..v`` exist."""
        if v > self._nvars:
            self._grow(v)

    def add_internal(self, clauses) -> bool:
        """Like :meth:`add_clauses` for clauses already in the internal
        literal encoding (variables must exist, see :meth:`ensure_vars`)."""
        if not self._ok:
            return False
        if self._trail_lim:
            self._backtrack(0)
        val = self._val
        watches = self._watches
        cls = self._clauses
        for lits in clauses:
            for l in lits:
                if val[l] is not None:
                    if not self.add_clause([-(l >> 1) if l & 1 else l >> 1 for l in lits]):
                        return False
                    break
            else:
                if len(lits) == 1:
                    l = lits[0]
                    val[l] = True
                    val[l ^ 1] = False
                    self._level[l >> 1] = 0
                    self._reason[l >> 1] = None
                    self._trail.append(l)
                else:
                    c = Clause(lits)
                    cls.append(c)
                    watches[lits[0]].append(c)
                    watches[lits[1]].append(c)
        self._witness = None
        self._stamp += 1
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
        self._stamp += 1
        return True

    def propagate(self) -> bool:
        """Run unit propagation at root; False iff there is a root conflict."""
        if not self._ok:
            return False
        if self._trail_lim:
            self._backtrack(0)
        if (self._tpropagate() if self._theories else self._propagate()) is not None:
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
        return [-(l >> 1) if l & 1 else l >> 1 for l in trail]

    def implied(self, assumptions: Iterable[int] = ()) -> list[int] | None:
        """Literals forced by unit propagation under ``assumptions``.

        Returns the list of *all* assigned literals (root facts, the
        assumptions and their consequences) or None if propagation runs into
        a conflict.  No search and no learning; the solver is left at root.
        """
        trail = self._assume(assumptions)
        if trail is None:
            return None
        return [-(l >> 1) if l & 1 else l >> 1 for l in trail]

    def _assume(self, assumptions) -> list[int] | None:
        """Propagate at root, then under ``assumptions`` (each at its own
        level); return the internal trail reached, or None on conflict.
        The solver is left at root.  The returned list must not be mutated.

        The result is cached.  It is a function of the assumptions, the
        clause database and the root assignment only: propagation reaches
        the same fixpoint (or a conflict) whatever the order.  The cache key
        is therefore the assumption literals, ``_stamp`` (bumped by every
        clause or theory-atom addition, every learnt clause and every
        learnt-clause deletion) and the length of the root trail (root
        assignments only ever grow, so an unchanged length means an
        unchanged root assignment).  A result is only cached if nothing
        changed ``_stamp`` while it was computed, e.g. a theory conflict
        adding a learnt clause.  With theories the result also depends on
        theory propagation; registering an atom bumps ``_stamp``.  If a
        theory's propagation depends on its history (e.g. simplex state), a
        recomputation could derive a different set, but a cached result is
        still sound: it was derived from the same assumptions, clauses and
        atoms.
        """
        if self._trail_lim:
            self._backtrack(0)
        if not self._ok:
            return None
        theories = self._theories
        if (self._tpropagate() if theories else self._propagate()) is not None:
            self._ok = False
            return None
        lits = self._internal_lits(assumptions)
        stamp = self._stamp
        key = (lits, stamp, len(self._trail))
        cached = self._acache
        if cached is not None and cached[0] == key:
            return cached[1]
        trail = self._trail[:] if self._assume_propagate(lits) else None
        self._backtrack(0)
        if self._ok and self._stamp == stamp:
            self._acache = (key, trail)
        return trail

    def _assume_propagate(self, lits: list[int]) -> bool:
        """Assume each internal literal of ``lits`` at its own level and
        propagate; the solver must be at root with propagation done.

        On success the solver is left in the assumed state (caller must
        backtrack).  Returns False on conflict.
        """
        theories = self._theories
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
            if theories:
                for t in theories:
                    t.push_level()
                if self._tpropagate() is not None:
                    return False
            elif self._propagate() is not None:
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
        if self._theories:
            if self._thead > start:
                self._thead = start
            for _ in range(len(trail_lim) - lvl):
                for t in self._theories:
                    t.pop_level()
        del trail_lim[lvl:]

    # ------------------------------------------------------------------
    # Theories (DPLL(T)); see satassume/theory.py for the contract
    # ------------------------------------------------------------------

    def attach_theory(self, theory) -> None:
        """Attach a theory solver (see :class:`satassume.theory.TheorySolver`).

        Several theories may be attached; each sees only the variables
        registered for it with :meth:`register_atom`.  The theory must be
        fresh (level 0, nothing asserted).
        """
        if any(t is theory for t in self._theories):
            raise ValueError("theory already attached")
        if self._trail_lim:
            self._backtrack(0)
        self._theories.append(theory)
        prop = getattr(theory, "propagate", None)
        if prop is not None:
            self._tprops.append(prop)
        self._witness = None
        self._stamp += 1

    def theories(self) -> list:
        return list(self._theories)

    def register_atom(self, theory, var: int, payload) -> bool:
        """Declare that variable ``var`` is a theory atom of ``theory``
        (already attached) with the opaque ``payload``; calls
        ``theory.register_atom(var, payload)``.  If ``var`` is already fixed
        at root, the theory is told at once.  Returns False iff the problem
        is now unsatisfiable at root (like :meth:`add_clause`).
        """
        if not any(t is theory for t in self._theories):
            raise ValueError("theory not attached")
        var = int(var)
        if var <= 0:
            raise ValueError("register_atom takes a positive variable")
        if var > self._nvars:
            self._grow(var)
        if self._trail_lim:
            self._backtrack(0)
        ts = self._tmap.get(var)
        if ts is None:
            self._tmap[var] = [theory]
        elif any(t is theory for t in ts):
            raise ValueError(f"variable {var} already registered with this theory")
        else:
            ts.append(theory)
        self._witness = None
        self._stamp += 1
        theory.register_atom(var, payload)
        if not self._ok:
            return False
        l = 2 * var
        vl = self._val[l]
        if vl is not None and self._trail.index(l if vl else l ^ 1) < self._thead:
            # Fixed at root and already past the report cursor: report now.
            # (Anything after the cursor is reported by the next sync.)
            r = theory.assert_lit(var if vl else -var)
            if r is not None and r[0] is False:
                self._theory_conflict(r[1])
                return False
        return True

    def theory_models(self) -> list | None:
        """After a satisfiable :meth:`solve` with theories attached: the
        model part of each theory's ``check`` result (None where ``check``
        returned None), in attachment order; else None."""
        return list(self._tmodels) if self._tmodels is not None else None

    def _tpropagate(self) -> Clause | None:
        """Unit propagation interleaved with reporting to the theories until
        both are quiet.  Returns a conflicting clause or None; after a
        theory conflict the solver has backtracked to the highest level of
        the clause (see :meth:`_theory_conflict`)."""
        while True:
            confl = self._propagate()
            if confl is not None:
                return confl
            confl = self._theory_sync()
            if confl is not None:
                return confl
            if self._qhead == len(self._trail):
                return None

    def _theory_sync(self) -> Clause | None:
        """Report trail entries from the cursor on to the theories that
        registered them, then ask propagating theories for implications."""
        trail = self._trail
        i = self._thead
        if i == len(trail):
            return None
        tmap = self._tmap
        while i < len(trail):
            l = trail[i]
            i += 1
            ts = tmap.get(l >> 1)
            if ts is None:
                continue
            x = -(l >> 1) if l & 1 else l >> 1
            for t in ts:
                r = t.assert_lit(x)
                if r is not None and r[0] is False:
                    self._thead = i
                    return self._theory_conflict(r[1])
        self._thead = i
        for prop in self._tprops:
            for x, why in prop():
                confl = self._theory_imply(x, why)
                if confl is not None:
                    return confl
        return None

    def _theory_clause(self, lits, what: str) -> list[int]:
        out = []
        for x in lits:
            x = int(x)
            v = -x if x < 0 else x
            if v == 0 or v > self._nvars:
                raise RuntimeError(f"theory {what} has a bad literal {x}")
            l = 2 * v + 1 if x < 0 else 2 * v
            if l not in out:
                out.append(l)
        return out

    def _theory_conflict(self, lits) -> Clause:
        """Turn a theory conflict clause into a solver clause, backtrack to
        its highest level (so that analysis finds a literal of the current
        level) and store it as a learnt clause watched on its two highest
        literals.  A clause false at root makes the solver UNSAT."""
        raw = self._theory_clause(lits, "conflict clause")
        if not raw:
            raise RuntimeError("theory returned an empty conflict clause")
        val = self._val
        level = self._level
        for l in raw:
            if val[l] is not False:
                raise RuntimeError(
                    f"theory conflict clause literal {self._to_ext(l)} is not false")
        raw.sort(key=lambda l: level[l >> 1], reverse=True)
        c = Clause(raw)
        ml = level[raw[0] >> 1]
        if ml < len(self._trail_lim):
            self._backtrack(ml)
        if ml == 0:
            self._ok = False
            return c
        if len(raw) > 1:
            c.learnt = True
            c.act = 0.0
            self._stamp += 1
            self._learnts.append(c)
            self._watches[raw[0]].append(c)
            self._watches[raw[1]].append(c)
        return c

    def _theory_imply(self, x: int, lits) -> Clause | None:
        """A theory propagation: ``x`` is implied by clause ``lits``."""
        raw = self._theory_clause(lits, "reason")
        val = self._val
        l = 2 * x if x > 0 else -2 * x + 1
        if l not in raw:
            raise RuntimeError(f"theory reason for {x} does not contain it")
        vl = val[l]
        if vl is True:
            return None
        if vl is False:
            return self._theory_conflict(lits)
        raw.remove(l)
        for q in raw:
            if val[q] is not False:
                raise RuntimeError(
                    f"theory reason literal {self._to_ext(q)} for {x} is not false")
        level = self._level
        dl = len(self._trail_lim)
        v = l >> 1
        if dl == 0 or not raw:
            reason = None if dl == 0 else Clause([l])
        else:
            raw.sort(key=lambda q: level[q >> 1], reverse=True)
            reason = Clause([l] + raw)
            reason.learnt = True
            reason.act = 0.0
            self._stamp += 1
            self._learnts.append(reason)
            self._watches[l].append(reason)
            self._watches[raw[0]].append(reason)
        val[l] = True
        val[l ^ 1] = False
        level[v] = dl
        self._reason[v] = reason
        self._trail.append(l)
        return None

    def _theory_check(self) -> Clause | None:
        """Final check on a total assignment."""
        models = []
        for t in self._theories:
            r = t.check()
            if r is None:
                models.append(None)
            elif r[0] is False:
                return self._theory_conflict(r[1])
            else:
                models.append(r[1])
        self._tmodels = models
        return None

    def _learn(self, confl: Clause) -> bool:
        """Conflict analysis and learning for a conflict found outside the
        propagation loop of :meth:`_search`.  False iff UNSAT at root."""
        self._n_conflicts += 1
        if not self._trail_lim:
            self._ok = False
            return False
        learnt, bt = self._analyze(confl)
        self._backtrack(bt)
        self._n_learned += 1
        self._stamp += 1
        l0 = learnt[0]
        v0 = l0 >> 1
        if len(learnt) == 1:
            reason = None
        else:
            reason = Clause(learnt)
            reason.learnt = True
            reason.act = 0.0
            self._bump_clause(reason)
            self._learnts.append(reason)
            self._watches[learnt[0]].append(reason)
            self._watches[learnt[1]].append(reason)
        self._val[l0] = True
        self._val[l0 ^ 1] = False
        self._level[v0] = len(self._trail_lim)
        self._reason[v0] = reason
        self._trail.append(l0)
        self._var_inc /= self._var_decay
        self._cla_inc /= self._cla_decay
        return True

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
        self._stamp += 1
        self._max_learnts *= self._learnt_size_inc

    def _search(self, nof_conflicts: int) -> bool | None:
        """Search until a result or ``nof_conflicts`` conflicts (then None)."""
        val = self._val
        trail = self._trail
        trail_lim = self._trail_lim
        level = self._level
        reason = self._reason
        assumptions = self._assumptions
        theories = self._theories
        propagate = self._tpropagate if theories else self._propagate
        conflict_c = 0
        while True:
            confl = propagate()
            if confl is not None:
                self._n_conflicts += 1
                conflict_c += 1
                if not trail_lim:
                    self._ok = False
                    return False
                learnt, bt = self._analyze(confl)
                self._backtrack(bt)
                self._n_learned += 1
                self._stamp += 1
                l0 = learnt[0]
                v0 = l0 >> 1
                if len(learnt) == 1:
                    val[l0] = True
                    val[l0 ^ 1] = False
                    level[v0] = 0
                    reason[v0] = None
                    trail.append(l0)
                else:
                    c = Clause(learnt)
                    c.learnt = True
                    c.act = 0.0
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
                        if theories:
                            for t in theories:
                                t.push_level()
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
                        if theories:
                            confl = self._theory_check()
                            if confl is not None:
                                conflict_c += 1
                                if not self._learn(confl):
                                    return False
                                continue
                        return True                      # all assigned: model
                trail_lim.append(len(trail))
                if theories:
                    for t in theories:
                        t.push_level()
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
        self._tmodels = None
        self._conflict = []
        if self._trail_lim:
            self._backtrack(0)
        if not self._ok:
            return False
        if (self._tpropagate() if self._theories else self._propagate()) is not None:
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
        trail = self._assume(assumptions)
        if trail is None:
            raise ValueError("inconsistent assumptions")
        v = -lit if lit < 0 else lit
        if v > self._nvars:
            self._grow(v)
        l = 2 * v + 1 if lit < 0 else 2 * v
        vl = True if l in trail else False if l ^ 1 in trail else None
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
