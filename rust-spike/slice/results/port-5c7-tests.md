# Before 5c7: the public-API `test_incremental_matches_fresh` family and the zero-twin workload (issue 323)

Test-only step (sa-port-136), under the planner's three conditions: the tests pass on pure Python first, the step adds
tests and removes none, and a Python failure is a finding against main, not fixed here. No engine or crate code changed.

## What was added
- **`tests/test_public_incremental.py`** (34 tests), beside `tests/test_solver_incremental.py`, whose internals-based
  `test_incremental_matches_fresh` family is untouched. It reads no private name. One `Engine` answers a seeded stream and
  every outcome (a raise included) is compared with a new engine answering that op alone:
  - `test_public_incremental_matches_fresh[0-3]`: `Engine.ask`, `is_`, `is_many` and `verdict` over P atoms and every
    connective (And, Or, Not, Implies, Equivalent, Exclusive, ITE), under assumption sets built in sequence (conjuncts
    added, dropped, cleared);
  - `..._with_hold[0-3]`: the sets are mostly prefixes of one list that grows and is cut back, so a set often extends the
    one before or repeats it (the public counterpart of a held prefix); asserts both happened;
  - `..._with_theories[0-3 x default, whole, notransfer]`: `sympy_api.ask` with unary predicates, order and equality
    relations over symbols, sums and applications `g(..)`;
  - `test_public_mix_covers_the_outcomes`: every op, True, False, None, a raise, and set extensions are reached;
  - `test_public_comparison_catches_a_planted_history_dependence`: a planted memo that ignores the set is caught;
  - `test_public_zero_twins_incremental_matches_fresh[pair, cross, query-zero x 3 configs]` and
    `test_public_zero_pair_reversed_matches_fresh[3 configs]`: zero-twin streams (below).
  `PUBLIC_SEEDS` (default 24) sets the seeds per stream.
- **`rust-spike/slice/zero_wl.py`**, run as `live.py zero` (one line in `live.py`): 854 queries built from the code,
  not from held-out data: `Session._glue_of` and `_ensure_twins` (engine.py :1182-1230; `session_glue.rs` glue_of on Rust),
  `relations.zero_twins`' condition (scope.py :35-46: a twin only when `t` is under an application, "chosen for its cost")
  and `_within_budget`'s `cross` twins (engine.py :1801-1808). Five terms (`k - x + 1` among them), each set and query in
  the `zero` and `eq` spellings, with the application in the set, in the query, in both and in neither. Under each set the
  pair is asked again after the twin-making queries, and the pinned pair comes last. `python zero_wl.py` compares warm
  (one engine, in sequence) against fresh.

## Python's results (the reference)
- **All 34 new tests pass on pure Python** (orion, 10 s), and again at `PUBLIC_SEEDS=200` (34 passed, 67 s). **No
  finding against main**, so nothing is marked xfail.
- **Zero-twin workload on Python:** 854 queries, True 220, False 100, None 460, ValueError 74 (SymPy's inconsistent
  assumptions). **Warm against fresh: 0 differ.** The pair: under `integer(k) & integer(x) & negative(k) & positive(x)`,
  **`Q.zero(k - x + 1)` is None and `Q.eq(k - x + 1, 0)` is False**, as expected on main. `~Q.zero` and `Q.nonzero` are
  None too. The same in the incremental streams, in either order, in all three configurations: warm equals fresh.
  With an application over the sum in the set (`& Q.finite(g(k - x + 1))`) both spellings give False. This difference
  is already a finding pinned on main: `tests/test_zero_glue.py::test_outside_the_condition_a_bounded_sum` (strict
  xfail, relations.py :171-181). No new marker was added for it: it's a difference between spellings, and history plays
  no part.

## The glue-of-plain catch (gaps ruling)
On the zero workload, against this run's Python (bar extra phase; orion gave the same):

| run | answers | state (end/stream/lra) | verdict |
|---|--:|--:|---|
| Rust, no plant | 0 | 0 | MATCH (answers_sha d9ed3534a2093027 both) |
| Rust, `glue-of-plain` (fired 2,948) | 19 | 235 | **DIFFER** (first: q18, Python raises for `BASE & zero(k - x + 1)`, the plant gives None) |

So `glue-of-plain` is caught by a workload. **The gaps-ruling footnote for `_glue_of`'s twin branch is closed.** The
same workload also catches, on orion (`~/sa-rust-ids-work/sa-port-136/zero2/`, plain Rust MATCH there too):
`glue-no-twins` (5c5, `glue_atoms`' twins): DIFFER, 29 answers, 235 state rows; `drop-prep-twins` (5c4): DIFFER in state
only (3 end/stream/lra rows, 0 answers). That's the one workload 5c6's owed list asked for, covering all four. Every
other plant also DIFFERs on zero (table in sum.txt). The new pytest tests don't catch `glue-of-plain` (it changes
warm and fresh alike). `test_zero_glue.py` does: 25 failures under the plant, as in 5c6.

