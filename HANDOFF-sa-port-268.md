# HANDOFF sa-port-268: formula step (issue 323), twelfth part

Branch `port/formula`, head = this commit, on rust-slice **9151316**. **Unbarred, unlanded.** Handed off at the context
budget, between items. The gate's first item (the discard rolls back the Rust-native tables) is committed with its tests
and plant; plant 608 was run on the two-order harness. The second ruling (`_context_session`, `_within_budget`), the
relations.py fallback carrier, items 4b-4j and the bar are **not started**. Before this: HANDOFF-sa-port-267.md.

## Commit of this session
`1a91a81` the discard rolls back the Rust-native tables (the planner's ruling on lra's cause, gate for sa-port-268).
- **The carrier of q204's constant order is named: the engine's structure memos `Engine._kids`, `_cones` and `_qcones`**
  (native `EngineMemo`s). With the rollback of any one of the three skipped, lra queries 204 and 585 differ from Python
  again (end, stream, lra; stats equal). `Engine.splits` or `_verdict` skipped: query 73 differs (2 sessions for Python's
  3) and the stats of all four. Skipping any one of `_glue_adapters`, `_failed`, `_xbasis`, `_SPLIT`, `_WANT`, `_NEIGH`,
  `_CLOSED`, `_SYMPY_ATOMS`, `SPEC_ROWS`, `ENCLOSURES` leaves the four queries MATCHing. Table:
  `~/sa-rust-ids-work/sa-port-268/lra/skip-table.txt` (skip1.sh NAME).
- Rust: every native table marks itself and takes out what a run added. `EngineMemo._nt_mark/_nt_rollback` cut the map
  back to its size at the mark; a map emptied since the mark is emptied (as `_Mark` does a Python table). The process
  tables (`_WANT`, `_SPLIT`, `_NEIGH`, `_CLOSED`, `_SYMPY_ATOMS`, `SPEC_ROWS`, `ENCLOSURES`) log the keys they add
  (memos.rs `AddLog`) and `NativeTable._nt_mark/_nt_rollback` remove those. A value written over an existing key is not
  undone, as in a Python dict rolled back by size.
- term_live.py `_Mark`: marks every native view (`_note`), rolls them back first (`rollback`), counted
  `rollback:native`. **Plant 611 `mark-skips-native`** leaves them all; `mark-skips-native:NAME` leaves one table.
