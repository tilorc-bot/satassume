# Handoff: sa-port-55, component 4 slice A (issue 323)

Branch `port/4a`, tested source `56bc4e1` (this file's commit adds only this file and `results/port-4a.md`), on `rust-slice` 4b2f12b. **Not landed.** All bar checks passed on that source, but `rust-slice` has moved and 1b must land first. Nothing is running for this session. Brief: `~/dev/architect/briefs/NEXT-port-4a.txt`.

## What's left, in order
1. **Wait for 1b.** Architect, twice: 1b lands before slice A. `rust-slice` is `dcfc1af` (realroots, on 4b2f12b). Wait on `git ls-remote origin rust-slice` in a background shell. Don't start landing runs before 1b is on it; they would have to restart. If 1b stalls, ask the architect rather than landing ahead of it.
2. **Rebase on it. Expect conflicts.** `git merge-tree` shows `knowledge_live.py` conflicting with realroots. It adds to `install()` and `undo()`; keep theirs and `term_live`'s side, as I did for `_common` (commit `934655e`). `rust_plugin.py` is touched by both 1b and this branch. 1b's source in `~/dev/sa-port-19`, 30 files against 4b2f12b when I looked.
3. **Rerun: the rule requires it.** Incoming `knowledge_live.py`, `lib.rs` and 1b's LRA path all change code the run executes. On pareto1: `cp ~/sp19/job55.sh ~/sp19/job-NEXT.sh`, change `sa-port-55` in it to your name, push `port/4a`, then from your output directory on orion:
   `setsid nohup machine run pareto1 --shared --wait 4h -r WHY -- bash /home/tilo/sp19/JOB FULLSHA TAG > TAG.machine.out 2>&1 < /dev/null &`
   It took about 19 minutes. `$B/DONE` is written last, `$B/FAILED` names a setup failure.
4. **Read it, as below**, and replace the numbers in `results/port-4a.md`: its first line, the tables, and the merge finding if the rebase adds one. Check each against the new output; most should not change, and any that does gets explained.
5. Short check after any further rebase, push to `rust-slice` without force, report tested SHA, landed SHA, incoming diff. Then stop.

## Reading the job (`B=/home/tilo/sa-rust-ids-work/sa-port-55/m1` on pareto1 is the last one)
| In `$B` | How to read | On `56bc4e1` |
|---|---|---|
| `tree.txt` | check first | SHA, x86-64 .so, imports from the clone |
| `units.txt`, `units-hc.txt`, `units-rust.txt`, `lazy_fire.txt`, `quiet_fire.txt` | tail, each ends `rc=` | all rc=0: 124 passed 5 skipped, 2, 17 |
| `fresh/` | `rows` compare: tab-separated, field 1 answer, field 2 digest. `.json` has `counts`, `left`, `term` for discard columns, `refusals`, `term` for `rkeys` | 0 differ on all 8 pairs; `dev-py:dev-noroll` 494 digests, 493 sessions, 0 answers; clean 100% |
| `live/summary.txt` | `grep -c MATCH` | 8 |
| `mut0-cmp.txt` | tail | DIFFER: 47 ends, 49 streams, 19 LRA, first q348 |
| `shadow-{dev,fuzz}.json` | `bad`, `counts` | empty |
| `suite/` | scp to orion. By id against `~/sa-rust-ids-work/port-census/pr328-check/suite-rust`, then `suite_report.py SUITE ~/sa-rust-ids-work/port-census/pr328-check/suite-python` with env sourced and PYTHONPATH set | 5,961 / 77 / 46, 0 changed. `handlers.*.jsonl` by `where`, `site`, `text`: 39 rows, 2 tests. `term.*.json`: sum `counts` per worker |

`job55.sh` differs from `job53.sh` by three fixes: `test_handler_count.py` runs with its plugin; `ln -sfn $T/rust-spike/lra $B/lra`, without which the mutant never built (sa-port-53's `mutb` was void); and it runs `livecmp.py` for the mutant.

## Done here
- Read sa-port-53's job on `f1e474b`: suite and live clean. Its mutant 0 didn't build, so that column is void; use `m1`'s.
- Rebased on 4b2f12b. **Merge finding:** `py.rs`'s non-bool `const_value` became a TermRefuse past `_common`'s fault. It's a `TypeError` now, and sa-port-48's test passes unedited. `knowledge_live.kept()` reads `term_live.current()`.
- `rust_plugin.py` writes `term.PID.json` per worker: refusals and reads for the suite now exist. Inventory line 373 and section 9 updated.
- `port/4a` was force-pushed once with a lease for the rebase; old head 9fb46ed. Never force `rust-slice`.

## Open points, not settled
- **The 0 refusals are weak evidence.** `_key_consumer` asks Rust only for input terms; `key:not-input` 67,842 in the suite returns without asking. The refusal path has run on plants only. The report says this; keep saying it.
- **Exp-factor refusals are 0 and don't answer the planner's question**, for the same reason. Slice B makes the count meaningful.
- `_CONSTANTS` and `_BY_KEY`: what survives a discard holding one is unchecked, and 1b is moving that code. Look once it's on, since it's now in reach.
- `handler_count` covers 2 of the 7 handlers.
- Seen, not mine: sa-port-51's suite log on pareto1 read 124 failed, 5,960 passed, one off the base. Not looked into; if the base moves, use the new base rows 1b reports.

## Map
- `term_live.py`: `_Mark` `:104`, `_key_consumer` `:193`, `_install` and `_ask` `:238`, `from_env` at the end. `term_discard.py`: `SITES`, `state`, `check`. `fresh.py`: `--term`, `--discard`, `--no-rollback`.
- Handlers: `engine.py:1906`, `sympy_api.py:1107`, `relations.py:1989`, `:2011`, `:2018`, `lra.py:461`, `lra_bounds.py:249`. `test_term_live.py`'s `HANDLERS`.
- `solver_rs/src/term/py.rs`: `TermRefuse` near `:16`, `resolve` read `:360`. `rust_plugin.py`: `pytest_unconfigure`, term_live install. `knowledge_live.py`: `kept()`, `install()`, `undo()`.
- Report: `rust-spike/slice/results/port-4a.md`.

## Must stay in the report
SHA, tested and landed, and the incoming diff; three numbers and the passed split (5,960 and 1); what ran and what didn't, the whole moved list; modules whole: **0 of 32**; the 7 handlers; real refusals by reason per workload; `read_raised`; `read_term_missing`; exp-factor refusals; the recount at `engine.py:1906`, shown firing first; `rollback:cleared` and `rollback:restamped` per workload; that the keys consumer drops its value, so answers still come from Python; the merge finding. S's standing wording, and the `_n_conflicts` shim with its 64 tests.
