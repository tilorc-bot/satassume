"""EUF: equality with uninterpreted functions, as a DPLL(T) theory solver.

:class:`EUFTheory` implements the protocol of :mod:`satassume.theory`
(``register_atom``, ``assert_lit``, ``check``, ``push_level``,
``pop_level`` and ``propagate``) with an incremental congruence closure in
the style of Nieuwenhuis and Oliveras, "Fast congruence closure and
extensions" (Inf. Comput. 2007):

* **Terms** are small ints handed out by :meth:`EUFTheory.term` (an opaque
  constant, or a function head applied to argument terms) and
  :meth:`EUFTheory.value` (an interpreted constant, pairwise distinct from
  every other value).  An application ``f(a1, ..., an)`` is curried into
  binary applications ``apply(...apply(F, a1)..., an)``, where ``F`` is a
  head constant keyed by ``(f, n)``.  Heads with different arities never
  share a partial application, so ``f(a) = f(b)`` says nothing about
  ``f(a, c)`` and ``f(b, c)``.  Heads live in their own namespace, apart
  from constants.
* **Closure.**  There is one representative per class (``_repr`` is a
  direct pointer, and each class keeps a member list).  Union by size moves
  the members of the smaller class.  Each class has a use list of the
  applications that have an argument in it, and ``_lookup`` maps
  ``(repr f, repr a)`` to an application.  Merges go through a pending
  queue.
* **Explanations** come from a proof forest.  Every union adds one edge,
  labelled with either the asserted literal or the pair of congruent
  applications.  Explaining ``a = b`` walks both paths to their nearest
  common ancestor.  It recurses into congruence edges, and an auxiliary
  union-find makes sure each edge is explained once (the paper's
  ``Explain``).  The result is the set of asserted literals behind the
  equality.  It is not guaranteed minimal, but it is irredundant along the
  proof forest.
* **Backtracking** undoes a trail, and nothing is rebuilt.  A union
  records what it changed, and undoing it costs as much as the union did:
  the members of the smaller class get their old representative back, the
  lists that grew are truncated, the lookup entries it added are deleted,
  and the proof-forest edge is removed with the path it reversed turned
  back.  Lookup entries left behind under a former representative stay in
  place, because they become valid again exactly when the union that
  retired that representative is undone.

Disequalities ``s != t`` are kept in per-class lists and checked when their
classes merge.  Two value terms in one class are a conflict.  Both are
detected eagerly in :meth:`assert_lit`, so the theory is complete eagerly
and :meth:`check` has nothing left to find.  Conflict clauses are the
negations of the asserted literals behind the conflict: the explanation of
the equality, plus the violated disequality literal when there is one.

Theory propagation: when a union makes the two sides of a registered,
unassigned atom equal, :meth:`propagate` reports the literal that makes
the atom's equation true, with the explanation as its reason.  Propagating
disequalities (from values or asserted disequalities) is not implemented.
Leaving it out is always sound, and the eager conflict still catches the
case.

Merge hook: if :attr:`EUFTheory.on_merge` is set, it is called as
``on_merge(ra, rb)`` after every union, with ``ra`` the representative that
was retired and ``rb`` the one that now stands for the merged class.
Nothing is called on undo; a listener must not keep state that a
``pop_level`` would have to revert, or must revert it through its own
``pop_level`` (the transfer layer, :mod:`satassume.transfer`, recomputes
from the current classes and needs no undo).

Out of scope here: arithmetic and AC reasoning.  Substitution of equals
into unary predicates (``Q.prime(x)`` from ``Q.eq(x, y) & Q.prime(y)``) is
done by :mod:`satassume.transfer` on top of this theory's classes.
"""
from __future__ import annotations

from collections import namedtuple
from typing import Any, Hashable, Iterable

__all__ = ["EUFTheory", "EqAtom"]


EqAtom = namedtuple("EqAtom", "lhs rhs positive", defaults=(True,))
EqAtom.__doc__ = """Payload of an EUF atom: ``lhs == rhs`` between term ids.

With ``positive=False`` the variable stands for ``lhs != rhs``.  A plain
``(lhs, rhs)`` tuple is accepted as well."""

# Trail opcodes
_UNION, _LOOKUP, _ASSIGN, _DISEQ, _REG_APP, _REG_ATOM, _USE = range(7)


