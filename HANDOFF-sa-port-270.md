# HANDOFF sa-port-270: formula step (issue 323), fourteenth part

Branch `port/formula`, head = this commit, on rust-slice **9151316**. **Unbarred, unlanded.** Handed off at the context
budget, between items. Done this session: both markers read, `cls:eq` explained (the gate's first item), the exact
`fm:again` rows with their bar phase and kept test (gate (2), first half), item 4f, the probe's two `_rust_call`
reasons shown to fire. **Not done:** the plant table to the independent-check standard (its sweep is read below, the
table is not written into port-formula.md), gate (1) in a report, the relations.py carrier runs (scripts ready, not
run), items 4b-4e and 4g-4j, the bar. Before this: HANDOFF-sa-port-269.md.

## Markers (task 1)
- Whole lra workload on ded8c3f against Python, `--check entry`: **MATCH** (`~/sa-rust-ids-work/sa-port-269/lra-ded8c3f/`:
  1,500 queries, `answers_sha` dfd39d2b106757ce, 456 discarded runs, `rust.err` empty, every `*_diff` 0).
- 269's six chain suites (pareto1, `-n 8`): each **127 failed / 5,991 passed / 23 skipped / 18 xfailed**, af8cc0b's
  source included. 1a91a81's earlier 128 / 5,990 was the wall-clock test
  `test_wide_derived.py::test_wide_or_compiles_in_linear_time[nonnegative]`. The failed ids were not listed against the
  base set this session (the count equals f42047a's and base's 127).

## cls:eq (the gate's first item): not a fall by commit. Commit `6ec4638`
Full text: results/port-formula.md, last section. In short:
- The chain's six suites give 105, 67, 144, 343, 434, 140 (4d34c27, f848edd, f848edd + plant 609, 1a91a81, 1a91a81 +
  plant 611, af8cc0b), each time in one or two xdist workers and in different test files. The same SHA has two numbers
  (f848edd 457 and 67; 1a91a81 30 and 343).
- Eight test files in one process and a fixed order: **118 on 4d34c27, f848edd, 1a91a81 and af8cc0b**; with SymPy's
  cache emptied before every test **300 on all four**; 0 tests differ between any two runs; plants 609 and 611 leave
  both numbers as they are.
- Cause: SymPy caches `Function('f')`. When that entry is lost, the next `Function('f')` is a new, equal class, and
  `f(x)` on it returns the cached application of the old class (`~/sa-rust-ids-work/sa-port-270/mech.py`). Eviction as
  the suite's way of losing the entry is inferred (no test under tests/ calls `clear_cache`), not traced.
- No path stopped, no work removed, nothing for the planner as a fall. No table is named by `mark-skips-native:NAME`.

## Gate (2), first half: exact conversion rows. Commits `6648573` and this one (lra's row)
- `fm_rows.py run OUT.json WL` (live.py on Rust, `--check plain`, `formula_track(True)`) and `fm_rows.py check DIR`
  against results/fm_rows.json: exit 1 on any difference, a workload with no row, a row with no run. The row is
  `fm:again`, `fm:convert`, `fm:twice`, `fm:twice:patched`, `fm:nosession`; `fm:plant_fired` is written beside it and
  never compared.
- Rows on af8cc0b's source, 20 workloads, in results/fm_rows.json. The 19 short ones were run twice on orion with equal
  rows. lra: `fm:again` 98, `fm:convert` 7,308, answers_sha dfd39d2b106757ce, two runs with equal rows
  (`fm-lra/`, `fm-lra2/`). Its plant 608 run was started detached and had not ended when this was written
  (`fm-lra-p608/end.txt`): **not read**.
- Plant 608 `fm-hand-kept` on the 19: the check fails on **17**. It is **void on f6** (`fm:plant_fired` 0 there, row
  unchanged: the plant does not fire in f6 although f6 has `fm:again` 896; not looked into) and on twin (`fm:again` 0).
- bar.sh has a phase `fmrows` (FM_WLS, FM_PLANTS; `$B/fmrows/check.txt`, `$B/fmrows-PLANT/check.txt`) and bar_sum.py
  prints each check's last two lines. Kept test test_fm_rows.py (3 pass): cert and opaque match their rows; plant 608
  fails the check on both without its counter; a missing run and an unknown workload fail.
- Every `fm:twice`, `fm:twice:patched` and `fm:nosession` is 0 on all 20.