- term_discard.py: the check reads a native table's rows (`_native`); before, it compared the live view with itself.
  `fresh.py --full` installs session_live and knowledge_live as live.py does, so `--discard` checks the native tables
  (without it the engine's memos are Python dicts and the check never saw a native one).
- live.py and moved_digest.py: a discarded run's solvers, sessions and relations leave the record with the run
  (`_discarded_runs`; fresh.py already did this). Counted in the totals line, `discarded`: runs, solvers,
  digest_sessions. **This is a change to the recorder and it is the planner's to accept**: before the fix the rerun did
  one session fewer than Python and the discarded run's session made the counts equal by accident; with the fix the
  record held 4 sessions for Python's 3 on query 73 until the discarded one was dropped.
- Kept tests, test_discard_exempt.py (5 pass): the unplanted `--full` run is clean on 30 of 30 with 1,530 native reads;
  plant 611 is flagged on 29 of 30 and names `splits`, `_verdict`, `_kids`, `_cones`, `_qcones` (also `_SPLIT`, `_WANT`,
  `_CLOSED`).

## Results on 1a91a81
- The four lra queries (73, 204, 585, 6), `--check entry`, Rust against Python: **MATCH** (`lra/q4-fix.cmp`); on the
  head before (3f55839): DIFFER. With plant 611: DIFFER (`lra/s-all.cmp`), so lra catches the plant.
- The whole lra workload against Python (`--check entry`, orion, `lrafull.sh lra-1a91a81`): **still running, detached**
  when this was written. Its verdict is the last word of `~/sa-rust-ids-work/sa-port-268/lra-1a91a81/end.txt` (cmp.txt
  beside it; Python's side is `lra-py/`). lra's known row is **not removed yet**: that waits for this MATCH.
- Suite (pareto1, -n 8, `suite-1a91a81`, ended 02:09Z): **128 failed, 5,990 passed, 23 skipped, 18 xfailed**; f848edd and
  base: 127 failed, 5,991 passed. **One test differs:** `tests/test_wide_derived.py::test_wide_or_compiles_in_linear_time
  [nonnegative]`, a wall-clock assertion (`perf_counter() - t < 1.0`, it took 1.72 s under -n 8 with another job on the
  machine). The file alone passes, 72 of 72, on 1a91a81 (twice) and on f848edd (`wide-1a91a81`, `wide-1a91a81-b`,
  sa-port-267's `wide-f848edd-268`). The other 127 failures are the same tests as f848edd's.
  Suite sums (f848edd): `fm:convert` 89,351 (89,236), `fm:give` 90,508 (89,980), `rk:intern:engine` 991,048 (993,317),
  `rk:intern:input` 106,589 (106,698), relations.py frames in converted queries 0 (0), **`cls:eq` 30 (457; base 722)**.
  The second fall of `cls:eq` came with this commit and was **not looked into**; the planner's item (explain 722 to 457
  before landing) now has to cover 457 to 30 as well. The `fm:twice`, `fm:nosession`, `fm:twice:patched` rows and the
  catch counts against the base were not read on this suite (sum266.py's output is `suite-1a91a81/sum.txt`, f848edd's
  beside it as `sum-f848edd.txt`). Passed was not split by firing.
- 20 workloads (pareto1, `wl-1a91a81`, `--check plain`, ended 02:07Z, all exit 0) against `wl-f848edd`: every counter
  of pyc_wl.py's is equal on 17 workloads. The three with discarded runs differ, as the fix intends: f6 (13 discarded
  runs, 7 counters, e.g. `bud:kids_hit` 892 to 889, `rel:closed_units` 12,223 to 12,226), wiring (1 run, 7 counters),
  lra (456 runs, 187 counters, e.g. `ad:cb_memoized` 26,972 to 29,427). `answers_sha` is equal on f6, wiring, lra, dev
  and fuzz; the other 15 were not compared by answer (their counters are all equal). The per-workload table of the
  report's standing rows was not rebuilt.
- Slice test files (orion, 3 at a time, `tests-1a91a81/tests.txt`, one line a file; **still running, detached**, 42 of
  59 files done when this was written, `end.txt` when all are): the only non-zero exits so far are the three known
  invocation ones, test_catch_count.py (3 failed), test_handler_count.py (2 failed) and test_cf_diff.py (1 error),
  run here without their plugins. No f848edd run of all 59 files exists to compare with; sa-port-267 ran eight.

## Plant 608 on the two-order harness: fires, moves no answer
`~/sa-rust-ids-work/sa-port-268/two/` (two608.py MODE OUT [PLANT] runs sa-port-250's twoorder.py after
`test_discovery_core._rust()`). 560 rows in each order. Plant `fm-hand-kept`: `fm:plant_fired` 621, `formula_held()`
1,135 (orig-first) and 1,134 (twin-first) against 0 unplanted, `fm:convert` 514 and 513 against 1,135 and 1,134.
**Answers: 0 of 560 rows differ from the unplanted run in either order, and 0 flip between the orders.** So the harness
sees plant 608 by its counters only, not by an answer: its twin is a new object and a kept node answers only for the
object it was built from. H2 asks for the plant to be caught by the two-order harness; whether the counter reading
counts, or the harness needs a row where one object is asked twice with something changed between, is the planner's.

## Stores the discard does not restore and the check does not read (named, no owner yet)
Not in the registry, so neither `_Mark` nor term_discard.py reaches them: `Dispatch.memo` and `Dispatch.classes`
(term/dispatch.rs :52-:56, Rust's stand-in for `registry._clauses_cache`/`_mro_cache`), adapters.rs `LIVE` (the LRA
slot, :221), formula.rs `SEEN`/`KEPT`. `Engine._context_sessions` (slot 7) and `_constructing` are compared by length
and by content, as before. By the gate, each needs a rollback or the same proof `_CACHE` has; none was looked into.

## Not started
The second ruling for 268 (one helper for `verdict`, `_context_session`, `_within_budget`: registered instrument keeps
the direct call, a user's patch is called by name inside `formula::Patched`, one kept test each). Read for it: only
tools/query_log.py:169 patches `Engine._context_session`, and nothing of ours patches `_within_budget`, so (a) has no
instrument to register today; the sites are context.rs `context_session_from` :140 and budget.rs `within_from` :560,
both through `patched_method` :103, and `verdict_from` :148 has the shape to reuse. Also not started: `cls:eq` 722 to
457 explained; the relations.py fallback carrier (bis-order.txt on the head in both orders, the bisect on base, pyc266's
two `_rust_call` reasons on a plant); items 4b-4j; the bar. The report's standing rows were not measured this session:
handler multiset, plant table, inventory, kept shares, `_SPLIT`/`_CACHE` rows, cache_det, module-wide probes, answers
against the reference, Formula callbacks per workload, Group D seconds.

## File:line map (this head)
- engmemo.rs: `emptied` :75, `wipe` :169, `_nt_mark` :255, `_nt_rollback` :261. memos.rs: `AddLog` :37, `since` :56,
  `Native.mark/rollback` fields, `NativeTable._nt_mark` :169, `_nt_rollback` :173. procmemo.rs: `Gone` :54,
  `PyKeyMap::rollback` :117, `split_mark` :204, `split_rollback` :208. relations_core.rs: `SPEC_LOG` :2698,
  `spec_rows_rollback` :2754. constfield.rs: `ENC_LOG` :187, `enclosures_rollback` :210.
- term_live.py: `_Mark` :134, `_note` :164 (natives :171), `rollback` :190 (plant 611 :196-:201, plant 667 after it),
  PLANT :309. term_discard.py: EXEMPT :48, `_sig` :80, `_native` :84, `_copy` :92, `check` :136. fresh.py `--full` :34,
  :125. live.py `_discarded_runs` :296, its install :456, the totals :578. moved_digest.py `run_mark` :198,
  `run_discard` :202. test_discard_exempt.py: `run` :29, NATIVE :82, tests :54-:105.
- context.rs: `Method` :65, `method_of` :75, `patched_method` :103, `context_session_from` :140, `verdict_from` :148.
  budget.rs `within_from` :560. entry.rs callers :769, :773, :795; relevance.rs :638; context.rs :332.
- Everything else: HANDOFF-sa-port-267.md's map (formula.rs, session_live.py, test_convert_once.py, unchanged).

## Helpers and output
- orion `~/sa-rust-ids-work/sa-port-268/`: py.sh (python on this clone, cwd rust-spike/slice), lra/ (q4-*.jsonl,
  skip1.sh's s-*.cmp, skip-table.txt), lrafull.sh OUT (whole lra, both backends, livecmp, end.txt), disc/, two/,
  tests.sh OUT [FILES], tests-1a91a81/, p1/ (sa-port-267's helpers with this session's paths).
- pareto1 `~/sp19/sa-rust-ids-work/sa-port-268/` (p1/, suite-1a91a81/, wl-1a91a81/), tree
  `~/sp19/dev/sa-port-268-1a91a81` with its x86-64 .so. Launch as in HANDOFF-sa-port-266.md with `sa-port-268`.
- Plant 611 is taken this session (612-629, 668-669 free); no counter was taken (649-659, 673-679 free).