class EUFTheory:
    """Incremental congruence closure with explanations and trail undo.

    Terms are made with :meth:`term` and :meth:`value`, and atoms are
    registered with :meth:`register_atom` (payload :class:`EqAtom`).  The
    other public methods are the theory protocol plus :meth:`find`,
    :meth:`equal` and :meth:`explain`.
    """

    def __init__(self) -> None:
        self._keys: dict[Any, int] = {}       # interning key -> term
        self._app: list = []                  # term -> (f, a) or None
        self._repr: list[int] = []            # term -> class representative
        self._members: list[list[int]] = []   # rep -> members of its class
        self._use: list[list[int]] = []       # rep -> apps with an argument in the class
        self._lookup: dict[tuple, int] = {}   # (repr f, repr a) -> app
        self._pfp: list[int] = []             # proof forest parent (-1: root)
        self._pfl: list = []                  # label of the edge to the parent
        self._val: list[int] = []             # rep -> value term of the class or -1
        self._diseq: list[list] = []          # rep -> [(lit, s, t)] touching the class
        self._atoms_of: list[list[int]] = []  # rep -> atom vars with a side in the class
        self._atoms: dict[int, tuple] = {}    # var -> (s, t, positive)
        self._assigned: dict[int, int] = {}   # var -> asserted literal
        self._pending: list = []              # merges to do: (a, b, label)
        self._propq: list[int] = []           # atom vars that became equal
        self._conflict = None                 # (False, clause) until popped
        self._trail: list[tuple] = []
        self._lims: list[int] = []
        #: ``on_merge(retired_rep, new_rep)`` after each union, or None
        self.on_merge = None

    # ------------------------------------------------------------------
    # Terms
    # ------------------------------------------------------------------

    def _new(self, key, app=None, value=False) -> int:
        t = len(self._repr)
        self._keys[key] = t
        self._app.append(app)
        self._repr.append(t)
        self._members.append([t])
        self._use.append([])
        self._pfp.append(-1)
        self._pfl.append(None)
        self._val.append(t if value else -1)
        self._diseq.append([])
        self._atoms_of.append([])
        return t

    def term(self, head: Hashable, args: Iterable[int] = ()) -> int:
        """The term ``head(*args)``, or the constant ``head`` if ``args`` is
        empty.  ``args`` are term ids.  Interned: equal inputs give the
        same id."""
        args = tuple(args)
        if not args:
            key = ("c", head)
            t = self._keys.get(key)
            return self._new(key) if t is None else t
        n = len(self._repr)
        for a in args:
            if not (isinstance(a, int) and 0 <= a < n):
                raise ValueError(f"not a term id: {a!r}")
        hkey = ("h", head, len(args))
        t = self._keys.get(hkey)
        if t is None:
            t = self._new(hkey)
        for a in args:
            t = self._apply(t, a)
        return t

    def value(self, key: Hashable) -> int:
        """An interpreted constant.  ``value(k1)`` and ``value(k2)`` are
        distinct terms that can never be equal iff ``k1 != k2``."""
        k = ("v", key)
        t = self._keys.get(k)
        return self._new(k, value=True) if t is None else t

    def _apply(self, f: int, a: int) -> int:
        key = ("a", f, a)
        t = self._keys.get(key)
        if t is None:
            t = self._new(key, (f, a))
            self._index_app(t)
            self._process()
        return t

    def _index_app(self, t: int) -> None:
        """Enter application ``t`` into the lookup table and use lists, or
        queue its merge with a congruent application."""
        lims = self._lims
        if lims:
            self._trail.append((_REG_APP, t))
        f, a = self._app[t]
        rep = self._repr
        rf, ra = rep[f], rep[a]
        key = (rf, ra)
        o = self._lookup.get(key)
        if o is None:
            self._lookup[key] = t
            self._use[rf].append(t)
            if lims:
                self._trail.append((_LOOKUP, key))
                self._trail.append((_USE, rf))
            if ra != rf:
                self._use[ra].append(t)
                if lims:
                    self._trail.append((_USE, ra))
        elif rep[o] != rep[t]:
            self._pending.append((t, o, (t, o)))

    def num_terms(self) -> int:
        return len(self._repr)

    def members(self, t: int) -> list[int]:
        """The terms of ``t``'s class (the live list: do not modify)."""
        return self._members[self._repr[t]]

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def find(self, t: int) -> int:
        """The representative of ``t``'s class."""
        return self._repr[t]

    def equal(self, a: int, b: int) -> bool:
        return self._repr[a] == self._repr[b]

    def explain(self, a: int, b: int) -> list[int]:
        """The asserted literals (true under the current assignment) whose
        conjunction implies ``a == b``.  ``a`` and ``b`` must be equal."""
        if self._repr[a] != self._repr[b]:
            raise ValueError("explain: terms are not equal")
        return sorted(self._explain(a, b, set()))

    # ------------------------------------------------------------------
    # Union and the proof forest
    # ------------------------------------------------------------------

    def _reroot(self, x: int) -> int:
        """Make ``x`` the root of its proof tree by reversing the path to
        the old root.  Returns the old root."""
        pfp, pfl = self._pfp, self._pfl
        prev, plab, cur = -1, None, x
        while cur != -1:
            nxt, lab = pfp[cur], pfl[cur]
            pfp[cur], pfl[cur] = prev, plab
            prev, plab, cur = cur, lab, nxt
        return prev

    def _union(self, a: int, b: int, label) -> None:
        rep = self._repr
        ra, rb = rep[a], rep[b]
        if ra == rb:
            return
        members = self._members
        if len(members[ra]) > len(members[rb]):
            a, b, ra, rb = b, a, rb, ra
        old_root = self._reroot(a)
        self._pfp[a] = b
        self._pfl[a] = label
        ma = members[ra]
        for c in ma:
            rep[c] = rb
        members[rb].extend(ma)
        use_b, diseq_b, atoms_b = self._use[rb], self._diseq[rb], self._atoms_of[rb]
        val = self._val
        set_val = val[rb] < 0 <= val[ra]
        trail = self._trail if self._lims else None
        if trail is not None:
            trail.append((_UNION, ra, rb, a, old_root, len(use_b),
                          len(diseq_b), len(atoms_b), set_val))
        conflict = None
        if set_val:
            val[rb] = val[ra]
        elif val[ra] >= 0:
            # two distinct values in one class
            conflict = self._explain(val[ra], val[rb], set())
        # congruence: rekey the applications that used the smaller class
        lookup, app, pending = self._lookup, self._app, self._pending
        for t in self._use[ra]:
            f, x = app[t]
            key = (rep[f], rep[x])
            o = lookup.get(key)
            if o is None:
                lookup[key] = t
                use_b.append(t)
                if trail is not None:
                    trail.append((_LOOKUP, key))
            elif rep[o] != rep[t]:
                pending.append((t, o, (t, o)))
        # disequalities between the two classes are now violated
        dl = self._diseq[ra]
        if dl:
            if conflict is None:
                for lit, s, t in dl:
                    if rep[s] == rep[t]:
                        conflict = self._explain(s, t, {lit})
                        break
            diseq_b.extend(dl)
        # atoms whose sides just became equal
        al = self._atoms_of[ra]
        if al:
            assigned, atoms = self._assigned, self._atoms
            for v in al:
                if v not in assigned:
                    s, t, _ = atoms[v]
                    if rep[s] == rep[t]:
                        self._propq.append(v)
            atoms_b.extend(al)
        if conflict is not None:
            self._conflict = (False, sorted(-l for l in conflict))
        if self.on_merge is not None:
            self.on_merge(ra, rb)

    def _undo_union(self, ra, rb, a, old_root, nuse, ndiseq, natoms, set_val):
        self._pfp[a] = -1
        self._pfl[a] = None
        self._reroot(old_root)
        ma = self._members[ra]
        mb = self._members[rb]
        del mb[len(mb) - len(ma):]
        rep = self._repr
        for c in ma:
            rep[c] = ra
        del self._use[rb][nuse:]
        del self._diseq[rb][ndiseq:]
        del self._atoms_of[rb][natoms:]
        if set_val:
            self._val[rb] = -1

    def _process(self) -> None:
        pending = self._pending
        i = 0
        while i < len(pending) and self._conflict is None:
            a, b, label = pending[i]
            i += 1
            self._union(a, b, label)
        pending.clear()

    def _explain_edge(self, cur, out, todo, aux, high) -> int:
        """Explain the proof-forest edge from ``cur`` to its parent; return
        the next node to look at."""
        p = self._pfp[cur]
        lab = self._pfl[cur]
        if isinstance(lab, int):
            out.add(lab)
        else:
            t1, t2 = lab
            app = self._app
            f1, a1 = app[t1]
            f2, a2 = app[t2]
            if f1 != f2:
                todo.append((f1, f2))
            if a1 != a2:
                todo.append((a1, a2))
        aux[cur] = p
        return high(p)

    def _explain(self, a: int, b: int, out: set) -> set:
        """Add to ``out`` the asserted literals behind ``a == b``."""
        pfp = self._pfp
        aux: dict[int, int] = {}

        def high(x):
            r = x
            while r in aux:
                r = aux[r]
            while x in aux:
                aux[x], x = r, aux[x]
            return r

        todo = [(a, b)]
        while todo:
            x, y = todo.pop()
            if x == y:
                continue
            # x's path to the root (node -> distance from x), then y's path
            # up to the first node on x's path: the nearest common ancestor
            px = {}
            c, i = x, 0
            while c != -1:
                px[c] = i
                c, i = pfp[c], i + 1
            py = set()
            c = y
            while c not in px:
                py.add(c)
                c = pfp[c]
            top = px[c]
            # explain the edges below the ancestor on both paths; high()
            # skips chains of edges explained already (it only moves up)
            cur = high(x)
            while px[cur] < top:
                cur = self._explain_edge(cur, out, todo, aux, high)
            cur = high(y)
            while cur in py:
                cur = self._explain_edge(cur, out, todo, aux, high)
        return out

    # ------------------------------------------------------------------
    # Theory protocol
    # ------------------------------------------------------------------

    def register_atom(self, literal: int, payload) -> None:
        if literal <= 0 or literal in self._atoms:
            raise ValueError(f"bad or repeated atom variable {literal}")
        if isinstance(payload, EqAtom):
            s, t, pos = payload
        else:
            s, t = payload
            pos = True
        n = len(self._repr)
        if not (isinstance(s, int) and isinstance(t, int) and 0 <= s < n and 0 <= t < n):
            raise ValueError(f"EUF atom over unknown terms: {payload!r}")
        self._atoms[literal] = (s, t, bool(pos))
        self._index_atom(literal)

    def _index_atom(self, v: int) -> None:
        s, t, _ = self._atoms[v]
        rep = self._repr
        rs, rt = rep[s], rep[t]
        if self._lims:
            self._trail.append((_REG_ATOM, v, rs, rt))
        self._atoms_of[rs].append(v)
        if rt != rs:
            self._atoms_of[rt].append(v)
        elif v not in self._assigned:
            self._propq.append(v)

    def assert_lit(self, literal: int):
        v = abs(literal)
        atom = self._atoms.get(v)
        if atom is None:
            return None
        if self._conflict is not None:
            return self._conflict
        s, t, pos = atom
        self._assigned[v] = literal
        if self._lims:
            self._trail.append((_ASSIGN, v))
        rep = self._repr
        if (literal > 0) == pos:
            self._pending.append((s, t, literal))
            self._process()
        else:
            rs, rt = rep[s], rep[t]
            if rs == rt:
                expl = self._explain(s, t, {literal})
                self._conflict = (False, sorted(-l for l in expl))
            else:
                d = (literal, s, t)
                if self._lims:
                    self._trail.append((_DISEQ, rs, len(self._diseq[rs]),
                                        rt, len(self._diseq[rt])))
                self._diseq[rs].append(d)
                self._diseq[rt].append(d)
        return self._conflict

    def check(self):
        if self._conflict is not None:
            return self._conflict
        return (True, dict(enumerate(self._repr)))

    def propagate(self):
        q = self._propq
        if not q or self._conflict is not None:
            return []
        out = []
        seen = set()
        rep, atoms, assigned = self._repr, self._atoms, self._assigned
        for v in q:
            if v in assigned or v in seen:
                continue
            s, t, pos = atoms[v]
            if rep[s] != rep[t]:
                continue
            seen.add(v)
            lit = v if pos else -v
            out.append((lit, [lit] + sorted(-l for l in self._explain(s, t, set()))))
        q.clear()
        return out

    def push_level(self) -> None:
        self._lims.append(len(self._trail))

    def pop_level(self) -> None:
        lim = self._lims.pop()
        trail = self._trail
        redo_apps: list[int] = []
        redo_atoms: list[int] = []
        while len(trail) > lim:
            e = trail.pop()
            op = e[0]
            if op == _UNION:
                self._undo_union(*e[1:])
            elif op == _LOOKUP:
                del self._lookup[e[1]]
            elif op == _USE:
                self._use[e[1]].pop()
            elif op == _ASSIGN:
                del self._assigned[e[1]]
            elif op == _DISEQ:
                _, rs, ns, rt, nt = e
                del self._diseq[rt][nt:]
                del self._diseq[rs][ns:]
            elif op == _REG_APP:
                redo_apps.append(e[1])
            else:  # _REG_ATOM
                _, v, rs, rt = e
                if rt != rs:
                    self._atoms_of[rt].pop()
                self._atoms_of[rs].pop()
                redo_atoms.append(v)
        self._pending.clear()
        self._propq.clear()
        self._conflict = None
        # terms and atoms made above this level stay; index them again
        for t in reversed(redo_apps):
            self._index_app(t)
        self._process()
        for v in reversed(redo_atoms):
            self._index_atom(v)

    # ------------------------------------------------------------------

    def level(self) -> int:
        return len(self._lims)

    def __repr__(self) -> str:
        return (f"<EUFTheory {len(self._repr)} terms, {len(self._atoms)} atoms, "
                f"level {len(self._lims)}>")
