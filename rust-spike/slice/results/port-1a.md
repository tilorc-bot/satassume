# Component 1a, LRA rational: landing report (issue 323)

`theories/lra/lra.py`'s rational core runs in Rust in the real engine; `lra_adapter.py` stays Python and calls it. **This adds 1 of the 32 runtime modules: `lra.py`.** `lra_cert.py` isn't ported and doesn't count. Python stays the default and the reference; the backend stays optional. No heuristics added.

**Moving a session to Python by state transfer is temporary scaffolding on this branch.** It goes no later than 1b and can't be in a backend PR. Moves during search are reached only by forced moves; every natural move below is at level 0. Forced moves weren't rerun on this source.

Landing source: `port/1a` rebased on `rust-slice` e5dd23f, tree 56a8f3e; only this report and the inventory row come after it. Build on pareto1 (x86_64), sha256 starts c22df485fecb. Output: `~/sa-rust-ids-work/sa-port-36/land2/`, on pareto1 and rsynced to orion.

## The bar

| # | Item | Result |
|---|---|---|
| 1 | Suite by id, Rust solver, Rust EUF, Rust LRA, shuffled, `-n 8`, pareto1 | **5,961 / 77 / 46**, base 5,961 / 77 / 46. 6,125 ids, none added or gone, **0 outcomes changed**. 23 skipped, 18 xfailed |
| 2 | Fresh engine, memos cleared, dev 1,985 and fuzz 3,000 | **MATCH** on both: 0 answers, 0 messages, 0 session counts, 0 ends, 0 streams, 0 LRA states differ. Sessions 3,332 and 4,943. Answer digests 31cd0945c07f02a6 and 173502b6ef285ad6 on both backends |
| 3 | Planted bugs through that comparison, dev | **`LRA_MUT` 6 and 7 both DIFFER**, on this source: 1 end and 1 stream, q1887, answers unchanged. 0, the same build unmutated, reads MATCH |
| 4 | Quiet firings on Rust, that suite run | **39 rows, 2 tests**, below. 1 is a finding, already named in `port-2.md` |
| 5 | Known differences | Below, each with its cause |

The fresh `.handlers` files have 0 lines, on dev and fuzz, both backends. That counter hasn't been shown firing on this path in this run, so the zero isn't quoted as a result. Those runs rest on the comparison.

## Sessions

An LRA session is one with an `LRATheory`. Sessions with none aren't counted here.

| Run | Rust throughout | Moved, by reason | Python from the start |
|---|---|---|---|
| dev | 113 | 109: `constant` 95, `constant coefficient` 12, `constant offset` 2 | 0 |
| fuzz | 2,569 | 623: `constant` 623 | 0 |
| suite | 42,661 (sessions minus moved) | 2,697: `constant` 1,945, `constant offset` 445, `constant coefficient` 307, in 239 tests | not split out |

- A moved session doesn't count as running on Rust. 95 of dev's and 501 of fuzz's moves are at call 0, so Rust did nothing in those sessions but refuse. The rest of fuzz's are at call 1.
- All 2,697 suite moves and all dev and fuzz moves are at level 0.
- **What covers what:** a wrong value after a move is only caught by the comparison. Dev and fuzz have it. Moved sessions in the suite don't, so their passes rest on the tests' own asserts plus the counter. Moved tests: 235 passed, 4 xfailed.
- **Condition 4, a failure that doesn't raise:** not met for a bad state. A transfer failing inside `_move` raises `TransferFailed`. Nothing checks a wrong value at the move itself.
- **Kept on Python with reason:** Sum, Product, Integral, non-default registries and `enclose`, per the rulings. 0 Python-from-the-start sessions on dev and fuzz, so none of these was reached there. Not exercised by this run.

## Quiet firings on Rust

From `handler_count`, that suite run. The planner's split: **of the 5,961 passed, 5,960 have no firing and 1 has one** (`test_ci_stream_reports_only_what_replays`). Python's counter wasn't run on this source, so "that Python doesn't have" isn't read for this split.

| Test | Outcome | Rows | Site, type, text | Standing |
|---|---|---|---|---|
| `tests/test_invariants.py::test_ci_stream_reports_only_what_replays` | passed | 34 + 4 | `_consistent`, AttributeError, `'Solver' object has no attribute '_ok'`, `'_rb_clauses'` | The named needs-internals case. This test has moved sessions too |
| `tests/test_transfer.py::test_protocol_on_fuzz` | failed, as on the base's Rust run | 1 | `Engine._build_context`, RuntimeError, `Already mutably borrowed` | **Finding**, same text and test as `port-2.md`. Not from 1a: `port-2.md` has it on every build, base included |

`catch_count` on the same rows: 49 catches. 38 AttributeError and 1 RuntimeError (`complete_check`) are the rows above. **The other 10 are `Uninterpreted`** at `_consistent` and `consistent_by`, which `handler_count` doesn't list. They match Python's rows by test, site and text, 0 either way, against `sa-port-21/suite2/python` on df393bb's source, not this one.

## Known differences

