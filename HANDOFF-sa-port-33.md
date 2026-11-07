# Handoff: sa-port-33 to the next session (issue 323), lazy reads

Read the brief first: `~/.local/state/agent/briefs/sa-port-33-20261107T103700Z.txt`. Its terms, rulings and HELD TO all still apply, plus two rulings that came after it, both binding: `~/dev/architect/briefs/addenda/sa-port-lazy-nan-ruling.txt` and `sa-port-lazy-suite-shadow-ruling.txt` (same directory). **A mismatch on the suite's product keys goes to the architect first.** `HANDOFF-sa-port-32.md` holds for what's built and `HANDOFF-sa-port-29.md` for traps and the survey limits, which go in the final report. Clone `~/dev/sa-port-5`, branch `port/lazy`. Output: `~/sa-rust-ids-work/sa-port-33/` (`$O`). Nothing is on `rust-slice`. Modules of the 32: 0 added.

## Jobs running, detached, from frozen trees (10:47 UTC)

Don't wait on them with a file a stopped run can't write. Each has a `done.txt` line per run and `ALL` at the end.

| Job | Output | Tree | Read with |
|---|---|---|---|
| Suite, shadow off, Rust then Python, `handler_count`, `-n 4`. **These are the numbers quoted.** | `$O/suite/rust`, `python`; `$O/suite/done.txt` | `snap2` | `suite_report.py $O/suite/rust $O/suite/python`, then by id against `~/sa-rust-ids-work/port-census/pr328-check/suite-{rust,python}`; `suite-lists.md` beside them; `handlers.*.jsonl` for the passed split |
| Suite, shadow on, checks on | `$O/suite/shadow`; `done-shadow.txt` | `snap3` | below |
| `lazy_reads.py` fuzz (dev, corpus done) | `$O/lazy/` | `snap2` | last log line; `rg '"n_extra": [1-9]'` |
| `term_history.py` s0, s1, s2, rev, shuf, dirty on dev, fuzz, corpus | `$O/hist/` | `snap` | `term_history.py --cmp A B` (s0 against each; `dirty` shows memo leakage) |
| Shadow with shapes and handlers on dev, fuzz, corpus, stream, battery; drive and plain on the first three | `$O/shapes/` | `snap3` | `.json`, `.handlers`; `$O/held/summ.py F.json` |

`$O/hist-invalid/` is mine and invalid (xargs joined lines on a trailing blank): don't read it. **`stream` in the shapes job is the whole stream; the census used `stream-unique`.** Check it ended; if it's too slow, say so and use `stream-unique`.

## Done, with numbers (run from `snap`, or as named)

