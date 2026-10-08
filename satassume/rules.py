"""The unified single-node rule base, over a basis of predicates.

SymPy currently keeps two copies of essentially the same knowledge: the string
rules in ``sympy/core/assumptions.py`` (old system, compiled by ``FactRules``)
and the ``Q``-predicate facts in ``sympy/assumptions/facts.py`` (new system).
This module keeps ONE rule base, compiled once into clause *patterns* over
predicate indices.  A pattern is instantiated for every expression node the
engine visits, so every node gets the full closure (integer -> rational ->
real -> complex ...).

The vocabulary (``PREDICATES``, what a query may mention) is wider than what
is encoded: a node gets one solver variable per *basis* predicate
(``BASIS``), and every other predicate of the vocabulary is *derived*: a
conjunction or a disjunction of basis literals (``DEFINITIONS``), exactly
equivalent to it under SymPy's rule base.  ``real`` is ``extended_real &
finite``, ``positive`` is ``extended_positive & finite``, ``odd`` is
``integer & !even``, ...  A derived predicate never reaches the solver: a
literal of one is rewritten into basis literals wherever a clause is formed
(:func:`cnf_of`), and a query about one is decided through a definitional
variable (``Session.var``).  The rules (``RULES``) are stated over the
basis; ``tests/test_rules.py`` checks that, under the definitions, their
models are exactly those of SymPy's rule base over the whole vocabulary.

Grammar (one rule per string)::

    a -> b            a implies b
    a & b -> c | d    conjunction implies disjunction
    a == b & c        a is equivalent to the conjunction
    a == b | c        a is equivalent to the disjunction
    !a                negation of a (allowed anywhere)

The rule base holds for scalar expressions only (``hermitian`` is ``real``,
``antihermitian`` is ``zero | imaginary``: a number equals its conjugate iff
it is real, minus its conjugate iff it is zero or imaginary).
"""
from __future__ import annotations

from typing import Dict, List, Sequence, Tuple
from .memos import PROCESS as _PROCESS

# The predicate vocabulary.  This is the union of the old system's
# ``_assume_defined`` and the unary, scalar predicates of the new system.
PREDICATES: Tuple[str, ...] = (
    'algebraic', 'antihermitian', 'commutative', 'complex', 'composite',
    'even', 'extended_negative', 'extended_nonnegative',
    'extended_nonpositive', 'extended_nonzero', 'extended_positive',
    'extended_real', 'finite', 'hermitian', 'imaginary', 'infinite',
    'integer', 'irrational', 'negative', 'negative_infinite', 'noninteger',
    'nonnegative', 'nonpositive', 'nonzero', 'odd', 'polar', 'positive',
    'positive_infinite', 'prime', 'rational', 'real', 'transcendental',
    'zero',
)
#: vocabulary index: membership says whether a predicate is in scope
PRED_INDEX: Dict[str, int] = {p: i for i, p in enumerate(PREDICATES)}

#: The encoded predicates: one solver variable per node for each.
BASIS: Tuple[str, ...] = (
    'algebraic', 'complex', 'composite', 'even', 'extended_negative', 'extended_positive', 'extended_real', 'finite',
    'imaginary', 'integer', 'polar', 'prime', 'rational', 'zero',
)
BASIS_INDEX: Dict[str, int] = {p: i for i, p in enumerate(BASIS)}
NPRED = len(BASIS)

#: Every other predicate of the vocabulary as a conjunction (``&``) or a
#: disjunction (``|``) of basis literals.
DEFINITIONS: Dict[str, str] = {
    'real':                 'extended_real & finite',
    'hermitian':            'extended_real & finite',
    'infinite':             '!finite',
    'positive':             'extended_positive & finite',
    'negative':             'extended_negative & finite',
    'nonnegative':          'extended_real & finite & !extended_negative',
    'nonpositive':          'extended_real & finite & !extended_positive',
    'nonzero':              'extended_real & finite & !zero',
    'extended_nonnegative': 'extended_real & !extended_negative',
    'extended_nonpositive': 'extended_real & !extended_positive',
    'extended_nonzero':     'extended_real & !zero',
    'positive_infinite':    'extended_positive & !finite',
    'negative_infinite':    'extended_negative & !finite',
    'odd':                  'integer & !even',
    'irrational':           'extended_real & finite & !rational',
    'noninteger':           'extended_real & !integer',
    'transcendental':       'complex & !algebraic',
    'antihermitian':        'zero | imaginary',
    # every term in scope is commutative: SymPy's commutativity is fixed by
    # construction, and an argument with a non-commutative subterm is out
    # of scope (``sympy_api``, category "matrix"), so ``commutative`` is the
    # empty conjunction (true) and needs no variable, rule or template
    'commutative':          '',
}
assert set(DEFINITIONS).isdisjoint(BASIS) and set(DEFINITIONS) | set(BASIS) == set(PREDICATES)

