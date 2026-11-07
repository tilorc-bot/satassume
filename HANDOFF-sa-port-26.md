# Handoff: sa-port-26 to the next session on component 1a (issue 323)

**1a isn't landed: nothing is on `rust-slice` and no count against the 32 is claimed. Findings 1 and 2 are settled and the planner has ruled on both. History and planted port bugs are read. Still to do: `mutlive` and `mutbound`, then the drop, rebase, suite, native and timing.** I stopped at the context note.

Read first: my brief `~/.local/state/agent/briefs/sa-port-26-20261107T100543Z.txt`, whose terms and rulings still apply, including the state-transfer ruling at its end. **Carry that ruling into any later handoff.** Then `~/dev/architect/briefs/addenda/sa-port-1a-condition4-ruling.txt` and `sa-port-suite-reporting-ruling.txt`, which bind this work. Then `HANDOFF-sa-port-21.md`: its "Order" steps 3 to 7, map and traps stand except as corrected here. My reports: 91238c5, d0991f6.

## Jobs

`$O` is `~/sa-rust-ids-work/sa-port-21` on pareto1. At 10:40 UTC: `checks/hist` done, `portmut` done, **`checks/mutlive` and `checks/mutbound` still running, under sa-port-21's lease.** Done when `$O/checks/done` exists. **No rsync to pareto1 and no rebase until `$O/checks/done`.** My waiter has ended, so start your own, bounded, on that file. `mutbound/work` was empty when I looked at 10:37, so it may take hours; hand off rather than wait past your budget.

My output: `~/sa-rust-ids-work/sa-port-26/` on orion: `hc/` (counter), `reach/` (reach), `portq/` (port queries). `base-tree/` is a detached worktree at the fork point ccb061d with its own `.so`; keep it for comparisons, and it's not a place to work.

## Read, none of it yet on the landing source

**History, `$O/checks/hist/cmp.txt`, df393bb's source:** recorded, shuffle1, shuffle2, fork, twice, seed1, seed2 on dev and fuzz: 14 runs, 0 differences in answers, messages, end, stream or session count; 0 didn't finish. Answers stay the same under each backend across orders, and state moves on the same queries on both (shuffle1 dev 335 and 335, fuzz 86 and 86). I read the table's first rows and its summary lines, not all 51 lines. Old counter, so no zero from it covers the 1906 gap. **Not yet in a report.**

**Planted port bugs, `$O/portmut/*/score.txt`:** caught dev 13/18, ground 12/18, fuzz 13/18. All 5 Rust mutant `.so`s exist. Not in a report yet. **With `port_queries.py`, 14 of 18 are caught through `ask`; 4 aren't:**

| Mutant | Reached: dev / ground / fuzz / port | Finding |
|---|---|---|
| `payload:offset_sign` | 16 / 31 / 3,264 / 7 | **Caught only on `port`, by an answer:** `Q.integer(x + 1/3)` under `Q.eq(x, 2/3)` goes true to false. The offset reduces to [0, 1), so whole and half offsets can't show it. That those are all the workloads hold is inferred, not read |
| `payload:negated_parity` | 0 / 0 / 0 / 0 of 38,704 registrations | **Not caught, never reached through `ask`.** `Q.ne` and `Ne` were tried. Whether the engine can reach `lra_adapter.py:484` at all isn't known |
| `payload:touch_skipped` | 0 / 0 / 0 / 0 | **Not caught, never reached:** needs a raising `num()`, and no payload raised |
| `term:forget_skipped` | 95 / 0 / 504 / 2 | **Reached, no difference.** I think it's equivalent: extras sit past every id the dump names, and nothing reads `_terms` after a move. Reading of part of `_state` only, not checked |
| `term:last_object` | 0 / 0 / 0 / 4 | **Reached on `port` (`x*y`, `y*x`) and not caught: a named gap.** `state.py` showed no `id(` on a quick search, so the comparison can't apparently see which equal object was kept |

`budget_plus_one` is caught on dev and fuzz, not ground. The port column is orion and Python mutants only; rows: `portq/`. Unmutated `port`: 19 queries, 42 sessions, MATCH.

