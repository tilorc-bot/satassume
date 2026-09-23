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

# The same clauses in the solver's internal literal encoding relative to a
# node's base variable ``b``: internal literal = 2*(b + i) + neg = 2*b + const.
RULE_INTERNAL: Tuple[Tuple[int, ...], ...] = tuple(
    tuple(2 * (abs(l) - 1) + (1 if l < 0 else 0) for l in c) for c in RULE_CLAUSES)


def instantiate(var_of_pred) -> List[List[int]]:
    """Instantiate the rule clauses for one node.

    ``var_of_pred(i)`` maps a 0-based predicate index to a solver variable.
    """
    vars_ = [var_of_pred(i) for i in range(NPRED)]
    return [[(vars_[abs(l) - 1] if l > 0 else -vars_[abs(l) - 1]) for l in c]
            for c in RULE_CLAUSES]