- **Answers.** Plain and shadow equal, and equal to D0's base: dev a5349612416b55ef, fuzz d4006a14c365ecdf, corpus 544a8c885fcd4911. The first 200 of plain dev hash to 55fe320a718ef763, so that sha is now compared. mismatch 0 on all three; `read_term_missing` 0, `read_raised` 0 on all three. Kept: dev out-of-scope 50, corpus out-of-scope 190, fuzz none, no `too-deep`. **Still owed: compare Kept to the eager tree's by D0's report.** Files `$O/held/`.
- **Nan plant** (`$O/snap-nonan`, the line deleted): exactly 27 corpus queries miss (`queries-with-read-term-missing` 27), answers equal, 544a8c885fcd4911. Say these three things: (1) answers come from Python in a shadow run whatever Rust does, so equal answers are weak here, since nothing consumes the refusal yet; (2) the shadow scores them as 27 `mismatch:key`, all `key nan None`, because `check_table` sees Python with a key and Rust without one; (3) `read_term_missing` is 108, 4 per query: **a miss isn't memoized**, unlike a raise, since `Err` isn't stored in `fn read` (`table.rs:337`). A real run discards at the first refusal, so I left it. Your call whether it's worth a line; report it either way.
- **Count test**: `rust-spike/slice/test_lazy_reads.py`, 72 passed, 5 skipped (`$O/test/t2.log`). Skips: 2 don't build (`Max(y,r)`, `Lt(r,y)`, this root isn't real), 3 Kept out-of-scope (non-Expr, so conversion never reaches them through `Q.positive`). Zero `complex()` for convert, TermTable and Python's ask at d=5. Plants restoring the eager read fail it for key and complex (`y+r`), power (`Pow(y**(1+r),3/2)`) and finite (`Pow(y*r,3/2)`) on stock terms, and commutative only on a planted class (no stock class shown evaluating through it: survey limit). The counter fires in the ask window on `Q.gt(y+r,1)`. Miss path, `read_raised`, BaseException, memo death with a second table and the walk's weakref are covered. All 55 hand-built terms that convert: complex, evalf, root all 0, at d=5.
- **d=30**, the ruling's example (`$O/test/d30.py`): convert plus table 0.023 s, ask 0.016 s, 0 `complex()`, on loaded orion, not a timing claim.
- **`lazy_reads.py`** dev, corpus: `with_extra` 0, answers same on every query, no raised, no missing. dev reads key 501, commutative 737; Python key 12,002, complex 207, power 106. corpus reads key 179, commutative 610; Python key 2,719, complex 105, power 16. **Rust read complex, finite and power 0 times in drive mode on those two,** so those kinds' values are tested only by the forced reads under checks. `lazy_complex` counts the whole pass, Python's ask included (65 dev queries, 31 corpus): not a lazy read. Don't quote it as one. Fuzz at 150 queries: `with_extra` 0, still running in full. `is_commutative` isn't compared, and a finite read can be hidden by `_assumptions`: see the file's docstring.
- **Handlers**: `lazy_fire.py` exit 0 (`$O/fire/lazy_fire.txt`). Each of the 4 plants reached; a `TermRefuse` from `table.sort_key`, by a raising read and by a miss, is seen at `_build_context` and `_consistent`; a BaseException comes through and isn't counted; unplanted 0. `quiet_fire.py port2` fires 4 of 4. **What a zero covers:** the shadow catches `TermRefuse` itself, so a zero in a shadow run covers other Exceptions from the read machinery only, not refusals, and in a plain run no lazy read happens at all. Nothing consumes conversion yet.

## What's left, in order

