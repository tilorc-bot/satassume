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

# Adapters step, part C2: pi_laurent on Rust, constfield's six output rows classed (issue 323)

Per the planner's C2 ruling (about 06:40 UTC 8 Nov): (a) the six rows are output/display conversion, (b) `Element._new` is
its own step after C2 and isn't here, and (c) `pi_laurent` moves if it's exact arithmetic. It is (Fractions and `_scale`,
with no SymPy evaluation), so it moved, and it isn't a named callback.

## What moved
- **`pi_laurent` (constfield.py:1325) on Rust** (c62f25d, sa-port-152; was e12e622 before the rebase over 6g(b)):
  constfield.rs `pi_laurent_elem` ports it for an Element; pi's index is read once from `_PI_INDEX`. lra_cert.rs `laurent`
  (~:82, now `pub(crate)`) calls it, so the certificate makes no Python call and no `Element._new` at that boundary (it
  was `module.pi_laurent(x.to_py())` at lra_cert.rs:87). Counter **155 `cf:pi_laurent`** (Element bounds only).
- **Plant 111 `cf-laurent-rational`**: an Element bound reads as its rational part, with its pi terms dropped (a wrong
  value, not None). **112 `cf-laurent-refuse`** and **113 `cf-laurent-raise`** aren't plants. They replace the Python hook
  (`pi_laurent`) that test_term_live.py's two handler tests at lra.rs:935 used, because nothing in that handler calls
  Python now.
- **`cert` workload** (3a34da4, sa-port-153; was f296ed1): `cert_wl.py`, `live.py cert`, 61 queries. Built from
  `LRATheory._branch`'s Y skip (lra.py :930-960) and lra_cert's magnitude of `pi_laurent` (lra_cert.py :145-158), not
  from any eval set. It exists because the plant is void on dev and fuzz (see Plants).
- **(a), the six rows** (`Constant`, `Constant.__repr__`, `_coerce_foreign`, `Element.to_sympy`, `Element.__repr__`,
  `_sympy_constant`): not port, output/display conversion. `Constant` stays Python as the registry entry and the
  `enclose` receiver. Evidence (cf_trace, Rust mode, 12 workloads, table below): `Element.__repr__` is called only from the
  harness (state.py `f`/`lra_text`/genexpr/`fast`, live.py `show`): dev 2,870, fuzz 37,501, cert 533, the same before
  and after. The other five are 0 on all 12 workloads. Positive control (sa-port-153 `trace/control.py` ->
  `control.txt`): every wrapper counts when it's called, so the zeros aren't false. Rust reaches Python constfield only by
  call-time lookups (constfield.rs:1232 `call_method1("enclose")`, :2066 `_new`), which the wrappers see.
  **`_coerce_foreign`'s path:** its only caller is `Element.__eq__` (constfield.py:1214) with a non-constfield operand,
  for example a SymPy number. The suite reaches it at tests/test_constfield.py:845 (`PI == sympy.pi`). No engine path
  reaches it on any workload, so it's a Python removal candidate, next to `_bound`.
- **Shared-file changes:** test_term_live.py (its two lra.rs:935 handler tests now use plants 112/113 instead of a
  Python `pi_laurent` hook); session_live.py (plant list + `cf-laurent-rational`); `cf_op` (constfield.rs, a new
  `pi_laurent` op for test_cf_laurent.py); live.py (the `cert` entry); cert_wl.py (new); relations_core.rs (plants
  111-113, `unplant`); session.rs (counter 155). New step test: test_cf_laurent.py (2 tests: matches Python on more than
  100 Laurent and 30 None cases, more than 200 of them Elements; counter and plant fire).
- **Numbers C2 holds:** counter 155, plants 111-113. 5c7 (sa-port-154) takes numbers after them.

