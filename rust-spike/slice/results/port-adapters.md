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