1. **The suite ruling, on `$O/suite/shadow`.** `shadow-keys.*.jsonl` has a row per key at a sort key site that's a product or not an input term: id, q, pid, site, n, pows, derived, outcome (matched, mismatch, `refused: ...`, unknown, no-table, outside-ask), term. A query is (pid, q). The census's 39 are `site == 'lra_adapter'`, derived, Mul. It has no ids, so these rows are the ids; compare your count to its 39 queries and 311 calls, and say so if they differ (the census is a floor, memos on). Report matched, refused, mismatched by id; **unknown, no-table and outside-ask were never compared, so name those; a refusal isn't evidence; if most refuse, name the shape.** `shadow.PID.json` counts: `key-outcome:*`, `convert:read_term_missing`, `convert:read_raised`, `queries-with-read-term-missing`, `kept`, `bad`. `shadow-rows.*.jsonl` is by test. Any `read_raised`: compare to Python's own run; if Python didn't raise it's a finding, with its smallest case.
2. **The plant on that path: not built.** In `algebra.rs` `mul_key`, multi-factor path: `let n = keys.len() as i64;` to `+ 1`, and removing `self.sort_values(&mut keys)?;` there (check each anchor is unique, since `add_key` differs). Add both as rows to `M` in `mutate_term.py`, or copy `solver_rs` and build. Run the test ids from step 1 with `SLICE_SO=DIR` under the shadow plugin and check which build loaded (FALSE ZEROS). Those rows must turn to mismatch.
3. **Suite-only shapes**: merge `shapes` from `$O/suite/shadow/shadow.*.json`, subtract the five workloads' in `$O/shapes/check-*.json`; `shape_example` has one each. Shape is one level of class and arg classes, `I:` input, `D:` derived; say that's how coarse it is.
4. **Shadow on against off:** suite rows by id, `rust` against `shadow`: name each test that differs. Off's numbers are the ones quoted. Name `test_wide_derived.py`'s wall-clock failures and `test_performance_smoke_300_vars` if they appear. Passed split per the reporting ruling, with `handlers.*.jsonl`; `test_ci_stream_reports_only_what_replays` goes in the second group. S's standing as the planner's rulings word it.
5. **`mutate_term.py`** has never run with its moved anchors and new `read-memo-off`, `read-text-swapped`: run on dev, detached, base row must read "no".
6. **Whole ask under DRIVE:** add to `test_lazy_reads.py`, in a subprocess since `term_shadow.install` can't be undone: `Q.positive(y+r)` with `DRIVE[0] = True`, zero `complex()`. The current test's ask is Python's only.
7. **Ruling 6:** `term_counts.py` is fixed but has only had its edits, **not a run**: `py` and `conv` on dev, fuzz, corpus on orion for counts (`counts_summary.py` in `~/sa-rust-ids-work/sa-port-18/` may need the new fields). `conv` reads no table, so "keys computed" is 0 by construction and "used" comes from `lazy_reads` or `key-used`. Times on a quiet pareto1 lease: `~/sp19/p1_job.sh`, x86-64 `.so` rebuilt, `p1-site-time.py` needs its targets changed (`closed` and the eager keys are gone; time `_Walk.read` and `_read_*` by kind), `timing_summary.py`. With `klass`'s share, and stop there. Pareto1 had shared leases at 10:37; speed isn't a gate. The ruling's old numbers: 0.20x / 0.14x / 0.57x.
8. **Section 9** (`enclose` no longer "the one permanent callback": read-only callbacks on input terms; Closed terms, Power factors, Term facts rows are now reads; `:634`'s note), `convert.py`'s header lines 6-7, `TERMS-INTERFACE.md` (`reads`, `row` shows what's read so far, new methods, a lazy key can't add a term, `-oo`, `raised`). Say what changed: sa-port-31 builds on it.
9. Rebase on `origin/rust-slice` (ceb6ceb at 10:45: 3 docs files, **including `PORT-INVENTORY.md`, so section 9 may conflict**; no source changes, so no suite rerun unless more arrives). Push with no force. **Tell the architect the SHA first,** then report.

## The report owes

SHA; three numbers; passed split; what ran and didn't; module count against the 32; `read_term_missing` and `read_raised` per workload and suite; nan decision (accepted, the plant's result with the three caveats above); `is_finite` and `decompose_power` catching Exception; `Kept('too-deep')` against eager; survey limits; the sha compared (done above); handler zero's coverage; suite ruling's four items; ruling 3 Pow counts (dev 0 holding; corpus 9 holding, 9 finished with no refusal under checks; 8 `derived key: power base` refusals are on derived terms); evaluator wanted or not. Name shims: `_n_conflicts` view, 64 tests. Mutants 2, 5, 6, 7, 9 and the 10 of 25 boundary statement stand.

## Changes this session (all on `port/lazy`)

`convert.py`: `raised` list on the walk, nothing else. `term_shadow.py`: `KEY_HOOK`, `IN_TOP`, `SHAPES`, per-query miss and raise counts; the DRIVE flag ran for the first time in `lazy_reads.py`. `term_counts.py`: fixed, unrun. `term_shadow_fresh.py`: `--drive`, `--handlers`. New: `test_lazy_reads.py`, `lazy_reads.py`, `lazy_fire.py`, `term_shadow_suite.py`; copied from port/3: `handler_count.py`, `quiet_fire.py`.

## Traps

- `xargs -L 1`: a trailing blank joins the next line. It cost one batch.
- `git ls-files | tar` keeps the tree's modes: `run_suite.sh` isn't executable, so `bash` it.
- Snapshots: `snap` has no `lazy_reads.py`; `snap3` is the newest. Jobs read from them, so edit the clone freely. `convert.py` differs between clone and snapshots only if you change it, and then the runs need repeating.
- Kill by the session id of a detached job, after listing it with `ps -eo pid,sid,cmd | awk '$2==SID'`.

## Map (use rg)

| Topic | Where |
|---|---|
| Key outcome by site | `term_shadow.py` `counted`, `KEY_HOOK`; `term_shadow_suite.py` `_key` |
| Shapes | `term_shadow.py` `shape`, `note_shapes` |
| Key of a product | `algebra.rs` `mul_key` |
| LRA's key sites | `lra_adapter.py:324,348,412` |
| Mutants | `mutate_term.py` `M`, build `:85` |
