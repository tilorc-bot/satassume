"""Exact closure of a set of predicate literals under the unary rule base.

Stage 0 of the fact-lattice plan (``2026-09-25-fact-lattice-theory-plan.md``,
section 2.1): for an asserted set ``S`` over the 33 predicates of
``satassume.rules``, the *exact* closure is every literal ``l`` with
``S & RULES |= l``; ``None`` if ``S`` is inconsistent with the rules.  This
is stronger than unit propagation over ``RULE_INSTANTIATED`` (the engine's
rule block) because three rules are non-Horn.  Used by the stage 0 scripts
as an oracle; memoized per ``S``.

Literals are signed 1-based predicate indices, as in ``rules.RULE_CLAUSES``.
"""
from satassume.rules import NPRED, RULE_CLAUSES, RULE_INSTANTIATED, unit_propagate

_CL = tuple(RULE_CLAUSES)


def _up(clauses, assigned):
    """Unit propagation in place over ``assigned`` (a set); False on conflict."""
    changed = True
    while changed:
        changed = False
        for c in clauses:
            free = None
            nfree = 0
            for l in c:
                if l in assigned:
                    break
                if -l not in assigned:
                    nfree += 1
                    free = l
            else:
                if nfree == 0:
                    return False
                if nfree == 1:
                    assigned.add(free)
                    changed = True
    return True


def _model(assigned):
    """A total model extending ``assigned`` (a set of literals), or None."""
    a = set(assigned)
    if not _up(_CL, a):
        return None
    for v in range(1, NPRED + 1):
        if v not in a and -v not in a:
            for l in (-v, v):
                m = _model(a | {l})
                if m is not None:
                    return m
            return None
    return a


_MEMO: dict = {}


def closure(lits):
    """Frozenset of every literal entailed by ``lits`` under the rules
    (including ``lits``), or None if inconsistent."""
    key = frozenset(lits)
    r = _MEMO.get(key, 0)
    if r != 0:
        return r
    if any(-l in key for l in key):
        _MEMO[key] = None
        return None
    m = _model(key)
    if m is None:
        _MEMO[key] = None
        return None
    fixed = set(key)
    up = set(key)
    _up(_CL, up)
    fixed |= up
    # candidates: literals true in every model found so far
    cand = [(v if v in m else -v) for v in range(1, NPRED + 1)
            if v not in fixed and -v not in fixed]
    while cand:
        l = cand.pop()
        m2 = _model(key | {-l})
        if m2 is None:
            fixed.add(l)
        else:
            cand = [x for x in cand if x in m2]
    r = frozenset(fixed)
    _MEMO[key] = r
    return r


def up_closure(lits):
    """Unit propagation over the engine's rule block (``RULE_INSTANTIATED``)."""
    return unit_propagate(RULE_INSTANTIATED, list(lits))


def memo_size():
    return len(_MEMO)
