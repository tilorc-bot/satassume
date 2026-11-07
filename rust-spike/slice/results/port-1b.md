# Component 1b, LRA constants: landing report (issue 323)

Constants now run in Rust in the real engine: `lra_backend.py` keeps no Python theory behind a session, and every number runs in the core. **The state transfer is deleted (condition 6), with `_Move` and `move_every_call.py`; `identity_rule.py` stays with its moves removed.** Nothing suggested it had to outlive 1b.

**This adds 1 of the 32 runtime modules: `lra_cert.py`, whole.** All 11 names the inventory lists for it have a Rust counterpart in `solver_rs/src/lra_cert.rs`. **`constfield.py` isn't counted as whole**, by the planner's ruling: there's no per-query term table on the engine path, so `_from_sympy` stays on Python. `num()` makes a Python Element and `Num::from_py` converts it, a boundary component 4 removes. Python stays the default and the reference; the backend stays optional. No heuristics added or changed.

**Tested source: `cae6663`, on `rust-slice` 19ed342. Landed on dcfc1af without a full rerun, under the planner's rule:** a rebase needs one only if the incoming diff changes code the run executes.

- **Incoming diff, 19ed342 to dcfc1af:** `_common` (6 commits, to 4b2f12b) and `realroots.py` (3 commits, to dcfc1af). 0 diff lines in `satassume/`, `tests/`, `pyproject.toml`, `backend.py`, `rust_plugin.py`, `live.py`, `lra_backend.py`, `lra.rs`, `lra_cert.rs` or `constfield.rs`.
- **Crate:** `term/knowledge.rs` and `term/py.rs` gain new items and new methods; their removed lines are imports only, and every hunk was read by position, so no existing function body changes. `realroots.rs` is new. `lib.rs` gains 2 lines, `mod realroots` and `realroots::register(m)?`. **That register does run at import in rust mode.** It adds 6 functions and has no statics; nothing on the run path calls them.
- **`knowledge_live`:** `git grep` finds neither it nor `realroots` in `backend.py`, `rust_plugin.py`, `live.py`, `lra_backend.py`, `handler_count.py` or `run_suite.sh`. Runtime check on the landing tree, after `backend.install()` and one `ask`: `knowledge_live`, `convert`, `term_shadow`, `lazy_reads`, `realroots_cmp` and `knowledge_rootof_wl` aren't loaded.
- **New test files** `test_knowledge_common.py` and `test_knowledge_realroots.py` sit in `rust-spike/slice`; `testpaths` is `tests`, so the suite doesn't collect them.
- **Short check on the landing tree, orion (aarch64), merge ee064af:** build, sha256 starts fa465706d8ee; fresh dev MATCH, 1,985 queries, 3,332 sessions, answer digest as below, 0 handler rows; `test_lra_exhaustion.py` and `test_constfield.py` on Rust, 68 passed, 3 skipped, 1 failed, the changed test below.

Build on pareto1 (x86_64), sha256 starts 1cb066f17514. Full runs on pareto1. Output: `pareto1:~/sp51/out/land/`, read copies and the short check in `~/sa-rust-ids-work/sa-port-57/land/` on orion. The job was started by sa-port-51 and read by sa-port-57.

## The bar