## Gate (2), second half: the plant sweep (pareto1). READ, NOT YET A TABLE
Every plant of the step over the 19 short workloads on the head's source (pareto1 `sweep1/`, tree 6648573, 418 runs,
all exit 0; `python3 p1/sweep_sum.py sweep1`). Each run is `fm_rows.py run` (`--check plain`). "Caught" here means only:
the answers differ from the plain run (`answers_sha`) or the fm row differs. The two plain runs agree on both for all 19.
State against Python (`--check entry` and livecmp) was **not** run, so "not caught" below is not a verdict yet.

| plant | id | `fm:plant_fired` > 0 on | caught on (answers or row) |
|---|---|---|---|
| `fm-atoms-drop-last` | 601 | 19 | 11: answers on budget, cert, cls, dev, fuzz, port, scope, transfer:7:60, twin, zero; row also on loop |
| `fm-atoms-no-dedupe` | 602 | 16 | **0** |
| `fm-args-reverse` | 603 | 15 | **0** |
| `fm-implies-swap` | 604 | 4 | 3: answers on loop, scope, wiring |
| `fm-ite-swap` | 605 | **0** | 0: no workload reaches it |
| `fm-not-drop` | 606 | 14 | 14: answers on all 14 |
| `fm-hand-no-give` | 607 | 19 | 19: row on all |
| `fm-hand-kept` | 608 | 17 | 17: row on all 17 (void on f6 and twin) |
| `fm-hand-instrument-by-name` | 609 | 0 | 0: no workload registers an instrument; kept tests only (test_convert_once.py) |
| `fm-hand-patched-direct` | 610 | 0 | 0: no workload replaces a method; kept tests only |
| `ad-lra-class-is` | 660 | 13 | **0** |
| `class-is` | 661 | 2 | 2: answers on twin, row on cls |
| `ad-lra-atom-object` | 662 | 4 | **0** |
| `same-is` | 663 | **0** | 0: no workload reaches it |

For 600 `rows-product-verdict-flip`, 664 `atom-symbol-key-names`, 665 `dispatch-keeps-memo`, 666 `mark-cuts-patterns`,
667 `mark-leaves-entry` and 611 `mark-skips-native` the sweep shows only that no answer and no fm row moves on these 19:
they are not counted in `fm:plant_fired`, so whether they fired was not read, and their checks are elsewhere (the
kept_product mismatch counter, test_cache_fix.py, test_cache_rollback.py, test_discard_exempt.py and term_discard.py).

What this leaves for the table (and for 4d): 602, 603, 660 and 662 fire and move neither answers nor rows, so each
needs the state comparison against Python or a class (speed-only, redundant) with its reason; 605 and 663 are
unreached on the workloads and need a workload or a class. 4d names 602, 604, 605 and 663: 604 is caught on three.

Gate (1), discarded runs per workload from the same plain runs: f6 13, opaque 7, value 15, wiring 1, lra 456 (orion),
the other 15 are 0. Not yet in a report's table.

## Item 4f. Commit `271673f`
test_term_live.py's two failing tests built a `_Mark` by `__new__` without the `natives` field 1a91a81 added. Field
added in the tests; 20 passed, 1 skipped. The other half of 4f is the bar's invocation: test_handler_count.py and
test_catch_count.py with `-p rust_plugin -p handler_count`, test_cf_diff.py as a script (MISMATCHES 0); not set up.

## The relations.py fallback carrier (task 4): one part shown, the runs not started
- pyc266's two `_rust_call` reasons fire on planted calls (`~/sa-rust-ids-work/sa-port-270/rc_plant.py`, orion, the
  head): a table that is no TableView gives `rust_call:not_tableview` 1 for each of `_compile_formula` and
  `_formula_literal`; a `dv` that is not the session's gives `rust_call:dv_not_session` 1 for each; a real query
  before and after adds none. Their zero in the suite can now be reported.
- **Guess, not shown:** the carrier is the same lost SymPy cache entry as `cls:eq`'s. On base the 615 calls sat in the
  tests where the chain's plant-611 run has its `cls:eq` (5 of `test_split_relational_answer_is_the_part_answer`,
  `test_transfer_answers`, `test_undefined_function_connects`). On base a row across two class objects was compared
  by identity and fell back to Python; since the `same_class` rule (a5fa1f6, 425ca5e) it counts `cls:eq` and stays in
  Rust. If so, plant 661 `class-is` on the head brings the calls back, and emptying the cache before each test brings
  them on base without any earlier test.
