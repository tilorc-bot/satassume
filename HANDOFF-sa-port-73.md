# Handoff: component 4, slice C, landing runs under way (sa-port-73, issue 323)

Branch `port/4c`, tested source **a858030** on `rust-slice` ce19962, plus this file. **Nothing is on `rust-slice`. Modules running whole because of this: 0 of 32.** Stopped at the 144k context note with the job running. **Call made: land items 1-5 as C1 and slice again. Item 6 doesn't fit: say so in the report.** `knowledge_live.py` isn't touched, so the rows-kept guard ruling doesn't apply: say so.

## Running when I stopped: read it first

`pareto1:~/sa-rust-ids-work/sa-port-73/l1/`, started 15:41 UTC, detached under `machine run pareto1 --shared`, ends with `DONE` (`FAILED` if setup failed). Script `pareto1:~/sp19/job73.sh`, copy on orion in `~/sa-rust-ids-work/sa-port-73/`. PIDs for stopping it, taken on orion: `~/sa-rust-ids-work/sa-port-73/l1.pids`. No duration was measured, so don't assume one.

**Not read: no result from `l1` is known yet, apart from dev's four fresh jobs exiting 0.**

Read by summary:
- `ssh pareto1 python3 sp19/read73.py sa-rust-ids-work/sa-port-73/l1`: fresh, budgets, direct, suites' refusals and reach, the discard check. **The script has never run on finished output, so expect to fix it.**
- By id: `python3 ~/sa-rust-ids-work/sa-port-63/suite_ids.py l1/suite-base l1/suite` on pareto1.
- Three numbers: `suite_report.py`, with `. ~/sp56/env56.sh` and `PYTHONPATH=$PYTHONPATH:$S` (from sa-port-56's handoff, not rerun by me).

**What differs between the suite columns, to state in the report:**
- Head runs `-p discard_real`; base doesn't, because base has no such file. The plugin only reads `COUNTS`, but it's a difference.
- Neither sets `SLICE_KNOWLEDGE=atoms`, so atoms are off on both, as in slice B and unlike `_rows_runtime`'s landing.
- `tree-sa-port-73.txt`'s last line says `sa-port-73-base`. **That's a fault in the probe, not the run:** it ran with `-c` from the base clone's directory, so cwd came first. Checked: `suite/tree.txt` is the head, `suite-base/tree.txt` the base, and `/proc` on running fresh and pytest jobs shows the head's `PYTHONPATH` and `.so`.

## What's known

**`c3/run1` on the tree before this (1dce833's source), orion, all rc 0.** Python against Rust, dev 1,985 and fuzz 3,000: 0 answers, 0 digests, 0 refused, 0 faults; check mode the same.

| Plant | Dev answers / digests | Fuzz answers / digests | Reach, and why any miss |
|---|---|---|---|
| `le-swap` | 82 / 93 | 572 / 2,055 | |
| `no-ext` | 27 / 93 | 123 / 2,055 | |
| `is-number-false` | 0 / 169 | 13 / 2,947 | |
| `plan-drop` | 0 / 15 | 2 / 754 | `plan:_eq_links` dev 15, fuzz 795 |
| `plan-pred` | 0 / 15 | 2 / 754 | same |
| `interned-reversed` | 0 / 5 | **0 / 0** | `interned` fuzz 12,973 calls. **Why fuzz doesn't move wasn't looked into** |
| `affine-false` | **0 / 0** | 0 / 2 | `affine_pair:True` dev 0, so void there; fuzz 4 |
| `under-empty` | **0 / 0** | **0 / 0** | **Void on both:** `under_apps:nonempty` is 0 on dev (6,840 calls) and fuzz (2,133). Neither workload has a term under an application, so their MATCH says nothing about this function |
| `linked-drop` | **0 / 0** | **0 / 0** | **Void on both:** 6,278 nonempty on fuzz, but `rg '\.linked_terms' satassume` has 0 hits. The engine never reads the field: `ref.py:109` prints its size, and `tests/test_ref.py` and `test_scope.py` read it. It's also a plant on Python's own function |

Fuzz per-site reach is in `run1/fuzz.rust.json`, with `glue:termwise` 1,576 (100 True, 1,476 False), `plan:_eq_links` 795 and `scaffold:rebuilt` 332 (`glue_objects` 232, `relation_atom` 100). Dev rebuilt 69, all `glue_objects`.

**On a858030, orion, single process:**
- `test_term_ids.py` 112 passed on both solvers. Slice C's tests are new: order relations including nan, `_eq_infinity`'s three paths, `_under_apps`, `zero_twin`, and each plant's effect.
- `relations_direct.py 300 1` (`rd0.txt`): 293 cases, 0 `differs:*`, now `under_apps:nonempty` 336, `is_:_eq_infinity` 59, `plan:_eq_infinity` 96, `affine_pair:True` 43, `zero_twin` 866. This is `_under_apps`' evidence for now, and the suite's count is the next.

**The `mul` line, SymPy read:** the earlier handoff's reading holds. `core/expr.py:243` `__neg__` is a raw `Mul._from_args((-1, self))`, but `core/add.py:366` `Add.flatten` rebuilds through `Mul(c, s)` when `s` is neither `Mul` nor `Add`. So a correct `neg` alone wouldn't do and `mul` did need the change. `mul`'s refusals head against base come from `l1/direct/ids-{head,base}.txt` and `suite{,-base}/term.*.json`. **Not read yet.**

**A difference in calls, no state moved as far as read:** a plan calls `s.var` once per clause, where Python's `_eq_infinity` calls it once. `Session.var` (`engine.py:385`) is get-or-allocate, so numbering holds. Both recording sessions log allocations only, so they can't see this.

## Left, in order

1. Read `l1`. Explain any changed id, firing or difference. If the job failed, fix and rerun with `job73.sh SHA BASE TAG`.
2. Landing bar: rebase on `origin/rust-slice`, check the incoming diff by the planner's rebase rule (slice D is landing alongside and shares crate files). Write `rust-spike/slice/results/port-4c.md`, push to `rust-slice` without force, report the tested SHA, landed SHA and incoming diff.
3. Report owed, all from `l1`:
   - `termwise-true` at budgets 5 and 2, in `budget/`: on C's landing bar. It's caught if either moves. Sa-port-72's earlier numbers: fuzz budget 5, 7 answers and 74 digests; budget 2, 3 digests; dev void, with 0 real False.
   - `mul` refusals before and after, on the suite and direct. Slice B's base: 19 on 6 distinct queries. Shadow in `shadow-{dev,fuzz}.json`.
   - The discard check on real refusals: `discard/` with its no-rollback control `discard-noroll/`, which must show `left-something` or the zero means nothing. Ids in `refused-ids.txt`. `fuzz-rdisc` and `dev-rdisc` for planted ones.
   - Handler firings from `suite/`, by the planner's reporting rule. `handler_count` covers 2 of the 7 handlers. **Slice C added no new handler site** (`_guarded` wraps are counted as faults, not swallowed: confirm from `term_live.py` before saying it). `engine.py:1906` catches from `caught` in the rows, with `units/quiet_fire.txt` as the counter's control.
   - Rebuilt terms per step, from `scaffold:rebuilt:*`.
   - The `test_lazy_reads` flake: `units/flake-{head,base}-{1..6}.txt`, `-n 2` on Rust, both trees. Report it either way. Sa-port-72 saw `test_stock_term_plant_is_caught[finite-stock_finite]` fail once in 4 runs. Note that these runs also carry the job's load.
   - `test_performance_smoke_300_vars` if it fails: the load is high by design here.
   - Modules whole: expect `relations.py`, `euf_adapter.py` and `scope.py` all partial, so 0 of 32.
4. **Then C2, in a further session, not part of landing.** Slice proposal below.

## Item 6: the slice proposal

`relations.py:777-1921` is about 1,100 lines in 36 methods. Tilo asked why so little has been ported, so the report should say this plainly: **slice C moves term work; it doesn't make a module whole, and item 6 alone can't either while `Session` is Python.** `P`, `And`, `Args`, the session and every `s.var` key hold SymPy objects until component 5, so a "clause over ids" here is a plan Python runs. I'd put this question to the planner: does C2 go before component 5, as plans that component 5 then replaces, or with it? I didn't size that, so it's a question and not a finding.

If C2 goes first, in this order, smallest term work first. Lengths are from the source, the split is my judgment and none of it is tried:
- **C2a, order:** `_closed_extended_real:1375` (12), `_order_sides:1387` (18), `_order_infinite:1405` (58), `_trichotomy:1154` (43), `_mention_number:958` (17), `_link_integer:1106` (21). Same shape as `_eq_links`' plan.
- **C2b, interpretation:** `_interpret:998` (84), `_guard:1082` (24), `_link:1480` (36), `_bound:1463`, `_fresh:980`, `selectors_of:1527` (57).
- **C2c, transfer:** `_add_role:1197`, `_apply_role:1219`, `_tsource:1264`, `_tvar:1282`, `_engage_transfer:1662`, `_transfer_terms:1691`, `sync_transfer:1750` (98), `_congruence_pairs:1855` (67), `_congruent:1624`, `_share_guard:1600`.

## Limits to keep in the report

All of sa-port-72's stand, in `HANDOFF-sa-port-72.md`'s "Limits": atoms stay Python's, `_is_number`'s wide wrapper, `is_Rational` as a class flag, `_under_apps`' insertion order, `own-atoms` never firing, `_intern` staying Python's. Its last two limits are fixed: the duplicate generator and `zero_only` are gone.

## File map

As `HANDOFF-sa-port-72.md`'s, with these changes:

| What | Where |
|---|---|
| Slice C's tests | `rust-spike/slice/test_term_ids.py`, from `ORDER_PAIRS` to the end |
| `twin-one` plant, `zero_twin` count | `term_live.py` `_zero_twin` (`:562`) |
| Real-refusal discard | `rust-spike/slice/discard_real.py`: `SLICE_DISCARD_REAL`, `SLICE_DISCARD_NOROLL`, `refused.PID.jsonl`, `discard.PID.json`; hooks `term_live.BEFORE_RUN`, `AFTER_ROLLBACK`; check `term_discard.py` `_before`, `check` |
| Direct comparison | `relations_direct.py` `NUMBERS`, closed sides, `zero_twin`, printed reach |
| Job and reader | `job73.sh`, `read73.py` on orion `~/sa-rust-ids-work/sa-port-73/` and pareto1 `~/sp19/` |
| Clones on pareto1 | `~/sp19/dev/sa-port-73` (head), `~/sp19/dev/sa-port-73-base` |
| Run1 reader | `~/sa-rust-ids-work/sa-port-72/cmp3.py` |