| # | Item | Result |
|---|---|---|
| 1 | Suite by id, Rust solver, EUF, LRA with constants, and transfer, shuffled | **5,960 / 77 / 46, plus 1 failure explained below** (124 failed), base 5,961 / 77 / 46. 6,125 ids, none added or gone, **1 outcome changed** against `sa-port-38/s1/rust`. 23 skipped, 18 xfailed |
| 2 | Fresh engine, dev 1,985 and fuzz 3,000 | **MATCH on both.** dev 3,332 sessions, fuzz 4,943: 0 differ in answers, messages, session counts, end state, stream or LRA state. Answer digests `31cd0945c07f02a6`, `173502b6ef285ad6`. 0 Python solvers made on Rust |
| 3 | Planted bugs through that comparison | **2 of 2 caught, `LRA_MUT` 6 and 7; the unmutated rebuild, 0, reads MATCH.** Each differs in **1 session of 3,332**, in end state and stream, not in answers or LRA state. That's a thin catch: dev only, and one session |
| 4 | Quiet firings on Rust, that suite run | **39 rows, 2 tests**, both already named, the same rows as the base. **0 findings** |
| 5 | Known differences | One, the changed test below, with its cause. 0 in answers or read state on fresh or history |
| + | Constants history, added by the planner's ruling | Rust against Python: **0 answers, 0 messages, 0 end states, 0 streams, 0 session counts differ in all 14 runs.** Below |

These `LRA_MUT` numbers are plants in `lra.rs:1342`, the dirty set's order. They aren't the boundary mutants 6 and 7 on the not-run list. This run settles the open question of whether they fire on this core: they do.

**The 5,960 by firing, on Rust:** 5,959 with no Rust-only firing, 1 with one (`test_ci_stream_reports_only_what_replays`). 0 tests fire on Python. So the 5,960 still includes that test.

S's standing: S's gate is met except for the 46 named stub failures, one cause. They stay listed in number 3, and the crate is unchanged for them. The `_n_conflicts` view in `rust_plugin.py` isn't a port: it's a test-plugin shim, and moved 64 tests.

### The changed outcome: kept on Python, with reason

**`tests/test_lra_exhaustion.py::test_split_beyond_the_certificate_bound_counts_as_exhausted`** went from passed to failed, at :288 (`exhausted` False). It's the only test on the kept-on-Python list.

- **Cause:** it patches `LRATheory._certificate` at :282 with a small bound. The Rust core's `_branch` reads its own certificate, not the Python attribute, so the patch has no effect. It's the case the 1b ruling sends to this list. It's the only such patch in `tests/`.
- **Python:** passes, in this source's Python suite.
- **What's lost:** the test's unpatched half still runs on Rust and passes, but nothing else in `tests/` drives `_certificate`'s bound to a small value through the theory on Rust.

No other test newly needs a real Python theory: the other 123 failures are the base's, by id.

### Quiet firings on Rust

| Test | Outcome | Rows | Site, type, text | Standing |
|---|---|---:|---|---|
| `tests/test_invariants.py::test_ci_stream_reports_only_what_replays` | passed | 34, 4 | `_consistent`, AttributeError, `'Solver' object has no attribute '_ok'`, `'_rb_clauses'` | The named needs-internals case |
| `tests/test_transfer.py::test_protocol_on_fuzz` | failed | 1 | `Engine._build_context`, RuntimeError, `Already mutably borrowed` | The named firing, the 46-stub cause, `tests/theory_harness.py:242` |

- **The counters fire:** `suite_plant_handlers.py` fired `_consistent` and `Engine._build_context` on both Rust and Python, a planted ValueError at each. Both plant runs: 2 passed.
- **Quiet catches at `engine.py:1906` (`complete_check`):** suite, **1 on Rust** (that `test_protocol_on_fuzz` row), 0 on Python. Fresh, 0 rows with any catch on either backend, dev or fuzz. History, 0 handler rows.
- **Uninterpreted, counted but re-raised:** 10 in the suite (7 at `_consistent`, 3 at `consistent_by`), the same on both backends.

### Constants history

**The ruling's question doesn't arise in the form asked: there's one registry, not two.** Rust reads Python's `_CONSTANTS` live by index (`constfield.rs:1085-1089`) and caches nothing about a constant, so the two can't disagree on order, and there's no smallest case to report. That rests on reading that code, plus the runs below. Python's global registration order stays as history dependent as it is today, on both backends.

14 runs on dev and fuzz, Rust against Python on the same query, order and seed, on `cae6663`: recorded, two shuffles and `twice` in one persistent process, `fork` as a fresh child per query, and two other hash seeds. All 0 differences. Answer digests are the same across all 12 runs of the recorded query set. Each backend against its own recorded run:

