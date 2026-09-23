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
