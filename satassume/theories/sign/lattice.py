"""Class propagators: the DPLL(T) machinery shared by SIGN and CLOSURE.

A *lattice* here is a finite partition of the values a term can take
(the *atoms*, at most a few dozen) plus ``NAN`` ("no claim"), with one
table per operation (``ADD``, ``MUL``) giving the set of atoms ``a op b``
can take for ``a``, ``b`` in two atoms.  A set of atoms is a bit mask.
:class:`Lattice` folds the tables over masks (memoised), and
:class:`ClassTheory` is the theory over the nodes ``N = op(A1, ..., An)``
of a session: forward, ``S(N) &= fold(S(A))`` unless the fold may be
``NAN``; backward, an atom ``c`` stays in ``S(Ak)`` only if ``op(c,
fold(S(Aj), j != k))`` may be ``NAN`` or meets ``S(N)``.  A literal of a
term is an atom set (its predicate); it is implied when the term's set lies
inside or outside it, and an empty set is a conflict.  The reason of each
is a subset of the node's and the arguments' literals that suffices,
minimised by deletion.

Two lattices use it: :mod:`.sign` (signs of the real and imaginary parts,
zero, finiteness: issue #149 T1) and :mod:`.closure` (membership in the
integers, rationals, algebraic numbers, reals and complex numbers: T3).
Both operations are commutative and associative on values and each table
over-approximates its step, so any bracketing of a fold is sound.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Sequence, Tuple

ADD, MUL = 0, 1


class Lattice:
    """``natoms`` atoms ``0 .. natoms - 1``, ``NAN`` the bit ``natoms``,
    ``ops[op](a, b)`` the atom set of ``a op b`` (a mask, possibly with
    the ``NAN`` bit).  ``memo`` is the module's process memo (adopted by
    :mod:`satassume.state.memos` there): :meth:`mop` and :meth:`allowed`
    are pure functions of their keys."""

    def __init__(self, natoms: int, ops: Sequence[Callable[[int, int], int]], memo: Dict):
        self.natoms = natoms
        self.ALL = (1 << natoms) - 1
        self.NANB = 1 << natoms
        self.ops = tuple(ops)
        self.memo = memo

    def mop(self, op: int, ma: int, mb: int) -> int:
        """The atom set of ``a op b`` for ``a`` in ``ma`` and ``b`` in ``mb``."""
        key = (op, ma, mb) if ma <= mb else (op, mb, ma)
        memo = self.memo
        r = memo.get(key)
        if r is None:
            nanb, full = self.NANB, self.ALL
            r = nanb if (ma | mb) & nanb else 0
            ma &= full
            mb &= full
            f = self.ops[op]
            n = self.natoms
            for a in range(n):
                if ma >> a & 1:
                    for b in range(n):
                        if mb >> b & 1:
                            r |= f(a, b)
            memo[key] = r
        return r

    def allowed(self, op: int, rest: int, newn: int) -> int:
        """The atoms ``c`` with ``op(c, rest)`` holding ``NAN`` or meeting
        ``newn``: those an argument keeps when the others fold to ``rest``
        and the node lies in ``newn`` (memoised with :meth:`mop`, under
        keys of their own length)."""
        key = (op, rest, newn, 0)
        memo = self.memo
        r = memo.get(key)
        if r is None:
            r = 0
            nanb = self.NANB
            for c in range(self.natoms):
                m = self.mop(op, 1 << c, rest)
                if m & nanb or m & newn:
                    r |= 1 << c
            memo[key] = r
        return r

    def fold(self, op: int, masks) -> int:
        it = iter(masks)
        r = next(it)
        mop = self.mop
        for m in it:
            r = mop(op, r, m)
        return r

    def node_masks(self, op: int, nmask: int, amasks: List[int]) -> Tuple[int, List[int]]:
        """One round of propagation over ``N = op(A1, ..., An)``: the new
        set of the node and of each argument (an empty set is a
        conflict)."""
        mop, nanb = self.mop, self.NANB
        n = len(amasks)
        pre: list = [None] * n
        acc = None
        for i in range(n):
            pre[i] = acc
            acc = amasks[i] if acc is None else mop(op, acc, amasks[i])
        total = acc
        newn = nmask if total & nanb else nmask & total
        out = list(amasks)
        if newn & self.ALL == self.ALL or n < 2:
            return newn, out
        suf = None
        allowed = self.allowed
        for i in range(n - 1, -1, -1):
            p = pre[i]
            rest = p if suf is None else (suf if p is None else mop(op, p, suf))
            m = amasks[i]
            suf = m if suf is None else mop(op, suf, m)
            if rest & nanb:
                continue
            out[i] = m & allowed(op, rest, newn)
        return newn, out


class ClassTheory:
    """The theory of one lattice ``L`` (a class attribute of the
    subclass; contract: :mod:`satassume.sat.theory`)."""

    L: Lattice
    gave_up = False     # in the current search (reset at the root)
    #: theory conflicts allowed between two returns to the root level
    MAX_CONFLICTS = 2000
    budget = MAX_CONFLICTS
    #: over this many arguments, a reason keeps every literal of a term it
    #: needs (no deletion of single literals): the deletion is quadratic
    WHY_FINE = 16

    def __init__(self):
        self.tvars: List[List[Tuple[int, int]]] = []   # term -> its (variable, atom set)
        self.fixed: List[int] = []           # term -> atom set known from its value
        self.tnodes: List[List[int]] = []    # term -> the nodes it takes part in
        self.nodes: List[Tuple[int, int, Tuple[int, ...]]] = []   # (op, node, args)
        self.atom: Dict[int, Tuple[int, int]] = {}   # variable -> (term, atom set)
        self.val: Dict[int, bool] = {}
        self.trail: List[int] = []
        self.lim: List[Tuple[int, int]] = []
        self.cur: List[int] = []             # term -> its set under the asserted literals
        self.mtrail: List[Tuple[int, int]] = []   # (term, its set before) to undo
        self.dirty: set = set()
        self.stats = {"props": 0, "conflicts": 0}

    # -- structure (told by the adapter) ----------------------------------
    def term(self, fixed: int = -1) -> int:
        if fixed < 0:
            fixed = self.L.ALL
        self.tvars.append([])
        self.fixed.append(fixed)
        self.cur.append(fixed)
        self.tnodes.append([])
        return len(self.tvars) - 1

    def add_node(self, op: int, t: int, args) -> None:
        i = len(self.nodes)
        self.nodes.append((op, t, tuple(args)))
        for u in {t, *args}:
            self.tnodes[u].append(i)
        self.dirty.add(i)

    # -- the contract -------------------------------------------------------
    def register_atom(self, v: int, payload) -> None:
        """``payload = (t, m)``: ``v`` says that term ``t`` lies in the
        atom set ``m`` (a predicate of the lattice, or a derived one over
        them, ``sign_adapter.def_mask``), and ``-v`` that it lies outside
        it."""
        t, m = payload
        if v in self.atom:
            return
        self.tvars[t].append((v, m))
        self.atom[v] = (t, m)
        self.dirty.update(self.tnodes[t])     # (it may imply the new atom)

    def assert_lit(self, lit: int):
        v = lit if lit > 0 else -lit
        a = self.atom.get(v)
        if a is None or v in self.val:
            return None
        self.val[v] = lit > 0
        self.trail.append(v)
        t, m = a
        old = self.cur[t]
        new = old & m if lit > 0 else old & ~m
        if new != old:
            # only a narrower set can propagate: the theory's own
            # implications, once asserted, mostly leave it as it is
            self.mtrail.append((t, old))
            self.cur[t] = new
            self.dirty.update(self.tnodes[t])
        return None

    def push_level(self) -> None:
        self.lim.append((len(self.trail), len(self.mtrail)))

    def pop_level(self) -> None:
        k, km = self.lim.pop()
        trail, val = self.trail, self.val
        while len(trail) > k:
            del val[trail.pop()]
        mtrail, cur = self.mtrail, self.cur
        while len(mtrail) > km:
            t, m = mtrail.pop()
            cur[t] = m
        # sets only widen on backtrack: no propagation is owed
        if not self.lim:
            # back at the root: a new search, a new budget (a theory that
            # gave up in the last one has missed no literal: assert_lit
            # records them all; the propagation it owes is redone)
            self.budget = self.MAX_CONFLICTS
            if self.gave_up:
                self.gave_up = False
                self.dirty = set(range(len(self.nodes)))

    # -- propagation ----------------------------------------------------------
    def _lits(self, t: int) -> List[int]:
        val = self.val
        return [v if val[v] else -v for v, _ in self.tvars[t] if v in val]

    def _mask(self, t: int, lits) -> int:
        m = self.fixed[t]
        atom = self.atom
        for l in lits:
            pm = atom[l if l > 0 else -l][1]
            m &= pm if l > 0 else ~pm
        return m

    def _width(self, l: int) -> int:
        m = self.atom[l if l > 0 else -l][1]
        return bin(m if l > 0 else self.L.ALL & ~m).count("1")

    def _slot(self, i: int, masks: List[int], j: int) -> int:
        """The new set of slot ``j`` of node ``i`` (0 the node, ``k + 1``
        argument ``k``) for the sets ``masks`` of the node and its
        arguments: the same set as :meth:`Lattice.node_masks` gives,
        computing only what slot ``j`` needs (the forward fold for the
        node)."""
        L = self.L
        op = self.nodes[i][0]
        nm, am = masks[0], masks[1:]
        total = L.fold(op, am)
        newn = nm if total & L.NANB else nm & total
        if j == 0:
            return newn
        m = am[j - 1]
        if newn & L.ALL == L.ALL or len(am) < 2:
            return m
        rest = L.fold(op, am[:j - 1] + am[j:])
        if rest & L.NANB:
            return m
        return m & L.allowed(op, rest, newn)

    def _why(self, i: int, lits, j: int, test) -> List[int]:
        """A subset of the literals ``lits`` (term -> literals) of node
        ``i`` under which ``test`` still holds of the new set of slot ``j``
        (0 the node, ``k + 1`` argument ``k``): greedy deletion, first of
        the whole literal set of each slot, then of single literals of the
        slots kept.  Any subset is a sound reason (the sets only widen as
        literals go); the deletion only makes it shorter."""
        op, t, args = self.nodes[i]
        slots = (t, *args)
        ls = [lits[u] for u in slots]
        masks = [self._mask(u, l) for u, l in zip(slots, ls)]
        wide = [self.fixed[u] for u in slots]
        for k in range(len(slots)):
            if ls[k] and masks[k] != wide[k]:
                old = masks[k]
                masks[k] = wide[k]
                if test(self._slot(i, masks, j)):
                    ls[k] = ()
                else:
                    masks[k] = old
            elif ls[k]:
                ls[k] = ()          # the literals say no more than the value
        if len(args) <= self.WHY_FINE:
            for k in range(len(slots)):
                if len(ls[k]) < 2:
                    continue
                kept = list(ls[k])
                # the narrowest literals first: a reason that keeps the wide
                # ones (``~negative_infinite(x)`` over ``finite(x)``) holds
                # in more branches, and so does the clause learnt from it
                for l in sorted(kept, key=self._width):
                    kept.remove(l)
                    masks[k] = self._mask(slots[k], kept)
                    if not test(self._slot(i, masks, j)):
                        kept.append(l)
                masks[k] = self._mask(slots[k], kept)
                ls[k] = kept
        # a term may fill several slots (``x*x``): its literals once
        out = []
        for l in ls:
            for x in l:
                if x not in out:
                    out.append(x)
        return out

    def _reason(self, i: int, lits, j: int, test, lit: int):
        """The lazy reason of ``lit``, implied at slot ``j`` of node ``i``
        under the literals ``lits``: a function returning the clause."""
        def reason():
            return [lit] + [-l for l in self._why(i, lits, j, test) if l != -lit]
        return reason

    def _node(self, i: int, out: list, seen: set) -> bool:
        """Propagate node ``i`` into ``out``; False after a conflict."""
        nanb = self.L.NANB
        op, t, args = self.nodes[i]
        cm = self.cur
        am = [cm[u] for u in args]
        newn, newa = self.L.node_masks(op, cm[t], am)
        if newn == cm[t] and newa == am and newn:
            # no set narrows: every literal it could imply is implied by
            # the term's own literals (the rule block and the definitions
            # of the derived atoms write those)
            return True
        lits = {u: self._lits(u) for u in (t, *args)}
        val = self.val
        for j, u in enumerate((t, *args)):
            m = newn if j == 0 else newa[j - 1]
            if m == cm[u] and m:
                continue                    # (as above, for this slot)
            if not m:
                why = self._why(i, lits, j, lambda s: not s)
                if not why:
                    continue                # (only constants: not a claim)
                self.stats["conflicts"] += 1
                self.budget -= 1
                if self.budget < 0:
                    # a search that splits on many arguments without a
                    # shared literal (the reasons differ per case): stop
                    # contributing (satassume.sat.theory, "Giving up")
                    self.gave_up = True
                    return True
                c = [-l for l in why]
                out.append((c[0], c))
                return False
            if m & nanb:
                continue
            for v, pm in self.tvars[u]:
                if not m & ~pm:
                    lit = v
                    test = (lambda s, pm=pm: not s & ~pm)
                elif not m & pm:
                    lit = -v
                    test = (lambda s, pm=pm: not s & pm)
                else:
                    continue
                cur = val.get(v)
                if (cur is not None and cur == (lit > 0)) or lit in seen:
                    continue
                seen.add(lit)
                self.stats["props"] += 1
                if cur is None:
                    # a lazy reason (satassume.sat.theory): explained only
                    # if conflict analysis reads it, from the literals
                    # asserted now (``lits`` is not changed afterwards)
                    out.append((lit, self._reason(i, lits, j, test, lit)))
                    continue
                why = self._why(i, lits, j, test)
                out.append((lit, [lit] + [-l for l in why if l != -lit]))
                self.stats["conflicts"] += 1
                self.budget -= 1
                return False                # the literal is false: a conflict
        return True

    def propagate(self):
        if not self.dirty or self.gave_up:
            return ()
        out: list = []
        seen: set = set()
        dirty, self.dirty = self.dirty, set()
        for i in sorted(dirty):
            if self.gave_up:
                break
            if not self._node(i, out, seen):
                self.dirty |= dirty
                break
        return out

    def check(self):
        if self.gave_up:
            return None
        self.dirty = set(range(len(self.nodes)))
        for lit, why in self.propagate():
            v = lit if lit > 0 else -lit
            if v in self.val and self.val[v] != (lit > 0):
                return (False, why)
        return None
