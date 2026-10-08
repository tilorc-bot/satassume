"""The unified single-node rule base.

SymPy currently keeps two copies of essentially the same knowledge: the string
rules in ``sympy/core/assumptions.py`` (old system, compiled by ``FactRules``)
and the ``Q``-predicate facts in ``sympy/assumptions/facts.py`` (new system).
This module keeps ONE list, in the old system's compact string syntax, and
compiles it once into clause *patterns* over predicate indices.  A pattern is
instantiated for every expression node the engine visits, so every node gets
the full closure (integer -> rational -> real -> complex ...).

Grammar (one rule per string)::

    a -> b            a implies b
    a & b -> c | d    conjunction implies disjunction
    a == b & c        a is equivalent to the conjunction
    a == b | c        a is equivalent to the disjunction
    !a                negation of a (allowed anywhere)

Rules that hold only for scalar expressions are grouped separately from the
few that also hold for matrices, so the engine can instantiate the right set.
"""
from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

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
PRED_INDEX: Dict[str, int] = {p: i for i, p in enumerate(PREDICATES)}

# Copied from sympy/core/assumptions.py (BSD licensed) and extended with the
# predicates that only the new system knows about.
RULES: Tuple[str, ...] = (
    'integer        ->  rational',
    'rational       ->  real',
    'rational       ->  algebraic',
    'algebraic      ->  complex',
    'transcendental ==  complex & !algebraic',
    'imaginary      ->  complex',
    'extended_real  ->  commutative',
    'complex        ->  commutative',
    'complex        ->  finite',
    'odd            ==  integer & !even',
    'even           ==  integer & !odd',
    'real           ->  complex',
    'extended_real  ->  real | infinite',
    'real           ==  extended_real & finite',
    'extended_real        ==  extended_negative | zero | extended_positive',
    'extended_negative    ==  extended_nonpositive & extended_nonzero',
    'extended_positive    ==  extended_nonnegative & extended_nonzero',
    'extended_nonpositive ==  extended_real & !extended_positive',
    'extended_nonnegative ==  extended_real & !extended_negative',
    'real           ==  negative | zero | positive',
    'negative       ==  nonpositive & nonzero',
    'positive       ==  nonnegative & nonzero',
    'nonpositive    ==  real & !positive',
    'nonnegative    ==  real & !negative',
    'positive       ==  extended_positive & finite',
    'negative       ==  extended_negative & finite',
    'nonpositive    ==  extended_nonpositive & finite',
    'nonnegative    ==  extended_nonnegative & finite',
    'nonzero        ==  extended_nonzero & finite',
    'zero           ->  even & finite',
    'zero           ==  extended_nonnegative & extended_nonpositive',
    'zero           ==  nonnegative & nonpositive',
    'nonzero        ->  real',
    'prime          ->  integer & positive',
    'composite      ->  integer & positive & !prime',
    '!composite     ->  !positive | !even | prime',
    'irrational     ==  real & !rational',
    'imaginary      ->  !extended_real',
    'infinite       ==  !finite',
    'noninteger     ==  extended_real & !integer',
    'extended_nonzero == extended_real & !zero',
    # --- new-system predicates (sympy/assumptions/facts.py) ---
    'positive_infinite == extended_positive & infinite',
    'negative_infinite == extended_negative & infinite',
    'real           ->  hermitian',
    'imaginary      ->  antihermitian',
    'zero           ->  hermitian | antihermitian',
    # For scalars the new system's generic handlers define ``hermitian`` as
    # ``real`` (a number equals its conjugate iff it is real) and
    # ``antihermitian`` as ``zero | imaginary`` (a number equals minus its
    # conjugate iff it is zero or imaginary); the three rules above are the
    # weaker statements SymPy's fact base keeps for matrices.  This rule base
    # is only instantiated for scalar nodes.
    'hermitian      ==  real',
    'antihermitian  ==  zero | imaginary',
)

Clause = Tuple[int, ...]   # signed predicate indices, 1-based like DIMACS


def _lit(tok: str) -> int:
    tok = tok.strip()
    neg = tok.startswith('!')
    name = tok[1:].strip() if neg else tok
    if name not in PRED_INDEX:
        raise ValueError(f"unknown predicate {name!r}")
    v = PRED_INDEX[name] + 1
    return -v if neg else v


def _side(s: str) -> Tuple[str, List[int]]:
    if '&' in s and '|' in s:
        raise ValueError(f"mixed & and | in {s!r}")
    if '|' in s:
        return '|', [_lit(t) for t in s.split('|')]
    return '&', [_lit(t) for t in s.split('&')]


def compile_rule(rule: str) -> List[Clause]:
    """Compile one rule string to clauses over signed predicate indices."""
    if '==' in rule:
        lhs, rhs = rule.split('==')
        a = _lit(lhs)
        op, lits = _side(rhs)
        if op == '&':
            # a <-> (b & c): (~a | b), (~a | c), (a | ~b | ~c)
            return [(-a, l) for l in lits] + [tuple([a] + [-l for l in lits])]
        # a <-> (b | c): (~a | b | c), (a | ~b), (a | ~c)
        return [tuple([-a] + lits)] + [(a, -l) for l in lits]
    if '->' in rule:
        lhs, rhs = rule.split('->')
        lop, llits = _side(lhs)
        rop, rlits = _side(rhs)
        if lop == '|' and len(llits) > 1:
            raise ValueError(f"disjunctive antecedent unsupported: {rule!r}")
        if rop == '&' and len(rlits) > 1:
            return [tuple([-l for l in llits] + [r]) for r in rlits]
        return [tuple([-l for l in llits] + rlits)]
    raise ValueError(f"cannot parse rule {rule!r}")


def compile_rules(rules: Sequence[str] = RULES) -> List[Clause]:
    out: List[Clause] = []
    for r in rules:
        out.extend(compile_rule(r))
    return out


RULE_CLAUSES: Tuple[Clause, ...] = tuple(compile_rules())
NPRED = len(PREDICATES)


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
#: Predicates no instantiated rule clause mentions (``polar``).
RULE_FREE: frozenset = frozenset(range(NPRED)) - {abs(l) - 1 for c in RULE_INSTANTIATED for l in c}


def instantiate(var_of_pred) -> List[List[int]]:
    """Instantiate the rule clauses for one node.

    ``var_of_pred(i)`` maps a 0-based predicate index to a solver variable.
    """
    vars_ = [var_of_pred(i) for i in range(NPRED)]
    return [[(vars_[abs(l) - 1] if l > 0 else -vars_[abs(l) - 1]) for l in c]
            for c in RULE_CLAUSES]
