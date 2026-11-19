# Handoff: sa-port-332 to the next session (issue 323, F_MAYBE_NAN removal)

Handed off at the budget note with the source written, built and pushed, and **nothing under the bar yet**.

## State

- Branch `port/maybe-nan-removal`, head 7dd452c (source; this file is one commit above it), from rust-slice ec34788.
  Pushed to the clone's origin. Worktree: orion `~/sa-rust-ids-work/sa-port-332/wt` (clone ~/dev/sa-port-24).
- Orion .so of 7dd452c: 4465a343 (aarch64, not the bar's). 17 compiler warnings (base 18).
- No job is running. No lease is held. Nothing was run on pareto0 or pareto1.

## Ruling item (1): why the bit existed, and its readers. No stop condition met

- `git log -S F_MAYBE_NAN`: added by **5501d34** (7 Nov, "Conversion, term table and shadow, run on dev; handoff").
  Its message gives no reason for the bit. The reason is in the format it built: PORT-INVENTORY.md:330 (2c195c4), Term
  facts "... `may_be_nan`", requirement column "`_may_be_nan`"; HANDOFF-sa-port-5.md:28 names the Python reader it
  mirrors, `templates/__init__.py` `_may_be_nan`; TERMS-INTERFACE.md:54 (1871dc1) lists it under `table.facts(t)`.
- `fact::MAYBE_NAN` (table.rs:57) came in with the same commit and was never used after it.
- The planned reader is built and does not use the bit: the templates decide through `_applied_to_nan`, which is
  `Dispatch::opaque` (dispatch.rs:101) and calls the native `may_be_nan` on the arguments.
- HANDOFF-sa-port-13.md:45 says derived rows don't carry `MAYBE_NAN` and "a consumer in 2 or 4 must add them or refuse".
  Components 2 (EUF core) and 4 (relations and adapters) are landed and neither reads it: the algebra's inherit mask
  is NAN|BAD|FLOAT|UNDEF (algebra.rs:79), and lra_read.rs:171-174, :327, :390-393, tcore.rs:87 and table.rs:442-494 mask
  other flags.
- Python readers of a row's flags: convert.py:71 (the constants) and :305 (the writer, removed); term_shadow.py:161
  (a check against `_may_be_nan`, removed with the bit); term_history.py:78-83 (masks F_NUMBER and F_READ, and hashes
  `row[:5]`, the whole byte: both sides of its comparison lose the bit alike); py.rs:343 hands the byte to
  `Table.row`. No non-test reader consumes the bit.

## What 7dd452c changes

- convert.py:72 `F_RESERVED_32` in the bit's place; `term_row` (:269) no longer calls `_may_be_nan`, and the import is
  gone. `WALK_PLANTS` (:446) ends at 5.
- walk.rs: `term_row_native` (:634) no longer sets the bit; `F_MAYBE_NAN`, the three plant numbers, `nan_plant` and
  `WalkCtx.specials` are gone. table.rs:57 is a comment reserving 32.
- dispatch.rs: `may_be_nan` (:124) is private again, without the plant parameter and its three branches. Its cases
  are the ones it had. `opaque` (:101) has plant 753 `dispatch-nan-arg-off` (SLICE_SESSION_PLANT, listed at
  knowledge_live.py:70): a True of `may_be_nan` for an argument is taken as False; counted as `plant:fired` (:434-437).
- term_shadow.py:160 drops the bit from its facts check. mutate_term.py: `conv-maybe-nan` removed.
- test_convert_walk.py: `nan_cases`, `nan_rows`, `nan_differences` and their two tests removed; plants 746-748 removed
  from `ALL_PLANTS` (:37); new `test_reserved_bit_is_zero` (:145). `inputs()` is back to 51 cases.
- p1/bar.sh: one comment line. registry_count.py:206 still prints whether convert's `_may_be_nan` was rebound; it now
  prints False. Not edited.
- Python's `_may_be_nan` and `_applied_to_nan` (templates/__init__.py:142-171): unchanged.
- Row bytes differ from ec34788 in bit 32 only (not yet measured on a workload; see Open 3).

## Checked so far, orion only (7dd452c, .so 4465a343)

- test_convert_walk.py: 16 passed (-n 4).
- `live.py opaque`: Rust against Python MATCH (livecmp --end-only exit 0).
- Plant 753 on `opaque`: DIFFER (answers_sha c7e1a7ca3a110ebb against 88400508b492fed1). **Its fired count was not
  read** (my grep of the run's output found no `plant:fired`); the bar's `fired()` reads it.
- Outputs: ~/sa-rust-ids-work/sa-port-332/ (build.log, tree.txt, tcw.log, op-*.out, op-*.cmp).

## To tell the planner about plant 753

`dispatch-opaque-off` already exists at the same site (dispatch.rs:439, in knowledge_live.PLANTS): it turns `opaque`'s
True into False, and port-6g.md:47 has it firing 274 times on the `opaque` workload, caught. Plant 753 as written has
the same effect, one line earlier. If the planner would rather have a different wrong value at the call (for example
an empty `specials`, so only infinities in arithmetic go unseen), it is a two-line change at dispatch.rs:107.

## Open, in order

1. The 2x2 and the count probe, pareto1, shared lease: results/tools324/pc324.sh REF TAG with its paths renamed to
   sa-port-332 (it clones origin/REF, builds, runs the 20 workloads' Python references and the four cells under
   pcby324.py). Once on ec34788 (before), once on the head (after). Expect templates/__init__.py at 20 import calls
   in all four cells after; say whether the count moves from 21/32.
2. The bar, pareto0, with only the rows this step needs. Start from results/tools324/job326.sh (317's config). Drop
   the three `convert:nan-*` rows; add `dispatch-nan-arg-off` to PLANTS and SUITE_PLANTS; keep `walk:rust`,
   `both:rust`, the five `convert:*` rows and `dispatch-opaque-off` beside 753. BASE: 326's bar suite rows on pareto0,
   ~/sp19/sa-rust-ids-work/sa-port-326/bar/suite (tested 6587181, source of rust-slice ec34788). The x86-64 .so is
   built on pareto1 and copied. `machine ls` first; rule [91].
3. One line for "row bytes differ in the bit only": convert_diff or term_history rows of `opaque` on ec34788 against
   the head (327 counted 5,838 True calls there, 0 on the other 17 workloads).
4. Report whether a workload answer or a suite id catches 753, with its fired count. If nothing does, list `opaque`'s
   use as a removal candidate with an owner; don't remove it.
5. Land per the brief (rebase, `bar.sh land`, push without force), then results/maybe-nan-removal.md and the report.

## File:line map (7dd452c)

- solver_rs/src/term/dispatch.rs: `opaque` :101, plant 753 :108, `may_be_nan` :124, fired count :434-437,
  `dispatch-opaque-off` :439.
- solver_rs/src/term/walk.rs: reserved comment :51, `term_row_native` :634, `Depth` ~:238.
- solver_rs/src/term/table.rs: reserved comment :57. py.rs:343 hands the row's bits to Python.
- convert.py: flags :72, `term_row` :269, WALK_PLANTS :446. term_shadow.py:160. term_history.py:78-83.
- test_convert_walk.py: ALL_PLANTS :37, `test_reserved_bit_is_zero` :145, `test_plant_is_caught` :222.
- knowledge_live.py: PLANTS :68-70. p1/bar.sh: `penv` :91.
- results/tools324/: pc324.sh, pcby324.py, pccmp324.py (2x2 and probe), job326.sh (bar launcher).
  results/tools327/: run1.sh, sweep.sh (planted-history repeat check), nancount327.py.
