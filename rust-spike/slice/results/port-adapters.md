# Adapters step, part A: AdapterSpec converted once (issue 323)

## Step 0 (the planner's check on relations.py's 8 of 32)
On 2ee0c8c, Rust read `AdapterSpec`'s fields per query and called `spec.factory()` once per spec for each Relations
object, which means once per session. That is the shell case in ruling (1), so **relations.py does not count whole yet**.
Evidence: relations_core.rs on 2ee0c8c, `rel_interpret` :791-794, `rel_link` :906-909, `engage_transfer` :1246-1249,
`rel_adapter` :1917-1931 (5c5's memo: `spec.name` on every call, `factory()` on a miss) and `guarded_adapters`
:2422-2441 (per query through `link_objects` from engine.py:1749). Trace on dev (AdapterSpec swapped for a counting
tuple subclass, `~/sa-rust-ids-work/sa-port-125/step0/` on orion): Rust read `guarded` about 4,100 times and `name`
about 3,600 times, in 198 queries. It called `factory()` 397 times, the same 396 + 1 as Python. `name` is also read
4,884 times at convert.py:398, which is conversion. `Uninterpreted`: Rust only constructs and raises it
(relations_core.rs:1902) and reads none of its fields.

## What moved (part A, f2e70ba)
- `spec_row` (relations_core.rs) reads a spec's `name`, `factory` and `guarded` once, the first time Rust sees that spec.
  It keeps them in a memo keyed by the spec object, and the memo holds the spec so its address isn't reused. A spec is a
  NamedTuple and can't change. The five readers above use the memo. No attribute was added to Relations, so `vars(rel)`
  is unchanged. New counter `rel:cb_spec_read` (one tick per field read): **6 on dev** (2 specs x 3 fields), down from
  about 7,600. Answers unchanged.
- **Why part A stands alone:** it removes every per-query field read and moves no ownership row. The bar below passes on
  its own. What's left of step 0 is `factory()` per session, which returns the adapters, so it goes with part B.
- Not moved yet: everything the brief lists (LRAAdapter, EUFAdapter, EqAtom, Negated/Integral, constfield's rows). See
  HANDOFF-sa-port-125.md and the next brief.

## SHAs
Tested **f2e70ba** (port/adapters on rust-slice 2ee0c8c). Rows are on pareto1 at `~/sp19/sa-rust-ids-work/sa-port-125/bar-A/`
(`sum.txt`, `commands.txt`). The `.so`'s sha256 is df6c0618…. The base is sa-port-122's bar-5c5 suite rows. The landed
SHA and the incoming diff are in the `agent report` for this landing. Between the landed SHA and f2e70ba are only this file,
port-ownership.md and HANDOFF-sa-port-125.md: docs, which no run executes.

## The bar (sa-port-125/bar-A)
1. **Suite by id against 5c5's rows:** 5,958 passed, 126 failed, 23 skipped, 18 xfailed, 6,125 ids. New 0, gone 0, changed
   outcome 0. Passed: 5,957 with no firing and 1 with a firing (`test_ci_stream_reports_only_what_replays`). S's standing:
   S's gate is met except for the 46 named stub failures, one cause.
2. **Fresh dev, fuzz and loop:** answers and state MATCH, with every control MATCHing. Dev 31cd0945c07f02a6 (1,985 q),
   fuzz 173502b6ef285ad6 (3,000 q), loop 09238b2537e54383 (420 q). Seed1 dev and fuzz also MATCH. Rust runs made 0 Python solvers.
3. **Plants:** 2 of 3 caught; the third fires and MATCHes, as it did at 5c5 (table below).
4. **Quiet handlers, suite:** 39 rows in 2 tests, the same multiset as base: `_consistent` AttributeError, 34 on `_ok` and
   4 on `_rb_clauses` (the named needs-internals case), and `Engine._build_context` "Already mutably borrowed" 1 in
   `test_protocol_on_fuzz` (the 46-stub cause). `caught` rows per id match base. **Quiet catches at engine.py:1906: 1**,
   in the suite, as on base. There are 0 on dev, fuzz, loop and seed1: their handler files have 0 rows. The plant runs'
   handler files have rows (spec-row-flip: dev 2, fuzz 315), which shows the counter fires. TermFault 0.
5. **Known differences:** none. Tests: 503 passed, and `relations_direct.py` exited 0.

## Plants (fired; D = DIFFER)
| plant | item | dev | fuzz | loop | caught by |
|---|---|---|---|---|---|
| spec-row-flip | spec_row (new) | 1,535 D | 39,216 D | 0 | dev, fuzz |
| adapter-fresh | _adapter (touched) | 3,162 D | 80,339 D | 0 | dev, fuzz |
| guarded-none | _guarded_adapters (touched) | 226 MATCH | 11,684 MATCH | 0 | funcs (5c5), not rerun here |

None is void. `guarded-none` fires and MATCHes, as at 5c5: it feeds the relevance cone, which the stream doesn't see.
No plant fired 0 on both workloads, so `zero` selected none and no suite plants ran.

## Reached
`spec_row` is reached on dev and fuzz, through every reader (6 conversions, then memo hits). Loop doesn't reach it (0 fires).

## Module count
Under the count rule: **7 of 32**. relations.py waits on step 0 (factory() per session, part B). The footnote stands:
realroots and `value_units` are wired, but neither dev nor fuzz reaches them.

## Not run
Moved to "before any backend PR", and none quoted as met: the mutant 2, 5, 6, 7, 9 rerun and mutlive's control; the
boundary rescore and suite column; the final drop score and its lost rows; the suite split with Python's counter;
`order:_rows`' evidence (not caught meanwhile); the `_forms` guard test; history reruns; forced moves; the native path;
timing. Also not run: `funcs` under `guarded-none` (5c5 showed it catches it; part A only changed how the spec is read).

Other notes:
- Mutants 2, 5, 6, 7, 9 still rest on the API fuzzer alone. 10 of the 25 boundary mutants have no real-engine catch, and
  the boundary suite column wasn't run.
- **Speed not measured.**
- The `_n_conflicts` view in rust_plugin.py is a test-plugin shim, not a port (64 tests).
- The public-API `test_incremental_matches_fresh` family is still owed: a test-only step before 5c7.
- `tests/test_relations.py::test_equality_sharing_is_needed_and_works` is unedited and still named needs-internals.

## Addendum (sa-port-129, 8 Nov): part A's bar on the landed SHA d91ee15 (bar-A2)
**The slip:** sa-port-125 tested f2e70ba and pushed d91ee15 with PUSH=1, though the rebase had brought in 6g(a)'s source
(convert.py, knowledge_live.py, live.py, term/dispatch.rs, term/mod.rs, lib.rs, dispatch_direct.py,
knowledge_opaque_wl.py, test_knowledge_value_units.py), which the run executes. The full rerun ran after the push:
pareto1 `~/sp19/sa-rust-ids-work/sa-port-125/bar-A2/sum.txt`, tested source **d91ee15**, .so sha256 86b1c307….
Per the planner's ruling (03:24 UTC), it matches, so **d91ee15 stands**. bar.sh's push guard (landing with part B) now
refuses such a push.
1. Suite by id against sa-port-122's bar-5c5: 5,958 passed / 126 failed / 23 skipped / 18 xfailed, new 0, gone 0, changed 0.
   Passed: 5,957 with no firing, 1 with a firing (`test_ci_stream_reports_only_what_replays`, the named one).
2. Dev 31cd0945c07f02a6 and fuzz 173502b6ef285ad6 MATCH (answers, traced end states); loop 09238b2537e54383 MATCH;
   seed 1 dev and fuzz MATCH.
3. Plants: spec-row-flip and adapter-fresh caught on dev and fuzz; guarded-none fires but MATCH (as in bar-A); all three
   fire 0 on loop.
4. Handler rows 39 in 2 tests, multiset same as base (34 + 4 `_consistent` AttributeError in the named test, 1
   `_build_context` "Already mutably borrowed" in test_protocol_on_fuzz, the 46-stub cause). TermFault 0.
5. No known difference in answers or read state.
Tests phase 503 passed. Same as bar-A on every item.

# Adapters step, parts B and C1: Rust adapters and Rust payloads, landed together (issue 323)

One bar for both parts, on the merged tree at C1's tip (planner's ruling, about 05:20 UTC 8 Nov). Its three conditions:
B's and C1's plants are in separate rows below and each part is shown caught; the bar didn't differ, so B wasn't landed alone to
bisect; the push guard saw one tested SHA, and that source is what landed.

## What moved
- **Part B (adapters.rs, sa-port-129):** `LRAAdapter` and `EUFAdapter` are Rust classes. `make_adapter` builds the default
  specs' adapters in Rust with no `spec.factory()` call. A user-supplied factory stays a Python call, named and counted
  `ad:cb_factory`, the same exception as non-default registries. Callbacks into Python, named and counted: `_memoized` with
  `interpret`/`order_sides`/`integer_form` (`ad:cb_memoized`), `constant_bounds` (`ad:cb_constant_bounds`, R9),
  `EUFAdapter.parse` (`ad:cb_parse`), `structural` (`ad:cb_structural`), `EUFAdapter.interned` (`ad:cb_interned`), the
  theory constructor (`ad:cb_theory_new`).
- **Part C1 (payloads.rs, sa-port-138):** `Negated`, `Integral` and `EqAtom` are Rust pyclasses, built by the Rust adapters
  with no Python tuple in between. Python's classes are built only for Python's own theories, counted `ad:cb_py_payload`
  (adapter side) and `ad:integral_to_py` (lra_live.py:205, a Rust `Integral` that Python's `LRAAdapter` hands to Python's
  `LRATheory`). The Python classes stay for the pure-Python default and `constraint()` (tests only).
- **Renumbering:** part B's plants are **104-107** (`ad-lra-shared`, `ad-euf-node`, `ad-kind-swap`, `ad-euf-shared`; they
  were 91-94 in sa-port-129's handoff and part B's commit message) and its counters **140-150** (`ad:lra_new` ..
  `ad:euf_register`; were 123-133), after rebases over scope and 5c6 (sa-port-133). C1's plants are **108-110**
  (`pay-neg-twice`, `pay-int-offset`, `pay-eq-flip`) and its counters **151-154**. 6d didn't renumber, and 5c7-tests didn't
  either. Plants and counters are addressed by name in Python, so nothing else changed.
