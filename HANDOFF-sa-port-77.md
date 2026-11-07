# Handoff, sa-port-77: component 5, step 5a, limits fixed, landing runs not started

Head: `port/5a` 7cfd5d1 plus this file, on `rust-slice` d29e94b. Not landed. Read `HANDOFF-sa-port-75.md` for the file map; the map below is what changed.

## Ran
Only `rust-spike/slice/test_session_limits.py` on orion, aarch64, at 7cfd5d1: 77 passed. It compares Python and rust mode in separate processes: result, clause stream, table.
Commits 047d211, de15d16 and f915c0c each had one failing test in that file, which is my test's wrong assertion. Head passes.

## Not run on this source
Suite, dev, fuzz, any plant, the handler control, the evaluator, timing. The earlier dev MATCH and fuzz-1,500 MATCH are from 97ef020, before these changes, and don't carry over.
The x86-64 build was only queued (below). I did not see it finish.

## Changed
- **Depth (limit 1):** `FORMULA_DEPTH` 64, session.rs:40. Deeper formulas go to Python's compiler over the same table. Python's first failing depth, bare stack, limit 1000: `Implies` 330, `Not(Or)` about 495, others about 990, from a binary search. So 3 frames a level at worst.
- **Errors (limit 2):** `convert`, session.rs:286: any `Exception` while reading the formula returns "Python compiles it", before anything is emitted. A BaseException goes up. Unhashable `expr`, unhashable `pred` and a non-formula arg match Python on type, text and the clauses before the error.
- **A wrong result found:** a non-string predicate, `P(5, x)`, raised `TypeError` on Rust and works on Python. Fixed in `pred_id`, session.rs:196: custom predicates now key a Python dict.
- **`atom_of` view** was one short, session_live.py:152. Fixed. `tests/test_lazy_atoms.py:24` reads it, so the suite would have shown it.
- **`true_var`:** no `unsafe` now, compile.rs:444 and session.rs.
- **Selector read:** the `__closure__` read is gone. `_rust_call`, session_live.py:246: `Session.emit` is done directly, any other `emit` is called back (`rs:emit_callback`). A foreign `table` or `dv` compiles on Python. This is part of what the evaluator should read.
- **PR 334's key (limit from the brief):** `(abs(l), l)` at compile.py:61 and compile.rs:166, `set_order` removed. This changes `satassume/knowledge/compile.py`, so name it in the report. How often the tie fires was NOT measured.
- **Counters added:** `rs:emit_callback`, `refuse:depth`, `refuse:convert`. They fire in test_session_limits.py (`test_counters_fired`).
- **run_live.sh:** the traced rust column now passes `SESSION_REPORT=WORK/WL-rust.session.json` and `--handlers WORK/WL-rust.handlers`. Shared script, name it.

## Named differences, pinned by tests in test_session_limits.py
1. Limit 3: one object per node id, first seen at the boundary. `And(P('mine', 1.0), P('real', True))` shows `mine(True)` where Python shows `mine(1.0)`. Clauses, numbering and result match in that case. I have not shown it can't move an answer: `objs[nid]` also feeds `new_nodes` and `node_id`'s visit, so a class-reading discovery could see the other object. Report `join` on fuzz and suite; if it's non-zero, that's a finding to read.
2. Non-string predicates `==` across classes, on different nodes: `1(c)` against `True(c)`, shown form only.
3. Within a few frames of Python's own recursion limit the two differ, by ruling not reproduced: the shell adds frames and the views remove some. `test_threshold_is_near_pythons` asserts within 5 frames and more than 3*64. Its printed output has the numbers; I only saw Python's (orand 987, notor 494, implies 330), so read Rust's.
4. Not tested: a caller already within about 3*64 frames of the limit with a formula at or under depth 64. Python can raise there and Rust doesn't use those frames. Same for every ported component. Backend PR list unless you find otherwise.

## Pareto setup
Exact tree of 7cfd5d1 by `git archive` at `~/sp19/dev/sa-port-77` on pareto0 and pareto1, with `SHA` beside it. Scripts: `~/sp19/job77.sh` on both, `~/sp19/build77.sh` on pareto1. Usage: `bash ~/sp19/job77.sh SCRIPT` (HOME becomes ~/sp19). Remote output: `~/sp19/sa-rust-ids-work/sa-port-77`.
Build: detached on orion, started 16:49 UTC, queued behind a quiet lease on pareto1. Log: `~/sa-rust-ids-work/sa-port-77/build-p1.log`, which ends in `done`. `build77.sh` puts the .so in the pareto1 tree only: copy it to pareto0's `~/sp19/dev/sa-port-77/rust-spike/slice/`. It's for 7cfd5d1 source, and this handoff commit changes no code. No rsync on pareto0.

## Next, in order
1. Suite on pareto0 or pareto1: `run_suite.sh WORK rust` under job77.sh with `machine run`, detached; base rows on orion at `~/sa-rust-ids-work/port-census/pr328-check/suite-rust` (123 failed, 5961 passed, 23 skipped, 18 xfailed), read with `suite_report.py`.
2. `run_live.sh WORK` the same way. Read `fuzz-rust.session.json` for crossings, census and `join`.
3. Plants through `--so`; `live.py` already refuses a wrong load and records the SHA. Use your own crate copy and target dir. Check each one fired and differs, since a mutant with no reach proves nothing:
   - compile.rs: 393 swapped key (needs an `Or` over `MAX_EXACT`, may not reach dev); the `emit` in `true_lit`:444; 166 with `-l` also measures whether the tie is reached.
   - session.rs: 425 `have | need` to `have` should fire on dev; 466 drops `_link`'s implication clause, which is 0 on dev, so use fuzz, suite or `tests/test_wide_derived.py`.
4. `var-off`: why the one-predicate version wasn't caught is still unexplained. Hint only, unverified: `py:var` was 0 in the limits run, so `Session.var` may be rarely called. Check on dev.
5. Handler control: `suite_plant_handlers.py`, `quiet_fire.py`, `test_handler_count.py`. Show a plant fires before quoting a zero, on the `--handlers` path too.
6. At the bar: Status: progress with the one-line SendMessage so the architect launches the evaluator, then `results/port-5a.md`, rebase, land, report.
