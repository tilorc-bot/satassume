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