## SHAs
Tested **7276dff** (port/5c7-tests on rust-slice 1401d1f). Rows on pareto1 at
`~/sp19/sa-rust-ids-work/sa-port-136/bar-5c7t/` (`sum.txt`, `commands.txt`), `.so` sha256 c5c0e922…, the same as 5c6's.
Base: `sa-port-134/bar-5c6/suite`. Landing: **not landed yet.** The architect held rust-slice until 6d (sa-port-131) lands; 6d changes code these runs
execute, so under the rebase rule the landing source gets a full bar rerun (handoff: NEXT-port-5c7-tests.txt).

## The bar (bar-5c7t)
1. **Suite by id against bar-5c6:** 5,992 passed, 126 failed, 23 skipped, 18 xfailed, 6,159 ids. **New 34, gone 0,
   changed outcome 0.** The 34 new ids are exactly `tests/test_public_incremental.py`'s, all passed on Rust. Passed
   splits as 5,991 with no firing and 1 with a firing (`test_ci_stream_reports_only_what_replays`). S's standing: S's gate
   is met except for the 46 named stub failures, one cause.
2. **Fresh dev and fuzz, plus loop, scope and zero:** answers and state MATCH, every control MATCHes. dev
   31cd0945c07f02a6 (1,985 q), fuzz 173502b6ef285ad6 (3,000 q), loop 09238b2537e54383 (420 q), scope 12e06b0586faee40
   (169 q), all as 5c6; zero d9ed3534a2093027 (854 q, new). The Rust runs made 0 Python solvers.
3. **Plants:** 6 of 7 caught on dev and fuzz as before. `glue-of-plain` MATCHes on dev, fuzz, loop and scope and is
   **caught on zero** (above). None is void.
4. **Quiet handlers in the suite:** 39 rows in 2 tests, the same multiset as base, `caught` rows per id the same:
   `_consistent` AttributeError 34 on `_ok` and 4 on `_rb_clauses` (the named needs-internals case); `Engine._build_context`
   "Already mutably borrowed" 1 in `test_protocol_on_fuzz` (the 46-stub cause). **Quiet catches at engine.py:1906
   (`_build_context`): 1**, in the suite, as on base; 0 on every workload (dev, fuzz, loop, scope, zero handler files
   and the 14 dev/fuzz plant handler files all have 0 rows). The counter fires: the suite's own rows show it. TermFault 0.
5. **Known differences in answers or read state:** none. Slice tests: 510 passed (the 11 slice files, from the rerun of `tests`). `relations_direct.py` exited 0.

`test_equality_sharing_is_needed_and_works` is still named needs-internals; this step doesn't touch it.

## Kept reasons (planner ruling, 03:42 UTC 8 Nov)
| workload | queries at conversion | out-of-scope | refused | other named exceptions | base |
|---|--:|--:|--:|--:|---|
| dev | 1,221 | 24 (1.97%) | 0 | 0 | the same |
| fuzz | 2,998 | 0 | 0 | 0 | the same |
| loop | 384 | 0 | 0 | 0 | the same |
| scope | 169 | 0 | 0 | 0 | the same |
| zero | 740 | 0 | 0 | 0 | new workload |

**No share rose.** `const_value`'s fire count isn't counted on this branch (its counter comes with 6d).

## Module count
Unchanged: a test-only step. The ownership table isn't touched.

## Owed-list additions
- None new. 5c6's item (a live workload for `_glue_of`'s twin branch, `glue_atoms`' twins, `zero_twins` and
  `drop-prep-twins`) is met by `live.py zero`.

## Not run
Moved to "before any backend PR", and none quoted as met:
- the mutant 2, 5, 6, 7, 9 rerun and mutlive's control;
- the boundary rescore and suite column;
- the final drop score and its lost rows;
- the suite split with Python's counter;
- `order:_rows`' evidence (not caught meanwhile);
- the `_forms` guard test;
- history and seed reruns (seed1 not run);
- forced moves;
- the native path;
- timing.

Also not run: the suite under any plant (`SUITE_PLANTS` empty: `glue-of-plain` now has its workload catch, and 5c6's
bar-5c6-glue already showed the suite's 36). The bar's first `tests` phase was void (I passed the two root test files
in `TESTS`, which runs from the slice directory, so pytest exited 4). I reran `tests` and `sum` with 5c6's 11 files into the same
directory. The new tests ran on Rust in the suite.