# The rule base over the basis.  Under the definitions its models are
# exactly those of SymPy's rules over the whole vocabulary (the old
# system's ``sympy/core/assumptions.py`` plus ``sympy/assumptions/facts.py``).
RULES: Tuple[str, ...] = (
    'integer        ->  rational',
    'rational       ->  extended_real',
    'rational       ->  algebraic',
    'algebraic      ->  complex',
    'complex        ->  finite',
    'extended_real & finite -> complex',
    'extended_real  ==  extended_negative | zero | extended_positive',
    'extended_negative -> !zero',
    'extended_negative -> !extended_positive',
    'zero           ->  !extended_positive',
    'zero           ->  even',
    'zero           ->  finite',
    'even           ->  integer',
    'prime          ->  integer',
    'prime          ->  extended_positive',
    'composite      ->  integer',
    'composite      ->  extended_positive',
    'composite      ->  !prime',
    'even & extended_positive & !prime -> composite',
    'imaginary      ->  complex',
    'imaginary      ->  !extended_real',
)

Clause = Tuple[int, ...]   # signed predicate indices, 1-based like DIMACS


def _lit(tok: str, index: Dict[str, int] = BASIS_INDEX) -> int:
    tok = tok.strip()
    neg = tok.startswith('!')
    name = tok[1:].strip() if neg else tok
    if name not in index:
        raise ValueError(f"unknown predicate {name!r}")
    v = index[name] + 1
    return -v if neg else v


def _side(s: str, index=BASIS_INDEX) -> Tuple[str, List[int]]:
    if not s.strip():
        return '&', []                    # the empty conjunction: true
    if '&' in s and '|' in s:
        raise ValueError(f"mixed & and | in {s!r}")
    if '|' in s:
        return '|', [_lit(t, index) for t in s.split('|')]
    return '&', [_lit(t, index) for t in s.split('&')]


def compile_rule(rule: str, index: Dict[str, int] = BASIS_INDEX) -> List[Clause]:
    """Compile one rule string to clauses over signed predicate indices
    (1-based positions in ``index``)."""
    if '==' in rule:
        lhs, rhs = rule.split('==')
        a = _lit(lhs, index)
        op, lits = _side(rhs, index)
        if op == '&':
            # a <-> (b & c): (~a | b), (~a | c), (a | ~b | ~c)
            return [(-a, l) for l in lits] + [tuple([a] + [-l for l in lits])]
        # a <-> (b | c): (~a | b | c), (a | ~b), (a | ~c)
        return [tuple([-a] + lits)] + [(a, -l) for l in lits]
    if '->' in rule:
        lhs, rhs = rule.split('->')
        lop, llits = _side(lhs, index)
        rop, rlits = _side(rhs, index)
        if lop == '|' and len(llits) > 1:
            raise ValueError(f"disjunctive antecedent unsupported: {rule!r}")
        if rop == '&' and len(rlits) > 1:
            return [tuple([-l for l in llits] + [r]) for r in rlits]
        return [tuple([-l for l in llits] + rlits)]
    raise ValueError(f"cannot parse rule {rule!r}")


def compile_rules(rules: Sequence[str] = RULES, index: Dict[str, int] = BASIS_INDEX) -> List[Clause]:
    out: List[Clause] = []
    for r in rules:
        out.extend(compile_rule(r, index))
    return out


RULE_CLAUSES: Tuple[Clause, ...] = tuple(compile_rules())

#: derived predicate -> ``(op, lits)``: ``op`` is ``'&'`` or ``'|'`` and
#: ``lits`` the signed 1-based basis indices of the definition
DEF_LITS: Dict[str, Tuple[str, Tuple[int, ...]]] = {
    p: (lambda s: (s[0], tuple(s[1])))(_side(d)) for p, d in DEFINITIONS.items()}

