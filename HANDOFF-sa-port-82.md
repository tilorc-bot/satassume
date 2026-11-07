# Handoff, sa-port-82: component 5, step 5a, bar met on 77d04e3, evaluator's A1 and A2 hold the landing

Head: `port/5a` 77d04e3 plus this file, on `rust-slice` d29e94b. Not landed. **A1 and A2 hold it**: `~/dev/architect/briefs/addenda/sa-port-5a-a1a2-ruling.txt` (short, read it) and the verdict `~/sa-rust-ids-work/sa-port-83/verdict.txt` (report 8783d16). B1 to B10 go on the backend PR list in the report. Fixing A1 and A2 changes source, so every run below reruns on the new SHA before landing. `HANDOFF-sa-port-81.md`, `-79`, `-77` and `-75` still hold the join reading, setup and traps, named differences and base map.

## A1 and A2: probes run, on orion, aarch64, 77d04e3, nothing fixed
`~/sa-rust-ids-work/sa-port-82/a1a2/`: `probe.py py|rust` and `cmp.py`; `py.json`, `rust.json`. Run with `PYTHONPATH=$CLONE:$W/sympy:$W/shim:$CLONE/rust-spike/slice`. Two `==` objects come from `Pow(a, a)` and `Pow(a2, a)` after a cache clear.
- **A1, confirmed at the boundary, both orders:** after `table.node_base(slot)`, `s.var('real', passed)` visits `passed` on Python and `slot` on Rust. Clauses and `v` are the same in this case.
- **A2, confirmed at the boundary, both orders:** `Tuple(a, b) == Args((a, b))` with equal hashes. With that node in the table, `table.var(P('sexyprime', Args))` gives `slots[v].expr` and `new_custom` an `Args` on Python and a `Tuple` on Rust.
- **Through `ask`:** A1, 6 queries (`real`, `positive`, `nonzero`, each order): same answers. **This is weak**: I didn't show the second object reaches `Session` with a slot and no visit. A2 through `ask` is **not probed**: it needs a registered extension with a 2-argument handler, `extensions.py:157-177`. The ruling wants both through `ask`.

## Fix design, read and not built
Both look small, so by the ruling fix them without arguing reach.
- **A1, direct entries:** `var` :674, `dvar` :682 and :700, `dvar_raw_py` :705. Before calling the core, if the node isn't visited and `node` isn't `objs[n]`, call `visit_id(node, n, None)`; `node_id` then finds it visited. Python visits first on these paths (`engine.py:392`, `:443`, `:452`), but a `Kind::Custom` in `var_id` raises before any visit, so don't visit for it.
- **A1, compile route:** `nid_in_formula` :214 refuses only with no slot. Refuse a second object whenever the node has no visit, `visited(n) == 0`, so Python's compiler visits `f.expr` itself. This may raise `refuse:object`: report it.
- **A2:** keep each custom atom's own expr, a map from `(pred, nid)` to the object, and have `make_atom` use it for `Slot::Custom` only. `P.__eq__` compares args, so Python's `custom` dict joins these too and keeps the first atom to reach `table.var`. A direct entry with no slot yet overwrites; `atom_fields` at :285 records in conversion, and a different expr there with no slot refuses, as `nid_in_formula` does; a slot already made reads nothing. Separate this from `objs`, which stays the slot's object.
- **Tests:** add both orders of each to `test_session_limits.py`: which object was **visited**, and `.expr`'s type. **Any new case in `_cases()` has to go in `_ids()` too**, or it never runs. `test_node_joined_first_object_is_the_first_seen` :237 pins named difference 1 (`mine(True)`); the A2 fix should end that difference, so change the test to say it matches, and correct its docstring. Sa-port-34's object rule, `results/port-1a.md:57`: the first object to reach, in the session. Python's `Session` keeps the first for slots and custom atoms and visits the one passed; the tests should say so.
- If a probe shows a different answer from Python, report the smallest case. If neither reaches an answer through `ask`, the direct tests stay and it lands.

## Results on 77d04e3 (x86-64, pareto0, .so 416a28a78897; a tree hash matched on both paretos, 748 files). All void for landing once the source changes.
- **Suite, `-n 8`:** 5,960 passed, 124 failed, 23 skipped, 18 xfailed. 6,125 ids. Against `suite-cea574c`: 0 new, 0 gone, 0 changed. Against `pr328-check/suite-rust`: 0 new, 0 gone, 1 changed, the known `test_split_beyond_the_certificate_bound_counts_as_exhausted`. `suite_report.py`: 5,960 / 77 needs internals / 46 re-entry, plus that 1 other.
- **Handlers:** 39 rows in 2 tests: `test_ci_stream_reports_only_what_replays` passed, `_consistent` AttributeError, `_ok` 34 and `_rb_clauses` 4; `test_protocol_on_fuzz` failed, `_build_context` "Already mutably borrowed" 1. So 5,959 passed with no firing, 1 with. Control on this source: 4 passed, 6 rows; live dev `--limit 60`: formula 1, complete_check 13, assumption_lits 46, verdict 1.
- **Dev and fuzz:** all 8 comparisons MATCH, digests 31cd0945c07f02a6, 173502b6ef285ad6, 0 Python solvers on Rust, handlers empty.

