"""SIGN: the class of a sum or product from the classes of its arguments.

A DPLL(T) theory (issue #149, proposal T1, stage 1) over the sign basis
variables of ``Add`` and ``Mul`` nodes and their arguments: whatever the
arity, it propagates the class of the node from the classes of the
arguments (forward), and the class of one argument from the node and the
other arguments (backward).  It needs no SymPy: :mod:`.sign_adapter`
tells it the terms, nodes and constants.

**Atoms.**  The value of a term lies in one of 12 *atoms* of the extended
complex plane, plus ``NAN``:

* a finite value by the signs of its real and imaginary parts,
  ``F(sr, si)`` with ``sr, si`` in ``{-1, 0, 1}`` (9 atoms: ``F(0, 0)`` is
  0, ``F(+-1, 0)`` the finite nonzero reals, ``F(0, +-1)`` the imaginary
  numbers, the other four the finite values off both axes);
* ``PI`` (``oo``), ``NI`` (``-oo``) and ``IN``: every other infinity
  (``zoo``, ``oo*I``, ``oo*(1 + I)``, ``oo + I``);
* ``NAN``: the sum or product is ``nan`` (``oo - oo``, ``0*oo``,
  ``zoo + zoo``).  It is "no claim": a node that may be ``nan`` gets no
  literal from this theory, as in the templates (``docs/design.md``,
  "Extended reals and nan in templates").  Arguments are never ``nan``,
  the convention of the templates' soundness oracle
  (``tests/test_templates.py``): a ``nan`` argument makes the node ``nan``
  whatever its literals say.

A literal of a basis predicate is a set of atoms (:data:`PRED_MASK`):
``extended_real`` = the reals and ``+-oo``, ``finite`` = the 9 finite
atoms, ``zero``, ``extended_positive``, ``extended_negative``,
``imaginary`` = ``F(0, +-1)``.  The other predicates reach these six
through the rule block (``prime -> extended_positive``, ``integer ->
extended_real & finite``), which writes their literals on the trail.

**Operations.**  :func:`_add_atoms` and :func:`_mul_atoms` give the set of
atoms ``a + b`` and ``a * b`` can take for ``a``, ``b`` in two atoms:
interval arithmetic on the signs of the parts (``re(a*b) = ar*br -
ai*bi``) plus SymPy's conventions for infinities (each case commented
there).  A node folds them over its arguments: both operations are
commutative and associative on values, and the set operation
over-approximates each step, so any order is sound; ``NAN`` absorbs.
``tests/test_sign_theory.py`` checks both tables against SymPy at sample
points of every atom and the folds against n-ary ``Add`` and ``Mul``.

**Propagation.**  For a node ``N = op(A1, ..., An)`` with atom sets ``S``:
``S(N) &= fold(S(A))`` unless the fold holds ``NAN``, and for each ``k``
an atom ``c`` stays in ``S(Ak)`` only if ``op(c, fold(S(Aj), j != k))``
holds ``NAN`` or meets ``S(N)``.  A literal is implied when a set lies
inside (or outside) its predicate's set; an empty set is a conflict.  The
reason of each is a subset of the node's and the arguments' literals that
suffices, minimised by deletion: one clause, the template rule it stands
for.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from ...state.memos import adopt as _adopt_memo

#: the basis predicates the theory reads and writes, by local index
PREDS = ("extended_real", "finite", "zero", "extended_positive", "extended_negative",
         "imaginary")


def F(sr: int, si: int) -> int:
    """The atom of the finite values whose real part has sign ``sr`` and
    imaginary part sign ``si``."""
    return (sr + 1) * 3 + (si + 1)


PI, NI, IN, NAN = 9, 10, 11, 12
ZERO = F(0, 0)
FIN = (1 << 9) - 1
ALL = (1 << 12) - 1            # every atom but NAN: an argument's widest set
NANB = 1 << NAN


def _b(*atoms) -> int:
    m = 0
    for a in atoms:
        m |= 1 << a
    return m


PRED_MASK = (
    _b(F(-1, 0), ZERO, F(1, 0), PI, NI),           # extended_real
    FIN,                                           # finite
    _b(ZERO),                                      # zero
    _b(F(1, 0), PI),                               # extended_positive
    _b(F(-1, 0), NI),                              # extended_negative
    _b(F(0, -1), F(0, 1)),                         # imaginary
)


def _sadd(a: int, b: int) -> Tuple[int, ...]:
    """The signs of ``x + y`` for reals ``x``, ``y`` of signs ``a``, ``b``."""
    if a == 0:
        return (b,)
    if b == 0 or a == b:
        return (a,)
    return (-1, 0, 1)


def _fin(a: int) -> Tuple[int, int]:
    return a // 3 - 1, a % 3 - 1


def _add_atoms(a: int, b: int) -> int:
    if a < 9 and b < 9:
        (ar, ai), (br, bi) = _fin(a), _fin(b)
        return _b(*(F(r, i) for r in _sadd(ar, br) for i in _sadd(ai, bi)))
    if a < 9:
        a, b = b, a
    if b < 9:
        bi = _fin(b)[1]
        if a in (PI, NI):
            # oo + r = oo for a finite real r; oo + (r + s*I) with s != 0
            # is an infinity off the real axis (``oo + I``)
            return 1 << (a if bi == 0 else IN)
        # IN + r: a real r keeps the imaginary part (``oo + I + 1``) or
        # the undirected ``zoo``; a non-real one may cancel it
        # (``(oo + I) - I = oo``)
        return 1 << IN if bi == 0 else _b(PI, NI, IN)
    if a == b and a != IN:
        return 1 << a                       # oo + oo, -oo - oo
    return NANB                             # oo - oo, zoo + zoo, oo + zoo, ...


def _mul_atoms(a: int, b: int) -> int:
    if a < 9 and b < 9:
        (ar, ai), (br, bi) = _fin(a), _fin(b)
        m = _b(*(F(r, i) for r in _sadd(ar * br, -(ai * bi))
                 for i in _sadd(ar * bi, ai * br)))
        if a != ZERO and b != ZERO:
            m &= ~(1 << ZERO)               # the complex numbers are a field
        return m
    if a < 9:
        a, b = b, a
    if b < 9:
        if b == ZERO:
            return NANB                     # 0*oo, 0*zoo
        br, bi = _fin(b)
        if a in (PI, NI):
            if bi:
                return 1 << IN              # oo*I, oo*(1 + I)
            return 1 << (PI if (br > 0) == (a == PI) else NI)
        # zoo*r = zoo and (oo + I)*r = r*oo + r*I for a nonzero real r;
        # a non-real factor of an infinity off the axis is not tracked
        return 1 << IN if bi == 0 else NANB
    if a in (PI, NI) and b in (PI, NI):
        return 1 << (PI if a == b else NI)
    return NANB                             # IN times an infinity: not tracked


ADD, MUL = 0, 1
_ATOM_OPS = (_add_atoms, _mul_atoms)
_MEMO: Dict[Tuple[int, int, int], int] = {}     # a pure function of its key
_adopt_memo(__name__, "_MEMO")


def mop(op: int, ma: int, mb: int) -> int:
    """The atom set of ``a op b`` for ``a`` in ``ma`` and ``b`` in ``mb``."""
    key = (op, ma, mb) if ma <= mb else (op, mb, ma)
    r = _MEMO.get(key)
    if r is None:
        r = NANB if (ma | mb) & NANB else 0
        ma &= ALL
        mb &= ALL
        f = _ATOM_OPS[op]
        for a in range(12):
            if ma >> a & 1:
                for b in range(12):
                    if mb >> b & 1:
                        r |= f(a, b)
        _MEMO[key] = r
    return r


def fold(op: int, masks) -> int:
    it = iter(masks)
    r = next(it)
    for m in it:
        r = mop(op, r, m)
    return r


def node_masks(op: int, nmask: int, amasks: List[int]) -> Tuple[int, List[int]]:
    """One round of propagation over ``N = op(A1, ..., An)``: the new set
    of the node and of each argument (an empty set is a conflict)."""
    n = len(amasks)
    pre: list = [None] * n
    acc = None
    for i in range(n):
        pre[i] = acc
        acc = amasks[i] if acc is None else mop(op, acc, amasks[i])
    total = acc
    newn = nmask if total & NANB else nmask & total
    out = list(amasks)
    if newn & ALL == ALL or n < 2:
        return newn, out
    suf = None
    for i in range(n - 1, -1, -1):
        p = pre[i]
        rest = p if suf is None else (suf if p is None else mop(op, p, suf))
        m = amasks[i]
        suf = m if suf is None else mop(op, suf, m)
        if rest & NANB:
            continue
        keep = 0
        for c in range(12):
            if m >> c & 1:
                r = mop(op, 1 << c, rest)
                if r & NANB or r & newn:
                    keep |= 1 << c
        out[i] = keep
    return newn, out


class SignTheory:
    """The theory (contract: :mod:`satassume.sat.theory`)."""

    gave_up = False

    def __init__(self):
        self.tvars: List[List[int]] = []     # term -> its variables by PREDS (0: none)
        self.fixed: List[int] = []           # term -> atom set known from its value
        self.tnodes: List[List[int]] = []    # term -> the nodes it takes part in
        self.nodes: List[Tuple[int, int, Tuple[int, ...]]] = []   # (op, node, args)
        self.atom: Dict[int, Tuple[int, int]] = {}   # variable -> (term, pred)
        self.val: Dict[int, bool] = {}
        self.trail: List[int] = []
        self.lim: List[int] = []
        self.dirty: set = set()
        self.stats = {"props": 0, "conflicts": 0}

    # -- structure (told by the adapter) ----------------------------------
    def term(self, fixed: int = ALL) -> int:
        self.tvars.append([0] * len(PREDS))
        self.fixed.append(fixed)
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
        t, p = payload
        self.tvars[t][p] = v
        self.atom[v] = (t, p)
        self.dirty.update(self.tnodes[t])

    def assert_lit(self, lit: int):
        v = lit if lit > 0 else -lit
        a = self.atom.get(v)
        if a is None or v in self.val:
            return None
        self.val[v] = lit > 0
        self.trail.append(v)
        self.dirty.update(self.tnodes[a[0]])
        return None

    def push_level(self) -> None:
        self.lim.append(len(self.trail))

    def pop_level(self) -> None:
        k = self.lim.pop()
        trail, val = self.trail, self.val
        while len(trail) > k:
            del val[trail.pop()]
        # sets only widen on backtrack: no propagation is owed

    # -- propagation ----------------------------------------------------------
    def _lits(self, t: int) -> List[int]:
        val = self.val
        return [v if val[v] else -v for v in self.tvars[t] if v and v in val]

    def _mask(self, t: int, lits) -> int:
        m = self.fixed[t]
        atom = self.atom
        for l in lits:
            pm = PRED_MASK[atom[l if l > 0 else -l][1]]
            m &= pm if l > 0 else ~pm
        return m

    def _round(self, i: int, lits: Dict[int, List[int]]):
        op, t, args = self.nodes[i]
        return node_masks(op, self._mask(t, lits[t]), [self._mask(u, lits[u]) for u in args])

    def _why(self, i: int, lits, j: int, test) -> List[int]:
        """A subset of the literals ``lits`` (term -> literals) of node
        ``i`` under which ``test`` still holds of the new set of slot ``j``
        (0 the node, ``k + 1`` argument ``k``); greedy deletion."""
        keep = {u: list(ls) for u, ls in lits.items()}
        for u in list(keep):
            for l in list(keep[u]):
                keep[u].remove(l)
                nn, na = self._round(i, keep)
                if not test(nn if j == 0 else na[j - 1]):
                    keep[u].append(l)
        return [l for ls in keep.values() for l in ls]

    def _node(self, i: int, out: list, seen: set) -> bool:
        """Propagate node ``i`` into ``out``; False after a conflict."""
        op, t, args = self.nodes[i]
        lits = {u: self._lits(u) for u in (t, *args)}
        newn, newa = self._round(i, lits)
        val = self.val
        for j, u in enumerate((t, *args)):
            m = newn if j == 0 else newa[j - 1]
            if not m:
                why = self._why(i, lits, j, lambda s: not s)
                if not why:
                    continue                # (only constants: not a claim)
                self.stats["conflicts"] += 1
                c = [-l for l in why]
                out.append((c[0], c))
                return False
            if m & NANB:
                continue
            for p, v in enumerate(self.tvars[u]):
                if not v:
                    continue
                pm = PRED_MASK[p]
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
                why = self._why(i, lits, j, test)
                seen.add(lit)
                self.stats["props"] += 1
                out.append((lit, [lit] + [-l for l in why if l != -lit]))
                if cur is not None:
                    return False            # the literal is false: a conflict
        return True

    def propagate(self):
        if not self.dirty:
            return ()
        out: list = []
        seen: set = set()
        dirty, self.dirty = self.dirty, set()
        for i in sorted(dirty):
            if not self._node(i, out, seen):
                self.dirty |= dirty
                break
        return out

    def check(self):
        self.dirty = set(range(len(self.nodes)))
        for lit, why in self.propagate():
            v = lit if lit > 0 else -lit
            if v in self.val and self.val[v] != (lit > 0):
                return (False, why)
        return None
