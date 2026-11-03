# mutant-45deb0e

**Verdict: FAIL (gates: stream (2), battery (5), corpus (2), stream-unique (1), stream-shuffled (3), tests_own (3), tests_base_on_cand (3))**

Candidate: `cands/mutant-test` at `45deb0e` (planted history-dependent wrong answer)

Commits over 9bafaa5:
```
45deb0e evalbench mutant (never push)
```

```
satassume/sympy_api.py | 4 ++++
 1 file changed, 4 insertions(+)
```

## Gates: FAIL

| check | result | detail |
|---|---|---|
| stream | FAIL | 2 of 16232 differ |
| battery | FAIL | 5 of 16386 differ |
| corpus | FAIL | 2 of 2863 differ |
| ho-fuzz | pass | 0 of 3000 differ |
| fork-battery | pass | 0 of 103 differ |
| stream-unique | FAIL | 1 of 8393 differ |
| stream-shuffled | FAIL | 3 of 8393 differ |
| forkq (fresh process per query) | pass | 0 of 8393 differ |
| tests_own | FAIL | 3 failed, 6080 passed, 23 skipped, 18 xfailed, 6 warnings in 301.13s (0:05:01) |
| tests_base_on_cand | FAIL | 3 failed, 6080 passed, 23 skipped, 18 xfailed, 6 warnings in 421.09s (0:07:01) |

### stream: differences

* #12216: `Q.extended_negative(x)  |  Q.negative_infinite(x)`: base `True`, cand `None`
* #15958: `Q.extended_negative(x)  |  Q.negative_infinite(x)`: base `True`, cand `None`

### battery: differences

* #3893: `Q.negative(-1)  |  Q.ge(x, pi) & Q.le(x, 2*pi)`: base `True`, cand `None`
* #5661: `Q.negative(-1)  |  Q.ge(x, pi) & Q.le(x, 2*pi)`: base `True`, cand `None`
* #8281: `Q.negative(-1)  |  Q.even(n) & Q.imaginary(x)`: base `True`, cand `None`
* #12196: `Q.integer(0)  |  Q.real(t)`: base `True`, cand `None`
* #14596: `Q.nonnegative(n)  |  Q.integer(n) & Q.nonnegative(n) & Q.gt(k, n)`: base `True`, cand `None`

### corpus: differences

* #1019: `Q.complex(x + 1)  |  Q.complex(x)`: base `True`, cand `None`
* #1077: `Q.complex(x + 1)  |  Q.complex(x)`: base `True`, cand `None`

### stream-unique: differences

* #6212: `Q.extended_negative(x)  |  Q.negative_infinite(x)`: base `True`, cand `None`

### stream-shuffled: differences

* #3062: `Q.odd(3)  |  ~Q.zero(x)`: base `True`, cand `None`
* #4102: `Q.negative(-1)  |  Q.imaginary(x) & Q.positive(_t) & Q.real(_t) & Q.real(y) & ~Q.zero(_t)`: base `True`, cand `None`
* #5159: `Q.extended_negative(x)  |  Q.negative_infinite(x)`: base `True`, cand `None`

### tests_own: differences

* tests.test_history::test_module_state_inventory_is_classified
* tests.test_history::test_spec_level_catches_a_planted_engine_answer
* tests.test_verify_integration::test_relations_off_gives_old_behaviour_and_same_unary_answers

### tests_base_on_cand: differences

* tests.test_history::test_module_state_inventory_is_classified
* tests.test_lra_exhaustion::test_constants_no_warm_fresh_divergence
* tests.test_solver::test_performance_smoke_300_vars

## Time (pareto1, pinned, alternating cold processes; speedup = base/cand, paired by round)

(not run)

## Counters (deterministic; cand vs base, delta)

| counter | dev | ho-stream | ho-battery | ho-fuzz | corpus |
|---|---|---|---|---|---|
| context_builds | 833 | 3885 | 503 | 2938 | 1061 |
| set_checks | 833 | 3885 | 503 | 2938 | 1061 |
| sessions | 918 | 4334 | 558 | 3149 | 1816 |
| queries | 883 | 4311 | 587 | 3035 | 1798 |
| escalations | 315 | 1786 | 214 | 2606 | 678 |
| searches | 475 | 2604 | 328 | 2649 | 709 |
| relevant | 583 | 2695 | 213 | 1238 | 569 |
| consistency_checks | 64 | 150 | 43 | 324 | 78 |
| cache_hits | 1248 | 10198 | 939 | 685 | 918 |
| solver_conflicts | 257 | 1695 | 203 | 7720 | 87 |
| solver_decisions | 7738 | 43668 | 5327 | 106578 | 12906 |
| solver_propagations | 53418 | 318857 | 56695 | 790907 | 54680 |
| solver_clauses | 51769 | 308011 | 51477 | 663082 | 59098 |
| solver_vars | 41214 | 235324 | 40397 | 361067 | 61545 |

Phases on dev, instrumented (s, orion, indicative): build 0.280 (base 0.279), engine 0.208 (base 0.135), escalate 0.056 (base 0.056), front 0.048 (base 0.050), prepare 0.149 (base 0.151), propagate 0.036 (base 0.036), search 0.110 (base 0.108)

The stream is satassume's home ground (its corpus was recorded from the same SymPy tests).