- Landing with part B: bar.sh's push guard (the planner's ruling of 03:24 UTC) and bar_sum.py's kept-reasons section.

## SHAs and incoming diff
Tested **d676f36** (port/adapters on rust-slice bb3df19). Landed **4dd2ed9** on rust-slice by `PUSH=1 bar.sh land d676f36`.
The incoming diff (bb3df19..44f4762) is `rust-spike/slice/results/port-5c7-tests.md` only. tested..landed is that file plus
HANDOFF-sa-port-140.md: docs, which no run executes, so the guard passed. Rows: pareto1
`~/sp19/sa-rust-ids-work/sa-port-140/bar-BC2/` (`sum.txt`, `commands.txt`, `config.txt`). `.so` sha256 27f01aaf…. Base:
6d's suite rows (`sa-port-131/suite`) and kept reasons (`sa-port-131`). PLANTS: part B `ad-lra-shared ad-euf-node
ad-kind-swap ad-euf-shared spec-row-flip adapter-fresh`, part C1 `pay-neg-twice pay-int-offset pay-eq-flip`, controls
`theory-no-assume` (scope), `al-drop-delta` (5c6), `common-facts-drop` (6d). WLS `f6 value rootof core opaque scope loop
zero`; SEED1=1; SUITE_PLANTS=`ad-euf-node pay-neg-twice` (picked by `zero`: 0 fires on dev and fuzz).

## The bar (sa-port-140/bar-BC2)
1. **Suite by id against 6d's rows:** 5,992 passed, 126 failed, 23 skipped, 18 xfailed, 6,159 ids. New 34, gone 0, changed
   outcome 0. The 34 new ids are exactly `tests/test_public_incremental.py`'s (5c7-tests, landed after 6d's base), all
   passed. Passed: 5,991 with no firing and 1 with a firing (`test_ci_stream_reports_only_what_replays`). S's standing:
   S's gate is met except for the 46 named stub failures, one cause.
2. **Fresh dev and fuzz:** answers and state MATCH, with every control MATCHing. Dev 31cd0945c07f02a6 (1,985 q), fuzz
   173502b6ef285ad6 (3,000 q); traced end states MATCH on both. Seed1 dev and fuzz MATCH. The eight extra workloads MATCH:
   f6 fc0c2f738a1f6dbf, value 3ce3797a267d71a6, rootof b4cc56a71a21baeb, core 692dacf1cc791419, opaque c7e1a7ca3a110ebb,
   scope 12e06b0586faee40, loop 09238b2537e54383, zero d9ed3534a2093027. Rust runs made 0 Python solvers.
3. **Plants:** part B: 5 of 6 caught on dev and fuzz; part C1: 2 of 3 caught on dev and fuzz. The two void plants are named
   below (table).
4. **Quiet handlers, suite:** 39 rows in 2 tests, the same multiset as base: `_consistent` AttributeError, 34 on `_ok` and
   4 on `_rb_clauses` (the named needs-internals case), and `Engine._build_context` "Already mutably borrowed" 1 in
   `test_protocol_on_fuzz` (the 46-stub cause). `caught` rows per id match base (0 differ). **Quiet catches at
   engine.py:1906: 1**, in the suite, as on base. There are 0 on dev, fuzz, seed1 and the eight extra workloads: their
   handler files have 0 rows. The plant runs' handler files have rows (`ad-kind-swap` and `spec-row-flip`: dev 2, fuzz
   315), which shows the counter fires. TermFault 0.
5. **Known differences:** none. Tests phase: 625 passed (the 6d list + test_relations_core.py, test_term_ids.py,
   test_adapters_core.py). DIRECT: `relations_direct.py 300 0`, `dispatch_direct.py` and `common_direct.py` exit 0;
   `common_direct.py common-facts-drop` fired 8 with 6 DIFFERENCES (the control plant, caught).

## Plants (fired; D = DIFFER)
| part | plant | item | dev | fuzz | other workloads | caught by |
|---|---|---|---|---|---|---|
| B | ad-lra-shared | `LRAAdapter.register` (shared-term recording, adapters.rs:133) | 1,370 D | 33,953 D | scope 695 D, zero 4,501 D | dev, fuzz, scope, zero |
| B | ad-euf-node | `EUFAdapter.node_term` (adapters.rs:377) | 0 | 0 | 0 everywhere; suite 23 fires in 9 files, no outcome change | **void** (expected) |
| B | ad-kind-swap | `make_adapter`'s kind (relations_core.rs:2201) | 254 D | 4,191 D | scope 147 D, value 396 D, zero 1,439 D | dev, fuzz, scope, value, zero |
| B | ad-euf-shared | `EUFAdapter` shared terms (adapters.rs:408) | 465 D | 7,835 D | scope 185 D, value 394 MATCH, zero 1,441 D | dev, fuzz, scope, zero |
| B | spec-row-flip | `spec_row` (part A) | 1,535 D | 39,216 D | scope 729 D, value 3,048 D, zero 6,211 D | dev, fuzz, scope, value, zero |
| B | adapter-fresh | `_adapter` (part A) | 3,162 D | 80,339 D | scope 1,575 D, value 592 D, zero 14,049 D | dev, fuzz, scope, value, zero |
| C1 | pay-neg-twice | Rust `Negated` (payloads.rs:103) | 0 | 0 | 0 everywhere, suite 0 | **void on workloads**¹; test_adapters_core under `rust_plugin` |
| C1 | pay-int-offset | Rust `Integral` (payloads.rs:141) | 556 D | 18,488 D | scope 230 D, value 319 MATCH, zero 1,316 D | dev, fuzz, scope, zero |
| C1 | pay-eq-flip | Rust `EqAtom` (payloads.rs:200) | 511 D | 12,389 D | scope 191 D, value 197 D, zero 2,067 D | dev, fuzz, scope, value, zero |
| control | theory-no-assume | scope | 1,087 D | 5,918 D | | dev, fuzz |
| control | al-drop-delta | 5c6 | 197 D | 2,631 D | | dev, fuzz |
| control | common-facts-drop | 6d | 79 D | 60 D | | dev, fuzz |

All part B and C1 plants fire 0 on core, f6, loop, opaque and rootof, which don't reach the adapters (their `ad:` counters
are all 0, below).

¹ **pay-neg-twice: reached only through the adapter API, not through the engine.** The engine never builds `Negated`:
relations.py:526 lowers `ne` to `Not(eq)`, and theories get only eq/lt atoms (relations.py:366 `RELATION_ATOMS`). So no
workload and no suite test on the engine path reaches it (`ad:negated_new` 0 everywhere). tests/test_lra_adapter.py
registers `Q.ne` atoms through the public adapter API, and `test_rust_adapters_with_rust_theories_pass_the_adapter_tests`
(test_adapters_core.py) runs it under `rust_plugin` + `ad_swap`. Rerun by sa-port-149 on orion from the landed tree 4dd2ed9 (built here, .so sha256 524af627…; imports from the clone, `~/sa-rust-ids-work/sa-port-149/negcheck/`): without the plant test_adapters_core.py passes (2 passed; the inner adapter run 298 passed); with `SLICE_SESSION_PLANT=pay-neg-twice` the inner run has 2 failed, 296 passed (the truncated assertion shows `test_model_is_consistent_with_sympy`; sa-port-140 named the other `test_ne_and_eq_through_solver`), so the test fails. **Caught.** The bar's own tests phase ran without plants, so this catch is from the separate run, not from BC2.

`ad-euf-node` is void as expected: `EUFAdapter.node_term` isn't called on dev or fuzz. In the suite it fires 23 times in 9
files with no changed outcome, so the suite doesn't catch it either. It goes on the owed list (a workload that reaches
`node_term`).

## Reached (counters, Rust run)
| workload | lra_new | euf_new | lra_register | euf_register | integral_new | eqatom_new | negated_new | cb_py_payload | integral_to_py | cb_factory | cb_memoized | cb_constant_bounds | cb_parse | cb_structural | cb_interned | cb_theory_new |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev | 199 | 198 | 1,495 | 1,501 | 554 | 526 | 0 | 0 | 0 | 0 | 5,508 | 0 | 1,501 | 918 | 526 | 397 |
| fuzz | 3,019 | 3,018 | 36,397 | 36,397 | 18,547 | 12,733 | 0 | 0 | 0 | 0 | 164,954 | 0 | 36,397 | 26,151 | 12,733 | 6,037 |
| scope | 136 | 135 | 701 | 701 | 230 | 191 | 0 | 0 | not recorded | 0 | 2,472 | 0 | 701 | 413 | 191 | 271 |
| value | 198 | 198 | 0 | 197 | 319 | 197 | 0 | 0 | not recorded | 0 | 2,626 | 0 | 197 | 394 | 197 | 396 |
| zero | 557 | 556 | 5,514 | 6,278 | 1,740 | 2,803 | 0 | 0 | not recorded | 0 | 18,671 | 0 | 6,278 | 3,791 | 2,803 | 1,113 |
| core, f6, loop, opaque, rootof | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | not recorded | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Counters from `*-rust.session.json` (Rust's `ad:` counters); `ad:integral_to_py` is in term_live's COUNTS, which only dev and
fuzz dump (`*-rust.knowledge.json`: absent, so it never fired). Both `ad:cb_py_payload` and `ad:integral_to_py` fire only when a
Rust adapter pairs with Python's own theory: shown firing by test_relations_core's `test_same_core_python_methods_match`
(sa-port-138), and 0 on every workload, as expected on the default path. `ad:cb_constant_bounds` 0 everywhere: no
workload's LRA atom has a constant needing bounds through the adapter. So every moved item is reached on dev, fuzz, scope,
value and zero, except `Negated` (adapter API only, footnote 1) and `EUFAdapter.node_term` (void).

## Step 0 and the module count
**Step 0's answer:** relations.py counts whole. `AdapterSpec`'s fields are read once (`spec_row`, part A), and the default
specs no longer call `spec.factory()` per session: `ad:cb_factory` is 0 on every workload above, with 397 Rust adapters
built on dev (`ad:cb_theory_new`). `Uninterpreted` and `AdapterSpec` stay Python types as input.

**Module count (count rule): 12 of 32**, was 11 at 6d: relations.py added. (The brief's "8 of 32" counts relations.py over
the old 7; registry.py and templates/__init__.py already count from 6g(a) after step 0's two passes, and table.py and
`_common.py` from 6d.) Footnotes: table.py, kept paths only; `_common.py`, `const_value`; realroots and `value_units` are
wired, and neither dev nor fuzz reaches them. constfield.py's 6 rows are part C2 (not counted; the module isn't whole).

## Kept reasons (Rust run, share of queries, against 6d's base)
| workload | out-of-scope | refused | named exceptions |
|---|---|---|---|
| dev | 24/1,985 (1.21%), base 1.21% | 0, base 0 | |
| fuzz | 0, base 0 | 0, base 0 | |
| f6 | 0, base 0 | 13/2,902 (0.45%), base 0.45% | algebra Float 10, lra callback on a derived term 1, scaffold rebuilt form differs 2; all equal to base |
| value | 0, base 0 | 15/3,742 (0.40%), base 0.40% | algebra Float 15, equal |
| opaque | 0, base 0 | 7/2,546 (0.27%), base 0.27% | algebra infinity/nan/Float 2, infinity or nan 5, equal |
| core, rootof, scope | 0, base 0 | 0, base 0 | |
| loop, zero, seed1 dev/fuzz | 0 (seed1 dev 1.21%), no base row | 0, no base row | |

No share rose. (6d's report gave dev out-of-scope as 24 of 1,221, 1.97%; bar_sum.py divides by all 1,985 queries. The count, 24, is the same.)

## Not run
Moved to "before any backend PR", and none quoted as met:
- the mutant 2, 5, 6, 7, 9 rerun and mutlive's control;
- the boundary rescore and suite column;
- the final drop score and its lost rows;
- the suite split with Python's counter;
- `order:_rows`' evidence (not caught meanwhile);
- the `_forms` guard test;
- history reruns (seed1 was run, above);
- forced moves;
- the native path;
- timing.

Also not run: the suite under the caught plants (SUITE_PLANTS was only the two void ones). Part B's earlier bars B1 and B2,
and BC1 (de64ee2), were stopped as superseded; none is a landing bar.

Other notes:
- Mutants 2, 5, 6, 7, 9 still rest on the API fuzzer alone. 10 of the 25 boundary mutants have no real-engine catch, and
  the boundary suite column wasn't run.
- **Speed not measured.**
- The `_n_conflicts` view in rust_plugin.py is a test-plugin shim, not a port (64 tests).
- `test_incremental_matches_fresh`: its public-API family landed with 5c7-tests as `tests/test_public_incremental.py` (34
  tests), beside `tests/test_solver_incremental.py`, whose internals-based family is untouched. All 34 passed on Rust here.
- `tests/test_relations.py::test_equality_sharing_is_needed_and_works` is unedited and still named needs-internals.
- Part A's slip (tested f2e70ba, pushed d91ee15 over 6g(a)'s source) and bar-A2, which matched bar-A on every item, so
  d91ee15 stands: see the addendum above. bar.sh's push guard, which lands with part B, now refuses such a push; it passed
  here because the incoming diff was docs only.
- Owed list (for the architect to append): a workload reaching `EUFAdapter.node_term` (`ad-euf-node` void on every workload,
  suite fires without a catch); `Negated` reached only through the adapter API.