#: predicate name -> its CNF as a positive literal, as a tuple of clauses
#: over signed 1-based basis indices; the negation is :func:`cnf_of`
_CNF_POS: Dict[str, Tuple[Clause, ...]] = {}
_CNF_NEG: Dict[str, Tuple[Clause, ...]] = {}
for _p in PREDICATES:
    if _p in BASIS_INDEX:
        _CNF_POS[_p] = ((BASIS_INDEX[_p] + 1,),)
        _CNF_NEG[_p] = ((-(BASIS_INDEX[_p] + 1),),)
    else:
        _op, _ls = DEF_LITS[_p]
        if _op == '&':
            _CNF_POS[_p] = tuple((l,) for l in _ls)
            _CNF_NEG[_p] = (tuple(-l for l in _ls),)
        else:
            _CNF_POS[_p] = (tuple(_ls),)
            _CNF_NEG[_p] = tuple((-l,) for l in _ls)
del _p, _op, _ls


def cnf_of(pred: str, pos: bool = True) -> Tuple[Clause, ...]:
    """The literal ``pred`` (negated if not ``pos``) as a conjunction of
    clauses over signed 1-based basis indices: one unit clause for a basis
    predicate; the definition's literals for a derived one."""
    return _CNF_POS[pred] if pos else _CNF_NEG[pred]


#: predicate name -> the 0-based basis indices it reads
BASIS_OF: Dict[str, frozenset] = {
    p: frozenset(abs(l) - 1 for c in _CNF_POS[p] for l in c) for p in PREDICATES}


def basis_lits(pred: str, pos: bool = True) -> Tuple[str, Tuple[int, ...]]:
    """``(op, lits)``: the literal ``pred`` as ``op`` (``'&'`` or ``'|'``)
    of signed 1-based basis indices (a basis literal: ``('&', (l,))``)."""
    if pred in BASIS_INDEX:
        v = BASIS_INDEX[pred] + 1
        return '&', ((v if pos else -v),)
    op, ls = DEF_LITS[pred]
    if pos:
        return op, ls
    return ('|' if op == '&' else '&'), tuple(-l for l in ls)


def _basis_models() -> Tuple[Tuple[bool, ...], ...]:
    """The models of the rule base (:data:`RULE_CLAUSES`) over the basis,
    each a tuple of NPRED truth values."""
    last: List[List[Clause]] = [[] for _ in range(NPRED)]   # clauses by largest index
    for c in RULE_CLAUSES:
        last[max(abs(l) for l in c) - 1].append(c)
    out = []
    a = [False] * NPRED

    def dfs(i):
        if i == NPRED:
            out.append(tuple(a))
            return
        for v in (False, True):
            a[i] = v
            if all(any(a[l - 1] if l > 0 else not a[-l - 1] for l in c) for c in last[i]):
                dfs(i + 1)
    dfs(0)
    return tuple(out)


_DEF_IMPL = _PROCESS.table("satassume.rules._DEF_IMPL", "pure", 10_000)


def def_implications(d1, d2) -> Tuple[Tuple[int, int], ...]:
    """For two definitions of several basis literals (``(op, lits)`` as in
    :data:`DEF_LITS`): the binary clauses ``s1*v1 | s2*v2`` over variables
    ``v1 <-> d1``, ``v2 <-> d2`` that every model of the rule base satisfies,
    as sign pairs (``positive -> nonnegative`` is ``((-1, 1),)``); used by
    ``engine.Session.dvar``.  Memoized (the models too, under ``None``)."""
    r = _DEF_IMPL.get((d1, d2))
    if r is not None:
        return r
    models = _DEF_IMPL.get(None)
    if models is None:
        models = _basis_models()
        _DEF_IMPL.put(None, models)

    def val(d, m):
        t = [m[l - 1] if l > 0 else not m[-l - 1] for l in d[1]]
        return all(t) if d[0] == '&' else any(t)
    vals = {(val(d1, m), val(d2, m)) for m in models}
    # the clause s1*v1 | s2*v2 fails exactly on v1 == (s1 < 0), v2 == (s2 < 0);
    # kept if no model does that and neither literal is constant
    r = tuple((s1, s2) for s1 in (1, -1) for s2 in (1, -1)
              if (s1 < 0, s2 < 0) not in vals and any(v1 == (s1 < 0) for v1, _ in vals)
              and any(v2 == (s2 < 0) for _, v2 in vals))
    _DEF_IMPL.put((d1, d2), r)
    return r