| | dev | fuzz | suite |
|---|--:|--:|--:|
| `refuse:object` | 17 | 30 | 3,709 in 190 tests |
| `join` | 0 | 0 | 53 in 12 tests |
| `refuse:depth`, `refuse:convert` | 0 | 0 | 0 |
| `py:compile` | 833 | 2,952 | 38,663 |
| `py:dvar` | 21 | 120 | 586,001 |
| `py:literal` | 44 | 1,957 | 24,745 |
| `py:var` | 4,032 | 134,774 | 910,612 |
| `py:node` | 14,769 | 177,962 | 5,273,665 |
| `py:table` | 32,783 | 574,631 | 10,197,910 |
| `rs:visit` | 2,482 | 16,537 | 1,000,493 |
| `rs:add_clause` | 2,696 | 60,597 | 2,814,030 |
| `rs:emit_callback` | 2,568 | 8,703 | 265,514 |
| `rs:ensure_vars` | 886 | 19,336 | 542,824 |
| `rs:def_implications` | 0 | 0 | 731 in 56 tests |
| `rs:neg_shared` | 0 | 0 | 38,663 in 98 tests |

- **`refuse:object`'s cost, speed and not answers:** 3,709 of 38,663 compile calls, but `rs:emit_callback` fell from 3,133,410 to 265,514 against cea574c, and `py:table` rose 842,715; every emit-callback change is in tests where it fired, the largest in `test_transfer_fuzz.py`, 311,003 to 261. `py:dvar` is new on dev and fuzz; it probably comes from the same refusals, not traced.
- **Bar 3, plants through `--so`** (`plants-table.txt`):

| plant | dev | fuzz | suite | limits file, 199 |
|---|---|---|---|---|
| `c198-and`, compile.rs, And's args reversed | 1,269 fires, DIFFER, end 708, stream 713, answers 0 | 4,430, DIFFER, end 2,395, stream 2,398, answers 0 | not run | 46 fail |
| `s425-have`, session.rs | 1,694, DIFFER, end 172, stream 173, answers 0 | 65,376, DIFFER, end 2,945, stream 2,945, answers 0 | 0 changed, on cea574c | 13 fail |
| `c204-or`, compile.rs, Or's first clause dropped | 0, MATCH | 0, MATCH | 7,897 fires; 229 failed, 5,854 passed, 19 xfailed | 20 fail |
| `s466-impl`, session.rs `_link` | not rerun | not rerun | 25 changed, on cea574c | 34 fail, 488 fires |

- **`_link`, corrects the brief:** "no comparison reaches it" holds for dev and fuzz only. `test_session_limits.py` compares Python and Rust and catches it; the planner accepted this as satisfying its item 4. **Same shape, new gap:** neither dev nor fuzz reaches `compile`'s `Or` arm, which `Implies` also goes through. The limits file and the suite do.
- **PR 334's tie:** 0 fires on dev, fuzz and suite (no `c166-tie-suite.fired`; `c444-true-suite.fired` has 95, so logging works in workers), on cea574c, and `compile.rs` is unchanged since. The tie itself was never reached; the plant logs only ties, so this doesn't say how often that line runs. `c393-key` also 0 in the suite.
- **`var-off`, still unexplained:** `var-off:PRED` (commit 77d04e3, off by default, `var-count` census in the report). `_var` sees 9 predicates with `v > 1`: extended_negative, extended_positive, extended_real, integer, negative_infinite, nonzero, positive_infinite, real, zero. **All 9 fired and DIFFER on both workloads**, answers moved on all but nonzero on fuzz (answers 0, end 47). The narrowest, nonzero, is 30 fires on dev and moves 1 answer. So no one-predicate version among those misses. A predicate outside them, such as `positive`, would fire 0 and MATCH: a candidate, not shown, because the original was never committed.
- **Sizing is reported, by sa-port-75, journal:** 5b about 4 to 6 sessions, 5c about 4 to 6, from source lengths only, nothing tried. Quote it as that.
- **`compile.py` can't count whole:** `ref.py` imports it, `engine.py:2211` calls `basis_formula`, `session_live` passes `_Lit`, and every `refuse:*` runs Python's compiler by design. Per the planner, `ref.py` follows the inventory, not on the query path.

## Setup
- Trees: `~/sp19/dev/sa-port-82` on both paretos at 77d04e3, .so in place. Scripts, orion `~/sa-rust-ids-work/sa-port-82/scripts/`: `job82.sh`, `build82.sh`, `buildplants82.sh`, `mkplants.py` (`mkplants82.py` on pareto1), `stepA.sh` (build, pareto1), `launchB.sh`, `stepB.sh` (suite, live, handler control, plants, var; pareto0, 22 minutes), `stepC.sh` (c204-or suite, limits against plants), `read_suite.py WORK BASE...`, `read_plants.py F`, `emitdelta.py`. Output `~/sp19/sa-rust-ids-work/sa-port-82/` on the paretos, read copies on orion. `launchB.sh` hard-codes the reason's SHA and a scratchpad path: change both.
- Sync: `git archive HEAD` from the repo root over ssh, as in `HANDOFF-sa-port-79.md`; compare `find . -type f ! -name SHA`, sorted with `LC_ALL=C`, to `git ls-files | sed 's|^|./|'`. cargo is on pareto1 only; shared leases queue behind quiet ones. Copy .so files through orion.
- `stepB.sh`'s var-off loop can be dropped for the rerun, since `session_live.py`'s plant isn't changing; it needs only suite, live, handler control, c198-and, s425-have, and the limits file.

## Not fixed, backend PR list
B1 to B10 in the verdict, including `table.slots` past the end panicking where Python raises `IndexError` (B3; `sync_transfer` stays in range).

## Errors of mine
My first `read_suite.py` keyed handler rows on the wrong field, so "passed with firing" read 0. I saw it before reporting; report ee45d12 has the right number. Report ee45d12 says "No known answer or read-state difference left unexplained", written before the evaluator: A1 and A2 overtake it. Report ee45d12's line "`test_session_limits.py` ... s466-impl fires 488 and fails 34" stands.
