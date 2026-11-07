# Handoff: sa-port-53, component 4 slice A (issue 323)

Branch `port/4a`, tested source `f1e474b` (this file's commit adds only this file), on `rust-slice` 19ed342. **Not landed. The bar's suite and live comparison are still running; nothing below claims them.** Brief: `~/dev/architect/briefs/NEXT-port-4a.txt`.

## Running now: read this first
`machine run pareto1 --shared`, lease ff85f069, wrapper PID in `~/sa-rust-ids-work/sa-port-53/l1.machine.pid` on orion, log `l1.machine.out` beside it. Script `~/sp19/job53.sh f1e474b... l1` on pareto1. Clone `~/sp19/dev/sa-port-53` there. **Output is on pareto1, `B=/home/tilo/sa-rust-ids-work/sa-port-53/l1`, which isn't orion's disk: read by ssh.** `$B/DONE` is written last; `$B/FAILED` names a setup failure. It's detached, so ending this session doesn't touch it. Stop it only by that PID.

| In `$B` | What it is | How to read |
|---|---|---|
| `tree.txt` | SHA, .so hash, imports | check it first |
| `units.txt`, `units-rust.txt`, `lazy_fire.txt`, `quiet_fire.txt` | tests and firing controls; each ends `rc=` | tail |
| `fresh/{dev,fuzz}-{py,rust,rkeys,disc,rdisc}.txt`, `.json`, `.handlers`; `fresh/dev-noroll.*` | fresh engine columns; `fresh/DONE` | `~/sa-rust-ids-work/sa-port-53/a/cmp.py DIR A:B ... NAME`, scp it over; it wants `DIR/NAME.txt`, `.json` |
| `live/summary.txt` | `run_live.sh`'s 8 comparisons, with `term_live` on in rust mode | summary only |
| `mutb/m0`, `mut0-dev.jsonl`, `mutb.out` | solver mutant 0 through live. **The job doesn't compare it:** run `livecmp.py $B/live/dev-py.jsonl $B/mut0-dev.jsonl`; expect about 49 streams, 47 ends, first q348 as in `results/port-lazy.md:15`. Dev answers don't change under it | |
| `shadow-{dev,fuzz}.json` | shadow on the tested source | `bad` must be empty |
| `suite/` | `run_suite.sh`, `-n 8`, rows, `handlers.*.jsonl`, `exit.txt` | `suite_report.py` against the base rows, `~/sa-rust-ids-work/port-census/pr328-check/suite-rust` on orion; scp one way |

**`$B/units.txt` ends rc=1, and that's my job script, not the code:** 2 failed, 98 passed, 5 skipped. `test_handler_count.py::test_each_route_is_seen` and `::test_uninterpreted_is_not_counted` raise AttributeError on `handler_count._out`, None, because `job53.sh` runs that file without `-p handler_count` and `SLICE_SUITE_OUT`. Both results of running it each way on orion are in the sa-port-53 session's last step; rerun it with the plugin on x86-64 and quote that, not this row.

## Done and run here (orion, aarch64, seed 0, under `~/sa-rust-ids-work/sa-port-53/a/`)
- **The 3 stamps are settled.** The handoff's guess was right: `reset_module_state` unsets the stamp and the run restamps. `_Mark` now restores it (`term_live.py`, `rollback:restamped` 5,091 on dev).
- **A real hole, found while settling that:** a table the run emptied (restamp, or cleared when full) and regrew past the mark kept the run's first n entries, since `popitem` stopped at n and `rollback:cleared` only looked for `len < n`. `_Mark` now notes each table's last key and empties the table if it moved. Tested by `test_a_table_emptied_and_regrown_past_the_mark_keeps_nothing_of_the_run`. The tie case, a run that re-adds the same key object at the same position, isn't detected; the state check would still see it.
- **Dev discard, a refusal planted in every query, 12 sites:** Python solver and Rust solver, each against its plain run: 0 answers, 0 digests, 0 session counts differ; state clean **1,985 of 1,985** on each, `left` empty; `rollback:cleared` 0, `dummy-count-moved` 0, handler rows 0.
- **The plant, `--no-rollback`:** something left on 1,985 of 1,985, 45 kinds; 494 digests differ, 493 session counts; **0 answers differ.** So the state check catches this and answers alone wouldn't.
- **Plain Python against plain Rust, no `term_live`:** dev 1,985 and fuzz 3,000: 0 answers, 0 digests, 0 session counts differ.
- **Tests:** `test_term_live.py` new, 17 passed on Python's solver and 17 with `SLICE_TERM_TEST_RUST=1`. The 7 handlers, each with a plant shown reached; nested; second run; a Python theory's hook on the Rust solver; `read_raised` and `read_term_missing` to the top; 3 on rollback. Slice tests that touch this: 98 passed, 5 skipped (2 don't build, 3 kept `out-of-scope`).
- **Moved tests:** `lazy_fire.py` rows now expect TermRefuse past both handlers, counter 0, rc 0. `quiet_fire.py` unchanged, rc 0, and is the control: an Exception at the same 4 places shows on the counter, 1 each. `knowledge_quiet.py` handles `TermFault`: `fire` rc 0, `rust dev --limit 200` rc 0, counter 0 on its rows. 5 of its 6 reached-kind rows say "not reached" on that limit, which isn't a pass. The forced rows reached.
- **`term_shadow.py`:** 7 sites that count a check's raise named `CHECK_FAILS`, so a TermRefuse from a check is counted, as before, and doesn't end the query. Shadow on dev: `bad` 0, 183,980 compares, 27,342 key compares, 4,919 derived keys, on the source just before this edit. The pareto1 run has the edit.
- **Wiring, shared files:** `rust_plugin.py` and `live.py` call `term_live.from_env()` in rust mode only.
- **Not finished on orion:** `a/fdisc` and `a/frdisc` were still running, and pareto1 repeats them, so ignore them unless pareto1 fails.

## What's left, in order
1. Read `$B` when `DONE` appears. Bar: (1) suite by id with the three numbers, (2) `fresh` and `live`, (3) `dev-noroll` and mutant 0, (4) handler rows, (5) explain anything. Any firing other than `test_ci_stream_reports_only_what_replays` and `test_protocol_on_fuzz`'s "Already mutably borrowed" is a finding. The first is the named needs-internals case, the second the named 46-stub cause.
2. **Suite gap: `term_live`'s counts aren't written by the suite.** The plugin installs it and nothing dumps `COUNTS`, so this suite can't report refusals by reason, `read_raised` or `read_term_missing`. Dev and fuzz have them in `fresh/*-rkeys.json`. The bar doesn't need them; the report list below does. Add a `pytest_unconfigure` dump per worker to `rust_plugin.py`, and run it when the suite next runs, or state the gap. Don't rerun the suite only for this without saying why.
3. Update `rust-spike/PORT-INVENTORY.md:373` and section 9: 7 handlers, not 2, and why the base class changed. **Not done.**
4. Write `rust-spike/slice/results/port-4a.md`. Rebase, apply the planner's rebase rule, push to `rust-slice` without force, report.

## Open points, not settled
- Real refusals on dev plain were 0 in sa-port-49's run, so the real path has run on plants. `fresh/*-rkeys.json` gives dev and fuzz on this source.
- From sa-port-49, still true: overwrites of an existing memo key and in-place changes to non-container values aren't rolled back; the state check sees the first and copies one level for the second. SymPy's caches, `_assumptions` and `Dummy._count` are rollback's documented limits.
- `_CONSTANTS` and `_BY_KEY` are truncated from outside, and `harness/state.py:262` says live objects refer to entries by index. Nothing here checked what survives a discard holding one; the Rust LRA backend is the place to look, and 1b is moving it. `rdisc` on dev shows no difference, which is evidence and not that check.
- A nested `_ask` converts its own table; section 5 says the table belongs to the top-level query. `Engine.is_` and `Engine.ask` called directly have no table, so they can't refuse.
- `handler_count` covers the 2 named handlers only. The other 5 of the 7 aren't counted. TermRefuse can't be caught there (tested), but an ordinary Rust Exception there would be quiet. Say so.

## Map
- `term_live.py`: `_Mark` near `:101`, `_ask` in `_install`, `_key_consumer`, `from_env` at the end. `term_discard.py`: `SITES` `:27`, `state` `:81`, `check` `:112`. `fresh.py`: loop near the end, `--term`, `--discard`, `--no-rollback`.
- Handlers: `engine.py:1906`, `sympy_api.py:1107`, `relations.py:1989`, `:2011`, `:2018`, `lra.py:461`, `lra_bounds.py:249`. Queries reaching each: `HANDLERS` in `test_term_live.py`.
- Hook unwind: `solver_rs/src/lib.rs:43-50`. TermRefuse: `solver_rs/src/term/py.rs:16`. Counter: `handler_count.py:20-45`.
- Suite: `run_suite.sh`, `suite_report.py`. Last bar table: `results/port-lazy.md:9-17`. Remote recipe: `~/sp19/job53.sh` on pareto1.

## Must stay in the report
SHA; three numbers, and the passed split per the planner's reporting rule; what ran and what didn't, including the whole moved list; modules whole because of this: **0 of 32** expected; the 7 handlers; real refusals by reason per workload; `read_raised`; `read_term_missing`; exp-factor product refusals (planner's follow-up); the recount at `engine.py:1906`, shown firing first; `rollback:cleared` and `rollback:restamped` per workload; that the keys consumer drops its value, so answers still come from Python. S's standing wording, and the `_n_conflicts` shim with its 64 tests, as the planner ruled.