- Ready on pareto1, **not run**: `~/sp19/sa-rust-ids-work/sa-port-270/p1/carrier270.sh` (under a shared lease; output
  `carrier/`, a line per run in `carrier/runs.txt`, end marker `carrier/end.txt`), read with
  `python3 p1/carrier_sum.py carrier/*-*`. It runs 266's order and its reverse, and test_relevance.py + test_transfer.py
  plain and with the cache emptied per test, on the head, the head with plant 661, base 9151316, 1e90a19, a5fa1f6 and
  425ca5e. The three old SHAs are built there first and may not compile (the branch was rebased at 78962f7); a failed
  build is written to `carrier/builds.txt` and skipped. Wanted: 0 calls on the head in both orders; the calls back
  under plant 661; base's 511 in the forward order; the first SHA at 0 names the commit.

## Not started
- Gate (1): the discarded count per workload in the report. live.py's totals carry it (`discarded.runs`); the sweep's
  `plain1/*.tot` have it for the 19 short workloads on the head's source, lra is 456.
- 4b (`ad:cbm_noid == 0` on cls as a verdict line, plants 660-662 flip it), 4c (relations.py:1116), 4d (plants 602,
  604, 605, 663 classified: take it from the sweep), 4e (twin harness and two-order harness as kept tests), 4h (the
  `clear()` test), 4j (the join test's `link:second 3` line).
- 4g, **real work**: moved_digest.py :122-:138 still replaces `Relations.__init__`, `_interpret` and `_link` (its
  mid-query samples of the work lists, `sample` :300), so with the digest on Rust forwards by name (`sb:fwd_named`,
  session.rs :100). Either the digest registers as an instrument the way catch_count does for `verdict`
  (session_live.py `INSTRUMENTS` :941, context.rs :68-:92), or the samples are taken another way. Not designed.
- 4i is already in the tree (moved_digest.py :395-:397 compares keys and values, from 78962f7); it needs only its line
  in the bar report.
- The bar, D, E, C, and every standing row of the report (handler multiset, inventory, kept shares, `_SPLIT`/`_CACHE`
  rows, cache_det, module-wide probes, Formula callbacks, `rk:intern:*`, kept_product mismatch, PY_COMPILE fallback,
  catch counts, Group D seconds). None was measured this session.
- Budget gate for the bar: its projected end plus pareto1's lease wait before the early end of arch-tick's 90% range
  (20:22Z 11 Nov as read at 03:19Z; recheck the WEEK line).

## File:line map (this head)
- fm_rows.py: ROW :20, `run` :29, `check` :44. test_fm_rows.py: WLS :13, tests :48-:74. results/fm_rows.json.
- p1/bar.sh: phase list :72, `fmrows` phase :150-:159 (FM_WLS, FM_PLANTS in the header). p1/bar_sum.py: PHASES :6, the
  fm rows lines at the end.
- formula.rs: `same_class` :214, PLANTS :103, TRACK :137, `fm:again` tick :534, `formula_plant` :751,
  `formula_track` :795. term_live.py: `same_class` :355, `_Mark` :173 (`natives` :184), rollback :233, PLANT :352, the
  environment channels :1158.
- session_live.py: INSTRUMENTS :941, `_rust_call` :1338, `_compile_formula` :1350, `_formula_literal` :1360.
  moved_digest.py: the replaced methods :122-:138, `sample` :300, the `_CACHE` row :395.
- test_term_live.py: the two fixed tests :334, :351.
- Everything else: HANDOFF-sa-port-269.md's map and those it names.

## Helpers and output
- orion `~/sa-rust-ids-work/sa-port-270/`: fmrows.sh OUT WL... (TREE=, SLICE_SESSION_PLANT=, J=), fm-1/, fm-2/,
  fm-p608/, fm-lra/, fm-lra2/, fm-lra-p608/, mech.py, rc_plant.py (both by 269's py.sh), p1/ (copies of what is on
  pareto1).
- pareto1 `~/sp19/sa-rust-ids-work/sa-port-270/`: p1/ (fixed270.sh SHA OUT [pytest args], fixedall.sh, fixedplants.sh,
  clr270.py, sweep270.sh OUT, sweep_sum.py DIR, carrier270.sh, carrier_sum.py, bis-order.txt and its reverse),
  fixed-*/ (the `cls:eq` runs), prebar/ (the head's build), sweep1/. Tree `~/sp19/dev/sa-port-270` at 6648573, .so
  sha256 04edbdcb... (equal to af8cc0b's). `~/sp19/bar-sa-port-270.sh` is bar.sh as of 6648573.
- No plant and no counter was taken (612-629, 668-669 and 649-659, 673-679 are free).