## SHAs and incoming diff
Tested **3a34da4** (port/adapters on rust-slice b838d3f, 6g(b)'s landing). Landed **29ee93e** on rust-slice by
`PUSH=1 bar.sh land 3a34da4` (08:10 UTC 8 Nov). **Incoming diff: none** (rust-slice was still b838d3f, the tested base).
tested..landed is HANDOFF-sa-port-153.md only: docs, which no run executes, so the guard passed. Rows: pareto1
`~/sp19/sa-rust-ids-work/sa-port-153/bar-C2b/` (`sum.txt`, `commands.txt`, `config.txt`), `.so` sha256 637f2f0b….
PLANTS `cf-laurent-rational` (C2), `pay-int-offset` (C1), `ad-kind-swap` (B), controls `theory-no-assume` (scope) and
`al-drop-delta` (5c6); DIRECT as BC2, with `common_direct.py common-facts-drop` (6d). WLS `f6 value rootof core opaque
scope loop zero wiring cert`; SEED1=1; SUITE_PLANTS=`zero` (it picked none: every plant fires on dev or fuzz).

**Base caveat:** the suite base is BC2's rows (`sa-port-140/bar-BC2/suite`, before 6g(b)). 6g(b)'s own bar ran against
the same BC2 rows and found new 0, gone 0, changed 0, handler multiset equal (results/port-6g.md, 6g(b) section, in
b838d3f; the architect cites its report as f2ffeff). So BC2 stands as C2b's suite base with b838d3f in the tree, and no
new base run was needed. The kept-reasons base is BC2's too. `wiring` has no BC2 row, so it's checked against 6g(b)'s bar.

## The bar (sa-port-153/bar-C2b)
1. **Suite by id against BC2's rows:** 5,992 passed, 126 failed, 23 skipped, 18 xfailed, 6,159 ids. New 0, gone 0,
   changed outcome 0. Passed: 5,991 with no firing, and 1 with a firing (`test_ci_stream_reports_only_what_replays`).
   S's standing: S's gate is met except for the 46 named stub failures, one cause.
2. **Fresh dev and fuzz:** answers and state MATCH, with every control MATCHing. Dev 31cd0945c07f02a6 (1,985 q), fuzz
   173502b6ef285ad6 (3,000 q); traced end states MATCH on both. Seed1 dev and fuzz MATCH. The ten extra workloads MATCH,
   each with a Python control: f6 fc0c2f738a1f6dbf, value 3ce3797a267d71a6, rootof b4cc56a71a21baeb, core
   692dacf1cc791419, opaque c7e1a7ca3a110ebb, scope 12e06b0586faee40, loop 09238b2537e54383, zero d9ed3534a2093027,
   wiring a0df9fd43e5180c1, **cert 6a09c059eb266747** (new). Rust runs made 0 Python solvers.
3. **Plants:** C2's `cf-laurent-rational` is caught on cert (2 answers, below), void on dev and fuzz for a stated reason,
   and also caught by the suite (separate run). B's and C1's controls and the scope/5c6 controls are caught (table).
4. **Quiet handlers, suite:** 39 rows in 2 tests, the same multiset as base: `_consistent` AttributeError, 34 on `_ok`
   and 4 on `_rb_clauses` (the named needs-internals case), and `Engine._build_context` "Already mutably borrowed" 1 in
   `test_protocol_on_fuzz` (the 46-stub cause). `caught` rows per id match base (0 differ). **Quiet catches at
   engine.py:1906: 1**, in the suite, as on base. There are 0 on dev, fuzz, seed1 and the ten extra workloads (their
   handler files have 0 rows). The plant runs' handler files have rows (`ad-kind-swap`: dev 2, fuzz 315), which shows
   the counter fires. TermFault 0.
5. **Known differences:** none. Tests phase: 627 passed (BC2's 18 files + test_cf_laurent.py). DIRECT:
   `relations_direct.py 300 0`, `dispatch_direct.py` and `common_direct.py` exit 0; `common_direct.py common-facts-drop`
   fired 8 with 6 DIFFERENCES (the control plant, caught).

## Plants (fired; D = DIFFER)
| part | plant | item | dev | fuzz | cert | other workloads | caught by |
|---|---|---|---|---|---|---|---|
| C2 | cf-laurent-rational | `pi_laurent_elem` (constfield.rs), read by lra_cert.rs `laurent` | 121 MATCH | 200 MATCH | **119 D** | 0 on the other 9 | **cert** (q53, q59: True -> None; 34 end/stream/lra states); **suite** (2 tests, separate run) |
| C1 | pay-int-offset | Rust `Integral` (payloads.rs:141) | 556 D | 18,488 D | 250 D | scope 230 D, value 319 MATCH, zero 1,316 D | dev, fuzz, cert, scope, zero |
| B | ad-kind-swap | `make_adapter`'s kind (relations_core.rs) | 254 D | 4,191 D | 62 D | scope 147 D, value 396 D, zero 1,439 D | dev, fuzz, cert, scope, value, zero |
| control | theory-no-assume | scope | 1,087 D | 5,918 D | 122 D | scope 299 D, zero 1,263 D; core 243, f6 10, loop 244, opaque 32, rootof 369, value 322, wiring 5,016 MATCH | dev, fuzz, cert, scope, zero |
| control | al-drop-delta | 5c6 | 197 D | 2,631 D | 61 D | scope 36 D, value 197 D, zero 542 D | dev, fuzz, cert, scope, value, zero |
| control | common-facts-drop | 6d | | | | common_direct.py: fired 8, 6 DIFFERENCES | direct |

**cf-laurent-rational is void on dev and fuzz, with the reason:** the certificate's `Y` (lra.py :930-960) is
`(nt+1)*had*(X+1)*2**16`, far above every split there, so dropping the pi terms of a bound never changes a decision
(cert_wl.py's docstring). On `cert` (pi bounds near Y), the two-term `t + y` form at c = 10**8 loses its answer.
Single-variable bounds are decided by `assert_lit`'s rounding, with no split. **Suite catch** on the tested source 3a34da4
(sa-port-156, orion, `~/sa-rust-ids-work/sa-port-156/sp/`; 8 LRA test files under `rust_plugin`, -n 3): without the plant
44 failed (all failing on BC2's base too: the stub cause and theory-level tests), with it 46: +
`tests/test_lra_exhaustion.py::test_certificate_rational_rows_and_pi_bounds` and
`::test_certificate_reads_the_constfield_limits`. The same as sa-port-153's run on e12e622.

## Reached (moved item, Rust run)
`cf:pi_laurent` (session.json of the bar's Rust runs): dev 121, fuzz 200, seed1 dev 121 and fuzz 200, **cert 115**, and 0
on f6, value, rootof, core, opaque, scope, loop, zero and wiring. They equal Python's former `pi_laurent` calls on the
base (table below), so every call moved. Reached by dev, fuzz and cert. Only cert's reach is caught.

## Constfield callbacks per workload, before and after
cf_trace.py (sa-port-140/152), Rust mode, one pass; before = rust-slice b838d3f, after = 3a34da4 (sa-port-156, orion,
`~/sa-rust-ids-work/sa-port-156/trace/`; the base tree ran with 3a34da4's harness live.py/cert_wl.py, which only adds
the cert entry). Answers' digests are identical between the two trees on every workload, with 0 Python solvers. Rows not
shown (`Element.to_sympy`, `_coerce_foreign`, `_sympy_constant`, `Constant.__repr__`, `_short`, the gcd trio) are 0 on
every workload, before and after.

| workload | Element._new | pi_laurent | Constant.enclose | Element.__repr__ (harness) | _generic | constant | Constant.__init__ |
|---|---|---|---|---|---|---|---|
| dev | 703 | **121 -> 0** | 100 | 2,870 | 1 | 0 | 0 |
| fuzz | 1,552 | **200 -> 0** | 0 | 37,501 | 0 | 0 | 0 |
| cert | 163 | **115 -> 0** | 0 | 533 | 0 | 0 | 0 |
| f6 | 30 | 0 | 84 | 0 | 66 | 30 | 30 |
| core | 24 | 0 | 0 | 0 | 68 | 24 | 12 |
| wiring | 3 | 0 | 0 | 0 | 11 | 2 | 2 |
| opaque | 2 | 0 | 2 | 0 | 5 | 2 | 2 |
| value | 0 | 0 | 0 | 0 | 984 | 0 | 0 |
| rootof | 0 | 0 | 0 | 0 | 368 | 0 | 0 |
| zero | 0 | 0 | 0 | 0 | 1,478 | 0 | 0 |
| scope, loop | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

`Element._new`'s total doesn't change, but its callers do. On dev, lra_live `_rust` 460 and constfield `_env` 100 are
unchanged, lra_backend `check` goes 121 -> 69, and `_state` 117 -> 174. On cert, `check` goes 38 -> 8 and `_state` 4 -> 34.
The Elements that `check` stopped building are built by `_state` later, so C2 removes none. That's step (b)'s work.
`enclose` (R9) is unchanged.

## Module count
**13 of 32, unchanged** (count rule; checked against ~/dev/architect/STATUS.md's "Counted modules" list, not recounted):
solver, euf, lra, transfer, lra_cert; realroots.py, templates/atoms.py; registry.py, templates/__init__.py; scope.py;
table.py, _common.py; relations.py. Footnotes: table.py, kept paths only; `_common.py`, `const_value`; realroots and
atoms' `value_units` are wired, and neither dev nor fuzz reaches them (the suite reaches realroots). **constfield.py is
still not whole:** `Element._new`, `enclose` (R9, permanent), the gcd trio (`_to_dmp`, `_from_dmp`,
`_sympy_inner_gcd`), `_short`, `radical`, `_generic`, `constant` and `Constant.__init__` are still called back.
`pi_laurent` left the list. The six output rows are not port by ruling.

## Kept reasons (Rust run, share of queries, against base)
| workload | out-of-scope | refused | named exceptions |
|---|---|---|---|
| dev | 24/1,985 (1.21%), base 1.21% | 0, base 0 | |
| fuzz | 0, base 0 | 0, base 0 | |
| seed1 dev / fuzz | 1.21% / 0, base the same | 0, base 0 | |
| f6 | 0, base 0 | 13/2,902 (0.45%), base 0.45% | algebra Float 10, lra callback on a derived term 1, scaffold rebuilt form differs 2; all equal to base |
| value | 0, base 0 | 15/3,742 (0.40%), base 0.40% | algebra Float 15, equal |
| opaque | 0, base 0 | 7/2,546 (0.27%), base 0.27% | algebra infinity/nan/Float 2, infinity or nan 5, equal |
| core, rootof, scope, loop, zero | 0, base 0 | 0, base 0 | |
| wiring | 0 | 1/6,512 (0.02%) | lra callback on a derived term 1; no BC2 row, equal to 6g(b)'s bar (1/6,512) |
| cert | 0/61 | 0/61 | new workload, no base |

No share rose.

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

Also not run: the suite under a plant inside the bar (SUITE_PLANTS=`zero` picked none). The suite catch of
cf-laurent-rational comes from the separate 8-file run above. Bar C2 (f296ed1, before 6g(b)) was stopped at its plants
phase as superseded; it isn't a landing bar.

Other notes:
- Mutants 2, 5, 6, 7, 9 still rest on the API fuzzer alone. 10 of the 25 boundary mutants have no real-engine catch, and
  the boundary suite column wasn't run.
- **Speed not measured.**
- The `_n_conflicts` view in rust_plugin.py is a test-plugin shim, not a port (64 tests).
- `test_incremental_matches_fresh`: its public-API family landed with 5c7-tests as `tests/test_public_incremental.py` (34
  tests), beside `tests/test_solver_incremental.py`, whose internals-based family is untouched. All 34 passed on Rust here.
- `tests/test_relations.py::test_equality_sharing_is_needed_and_works` is unedited and still named needs-internals.
- Docs: port-ownership.md :101-105 and :132, and the TSV's constfield rows (pi_laurent landed 29ee93e Rust; the six not
  port; `Element._new`'s finisher "its own step after C2"). The md's summary count table (385/17/9 landed, 0/11/320 named)
  was already stale against the TSV before C2: the TSV has 524 `port` rows on Rust after C2, 523 before. It isn't recounted
  here.
- Owed list (carried from B+C1, for the architect): a workload reaching `EUFAdapter.node_term` (`ad-euf-node` void on every
  workload; the suite fires it without a catch); `Negated` is reached only through the adapter API, not the engine. New from
  C2: `_coerce_foreign` is a Python removal candidate next to `_bound` (no engine path).
- `Element._new` stays out of C2: its own step after C2 (ruling (b)), with the LRA-heavy workloads and a memo plant caught
  as a wrong value.
