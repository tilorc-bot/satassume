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
  single attribute test;
* an optional rule block (:meth:`Solver.set_rule_block`): one fixed clause
  pattern instantiated per base variable (:meth:`Solver.register_block`)
  and propagated by its exact closure (a shared table of the block's
  models) instead of watched clauses; its implications are written to the
  trail only for variables something else mentions (lazy writes).

Literals are plain signed integers externally (``v`` / ``-v``, ``v >= 1``).
Internally a literal is encoded as ``2*v + (1 if negative else 0)`` so that
all per-literal data lives in flat lists indexed by literal and negation is
``lit ^ 1``.  Variable ``v`` of a literal is ``lit >> 1``.

Assignments are stored per *literal*: ``_val[lit]`` is ``True``, ``False`` or
``None``, with ``_val[lit ^ 1]`` always the complement.

Between public calls the solver is at decision level 0, except that it may
*hold* the assumption levels of the last :meth:`Solver.implied` (see
:meth:`Solver._assume`); every root-level query ignores levels above 0.
Level-0 assignments are permanent facts entailed by the clause set (found
by unit propagation, by unit clauses, or as learned unit clauses).
"""
from __future__ import annotations

from collections.abc import Iterable


class Clause(list):
    """A clause created during search: a list of internal literals plus an
    activity score.

    Every clause is a list of internal literals.  Watched literals are
    always at positions 0 and 1.  For a clause that is the reason of an
    assignment, the implied literal is at position 0.

    Problem clauses (``add_*``) are plain lists, which are cheaper to
    build; learnt clauses and theory clauses are ``Clause`` instances.
    ``learnt`` and ``act`` are class-level defaults; learnt clauses set both
    on the instance.  Use :func:`_is_learnt` to test any clause.
    """

    learnt = False
    act = 0.0


def _is_learnt(c: list) -> bool:
    return c.__class__ is Clause and c.learnt


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


_RULE_TABLES: dict = {}
_EVEN = int("01" * 64, 2)          # bits 0, 2, 4, ... (positive relative literals)
_BIT = tuple(1 << i for i in range(128))       # relative literal -> its bit
_NBIT = tuple(~(1 << i) for i in range(128))   # ... and the complement


def _block_models(clauses, n: int) -> tuple[int, ...]:
    """All models of the block ``clauses`` (internal literals relative to
    variable 0) over ``n`` variables, each as a mask over the ``2*n``
    relative literals: bit ``2*i`` if variable ``i`` is true, bit
    ``2*i + 1`` if it is false.  DPLL with unit propagation; the engine's
    rule base has 48 models."""
    out: list[int] = []
    cls = [tuple(c) for c in clauses]

    def up(a: set) -> bool:
        changed = True
        while changed:
            changed = False
            for c in cls:
                free = -1
                for l in c:
                    if l in a:
                        break
                    if l ^ 1 not in a:
                        if free >= 0:
                            break
                        free = l
                else:
                    if free < 0:
                        return False
                    a.add(free)
                    changed = True
        return True

    def rec(a: set) -> None:
        if not up(a):
            return
        for i in range(n):
            if 2 * i not in a and 2 * i + 1 not in a:
                rec(a | {2 * i + 1})
                rec(a | {2 * i})
                return
        m = 0
        for l in a:
            m |= 1 << l
        out.append(m)
        if len(out) > 1 << 16:
            raise ValueError("rule block has too many models")

    rec(set())
    return tuple(sorted(set(out)))


class _BlockClosure:
    """The exact closure of a set of literals of one block under the block's
    clauses, from the table of its models (shared by every solver using the
    block).  A set is a mask over the relative literals (see
    :func:`_block_models`); its closure is the AND of the models that
    contain it (every literal true in all of them), or 0 if none does
    (the set is inconsistent with the block).  Explanations are subsets of
    a set that still entail a literal (or are still inconsistent): greedy
    over the models that must be excluded, then minimal by deletion."""

    __slots__ = ("models", "memo", "expl", "values", "vmemo", "bits", "fmemo", "n",
                 "msets", "all", "cls")

    def __init__(self, clauses, n: int):
        self.n = n
        self.fmemo: dict[int, tuple] = {}
        self.models = _block_models(clauses, n)
        # per relative literal, the set of models containing it (a bit per
        # model); closures are memoized per model set too
        self.msets = tuple(sum(1 << j for j, x in enumerate(self.models) if (x >> r) & 1)
                           for r in range(2 * n))
        self.all = (1 << len(self.models)) - 1
        self.cls: dict[int, int] = {}
        self.memo: dict[int, int] = {}
        self.expl: dict = {}
        # per model, the values of the n variables (for model completion)
        self.values = {x: [bool((x >> (2 * i)) & 1) for i in range(n)] for x in self.models}
        self.vmemo: dict[int, list] = {}
        # mask -> its relative literals, ascending
        self.bits: dict[int, tuple] = {}

    def flags(self, mm: int) -> tuple:
        """``(lazy, mentioned)`` byte strings of the block's variables
        for the mention mask ``mm``."""
        r = self.fmemo.get(mm)
        if r is None:
            n = self.n
            mt = bytes(1 if (mm >> (2 * i)) & 1 else 0 for i in range(n))
            r = (bytes(1 - x for x in mt), mt)
            if len(self.fmemo) >= 100_000:
                self.fmemo.clear()
            self.fmemo[mm] = r
        return r

    def lits_of(self, m: int) -> tuple:
        r = self.bits.get(m)
        if r is None:
            out = []
            b = m
            while b:
                low = b & -b
                out.append(low.bit_length() - 1)
                b ^= low
            r = tuple(out)
            if len(self.bits) >= 100_000:
                self.bits.clear()
            self.bits[m] = r
        return r

    def values_of(self, m: int) -> list:
        """The variable values of a model containing the consistent set
        ``m``."""
        r = self.vmemo.get(m)
        if r is None:
            r = self.values[self.model_of(m)]
            if len(self.vmemo) >= 100_000:
                self.vmemo.clear()
            self.vmemo[m] = r
        return r

    def closure(self, m: int) -> int:
        r = self.memo.get(m)
        if r is None:
            # the models containing m: AND of the model sets of its literals
            sets = self.msets
            S = self.all
            b = m
            while b and S:
                low = b & -b
                S &= sets[low.bit_length() - 1]
                b ^= low
            r = self.cls.get(S)
            if r is None:
                acc = -1
                x = S
                models = self.models
                while x:
                    low = x & -x
                    acc &= models[low.bit_length() - 1]
                    x ^= low
                r = acc if S else 0
                self.cls[S] = r
            memo = self.memo
            if len(memo) >= 400_000:
                memo.clear()
            memo[m] = r
        return r

    def model_of(self, m: int) -> int:
        """A model containing the consistent set ``m``."""
        for x in self.models:
            if x & m == m:
                return x
        raise RuntimeError("rule block: no model contains the set")

    def explain(self, m: int, t: int) -> tuple[int, ...]:
        """Relative literals of ``m`` (a consistent set whose closure has
        ``t``; or, with ``t < 0``, an inconsistent set) forming a subset
        that entails ``t`` (is inconsistent)."""
        key = (m, t)
        r = self.expl.get(key)
        if r is not None:
            return r
        if t < 0:
            bad = list(self.models)
        else:
            bad = [x for x in self.models if not (x >> t) & 1]
        lits = []
        b = m
        while b:
            low = b & -b
            lits.append(low.bit_length() - 1)
            b ^= low
        chosen: list[int] = []
        rest = bad
        while rest:
            best = -1
            bestk = -1
            for s in lits:
                k = 0
                for x in rest:
                    if not (x >> s) & 1:
                        k += 1
                if k > bestk:
                    best, bestk = s, k
            if bestk <= 0:
                raise RuntimeError("rule block explanation: set does not entail the literal")
            chosen.append(best)
            rest = [x for x in rest if (x >> best) & 1]
        # minimal by deletion
        i = 0
        while i < len(chosen) and len(chosen) > 1:
            sub = 0
            for j, s in enumerate(chosen):
                if j != i:
                    sub |= 1 << s
            if any(x & sub == sub for x in bad):
                i += 1
            else:
                del chosen[i]
        r = tuple(chosen)
        expl = self.expl
        if len(expl) >= 200_000:
            expl.clear()
        expl[key] = r
        return r


def _rule_tables(block, nvars: int | None) -> tuple[tuple, int]:
    """The shared data of a rule block, built once per block object and
    ``nvars``: ``((clauses, closure), nvars)`` with ``clauses`` the block
    (checked: clean clauses of two or more literals) and ``closure`` its
    :class:`_BlockClosure` (model table, closure and explanation memos)."""
    key = (id(block), nvars)
    hit = _RULE_TABLES.get(key)
    if hit is not None and hit[0] is block:
        return hit[1], hit[2]
    clauses = tuple(tuple(c) for c in block)
    top = max((l >> 1 for c in clauses for l in c), default=-1) + 1
    n = top if nvars is None else int(nvars)
    if n < top or n < 1:
        raise ValueError("rule block mentions a variable beyond nvars")
    if n > 64:
        raise ValueError("rule blocks have at most 64 variables")
    for c in clauses:
        if len(c) < 2 or len({l >> 1 for l in c}) != len(c) or min(c) < 0:
            raise ValueError(f"rule block clause {c} is not a clean clause of 2+ literals")
    tables = (clauses, _BlockClosure(clauses, n))
    # The entry keeps ``block`` alive, so its id is not reused.  Callers
    # pass one module-level block; the bound only matters for tests.
    if len(_RULE_TABLES) >= 64:
        _RULE_TABLES.clear()
    _RULE_TABLES[key] = (block, tables, n)
    return tables, n


class Solver:
    """Incremental CDCL SAT solver.  See the module docstring."""

    # Tunables (MiniSat defaults, mostly).
    _var_decay = 0.95
    _cla_decay = 0.999
    _restart_first = 100
    _restart_inc = 2.0
    _learnt_size_inc = 1.1
    _learnt_size_min = 1000
    _RING = 2                   # models kept for _ring_hit

    def __init__(self):
        # Per-literal data; indices 0 and 1 are unused (variable 0 is not a var).
        self._val: list[bool | None] = [None, None]
        self._watches: list[list[Clause]] = [[], []]
        # Per-variable data; index 0 unused.
        self._level: list[int] = [0]
        # reason: a clause, None (decision or root), or an int (a rule
        # block implication, see set_rule_block; read through _rb_reason)
        self._reason: list[Clause | int | None] = [None]
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
        # Model of the last successful solve: the values of variables 1..n
        # (``_mvals``) and the dict built from them on demand (``_model``).
        self._mvals: list | None = None
        self._mdict: dict[int, bool] | None = None
        # Last model found by any solve; a cheap witness that a set of
        # assumptions is consistent.  Invalidated when clauses are added.
        self._witness: list | None = None
        # Version of the clause database (problem and learnt clauses and
        # theory atoms); bumped by every change that can alter what
        # propagation derives.  Together with the length of the root trail
        # it keys the cache of :meth:`_assume` below.
        self._stamp = 0
        # Last propagation under assumptions: ``(key, trail)`` with
        # ``key = (assumptions, stamp, root trail length)`` and ``trail``
        # the internal trail it reached (None on conflict).
        self._acache: tuple | None = None
        # Held assumptions: the internal assumption literals whose levels
        # are kept on the trail between public calls, or None (see _assume).
        self._held: list[int] | None = None
        self._conflict: list[int] = []
        # Statistics.
        self._n_props = 0
        self._n_conflicts = 0
        self._n_decisions = 0
        self._n_learned = 0
        self._n_restarts = 0
        self._n_reductions = 0
        # Decision mode of the current solve: next variable index to scan,
        # or 0 for VSIDS (see _pick_branch).
        self._scan = 0
        # Theories (see satassume/theory.py).  ``_theories`` is the guard of
        # every hook: the no-theory path pays one attribute test per call.
        self._theories: list = []
        self._tmap: dict[int, list] = {}     # variable -> theories that registered it
        self._thead = 0                      # trail entries before it were reported
        self._tprops: list = []              # bound ``propagate`` methods
        self._tmodels: list | None = None
        self._tpending = False               # propagate() owed after register_atom
        # Rule block (see set_rule_block): per-variable base of the block
        # the variable belongs to, 0 if none; the shared tables
        # (see _rule_tables).
        self._rb_base: list[int] = [0]
        self._rbc: _BlockClosure | None = None   # the block's closure table
        # Lazy rule-block writes: per base, the mask of the block's literals
        # processed by _propagate and still on the trail (``_rb_mask``), and
        # of the literals of its mentioned variables (``_rb_ment``); per
        # variable, whether anything outside the block mentions it.
        self._rb_mask: list[int] = [0]
        self._rb_ment: list[int] = [0]
        # Undo of the masks: (base, mask) pairs, flat, each saved at the
        # first change of the block's mask at a level (``_rb_saved[base]``
        # is the id of that level, ``_uid`` the id of the newest level),
        # and per level the length of ``_rb_undo`` when it began
        # (``_rb_ulim``, parallel to ``_trail_lim``).
        self._rb_saved: list[int] = [0]
        self._rb_cl: list[int] = [0]
        self._rb_undo: list[int] = []
        self._rb_ulim: list[int] = []
        self._uid = 1
        self._ment = bytearray(1)
        # 1 for a block variable nothing else mentions: not decided by the
        # search (its block's exact closure keeps it consistent; models are
        # completed from the block's models, see _complete_model)
        self._lazy = bytearray(1)
        self._n_late = 0                     # late mentions that dropped held levels
        self._n_late_written = 0             # late mentions written at held levels
        self._rb_clauses: tuple | None = None
        self._rb_n = 0                       # variables per block
        self._rb_blocks = 0                  # registered blocks
        self._rb_nclauses = 0                # clauses they stand for
        self._rb_bases: list[int] = []       # bases, in registration order
        # The last models found by search (see _ring_hit): tuples
        # (values of variables 1..n, len(_clauses), root trail length,
        # registered blocks, theories, theory atoms, theory models).
        self._ring: list[tuple] = []
        self._n_ring_hits = 0
        # register_atom calls so far (a variable registered with a second
        # theory changes the problem without changing len(_tmap))
        self._n_registered = 0

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
        self._watches.extend([[] for _ in range(2 * k)])
        self._level.extend([0] * k)
        self._reason.extend([None] * k)
        self._act.extend([0.0] * k)
        self._polarity.extend([1] * k)
        self._seen.extend([0] * k)
        self._rb_base.extend([0] * k)
        self._ment.extend(bytes(k))
        self._lazy.extend(bytes(k))
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
        out = self._internal_lits(list(lits))
        if len(out) > 1:
            self._mention(out)          # (a unit is fixed at root: no need)
        return self._add_lits(out, True)

    def _add_lits(self, raw: list[int], clean: bool) -> bool:
        """:meth:`add_clause` for internal literals (variables must exist).
        ``clean``: merge duplicates and drop tautologies first; otherwise
        ``raw`` must be free of both (template patterns are)."""
        if not self._ok:
            return False
        if self._trail_lim and self._held is None:
            self._backtrack(0)
        if clean and len(raw) > 1:
            seen = set(raw)
            if len(seen) < len(raw):
                raw = list(dict.fromkeys(raw))  # merge duplicates, keep order
            for l in raw:
                if l ^ 1 in seen:
                    return True                 # tautology
        val = self._val
        level = self._level
        out: list[int] = []
        for l in raw:
            vl = val[l]
            if vl is not None and not level[l >> 1]:
                if vl:
                    return True                 # satisfied at root
                continue                        # false at root: drop literal
            out.append(l)
        self._witness = None
        self._stamp += 1
        if len(out) < 2 and self._trail_lim:
            self._backtrack(0)                  # root change: drop held levels
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
        self._clauses.append(out)
        if self._trail_lim:
            self._attach_held(out)
            return True
        watches = self._watches
        watches[out[0]].append(out)
        watches[out[1]].append(out)
        return True

    def _attach_held(self, c: list[int]) -> None:
        """Watch the new clause ``c`` (no literal fixed at root) while the
        assumption levels are held, and propagate it if it is unit there.

        Watching two non-false literals, or a true one and the false one of
        highest level where the true one's level is not higher, is the
        usual two-watched-literal invariant (a false watch implies a true
        other watch of no higher level), which survives backtracking to any
        level.  If ``c`` is unit, its literal is implied at
        the current (highest) level and propagated, which keeps the held
        trail the propagation fixpoint of the clause set under the held
        assumptions.  A unit at a lower held level (possible with several
        assumptions), a falsified clause or a conflict drops the held
        levels (backtrack to root, where any two literals may be watched).
        """
        val = self._val
        watches = self._watches
        n = len(c)
        k = 0                                   # c[:k] are non-false
        for i in range(n):
            l = c[i]
            if val[l] is not False:
                c[i] = c[k]
                c[k] = l
                k += 1
                if k == 2:
                    break
        if k == 1:
            # c[0] is the only non-false literal: watch the false literal
            # of highest level next to it.
            level = self._level
            best = 1
            for i in range(2, n):
                if level[c[i] >> 1] > level[c[best] >> 1]:
                    best = i
            c[1], c[best] = c[best], c[1]
            l = c[0]
            vl = val[l]
            if vl is True and level[l >> 1] > level[c[1] >> 1]:
                # Satisfied only by a literal of a higher level than all the
                # false ones: backtracking between the two levels (search
                # continuing from the held levels) would miss the unit.
                k = 0
            elif vl is None:
                dl = len(self._trail_lim)
                if level[c[1] >> 1] == dl:
                    v = l >> 1
                    val[l] = True
                    val[l ^ 1] = False
                    level[v] = dl
                    self._reason[v] = c
                    self._trail.append(l)
                    watches[l].append(c)
                    watches[c[1]].append(c)
                    # the theories hear of the unit (and may propagate) at
                    # this level, so the held trail stays their fixpoint too
                    if (self._tpropagate() if self._theories else self._propagate()) is not None:
                        self._backtrack(0)
                    return
                k = 0                           # unit below the top level
        if k == 0:
            self._backtrack(0)                  # no literal of c is assigned now
        watches[c[0]].append(c)
        watches[c[1]].append(c)

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
        if self._trail_lim and self._held is None:
            self._backtrack(0)
        nv = self._nvars
        ment = self._ment
        new = None
        for lits in clauses:
            if len(lits) == 1:
                continue                        # fixed at root: no mention needed
            for x in lits:
                v = x if x > 0 else -x
                if v > nv or not ment[v]:
                    if v > nv:
                        self._grow(v)
                        nv = self._nvars
                        ment = self._ment
                    if new is None:
                        new = []
                    new.append(2 * v)
        if new is not None:
            self._mention(new)
        val = self._val
        watches = self._watches
        cls = self._clauses
        level = self._level
        reason = self._reason
        trail = self._trail
        for lits in clauses:
            if len(lits) == 1:
                x = lits[0]
                v = x if x > 0 else -x
                if v > nv:
                    self._grow(v)
                    nv = self._nvars
                l = 2 * v + 1 if x < 0 else 2 * v
                if self._trail_lim:
                    self._backtrack(0)          # root change: drop held levels
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
            cls.append(out)
            watches[out[0]].append(out)
            watches[out[1]].append(out)
        self._witness = None
        self._stamp += 1
        return True

    def ensure_vars(self, v: int) -> None:
        """Make sure variables ``1..v`` exist."""
        if v > self._nvars:
            self._grow(v)

    def add_internal(self, clauses, mentions=None) -> bool:
        """Like :meth:`add_clauses` for clauses already in the internal
        literal encoding (variables must exist, see :meth:`ensure_vars`).
        ``mentions``: the variables the clauses mention, as
        :meth:`mention_blocks` pairs covering at least every literal (a
        caller that knows them saves the scan)."""
        if not self._ok:
            return False
        if self._trail_lim and self._held is None:
            self._backtrack(0)
        if mentions is not None:
            self.mention_blocks(mentions)
        else:
            ment = self._ment
            new = None
            for lits in clauses:
                for l in lits:
                    if not ment[l >> 1]:
                        if new is None:
                            new = []
                        new.append(l)
            if new is not None:
                self._mention(new)
        val = self._val
        watches = self._watches
        cls = self._clauses
        for lits in clauses:
            if len(lits) == 1 and self._trail_lim:
                self._backtrack(0)              # root change: drop held levels
            for l in lits:
                if val[l] is not None:
                    if not self._add_lits(list(lits), True):
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
                    c = list(lits)
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
        if self._trail_lim and self._held is None:
            self._backtrack(0)
        top = base + nvars - 1
        if top > self._nvars:
            self._grow(top)
        lo = 2 * base
        n2 = 2 * nvars
        self._mention([l + lo for c in pattern for l in c])
        val = self._val
        clauses = self._clauses
        watches = self._watches
        append = clauses.append
        if val[lo:lo + n2].count(None) != n2:
            # Some target variable is assigned (at root, or at a held
            # level): clauses with an assigned literal take the slow path.
            for c in pattern:
                out = [l + lo for l in c]
                for l in out:
                    if val[l] is not None:
                        if not self._add_lits(out, False):
                            return False
                        break
                else:
                    append(out)
                    watches[out[0]].append(out)
                    watches[out[1]].append(out)
        else:
            for c in pattern:
                out = [l + lo for l in c]
                append(out)
                watches[out[0]].append(out)
                watches[out[1]].append(out)
        self._witness = None
        self._stamp += 1
        return True

    # ------------------------------------------------------------------
    # Rule block: a fixed clause pattern propagated without clauses
    # ------------------------------------------------------------------

    def set_rule_block(self, block, nvars: int | None = None) -> None:
        """Install ``block`` as the rule block of this solver: clauses in
        internal encoding relative to variable 0 (like :meth:`add_pattern`;
        tautology- and duplicate-free, at least two literals each) over
        ``nvars`` variables (default: the highest variable mentioned, plus
        one).  Blocks are then instantiated per base variable with
        :meth:`register_block`.  At most one block per solver; calling this
        again with the same block is a no-op.  The tables are built once per
        block object and shared by every solver (:func:`_rule_tables`), so
        this is cheap enough to call per solver.

        A registered block is propagated by :meth:`_propagate` without
        clauses, by its **exact closure** (:class:`_BlockClosure`): per
        block the solver keeps the *asserted* literals (block literals on
        the trail that the block did not imply itself) and their closure,
        every literal true in all models of the block that contain them.
        That is at least what unit propagation over the clauses
        ``add_pattern(block, base, nvars)`` would insert derives (it can be
        more: the case splits of non-Horn clauses), and a set with no model
        is a conflict at once.  A literal the block implies has an int as
        its reason (the asserted set and the base), turned into a clause (a
        subset of the asserted set that entails it, negated) by
        :meth:`_rb_reason` where a reason is read (conflict analysis only).

        **Lazy writes.**  Above root, an implied literal is written to the
        trail only if its variable is *mentioned*: by a clause added with
        any ``add_*`` method (units excepted: they are root facts), an
        assumption, a theory atom, or :meth:`mention` (the engine's query
        literal); the rest live in the closure.  At root every implied
        literal is written (the root trail is the fact cache's source).  A
        variable mentioned while levels are held gets its implied value
        written then (:meth:`_rb_late`).  A block variable never mentioned
        is *lazy*: the search does not decide it (the closure keeps the
        block consistent, so a model of the rest extends), and a stored
        model gets its value on demand (:meth:`_fill`).  So
        :meth:`implied` may leave out literals of unmentioned variables
        that clause propagation would list; every other answer is as with
        clauses (or more definite).
        """
        tables, n = _rule_tables(block, nvars)
        if self._rb_clauses is not None:
            if tables[0] == self._rb_clauses and n == self._rb_n:
                return
            raise ValueError("the rule block is already set")
        self._rb_clauses = tables[0]
        self._rb_n = n
        self._rbc = tables[1]

    def register_block(self, base: int, mentions: int = 0) -> bool:
        """Instantiate the rule block (:meth:`set_rule_block`) on variables
        ``base .. base + nvars - 1`` (grown if needed): from now on the
        solver behaves as if ``add_pattern(block, base, nvars)`` had been
        called.  Returns False iff the problem is now UNSAT at root.

        Contract: callable at any time between public calls, like the
        ``add_*`` methods, including while assumption levels are held and
        whatever the block's variables already carry (clauses, root
        values, values at held levels).  Each variable belongs to at most
        one block (ValueError otherwise).

        * No variable of the block assigned (the common case): only the
          base is recorded; held levels stay the propagation fixpoint.
        * Some assigned, all at root: the closure of the assigned literals
          is written as root facts and propagated at once, or, if they
          have no model of the block, the problem is UNSAT (returns
          False).  A new root fact drops held levels (as a unit clause
          does); otherwise they stay.
        * Some assigned at a held level: held levels are dropped first
          (back to root), then as above.  Enqueuing the implications at a
          held level instead would have to follow ``_attach_held`` (a unit
          below the top level, or a clause satisfied only above its false
          literals, cannot be kept without losing it on a later backjump);
          this happens for 3 of 8,260 blocks on the replay.

        ``mentions``: literals of the block already known to be mentioned
        (a mask as in :meth:`mention_blocks`), e.g. by the clauses the
        caller is about to add.
        """
        if self._rb_clauses is None:
            raise ValueError("register_block before set_rule_block")
        base = int(base)
        if base < 1:
            raise ValueError("register_block takes a positive base variable")
        if not self._ok:
            return False
        if self._trail_lim and self._held is None:
            self._backtrack(0)
        n = self._rb_n
        top = base + n - 1
        if top > self._nvars:
            self._grow(top)
        rb_base = self._rb_base
        if rb_base[base:top + 1].count(0) != n:
            raise ValueError(f"variables {base}..{top} overlap a registered block")
        lo = 2 * base
        val = self._val
        assigned = val[lo:lo + 2 * n].count(None) != 2 * n
        if assigned and self._trail_lim:
            level = self._level
            if any(level[v] for v in range(base, top + 1) if val[2 * v] is not None):
                self._backtrack(0)
        rb_base[base:top + 1] = [base] * n
        if top + n > len(self._rb_ment):
            self._rb_room(top + n)
        ment = self._ment
        mm = (mentions | (mentions >> 1)) & _EVEN
        if mm >> (2 * n):
            raise ValueError("register_block: mentions beyond the block size")
        mm |= mm << 1
        # masks kept by mention_blocks at bases whose range overlaps this
        # block (normally just this base), shifted onto it
        rb_ment = self._rb_ment
        lo_b = max(1, base - n + 1)
        window = rb_ment[lo_b:top + 1]
        if window.count(0) != len(window):
            full = (1 << (2 * n)) - 1
            for k, x in enumerate(window):
                if x:
                    d = lo_b + k - base             # -n < d < n
                    mm |= (x << (2 * d) if d >= 0 else x >> (-2 * d)) & full
        if ment[base:top + 1].count(0) != n:
            for i in range(n):
                if ment[base + i]:
                    mm |= 3 << (2 * i)
        self._rb_ment[base] = mm
        lz, mt = self._rbc.flags(mm)
        self._lazy[base:top + 1] = lz
        ment[base:top + 1] = mt
        self._rb_mask[base] = 0
        self._rb_cl[base] = 0
        self._rb_blocks += 1
        self._rb_bases.append(base)
        self._rb_nclauses += len(self._rb_clauses)
        self._witness = None
        self._stamp += 1
        if not self._rbc.models:
            if self._trail_lim:
                self._backtrack(0)
            self._ok = False
            return False
        if not assigned:
            return True
        return self._rb_settle(base)

    def _rb_settle(self, base: int) -> bool:
        """Propagate a block just registered over variables some of which
        are assigned, all at root (their literals may already be past the
        queue head, so :meth:`_propagate` would never see them): the
        block's closure of its assigned literals is written at root (all of
        it: at root every block implication is written), or the problem is
        UNSAT at root if they are inconsistent with the block."""
        val = self._val
        lo = 2 * base
        n2 = 2 * self._rb_n
        m = 0
        for rel in range(n2):
            if val[lo + rel]:
                m |= 1 << rel
        self._rb_mask[base] = m
        if not m:
            return True                         # (held levels were dropped)
        c = self._rbc.closure(m)
        self._rb_cl[base] = c
        new = c & ~m
        if c and not new:
            return True                         # nothing to propagate
        if self._trail_lim:
            self._backtrack(0)                  # root change: drop held levels
        if not c:
            self._ok = False
            return False
        level = self._level
        reason = self._reason
        trail = self._trail
        while new:
            low = new & -new
            new ^= low
            l = lo + low.bit_length() - 1
            if val[l] is None:
                val[l] = True
                val[l ^ 1] = False
                level[l >> 1] = 0
                reason[l >> 1] = None
                trail.append(l)
        if self._propagate() is not None:
            self._ok = False
            return False
        return True

    def _rb_reason(self, v: int, r: int) -> list[int]:
        """The clause behind the int reason ``r`` of variable ``v`` (a rule
        block implication: ``r = mask << 32 | base``, ``mask`` the block's
        literals processed when ``v`` was implied, all on the trail before
        it), with the literal of ``v`` first: a subset of ``mask`` that
        entails it (:meth:`_BlockClosure.explain`), negated."""
        base = r & 0xFFFFFFFF
        lo = base << 1
        l = 2 * v if self._val[2 * v] else 2 * v + 1
        out = [l]
        for q in self._rbc.explain(r >> 32, l - lo):
            out.append((q + lo) ^ 1)
        return out

    # ------------------------------------------------------------------
    # Mentioned variables (lazy rule-block writes)
    # ------------------------------------------------------------------

    def _mention(self, lits) -> None:
        """Mark the variables of the internal literals ``lits`` as mentioned
        outside the rule block.  A block implication is written to the trail
        above root only for a mentioned variable; the rest stay in the
        block's closure.  A variable of a block that becomes mentioned while
        assumption levels are held and is implied there by its block (but
        not written) drops the held levels, so the next propagation writes
        it with its reason (at root every implication is written)."""
        ment = self._ment
        rb_base = self._rb_base
        pend = None
        for l in lits:
            v = l >> 1
            if not ment[v]:
                ment[v] = 1
                b = rb_base[v]
                if b:
                    if pend is None:
                        pend = {}
                    pend[b] = pend.get(b, 0) | (3 << (2 * (v - b)))
        if pend is not None:
            rb_ment = self._rb_ment
            for b, new in pend.items():
                mm = rb_ment[b] | new
                rb_ment[b] = mm
                self._rb_mentioned(b, new, mm)

    def _rb_room(self, base: int) -> None:
        """Make ``_rb_mask`` and ``_rb_ment`` (indexed by block base, grown
        on demand rather than per variable) cover ``base``."""
        k = max(base, self._nvars) + 1 - len(self._rb_ment)
        if k > 0:
            self._rb_mask.extend([0] * k)
            self._rb_ment.extend([0] * k)
            self._rb_saved.extend([0] * k)
            self._rb_cl.extend([0] * k)

    def mention_blocks(self, pairs) -> None:
        """Mention variables by ``(base, mask)`` pairs: bit ``2*i`` or
        ``2*i + 1`` of ``mask`` (either or both) mentions variable
        ``base + i``, for ``i`` below the block size; variables must exist.
        Same effect as :meth:`_mention` on those variables, per block
        instead of per variable when ``base`` is the base of a registered
        block, or when none of the variables is in a registered block yet
        (the mask is then kept at ``base`` for :meth:`register_block`,
        which collects every kept mask overlapping the new block).  Any
        other pair (a ``base`` inside a registered block, a range touching
        one) is mentioned variable by variable."""
        rb_ment = self._rb_ment
        rb_base = self._rb_base
        n = self._rb_n
        for base, mask in pairs:
            mask = (mask | (mask >> 1)) & _EVEN
            if not mask:
                continue
            if mask >> (2 * n):
                raise ValueError("mention_blocks: mask beyond the block size")
            mask |= mask << 1
            if base + n > len(rb_ment):
                self._rb_room(base + n)
            b0 = rb_base[base]
            if b0 != base and (b0 or rb_base[base:base + n].count(0) != n):
                lits = []
                while mask:
                    low = mask & -mask
                    mask ^= low
                    lits.append(2 * base + low.bit_length() - 1)
                self._mention(lits)
                continue
            old = rb_ment[base]
            new = mask & ~old
            if not new:
                continue
            mm = old | new
            rb_ment[base] = mm
            if b0 == base:
                self._rb_mentioned(base, new, mm)

    def _rb_mentioned(self, base: int, new: int, mm: int) -> None:
        """The registered block at ``base`` has the mention mask ``mm``, of
        which ``new`` (both literals of each variable) is new: update the
        per-variable flags, put variables that are no longer lazy back
        into the activity heap, and drop held levels if the block implies
        a newly mentioned variable there without having written it."""
        n = self._rb_n
        lz, mt = self._rbc.flags(mm)
        self._lazy[base:base + n] = lz
        self._ment[base:base + n] = mt
        hpos = self._hpos
        if -1 in hpos[base:base + n]:
            for i in range(n):
                v = base + i
                if hpos[v] < 0 and not lz[i]:
                    self._heap_insert(v)
        self._stamp += 1
        if self._trail_lim:
            imp = self._rb_cl[base] & new
            if imp:
                val = self._val
                lo = base << 1
                unw = 0
                for q in self._rbc.lits_of(imp):
                    if val[q + lo] is None:
                        unw |= 1 << q
                if unw:
                    self._rb_late(base, self._rb_mask[base], unw)

    def _rb_late(self, base: int, m: int, imp: int) -> None:
        """Held levels, and the block at ``base`` implies the literals
        ``imp`` of newly mentioned variables without having written them.
        If the literals of the block below the top level do not imply any
        of them, they are implied at the top level: write them there with
        their reason and propagate, which keeps the held trail the
        propagation fixpoint (as :meth:`_attach_held` does for a unit
        clause).  Otherwise, or on a conflict, drop the held levels (back
        to root, where every block implication is written)."""
        dl = len(self._trail_lim)
        lo = base << 1
        level = self._level
        rbc = self._rbc
        low = 0
        for q in rbc.lits_of(m):
            if level[(q + lo) >> 1] < dl:
                low |= 1 << q
        if rbc.closure(low) & imp if low else rbc.closure(0) & imp:
            self._n_late += 1
            self._backtrack(0)
            return
        val = self._val
        reason = self._reason
        trail = self._trail
        why = (m << 32) | base
        for q in rbc.lits_of(imp):
            l = q + lo
            if val[l] is None:
                val[l] = True
                val[l ^ 1] = False
                level[l >> 1] = dl
                reason[l >> 1] = why
                trail.append(l)
        self._n_late_written += 1
        if (self._tpropagate() if self._theories else self._propagate()) is not None:
            self._n_late += 1
            self._backtrack(0)

    def mention(self, lits: Iterable[int]) -> None:
        """Declare that the (external) literals' variables are read by the
        caller (e.g. a query literal nothing else mentions), so that their
        rule-block implications are written to the trail and seen by
        :meth:`implied`."""
        self._mention(self._internal_lits(lits))

    def propagate(self) -> bool:
        """Run unit propagation at root; False iff there is a root conflict."""
        if not self._ok:
            return False
        if self._held is not None:
            return True             # held levels are a propagation fixpoint
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
        a conflict.  No search and no learning.  Root-level state is not
        changed beyond root propagation (the solver may keep the assumption
        levels, see :meth:`_assume`).
        """
        trail = self._assume(assumptions)
        if trail is None:
            return None
        return [-(l >> 1) if l & 1 else l >> 1 for l in trail]

    def _assume(self, assumptions) -> list[int] | None:
        """Propagate at root, then under ``assumptions`` (each at its own
        level); return the internal trail reached, or None on conflict.
        The returned list must not be mutated and is only valid until the
        next solver call.

        Held levels.  A successful propagation keeps its assumption levels
        on the trail (``_held``) instead of backtracking; attached theories
        keep the same levels (they are not popped), and a unit that
        :meth:`_attach_held` propagates at the top held level is reported
        to them and may make them propagate, so the held trail is the
        fixpoint of unit and theory propagation together.
        The clause-adding methods then keep the held trail equal to the
        propagation fixpoint of the grown clause set (see
        :meth:`_attach_held`); anything that changes the root assignment
        (a unit clause), a falsified clause, or any other method that needs
        root (a search from other assumptions, attaching a theory or
        registering a theory atom) backtracks to root, which drops the held
        levels (:meth:`_backtrack`).  So while ``_held`` is set, the trail is
        exactly what propagating ``_held`` from root would give, and the
        same assumptions are answered from it directly.

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
        lits = self._internal_lits(assumptions)
        self._mention(lits)
        if self._held is not None:
            if self._held == lits:
                return self._trail
            self._backtrack(0)
        elif self._trail_lim:
            self._backtrack(0)
        if not self._ok:
            return None
        theories = self._theories
        if (self._tpropagate() if theories else self._propagate()) is not None:
            self._ok = False
            return None
        stamp = self._stamp
        key = (lits, stamp, len(self._trail))
        cached = self._acache
        if cached is not None and cached[0] == key:
            return cached[1]
        if self._assume_propagate(lits):
            trail = self._trail[:]
            if self._trail_lim:
                self._held = lits
        else:
            trail = None
        if self._held is None:
            self._backtrack(0)
        if self._ok and self._stamp == stamp:
            self._acache = (key, trail)
        return trail

    def _assume_propagate(self, lits: list[int]) -> bool:
        """Assume each internal literal of ``lits`` at its own level and
        propagate; the solver must be at root with propagation done.

        Like :meth:`_search`, an assumption that is already true gets an
        empty level, so level ``i + 1`` always belongs to ``lits[i]`` and a
        search can continue from these levels.  On success the solver is
        left in the assumed state (caller must backtrack).  Returns False
        on conflict.
        """
        theories = self._theories
        val = self._val
        trail = self._trail
        trail_lim = self._trail_lim
        rb_ulim = self._rb_ulim
        rb_undo = self._rb_undo
        level = self._level
        reason = self._reason
        for l in lits:
            vl = val[l]
            if vl is True:
                trail_lim.append(len(trail))    # empty level
                rb_ulim.append(len(rb_undo))
                self._uid += 1
                if theories:
                    for t in theories:
                        t.push_level()
                continue
            if vl is False:
                return False
            trail_lim.append(len(trail))
            rb_ulim.append(len(rb_undo))
            self._uid += 1
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
        conflicting clause or None.

        Each literal taken off the trail first goes through the rule block
        of its variable, if registered (see :meth:`set_rule_block`), then
        through the watch list of its negation.  Without a rule block the
        loop is :meth:`_propagate_clauses`."""
        if not self._rb_n:
            return self._propagate_clauses()
        val = self._val
        watches = self._watches
        trail = self._trail
        level = self._level
        reason = self._reason
        rb_base = self._rb_base
        rb_mask = self._rb_mask
        rb_ment = self._rb_ment
        rbc = self._rbc
        memo = rbc.memo
        BIT = _BIT
        rb_saved = self._rb_saved
        rb_undo = self._rb_undo
        rb_cl = self._rb_cl
        uid = self._uid
        bits = rbc.bits
        qhead = self._qhead
        dl = len(self._trail_lim)
        confl = None
        nprops = 0
        while qhead < len(trail):
            p = trail[qhead]
            qhead += 1
            nprops += 1
            pv = p >> 1
            base = rb_base[pv]
            if base and reason[pv].__class__ is not int:
                # A block literal the block did not imply itself (an int
                # reason): unless the block's closure has it already, it is
                # a new asserted literal of the block.
                bit = BIT[p - (base << 1)]
                cl = rb_cl[base]
                if not cl & bit:
                    m = rb_mask[base]
                    if dl and rb_saved[base] != uid:
                        # first change of this block at this level: save
                        # its state for _backtrack
                        rb_saved[base] = uid
                        rb_undo.append(base)
                        rb_undo.append(m)
                        rb_undo.append(cl)
                    m |= bit
                    c = memo.get(m)
                    if c is None:
                        c = rbc.closure(m)
                    if not c:
                        lo = base << 1
                        confl = [(q + lo) ^ 1 for q in rbc.explain(m, -1)]
                        qhead = len(trail)
                        break
                    rb_mask[base] = m
                    rb_cl[base] = c
                    new = c & ~cl & ~bit
                    if dl:
                        new &= rb_ment[base]
                    if new:
                        lo = base << 1
                        why = (m << 32) | base
                        rels = bits.get(new)
                        if rels is None:
                            rels = rbc.lits_of(new)
                        for l in rels:
                            l += lo
                            if val[l] is None:
                                v = l >> 1
                                val[l] = True
                                val[l ^ 1] = False
                                level[v] = dl
                                reason[v] = why
                                trail.append(l)
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

    def _propagate_clauses(self) -> Clause | None:
        """:meth:`_propagate` for a solver without a rule block: the watch
        lists only.  (The same watch loop as in :meth:`_propagate`; a
        solver without :meth:`set_rule_block` pays nothing for the hook.)"""
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
        self._held = None
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
        # the rule-block masks as they were when level lvl + 1 began
        undo = self._rb_undo
        k = self._rb_ulim[lvl]
        if len(undo) > k:
            rb_mask = self._rb_mask
            rb_cl = self._rb_cl
            for i in range(len(undo) - 1, k, -3):
                b = undo[i - 2]
                rb_mask[b] = undo[i - 1]
                rb_cl[b] = undo[i]
            del undo[k:]
        del self._rb_ulim[lvl:]
        self._uid += 1          # the top level is an older one: save anew
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
        self._mention((2 * var,))
        if self._trail_lim:
            self._backtrack(0)
        self._n_registered += 1
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
        # The theory may imply something about the new atom at once (an
        # LRA atom that is ground, an EUF equality whose sides are already
        # equal): the next sync, at root, asks it even if no trail entry is
        # new.  Otherwise the implication would first be delivered under
        # some assumption level and dropped when that level is popped.
        self._tpending = True
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
        if i == len(trail) and not self._tpending:
            return None
        self._tpending = False
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
        self._scan = 0
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
            if _is_learnt(confl):
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
            seen[pv] = 0
            path -= 1
            if path == 0:
                break
            confl = reason[pv]
            if confl.__class__ is int:
                confl = self._rb_reason(pv, confl)
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
                if r.__class__ is int:
                    r = self._rb_reason(q >> 1, r)
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
                    if r.__class__ is int:
                        r = self._rb_reason(v, r)
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
        """Next decision literal, or -1 if every variable is assigned.

        Until the first conflict of a :meth:`solve` call (``_scan > 0``),
        variables are decided in index order: nothing is popped from the
        activity heap, so backtracking has nothing to re-insert either.
        Most searches here are conflict-free (a model is found by the
        first descent), and without conflicts the activities carry no
        information yet for this call.  After a conflict (``_scan == 0``)
        decisions follow VSIDS; every variable not popped is still in the
        heap, so the switch needs no work.
        """
        val = self._val
        lazy = self._lazy
        v = self._scan
        if v:
            n = self._nvars
            while v <= n and (val[2 * v] is not None or lazy[v]):
                v += 1
            if v > n:
                return -1
            self._scan = v
            return 2 * v + self._polarity[v]
        heap = self._heap
        pol = self._polarity
        while heap:
            v = self._heap_pop()
            if val[2 * v] is None and not lazy[v]:
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
        self._n_reductions += 1
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
        rb_ulim = self._rb_ulim
        rb_undo = self._rb_undo
        conflict_c = 0
        while True:
            confl = propagate()
            if confl is not None:
                self._n_conflicts += 1
                self._scan = 0
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
                        rb_ulim.append(len(rb_undo))
                        self._uid += 1
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
                rb_ulim.append(len(rb_undo))
                self._uid += 1
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
        lits = self._internal_lits(list(assumptions))
        self._mention(lits)
        held = self._held
        keep = len(held) if held is not None and lits[:len(held)] == held else 0
        return self._solve(lits, keep)

    def _solve(self, lits: list[int], keep: int) -> bool:
        """:meth:`solve` on internal literals.  Afterwards the levels of the
        first ``keep`` assumptions are held (see :meth:`_assume`) if
        possible.

        If the held levels are those of ``lits[:len(held)]``, the search
        starts from them: they are exactly the state the search would
        reach by deciding those assumptions (one level per assumption,
        propagated to fixpoint, valid reasons and watches).  At the end,
        the levels of ``lits[:keep]`` are kept if they are still on the
        trail: CDCL keeps every level-prefix of the trail closed under
        propagation (a learnt clause is unit exactly at its backjump level
        and is propagated there), so they are again the propagation
        fixpoint of the (grown) clause set under ``lits[:keep]``.  Not if
        learnt clauses were deleted meanwhile (the fixpoint could have
        used one).  With theories the same holds for theory propagation:
        the kept levels were reached by :meth:`_tpropagate`, and every
        literal the search added at them was reported and propagated
        there.
        """
        self._mvals = self._mdict = None
        self._tmodels = None
        self._conflict = []
        if self._ring and self._ok:
            rec = self._ring_hit(lits)
            if rec is not None:
                # An earlier model is still a model of the formula and of
                # lits: no search.  Variables created since get False.
                mv = rec[0]
                pad = self._nvars - len(mv)
                self._mvals = self._witness = mv + [False] * pad if pad else mv
                self._tmodels = None if rec[6] is None else list(rec[6])
                self._n_ring_hits += 1
                return True
        held = self._held
        if held is not None and lits[:len(held)] == held:
            pass                                # continue from held levels
        else:
            if self._trail_lim:
                self._backtrack(0)
            if not self._ok:
                return False
            if (self._tpropagate() if self._theories else self._propagate()) is not None:
                self._ok = False
                return False
        self._held = None                       # the search owns the trail
        reductions = self._n_reductions
        self._scan = 1
        self._assumptions = lits
        self._max_learnts = max(self._max_learnts,
                                (len(self._clauses) + self._rb_nclauses) / 3.0,
                                float(self._learnt_size_min))
        status = None
        restarts = 0
        while status is None:
            budget = int(_luby(self._restart_inc, restarts) * self._restart_first)
            status = self._search(budget)
            restarts += 1
        self._n_restarts += restarts - 1
        if status:
            # The values of variables 1..n (positive literals), copied in C;
            # the dict of model() is built from them on demand.  _mvals,
            # _witness and the ring entry are the same list object: safe only
            # because nothing mutates it (all are read, or replaced by a new
            # list).
            self._mvals = self._witness = mv = self._val[2:2 * self._nvars + 2:2]
            ring = self._ring
            ring.append((mv, len(self._clauses),
                         self._trail_lim[0] if self._trail_lim else len(self._trail),
                         len(self._rb_bases), len(self._theories), self._n_registered,
                         self._tmodels))
            if len(ring) > self._RING:
                del ring[0]
        if (keep and self._ok and len(self._trail_lim) >= keep
                and self._n_reductions == reductions):
            self._backtrack(keep)
            self._held = lits[:keep]
        else:
            self._backtrack(0)
        self._assumptions = []
        return status

    def _fill(self, mv: list, v: int):
        """The value of variable ``v`` in the stored model ``mv`` where it is
        None: a lazy block variable (never decided, see ``_lazy``).  The
        block's segment of ``mv`` is completed with a model of the block
        containing its assigned values (one exists: their closure was
        consistent at the time of the model), so later reads agree; nothing
        else constrained a lazy variable, so ``mv`` stays a model."""
        b = self._rb_base[v]
        if not b:
            return None
        n = self._rb_n
        lo = b - 1
        m = 0
        for i, x in enumerate(mv[lo:lo + n]):
            if x is not None:
                m |= 1 << (2 * i + (0 if x else 1))
        mv[lo:lo + n] = self._rbc.values_of(m)
        return mv[v - 1]

    @property
    def _model(self) -> dict[int, bool] | None:
        """The model of the last successful solve as ``{var: value}``
        (built on first use), or None."""
        m = self._mdict
        if m is None and self._mvals is not None:
            mv = self._mvals
            if self._rb_blocks and None in mv:
                for v in range(1, len(mv) + 1):
                    if mv[v - 1] is None:
                        self._fill(mv, v)
            m = self._mdict = dict(zip(range(1, len(self._mvals) + 1), self._mvals))
        return m

    def _ring_hit(self, lits: list[int]):
        """A stored model (most recent first) that satisfies ``lits`` and
        the current formula, or None.  A model found by search satisfies
        every clause, block and root literal of its time; the formula has
        only grown since (problem clauses and blocks are only added, root
        literals only fixed), so checking what was added is enough.
        Theories: the model passed their final check for the same theories
        and registrations (``_n_registered``: a variable registered with a
        second theory adds a constraint without a new ``_tmap`` entry;
        otherwise it is skipped); theory lemmas are valid in the
        theory, so they hold in it.  A literal of a variable the model does
        not know does not count as satisfied."""
        trail = self._trail
        root = self._trail_lim[0] if self._trail_lim else len(trail)
        cls = self._clauses
        bases = self._rb_bases
        ntheories = len(self._theories)
        natoms = self._n_registered
        for rec in reversed(self._ring):
            mv, ncl, rlen, nb, nt, na, _ = rec
            if nt != ntheories or na != natoms:
                continue
            n = len(mv)
            for l in lits:
                v = l >> 1
                if v > n:
                    break
                x = mv[v - 1]
                if x is None:
                    x = self._fill(mv, v)
                if x is not (not l & 1):
                    break
            else:
                for i in range(rlen, root):
                    l = trail[i]
                    v = l >> 1
                    if v > n:
                        break
                    x = mv[v - 1]
                    if x is None:
                        x = self._fill(mv, v)
                    if x is not (not l & 1):
                        break
                else:
                    for i in range(ncl, len(cls)):
                        for l in cls[i]:
                            v = l >> 1
                            if v <= n:
                                x = mv[v - 1]
                                if x is None:
                                    x = self._fill(mv, v)
                                if x is not (l & 1 == 1):
                                    break           # l is true in the model
                        else:
                            break               # clause false in the model
                    else:
                        if nb == len(bases) or self._ring_blocks(mv, bases[nb:]):
                            return rec
        return None

    def _ring_blocks(self, mv: list, bases) -> bool:
        """Do the model values ``mv`` satisfy the rule block at every base
        of ``bases``?"""
        n = len(mv)
        clauses = self._rb_clauses
        for b in bases:
            lo = 2 * b
            for c in clauses:
                for q in c:
                    l = q + lo
                    v = l >> 1
                    if v <= n:
                        x = mv[v - 1]
                        if x is None:
                            x = self._fill(mv, v)
                        if x is not (l & 1 == 1):
                            break
                else:
                    return False
        return True

    def model(self) -> dict[int, bool] | None:
        """Model of the last successful :meth:`solve`, else None."""
        m = self._model
        return dict(m) if m is not None else None

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
        n = len(w)
        for a in assumptions:
            v = -a if a < 0 else a
            if v <= n:
                b = w[v - 1]
                if b is None:
                    b = self._fill(w, v)
                if b != (a > 0):
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
        assumptions = [int(x) for x in assumptions]    # as _assume reads them
        if lit == 0:
            raise ValueError("literal must be a nonzero integer")
        self.mention((lit,))
        # Cheap path: unit propagation only.
        trail = self._assume(assumptions)
        if trail is None:
            raise ValueError("inconsistent assumptions")
        v = -lit if lit < 0 else lit
        if v > self._nvars:
            self._grow(v)
        l = 2 * v + 1 if lit < 0 else 2 * v
        vl = True if l in trail else False if l ^ 1 in trail else None
        lits = self._internal_lits(assumptions)
        k = len(lits)
        if vl is not None:
            if self._witness_satisfies(assumptions) or self._solve(lits, k):
                return vl
            raise ValueError("inconsistent assumptions")
        # Full search.
        if not self._solve(lits + [l ^ 1], k):
            if not self._solve(lits + [l], k):
                raise ValueError("inconsistent assumptions")
            return True
        if not self._solve(lits + [l], k):
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
            "rule_blocks": self._rb_blocks,
            "witness_hits": self._n_ring_hits,
        }
