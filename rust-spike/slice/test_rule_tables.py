"""test_rule_tables.py: S2 (issue 323), the rule block's tables on Rust.

- the generated tables (gen_rule_tables.py -> solver_rs/src/rule_tables_gen.rs) are what `_rule_tables` computes today
  for the engine's block, regenerated and compared byte for byte, and Rust hands them out for that block;
- any other block is checked and enumerated in Rust (block.rs) with `_rule_tables`' result and errors;
- each of S2's plants is caught here (rb-gen-any and rb-check-skip are reached by no workload: no engine path passes
  another block, or a bad one).
Run from this directory or by pytest; it needs the clone's sa_solver.so.
"""
import os
import random
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

import pytest  # noqa: E402
import sa_solver  # noqa: E402

from satassume.knowledge.rules import NPRED, RULE_INTERNAL  # noqa: E402
from satassume.sat import solver as PS  # noqa: E402

PLANTS = ("rb-gen-model-flip", "rb-built-model-drop", "rb-gen-any", "rb-check-skip")


def py_tables(block, nvars):
    """`_rule_tables`' answer, or its error as `(type name, text)`."""
    try:
        (clauses, closure), n = PS._rule_tables(block, nvars)
    except Exception as e:  # noqa: BLE001 - the comparison is the point
        return ("raise", type(e).__name__, str(e))
    return ([list(c) for c in clauses], n, list(closure.models))


def rs_tables(block, nvars):
    try:
        clauses, n, models, source = sa_solver.rule_block_tables(block, nvars)
    except Exception as e:  # noqa: BLE001
        return ("raise", type(e).__name__, str(e)), None
    return (clauses, n, models), source


def random_block(rng):
    n = rng.randint(1, 9)
    clauses = []
    for _ in range(rng.randint(0, 3 * n)):
        k = rng.randint(2, min(4, n)) if n >= 2 else 2
        vs = rng.sample(range(n), k) if k <= n else [0, 0]
        clauses.append(tuple(2 * v + rng.randint(0, 1) for v in vs))
    return tuple(clauses), rng.choice([None, n, n + rng.randint(0, 3)])


BAD = [
    (((0,),), 2), (((0, 2),), 1), (((0, 2),), 65), ((), None), (((0, 1),), 1), (((0, 2, 2),), 2), (((-1, 2),), 2),
    (((0, 2 * 64),), 65), (((0, 2),), 0), (((0, 2),), -3), ([[0, 2], [3, 1, 4]], None), (((0, 2),), 2.0),
    (((0, 2),), "3"), (((0, 2), (5, 1 << 70)), None), (((0, 2), (5, 1 << 70)), 4), (((0, 2), (5, -(1 << 70))), 4),
    (((0, 2),), 1 << 80), (((0, 2),), -(1 << 80)), (((0, 2.5),), 2), ((x for x in [(0, 2), (1, 3)]), None),
    (((0, 2),), None), ((), 3),
]


def test_generated_file_regenerates():
    r = subprocess.run([sys.executable, os.path.join(HERE, "gen_rule_tables.py"), "--check"], capture_output=True,
                       text=True, env=dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path)))
    assert r.returncode == 0, r.stderr[-400:]


def test_engine_block_comes_from_the_generated_tables():
    got, source = rs_tables(RULE_INTERNAL, NPRED)
    assert source == "generated"
    assert got == py_tables(RULE_INTERNAL, NPRED)
    assert len(got[2]) == 44


def test_engine_block_as_lists_is_still_generated():
    got, source = rs_tables([list(c) for c in RULE_INTERNAL], NPRED)
    assert source == "generated" and got == py_tables(RULE_INTERNAL, NPRED)


def test_engine_block_minus_a_clause_is_built():
    for i in range(len(RULE_INTERNAL)):
        block = RULE_INTERNAL[:i] + RULE_INTERNAL[i + 1:]
        got, source = rs_tables(block, NPRED)
        assert source == "built" and got == py_tables(block, NPRED), i


def test_engine_block_wider_is_built():
    got, source = rs_tables(RULE_INTERNAL, NPRED + 1)
    assert source == "built" and got == py_tables(RULE_INTERNAL, NPRED + 1)


def test_random_blocks_match_python():
    rng = random.Random(323)
    for _ in range(600):
        block, nvars = random_block(rng)
        got, _ = rs_tables(block, nvars)
        assert got == py_tables(block, nvars), (block, nvars)


def test_bad_blocks_raise_as_python_does():
    for block, nvars in BAD:
        if not isinstance(block, (tuple, list)):
            continue
        assert rs_tables(block, nvars)[0] == py_tables(block, nvars), (block, nvars)


def test_generator_block_raises_as_python_does():
    assert rs_tables((x for x in [(0, 2), (1, 3)]), None)[0] == py_tables((x for x in [(0, 2), (1, 3)]), None)


def test_too_many_models():
    block = (tuple(2 * v for v in range(20)),)          # one clause over 20 variables: 2^20 - 1 models
    assert rs_tables(block, 20)[0] == py_tables(block, 20) == ("raise", "ValueError", "rule block has too many models")


def test_solver_set_rule_block_matches_python_solver():
    """The public method on both solvers: same block, same root facts and answers."""
    from satassume.sat.solver import Solver
    for block, nvars in [(RULE_INTERNAL, NPRED), (((0, 2), (3, 5)), 3), (RULE_INTERNAL[1:], NPRED)]:
        res = []
        for S in (Solver, sa_solver.Solver):
            s = S()
            s.set_rule_block(block, nvars)
            s.set_rule_block(block, nvars)                    # same block: no-op
            with pytest.raises(ValueError, match="already set"):
                s.set_rule_block(((0, 2),), 2)
            assert s.register_block(1)
            res.append([s.solve([l]) for l in range(1, nvars + 1)] + [s.solve([-l]) for l in range(1, nvars + 1)])
        assert res[0] == res[1], block


@pytest.mark.parametrize("plant", PLANTS)
def test_plant_is_caught(plant):
    sa_solver.rel_plant(plant)
    try:
        caught = []
        if rs_tables(RULE_INTERNAL, NPRED)[0] != py_tables(RULE_INTERNAL, NPRED):
            caught.append("engine block")
        rng = random.Random(323)
        for _ in range(200):
            block, nvars = random_block(rng)
            if rs_tables(block, nvars)[0] != py_tables(block, nvars):
                caught.append("random")
                break
        for i in range(len(RULE_INTERNAL)):
            block = RULE_INTERNAL[:i] + RULE_INTERNAL[i + 1:]
            if rs_tables(block, NPRED)[0] != py_tables(block, NPRED):
                caught.append("minus a clause")
                break
        for block, nvars in BAD:
            if isinstance(block, (tuple, list)) and rs_tables(block, nvars)[0] != py_tables(block, nvars):
                caught.append("bad")
                break
    finally:
        sa_solver.rel_plant(None)
    assert caught, plant


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
