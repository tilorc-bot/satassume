import random
from satassume.rules import RULES, RULE_CLAUSES, PREDICATES, PRED_INDEX, compile_rule


def test_every_rule_compiles():
    for r in RULES:
        assert compile_rule(r)


def test_vocabulary_is_unique_and_sorted():
    assert len(set(PREDICATES)) == len(PREDICATES)
    assert list(PREDICATES) == sorted(PREDICATES)


def test_rule_shapes():
    assert compile_rule('integer -> rational') == [(-PRED_INDEX['integer'] - 1, PRED_INDEX['rational'] + 1)]
    z, nn, np_ = (PRED_INDEX[k] + 1 for k in ('zero', 'nonnegative', 'nonpositive'))
    assert set(compile_rule('zero == nonnegative & nonpositive')) == {(-z, nn), (-z, np_), (z, -nn, -np_)}


def test_rule_base_matches_sympy_old_rules():
    """Every string rule in sympy.core.assumptions must be present verbatim
    (modulo whitespace) so the two systems cannot drift apart."""
    sympy = __import__('pytest').importorskip('sympy')
    import re, inspect, sys
    src = inspect.getsource(sys.modules['sympy.core.assumptions'])
    block = src.split('_assume_rules = FactRules([')[1].split('])')[0]
    old = {re.sub(r'\s+', ' ', s).strip() for s in re.findall(r"'([^']+)'", block)}
    ours = {re.sub(r'\s+', ' ', s).strip() for s in RULES}
    assert old <= ours, old - ours


def test_instantiated_rules_propagate_like_the_full_rule_base():
    """The minimised clause set derives exactly the same literals by unit
    propagation as the full rule base, from every literal and every pair."""
    from itertools import combinations
    from satassume.rules import RULE_INSTANTIATED, NPRED, unit_propagate
    assert len(RULE_INSTANTIATED) < len(RULE_CLAUSES)
    lits = [l for i in range(1, NPRED + 1) for l in (i, -i)]
    for a in lits:
        assert unit_propagate(RULE_CLAUSES, [a]) == unit_propagate(RULE_INSTANTIATED, [a])
    for a, b in combinations(lits, 2):
        assert unit_propagate(RULE_CLAUSES, [a, b]) == unit_propagate(RULE_INSTANTIATED, [a, b]), (a, b)


def test_instantiated_rules_have_the_same_models():
    from satassume.rules import RULE_INSTANTIATED, NPRED
    from satassume.solver import Solver
    for c in RULE_CLAUSES:
        s = Solver()
        for r in RULE_INSTANTIATED:
            s.add_clause(list(r))
        assert not s.solve([-l for l in c]), c


# -- unit_propagate over masks against the set-based reference --------------

def _unit_propagate_reference(clauses, assumptions):
    """The implementation unit_propagate replaced: sets of signed literals."""
    assigned = set(assumptions)
    if any(-l in assigned for l in assigned):
        return None
    changed = True
    while changed:
        changed = False
        for c in clauses:
            unassigned = None
            satisfied = False
            n_unassigned = 0
            for l in c:
                if l in assigned:
                    satisfied = True
                    break
                if -l not in assigned:
                    n_unassigned += 1
                    unassigned = l
            if satisfied:
                continue
            if n_unassigned == 0:
                return None
            if n_unassigned == 1:
                assigned.add(unassigned)
                changed = True
    return assigned


def test_unit_propagate_matches_reference_on_the_rule_base():
    from satassume.rules import NPRED, RULE_INSTANTIATED, unit_propagate
    rng = random.Random(11)
    for _ in range(200):
        lits = [rng.choice([-1, 1]) * v for v in rng.sample(range(1, NPRED + 1), rng.randint(0, 4))]
        assert unit_propagate(RULE_INSTANTIATED, lits) == _unit_propagate_reference(RULE_INSTANTIATED, lits)


def test_unit_propagate_matches_reference_on_random_clauses():
    from satassume.rules import unit_propagate
    rng = random.Random(5)
    conflicts = 0
    for _ in range(1500):
        n = rng.randint(1, 40)
        clauses = tuple(tuple(rng.choice([-1, 1]) * v
                              for v in rng.sample(range(1, n + 1), rng.randint(1, min(3, n))))
                        for _ in range(rng.randint(0, 15)))
        if rng.random() < 0.5:
            clauses = list(clauses)             # a list is not memoized
        lits = [rng.choice([-1, 1]) * v for v in rng.sample(range(1, n + 1), rng.randint(0, n))]
        if rng.random() < 0.3:
            # an assumption about a variable beyond the clauses' widest
            lits.append(rng.choice([-1, 1]) * rng.randint(n + 1, n + 50))
        want = _unit_propagate_reference(clauses, lits)
        assert unit_propagate(clauses, lits) == want
        conflicts += want is None
    assert conflicts > 100


def test_closure_mask_round_trip():
    from satassume.rules import closure_mask, lits_mask, mask_lits
    assert mask_lits(lits_mask([3, -1, 7])) == {3, -1, 7}
    assert closure_mask(((1, 2), (-2, 3)), lits_mask([-1])) == lits_mask([-1, 2, 3])
    assert closure_mask(((1, 2), (-2, 3), (-3,)), lits_mask([-1])) == -1
    assert closure_mask(((1, 2),), lits_mask([1, -1])) == -1