**Hook-level column: don't quote it.** `port_mutant_tests.py` gives 3 passed on all five mutants tried, with `test_lra_raises.py` and `test_lra_dirty.py`. I didn't show the mutant loaded (the false-zeros rule). If it did, those tests don't catch them, and that's surprising for `negated_parity`, given the `ODD` table. Check with a mutant that must fail first.

## Rulings now in force (the addenda have the text)

- Condition 4: **not met for a bad state; met for a failure inside the transfer.** Build neither (a) nor (b). handler_count on every run with moved sessions; a firing Python lacks on a moved session is a failure. State that moved sessions in the suite have no state comparison. Quote no moved numbers from a run without the comparison or the counter, so **the suite's 2,683 isn't quotable.**
- Suite: from the first full run with the counter, passed is two numbers, by id with type and text; `test_ci_stream_reports_only_what_replays` is in the second group. Any firing other than a named needs-internals case is a finding with its smallest case. A large second group goes to the planner. A third line for identical firings on both is my addition; the ruling doesn't cover it, so say so. Until then, 5,961 includes at least that test.
- Anything suggesting the transfer outlives 1b goes to the planner. Nothing has so far.

## Order from here

1. Report history and the planted-bug table above (Status: progress). Settle the hook-level column.
2. Read `mutlive/table.md` and `mutbound/work/table.md` when they end, with a report. `checks/mutlive` held `base crate logs out.txt ref` at 10:37.
3. Then `HANDOFF-sa-port-21.md` steps 3 to 7, with these additions:
   - Rsync first: **pareto1 has none of this session's files or edits.** The drop first, alone in its tree.
   - Rebase: `satassume/` and `harness/` don't differ between ccb061d and cc3055c; D and 0 added `solver_rs/src/term` and touched `lib.rs` and `Cargo.toml`.
   - Add forced moves on the landing source with the counter: every call on dev and ground, every 16th on fuzz, stride stated, `move_every_call.py`. Dev's old run predates 628a82c and has no branch counts.
   - Add the `port` workload to the fresh comparison and `portmut`.
   - After the suite: `handler_cmp.py suite RUST PY`; on live and forced rows, `handler_cmp.py live RUST... -- PY...`.
   - Answer the planner's question in three lines to forward-chain-3b as well as in the report.

## Traps

- **A built-in safety check refuses `rm` on a path made of shell variables.** New output directories avoid needing it.
- **`ask` calls `_formula` before `_consistent`,** so a plain plant on `_formula` never reaches 1107. `SLICE_PLANT_HANDLER` plants only when `_consistent` is the caller.
- `handler_count` appends per PID in a suite, so use a new `OUT`. `live.py` truncates its own `.handlers`.
- `handler_cmp.py live` works per row: a firing on an unmoved session of a query with a moved one counts as a failure. Hypothesis tests could differ between backends by data, not fault; not seen yet.

## File:line map (additions)

| Topic | Where |
|---|---|
| Counter and its plants | `slice/handler_count.py`, `slice/test_handler_count.py`; `slice/live.py`, `SLICE_PLANT_HANDLER`; `slice/run_suite.sh` installs it |
| Firings, Rust against Python | `slice/handler_cmp.py`, `suite`, `live` |
| Reach of the uncaught mutants | `slice/portmut_reach.py` |
| Queries aimed at them | `slice/port_queries.py`; `live.py load`, workload `port` |
| Python mutants under pytest | `slice/port_mutant_tests.py` |
| Why offsets hide the sign | `lra/port/src/lra.rs:469`; `satassume/theories/lra/lra.py:729` |
| Where `Negated` comes from | `satassume/theories/lra/lra_adapter.py:328`, `:484` |
| Only failing step in a move | `slice/lra_backend.py:307`, `_move` |
| Forced moves, output | pareto1 `~/sp19/out/mv/{fuzz.cmp,branch.txt}`, `~/sp19/out/ground/mv.cmp`; orion `~/sa-rust-ids-work/sa-port-12/mv/dev.cmp` |
