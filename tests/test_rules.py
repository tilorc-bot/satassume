import random
from satassume.rules import (RULES, RULE_CLAUSES, PREDICATES, PRED_INDEX, BASIS_INDEX,
                             compile_rule, compile_rules)


def test_every_rule_compiles():
    for r in RULES:
        assert compile_rule(r)


def test_vocabulary_is_unique_and_sorted():
    assert len(set(PREDICATES)) == len(PREDICATES)
    assert list(PREDICATES) == sorted(PREDICATES)


def test_rule_shapes():
    assert compile_rule('integer -> rational') == [(-BASIS_INDEX['integer'] - 1, BASIS_INDEX['rational'] + 1)]
    z, en, ep = (BASIS_INDEX[k] + 1 for k in ('zero', 'extended_negative', 'extended_positive'))
    er = BASIS_INDEX['extended_real'] + 1
    assert set(compile_rule('extended_real == extended_negative | zero | extended_positive')) == \
        {(-er, en, z, ep), (er, -en), (er, -z), (er, -ep)}
    i, r = PRED_INDEX['integer'] + 1, PRED_INDEX['rational'] + 1
    assert compile_rule('integer -> rational', PRED_INDEX) == [(-i, r)]


#: SymPy's rule base over the whole vocabulary (sympy/core/assumptions.py
#: plus sympy/assumptions/facts.py): the specification of RULES.
FULL_RULES = (
    'integer -> rational', 'rational -> real', 'rational -> algebraic', 'algebraic -> complex',
    'transcendental == complex & !algebraic', 'imaginary -> complex', 'extended_real -> commutative',
    'complex -> commutative', 'complex -> finite', 'odd == integer & !even', 'even == integer & !odd',
    'real -> complex', 'extended_real -> real | infinite', 'real == extended_real & finite',
    'extended_real == extended_negative | zero | extended_positive',
    'extended_negative == extended_nonpositive & extended_nonzero',
    'extended_positive == extended_nonnegative & extended_nonzero',
    'extended_nonpositive == extended_real & !extended_positive',
    'extended_nonnegative == extended_real & !extended_negative',
    'real == negative | zero | positive', 'negative == nonpositive & nonzero',
    'positive == nonnegative & nonzero', 'nonpositive == real & !positive',
    'nonnegative == real & !negative', 'positive == extended_positive & finite',
    'negative == extended_negative & finite', 'nonpositive == extended_nonpositive & finite',
    'nonnegative == extended_nonnegative & finite', 'nonzero == extended_nonzero & finite',
    'zero -> even & finite', 'zero == extended_nonnegative & extended_nonpositive',
    'zero == nonnegative & nonpositive', 'nonzero -> real', 'prime -> integer & positive',
    'composite -> integer & positive & !prime', '!composite -> !positive | !even | prime',
    'irrational == real & !rational', 'imaginary -> !extended_real', 'infinite == !finite',
    'noninteger == extended_real & !integer', 'extended_nonzero == extended_real & !zero',
    'positive_infinite == extended_positive & infinite', 'negative_infinite == extended_negative & infinite',
    'real -> hermitian', 'imaginary -> antihermitian', 'zero -> hermitian | antihermitian',
    'hermitian == real', 'antihermitian == zero | imaginary',
)


def test_rule_base_matches_sympy_old_rules():
    """Every string rule in sympy.core.assumptions must be in FULL_RULES
    (modulo whitespace) so the two systems cannot drift apart."""
    sympy = __import__('pytest').importorskip('sympy')
    import re, inspect, sys
    src = inspect.getsource(sys.modules['sympy.core.assumptions'])
    block = src.split('_assume_rules = FactRules([')[1].split('])')[0]
    old = {re.sub(r'\s+', ' ', s).strip() for s in re.findall(r"'([^']+)'", block)}
    ours = {re.sub(r'\s+', ' ', s).strip() for s in FULL_RULES}
    assert old <= ours, old - ours


def _count_models(clauses, nv):
    def rec(assign):
        assign = dict(assign)
        changed = True
        while changed:
            changed = False
            for c in clauses:
                free, nfree, sat = None, 0, False
                for l in c:
                    if abs(l) in assign:
                        if assign[abs(l)] == (l > 0):
                            sat = True
                            break
                    else:
                        nfree, free = nfree + 1, l
                if sat:
                    continue
                if nfree == 0:
                    return 0
                if nfree == 1:
                    assign[abs(free)] = free > 0
                    changed = True
        for v in range(1, nv + 1):
            if v not in assign:
                return rec({**assign, v: True}) + rec({**assign, v: False})
        return 1
    return rec({})


def test_basis_rules_have_the_models_of_the_full_rule_base():
    """RULES over the basis, with every other predicate read through its
    definition, has exactly the models of FULL_RULES over the vocabulary."""
    from itertools import product
    from satassume.rules import NPRED, basis_lits
    full = compile_rules(FULL_RULES, PRED_INDEX)
    seen = set()
    for bits in product((False, True), repeat=NPRED):
        a = {i + 1: b for i, b in enumerate(bits)}
        if not all(any(a[abs(l)] == (l > 0) for l in c) for c in RULE_CLAUSES):
            continue
        f = {}
        for p in PREDICATES:
            op, ls = basis_lits(p)
            vals = [a[abs(l)] == (l > 0) for l in ls]
            f[PRED_INDEX[p] + 1] = all(vals) if op == '&' else any(vals)
        assert all(any(f[abs(l)] == (l > 0) for l in c) for c in full), a
        seen.add(tuple(sorted(f.items())))
    # ``commutative`` is true by definition: the models with it true
    comm = (PRED_INDEX['commutative'] + 1,)
    assert len(seen) == _count_models([tuple(c) for c in full] + [comm], len(PREDICATES))


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