def expand_clause(lits: Sequence[Tuple[int, str, bool]]) -> List[Tuple[Tuple[int, int, bool], ...]]:
    """Expand a clause of ``(slot, pred, pos)`` literals over the vocabulary
    into clauses of ``(slot, basis index, pos)`` literals (0-based index):
    the product of the CNFs of its literals, tautologies dropped, duplicate
    literals merged."""
    out: List[Tuple[Tuple[int, int, bool], ...]] = [()]
    for k, pred, pos in lits:
        cnf = cnf_of(pred, pos)
        if len(cnf) == 1:
            ext = tuple((k, abs(l) - 1, l > 0) for l in cnf[0])
            out = [c + ext for c in out]
        else:
            out = [c + tuple((k, abs(l) - 1, l > 0) for l in cl) for c in out for cl in cnf]
    res = []
    seen = set()
    for c in out:
        c = tuple(dict.fromkeys(c))
        cs = set(c)
        if any((k, i, not p) in cs for k, i, p in c):
            continue
        key = frozenset(c)
        if key in seen:
            continue
        seen.add(key)
        res.append(c)
    return res


#: clause tuple (by id, kept alive) -> its clause masks (:func:`_masks`)
_MASKS: dict = {}


def lit_bit(l: int) -> int:
    """The bit of the signed literal ``l`` in a literal mask: ``2*(|l| -
    1)`` for a positive literal, one more for a negative one."""
    return 2 * (l - 1) if l > 0 else 2 * (-l - 1) + 1


def lits_mask(lits: Sequence[int]) -> int:
    """The mask of the signed literals ``lits``."""
    m = 0
    for l in lits:
        m |= 1 << lit_bit(l)
    return m


def mask_lits(m: int) -> set:
    """The signed literals of the mask ``m``."""
    out = set()
    while m:
        low = m & -m
        m ^= low
        b = low.bit_length() - 1
        out.add(-(b >> 1) - 1 if b & 1 else (b >> 1) + 1)
    return out