| Run | Answers moved, either backend | State moved, dev (Py = Rust) | State moved, fuzz (Py = Rust) |
|---|---:|---:|---:|
| shuffle1 | 0 | 335 | 86 |
| shuffle2 | 0 | 358 | 91 |
| fork | 0 | 1,549 | 2,981 |
| seed1, seed2 | 0 | 0 | 0 |

Limit: "state moved" isn't split by cause, so these runs don't show how much of it comes from registration order. They show the two backends move together.

## Choices named

- **`certified` and `certified_with`: answered from the same Rust port `_branch` uses.** The Rust `LRATheory` inherits Python's properties (`lra.py:417`, `:427`), which call `_certificate`, which is `LraCore.certificate` (`lra_backend.py:89`). Checked by a spy on `_certified_atoms()`: 3 calls, all reaching `LraCore`, with Python's values (True, True, False). `test_certificate_rational_rows_and_pi_bounds`, `test_certificate_reads_the_constfield_limits` and `test_certificate_refused` pass through it on Rust, so the earlier "no test through the theory" no longer holds. No extra code was needed, so no test went on the kept list for this.
- **Private reads:** `__getattr__` serves them read-only from the state dump, with no theory behind it. **A test-plugin shim, not a port:** 236,413 views in this suite run.
- **`Num::from_py`:** has no counter, so **this report quotes no speed number.** One must be added before anyone quotes one.

## The gcd

**`heu_gcd` stays, with a size guard, and its failures go to a counted, read-only callback to Python's `_sympy_inner_gcd`** (`constfield.rs:774`, `:800`). `rgcd` is deleted. The callback and any further gcd port are on the backend PR list. Python's install patch is dropped: Python-side arithmetic is what Python runs today.

| Planner's check | State | Evidence, `~/sa-rust-ids-work/sa-port-51/gcd/` unless named |
|---|---|---|
| 1. Acceptance checked | Met by sa-port-47, on the **pre-guard** build; plants 108, 111. **Not rerun on the guard** | `sa-port-47/gcd/` |
| 2. Counter | Met: `cf_gcd_counts`, `cf_gcd_guard_count` | |
| 3. Hang gone | Met on sa-port-42's input, then the guard's probe | `sa-port-47/gcd/stall/`, `probe-guard.txt` |
| 4. Differential, multivariate | **Met on the guarded build, 0 mismatches** | `large-dump.txt`: seed 20261107, 20,000 ops, 4 vars, degree 3: 43,844 compared; 5,273 heuristic, 30 callback, 30 guard rounds. `deg-guard.txt`: seed 11, 4,000 ops, 3 vars, degree 10: 26,544 compared; 3,485 heuristic, 148 callback |

**Guard:** `MAX_IMAGE_BITS = 1 << 15`, at the top of each round. Plant 113, guard off, 60 s limit: 36,024 bits 0.91 s, 90,908 bits 30.7 s, 2 of 18 shapes hit the limit, so the probe catches it.

**The unguarded stall:** sa-port-47's `large.txt` timed out at 50 min, on the same seed. Its Python stack ends in `op_once`'s `rf(a2, b2)`, so the time is inside Rust's `cf_op`. Python can't see further, so that it's `heu_gcd` is an inference from the guarded build finishing in about 2.5 min, not shown.

Limits:
- **One seed per shape** in the probe: 18 shapes, seed 1.
- **The guard bounds each image, not the whole gcd.** Up to 6 rounds at each level multiply, and that worst case wasn't constructed.
- **The limit is a judgement from timings on loaded orion,** which the ruling allows, since firing is only a speed number.
- **The start's argument is checked only by the planner's reading,** not formally. Mahler's (4) and (5) were checked in the ems.press reprint by extracted text, whose OCR garbles the sign in (4).
- **Sa-port-42's 3 surviving planted bugs (102, 105, 107) are still unproven.**