- **`_forms`, the planner's named exception.** Rust's `_state` doesn't keep Python's iteration order or key objects. Cause: the dump sorts (`lra_py.rs`, `forms.sort_by`), and the key is rebuilt from the first object per term. Nothing reads either: `lra.py`'s only three uses hash into it. `test_lra_order_guard.py` fails on any new use, and is shown firing on a planted one. The two strict xfails are gone. `order:_forms` and the object form are equivalent, for this reason. Evidence: `identity_rule.py`, 14,424 sequences, 344,304 answers, 0 differ; limits: hook level, plain Fractions, moves at level 0. Its runs were on df393bb's source.
- **`order:_rows`: not caught.** By reading, `lra.py:1016` is the only iteration of the outer dict and it keeps the minimum violating variable, so order shouldn't matter. That isn't shown. A first pivot-then-move run read 0 differences in 487 moves with the order differing, but its own sensitivity control also read 0, so that run can't see this dependency and isn't evidence. Script: `~/sa-rust-ids-work/sa-port-36/rows_order.py`, not in the tree. Before a backend PR.
- **Test-plugin shims, not port:** the `_n_conflicts` view in `rust_plugin.py`, with the 64 tests it moved. `lra_backend.py`'s `__getattr__` and `_certificate`, which answer private reads and `certified` from a Python copy: 235,671 such views in this suite. `certified` isn't reached from `engine.py` or `lra_adapter.py`, by search.

## The rule on which object Python keeps

For whoever does the rest of LRA. In `satassume/theories/lra/lra.py`, when equal, distinct objects land:
- **`_key`, `_var_of` keys, model keys (:1174 reads `_key`):** the first object to reach `_term_var` in the session. `_lin` calls it for every term before dropping zeros (:695), so a zero-coefficient or cancelled term counts. Within a payload, the first occurrence (`lin`'s dict key).
- **`_forms` keys (:705-716):** the objects of the first atom whose net form, after dropping zeros, is new; per term, that payload's first occurrence, whatever `_key` holds. A later atom with the same form changes nothing. Iteration is first-registration order. Not read, as above.
- **Nothing else holds terms** in these runs: all of Python's fields walked after registration and at session end find only those three.

The hard checks on `_key`, `_var_of` and model keys stay, in `test_lra_identity.py` and `identity_rule.py`. Limits as above, and no constants or certify path.

## What keeps the transfer alive past 1b

The planner's question. `_Move` is raised at 3 places, all constants (`lra_backend.py:191, 207, 238`), and all 2,697 suite moves, with dev's and fuzz's, have those reasons. So nothing in the engine path outlives 1b. Left to go with it: the test shims above, `move_every_call.py` and `identity_rule.py`'s moves. `certified` and private reads would need another answer than a Python copy, since `lra_cert` isn't ported.

## Standing numbers, unchanged, not rerun here

- **THE DROP:** 54 by comparison, 27 only by the state read, 2 not caught as scored (`order:_forms`, now equivalent by the ruling above, and `order:_rows`), 0 never effective. 68 / 13 / 2 / 0 stays provisional and not quotable until the rerun; the cause of the three mutants' lost rows is still unknown.
- **PLANTED PORT BUGS:** 14/18 through `ask`, on df393bb's source. Not caught through `ask`: `negated_parity`, `touch_skipped`, `forget_skipped`, `last_object`. Hook-level catches aren't real-engine catches.
- **mutlive:** 15 mutants all "no", on df393bb's source, and its positive control on dev catches: m24 30 answers, 198 streams; m3 133 streams; m20 27 streams; base no. Those rows share memos in one process: 918 solvers against 3,332 fresh sessions. Mutants 2, 5, 6, 7, 9 still have no real-engine catch.
- **S's standing:** S's gate is met except for the 46 named stub failures, one cause.

## Run on this source, and not

Run: suite on Rust; fresh dev and fuzz; `LRA_MUT` 0, 6, 7 on dev; identity and guard tests, on orion's build of the same tree. **History and seeds, run because the rebase brought EUF into the crate:** recorded, shuffle twice, fork, twice in a row, seeds 1 and 2, on dev and fuzz: Rust against Python 0 answers, 0 ends, 0 streams differ in every run, 0 runs differ or unfinished; 0 re-entry, 0 entry raises, 0 Python solvers made. Answers move in no run; state against recorded moves the same on both backends (fuzz: shuffle 86 and 91, fork 2,981). `land2/hist/cmp.txt`.

The lease wrapper for that history run was killed by another session's mistake at 11:47 UTC. The job kept running under the same lease record, which I renewed and released by hand, and it finished with every cell rc=0.

**Moved to before any backend PR, not run here:** the mutant 2, 5, 6, 7, 9 rerun; the boundary rescore and suite column (`sa-port-21/checks/mutbound/work/table.md` finished on df393bb's source, not read; 10 of the 25 boundary mutants have no real-engine catch as last stated); the final drop score and its lost rows; the suite split with Python's counter; `order:_rows`' evidence; forced moves on this source; the 18 port mutants on this source; fresh on `ground` and `port`; the native path; timing.

Not counted on this source: callback and SymPy-construction counts. `_move`'s `rebuilt` terms are construction, and they go with the transfer. Speed: not measured, so no moved count sits beside any speed number.