def _masks(clauses: Sequence[Clause]) -> Tuple[Tuple[int, ...], int]:
    """``(masks, even)``: each clause as the mask of its literals, and the
    mask of the positive literal of every variable the clauses mention.
    Memoized for a tuple of clauses (the rule base, ``RULE_INSTANTIATED``);
    any other sequence is converted again on every call, so a caller that
    propagates over the same clauses repeatedly passes them as a tuple."""
    key = id(clauses)
    hit = _MASKS.get(key)
    if hit is not None and hit[0] is clauses:
        return hit[1]
    masks = []
    top = 0
    for c in clauses:
        m = 0
        for l in c:
            m |= 1 << lit_bit(l)
            if abs(l) > top:
                top = abs(l)
        masks.append(m)
    r = (tuple(masks), (4 ** top - 1) // 3)
    if type(clauses) is tuple:
        if len(_MASKS) >= 64:
            _MASKS.clear()
        _MASKS[key] = (clauses, r)
    return r


def closure_mask(clauses: Sequence[Clause], a: int) -> int:
    """The unit-propagation fixpoint of the literal mask ``a`` under
    ``clauses``, as a mask, or -1 on a conflict.  ``sw`` is ``a`` with
    every literal replaced by its complement, so ``m & ~sw`` are the
    unassigned literals of a clause none of whose literals is true."""
    masks, even = _masks(clauses)
    nvars = (a.bit_length() + 1) // 2          # variables ``a`` reaches
    if nvars > (even.bit_length() + 1) // 2:
        even = (4 ** nvars - 1) // 3
    sw = ((a & even) << 1) | ((a >> 1) & even)
    if a & sw:
        return -1
    changed = True
    while changed:
        changed = False
        for m in masks:
            if a & m:
                continue
            free = m & ~sw
            if not free:
                return -1
            if not free & (free - 1):
                a |= free
                sw |= free << 1 if free & even else free >> 1
                changed = True
    return a


def unit_propagate(clauses: Sequence[Clause], assumptions: Sequence[int]):
    """Unit propagation to a fixpoint over signed-integer clauses; returns
    the set of derived literals (including ``assumptions``) or None on a
    conflict (:func:`closure_mask` over literal masks; ``clauses`` as a
    tuple reuses its masks, see :func:`_masks`)."""
    r = closure_mask(clauses, lits_mask(assumptions))
    return None if r < 0 else mask_lits(r)


def minimize_for_propagation(clauses: Sequence[Clause]) -> Tuple[Clause, ...]:
    """Drop clauses that unit propagation never needs: ``C`` is dropped if,
    for every literal ``l`` of ``C``, falsifying the other literals of ``C``
    makes the remaining clauses derive ``l`` (or a conflict) by unit
    propagation alone.  Whenever ``C`` would propagate, the rest propagates
    the same literal, so every level-0 fact and every search behaviour that
    depends on unit propagation is unchanged; the models are unchanged too.
    """
    kept = list(dict.fromkeys(tuple(sorted(c)) for c in clauses))   # exact duplicates
    i = 0
    while i < len(kept):
        c = kept[i]
        rest = kept[:i] + kept[i + 1:]
        for l in c:
            derived = unit_propagate(rest, [-m for m in c if m != l])
            if derived is not None and l not in derived:
                break
        else:
            kept = rest
            continue
        i += 1
    return tuple(kept)


#: The clauses the engine instantiates per node: the rule base minus the
#: clauses unit propagation never needs (same models, same propagation).
RULE_INSTANTIATED: Tuple[Clause, ...] = minimize_for_propagation(RULE_CLAUSES)

# The same clauses in the solver's internal literal encoding relative to a
# node's base variable ``b``: internal literal = 2*(b + i) + neg = 2*b + const.
RULE_INTERNAL: Tuple[Tuple[int, ...], ...] = tuple(
    tuple(2 * (abs(l) - 1) + (1 if l < 0 else 0) for l in c) for c in RULE_INSTANTIATED)
#: Basis predicates no instantiated rule clause mentions (``polar``).
RULE_FREE: frozenset = frozenset(range(NPRED)) - {abs(l) - 1 for c in RULE_INSTANTIATED for l in c}


def instantiate(var_of_pred) -> List[List[int]]:
    """Instantiate the rule clauses for one node.

    ``var_of_pred(i)`` maps a 0-based basis index to a solver variable.
    """
    vars_ = [var_of_pred(i) for i in range(NPRED)]
    return [[(vars_[abs(l) - 1] if l > 0 else -vars_[abs(l) - 1]) for l in c]
            for c in RULE_CLAUSES]


# ----------------------------------------------------------------------
# Side predicates: instantiated per node only when a node needs them.
# ----------------------------------------------------------------------
#: Basis predicates whose rule clauses leave the per-node rule block.  A
#: node's side variable that nothing mentions or fixes is constrained only
#: by its own rule clauses, which some value of it always satisfies
#: (prime := even & extended_positive & !composite, composite := even &
#: extended_positive & !prime, imaginary := false), so those clauses only
#: matter once the variable is touched (see Solver.set_rule_block).
SIDE: Tuple[str, ...] = ('prime', 'composite', 'imaginary')
_SIDE_IDX = frozenset(BASIS_INDEX[p] for p in SIDE)


def _side_of(c: Clause) -> frozenset:
    return frozenset(abs(l) - 1 for l in c if abs(l) - 1 in _SIDE_IDX)


def _internal(c: Clause) -> Tuple[int, ...]:
    return tuple(2 * (abs(l) - 1) + (1 if l < 0 else 0) for l in c)


#: The rule clauses kept in the per-node block (no side predicate).
RULE_CORE: Tuple[Clause, ...] = tuple(c for c in RULE_INSTANTIATED if not _side_of(c))
#: ``(side indices, clauses)``: the clauses mentioning exactly those side
#: predicates, instantiated for a node once all of them are touched.  The
#: groups together with ``RULE_CORE`` are ``RULE_INSTANTIATED``; for every
#: set T of touched side predicates, the core plus the groups within T has
#: the same models as the full rules with the side variables outside T
#: projected away (tests/test_side_preds.py).
SIDE_GROUPS: Tuple[Tuple[frozenset, Tuple[Clause, ...]], ...] = tuple(
    (s, tuple(c for c in RULE_INSTANTIATED if _side_of(c) == s))
    for s in sorted({_side_of(c) for c in RULE_INSTANTIATED if _side_of(c)},
                    key=lambda s: (len(s), sorted(s))))
RULE_CORE_INTERNAL: Tuple[Tuple[int, ...], ...] = tuple(_internal(c) for c in RULE_CORE)
#: The side groups as :meth:`Solver.set_rule_block` takes them: ``(variable
#: mask, clauses)``, bit i of the mask for basis index i, the clauses in the
#: block-relative internal encoding.
SIDE_INTERNAL: Tuple[Tuple[int, Tuple[Tuple[int, ...], ...]], ...] = tuple(
    (sum(1 << i for i in s), tuple(_internal(c) for c in cls)) for s, cls in SIDE_GROUPS)