## The transfer, gone

**Results kept:** dev 113 Rust / 109 moved, fuzz 2,569 / 623, suite 42,661 / 2,697 moved in 239 tests, all natural moves at level 0. `identity_rule.py` 14,424 sequences, 344,304 answers, 0 differ (hook level, plain Fractions, moves at level 0). The object rule is `port-1a.md`, "The rule on which object Python keeps".

**Condition 4,** as ruled: not met for a bad state. It's moot on this source, because the code is gone.

**What now covers the sessions that moved:**
- **Dev and fuzz:** those sessions run on Rust throughout, 222 and 3,192 LRA sessions, exactly the old totals, 0 moved. All sit under the state comparison above.
- **The suite's 2,697:** they run on Rust and pass, but **there's still no state comparison on the suite.** Their passes rest on the tests' asserts plus the counter. This run: 46,039 LRA sessions in 2,427 tests, 0 moved, against 46,636 on the base; the gap wasn't explained, and no outcome moved except the one above.
- **Moves during search:** no longer exist. Constants during search on Rust are covered by fresh and history, not by forced moves.

## Carried from 1a, unchanged and not rerun here

- **THE DROP:** 54 by comparison, 27 only by the state read, 2 not caught (`order:_forms`, now equivalent by the ruling; `order:_rows`), 0 never effective. 68 / 13 / 2 / 0 stays provisional and not quotable until the rerun; the cause of the three mutants' lost rows is still unknown.
- **PLANTED PORT BUGS:** 14/18 through `ask`, on df393bb. Not caught through `ask`: `negated_parity`, `touch_skipped`, `forget_skipped`, `last_object`. Hook-level catches aren't real-engine catches.
- **QUIET COUNTER:** not a zero, and 5,961 includes `test_ci_stream_reports_only_what_replays`. So does this run's 5,960.
- **`order:_rows` is NOT CAUGHT,** and its first run's control read 0, so it isn't evidence. `lra_text` now keeps the order, so a pivot-then-check case can supply it. Not run.

**Standing rulings:** mutants 2, 5, 6, 7, 9 rest on the API fuzzer alone. 10 of the 25 boundary mutants have no real-engine catch as last stated, and the boundary suite column wasn't run. A public-API version of `test_incremental_matches_fresh` is still due during the engine port, at the latest.

## Kept on Python

- **Queries, per the rulings:** Sum, Product, Integral (option A); queries under a non-default registry. Not exercised separately by this run.
- **Permanent callback:** R9 `enclose` (`constfield.rs:1211`), read-only on input terms.
- **Temporary callback, backend PR list:** `_sympy_inner_gcd`, counted.
- **On Python by design:** `num`, `_from_sympy` and `lra_adapter.py`.
- **Tests:** the one above, and the 77 needs-internals and 46 stub failures, unchanged by id.

## Not run

**Before any backend PR, not run on this source:** the mutant 2, 5, 6, 7, 9 rerun and mutlive's control; the boundary rescore and suite column; the final drop score and its lost rows; `order:_rows`' evidence; the `_forms` guard test; the native path; timing. Forced moves have nothing left to force.

**Full runs weren't on the landing tree.** The suite, fresh, plants and history ran on `cae6663`; only the short check ran on the merged tree, under the planner's rule.

**Also not run:** `run_live.sh`; history on the mutants; counts with `--sympy`; speed; plants 108 and 111 on the guarded build. Before any backend PR, the planner's 1a "not run" list stands as in `port-1a.md`.

**Backend PR list, from this step:** porting SymPy's heuristic gcd and removing the callback; the smaller one-variable start, speed only; a `Num::from_py` counter; re-entering the solver from a hook is allowed on Python and raises on Rust, and through `_build_context` it would become a quiet unknown, so name it in the Rust backend's contract. PR 328, or its order, must be on main first.
