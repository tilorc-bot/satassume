# HANDOFF sa-port-269: formula step (issue 323), thirteenth part

Branch `port/formula`, head = this commit, on rust-slice **9151316**. **Unbarred, unlanded.** Handed off at the context
budget, between items. Done this session: the markers read, gate item (4) (the four stores) and the patched-method helper,
each its own commit with tests. The `cls:eq` bisect (gate (3)) is **running detached**; its reading, gate (2)/(1), the
relations.py carrier, items 4b-4j and the bar are **not done**. Before this: HANDOFF-sa-port-268.md.

## Markers of 268's jobs (on 1a91a81)
- Whole lra workload against Python, `--check entry`: **MATCH** (`~/sa-rust-ids-work/sa-port-268/lra-1a91a81/end.txt`,
  1,500 queries, `answers_sha` dfd39d2b106757ce on both, 456 discarded runs, `rust.err` empty). lra's known row is
  removed: it was never an entry in a file (`known_moved.json` is `{}`), only the bar's stated expectation "lra DIFFER"
  (results/port-formula.md :375-:406, HANDOFF-sa-port-260.md :20). **The bar now expects lra to MATCH**; that text in
  port-formula.md is not edited yet.
- 59 slice test files: 55 exit 0. The four others: test_catch_count.py (3 failed), test_handler_count.py (2 failed),
  test_cf_diff.py (1 error), the known invocation ones, and **test_term_live.py (2 failed, 18 passed)**, the two stale
  tests of item 4f (268's handoff listed only three because this file had not ended).

## Commits of this session
`ded8c3f` gate (4): the four Rust stores outside the memo registry.
- `Dispatch.memo` and `Dispatch.classes` (+ `entries`): **rolled back and checked**. They mark by size and take out what
  a refused run added; a store emptied since the mark (epoch, `clear_memos`, the size limit) is emptied again.
- formula.rs `SEEN`: **rolled back and checked** (mark = its rows, rollback restores them). At a top query's discard it
  is empty: the discard happens in `sympy_api._ask`'s wrapper, after every entry's `Hand` has dropped.
- formula.rs `KEPT` and adapters.rs `LIVE`: **read by the check, not rolled back. This is an exemption from rollback and
  goes to the planner with this proof:** `KEPT`'s only writer is `Hand`'s drop under plant 608; `LIVE`'s only writer is
  `ad_lra_live` (lra_live's install and undo), which no query calls. Both are compared before the run and after the
  rollback at every discard, so a write would be flagged. An adapter's own slot is keyed by its `_Query` object, which
  it holds; a refused run's query is never current again (plant `ad-lra-slot-stale` is the existing check of that key).
- `term_live.NATIVE_EXTRA` lists the stores; `_Mark` notes them; term_discard.py reads each (`read:NAME`).
- Kept tests, test_discard_exempt.py (10 pass): plant 611 limited to `Dispatch.memo` or `Dispatch.classes` is named
  (24 and 30 of 30 runs); **plant 608 under the discard check is named `native:formula.KEPT`** (24 of 30; fresh.py
  `--formula-plant`), an independent check of 608 for ruling (2); `SEEN`'s mark and `LIVE`'s rows directly.
- lra's four queries (73, 204, 585, 6): MATCH on this commit; also MATCH with either Dispatch store's rollback skipped
  (lra does not see those two; the kept tests do).

`af8cc0b` the second ruling for 268: one helper, context.rs `call_from`, for `verdict`, `_context_session` and
`_within_budget`. `patched_method` is gone. Plants 609 and 610 cover all three methods now.
- Kept tests, test_convert_once.py (8 new): per method, a registered instrument keeps the direct call (wrapper 0 calls,
  `before()` 5 and 11 calls, `fm:twice:patched` 0, `_context_session`'s raise seen once); a user's method is called
  (5 and 12 calls) and its result decides the query (`'False'` and `'None'` where the real one gives `'True'`);
  plant 609 and plant 610 flip those rows. `_within_budget` has no raise to plant, so its `raised()` is not exercised.
- **A behaviour change to rule on:** `fm:nosession` is no longer counted behind a user's replaced method
  (`Hand::enter_inner` under a `Patched` scope). Before, a user's `_within_budget` calling the real one counted it (12 in
  the test's rows). No workload patches these methods.
- (a) of the ruling has no instrument to register today: tools/query_log.py:155 wraps `_context_session` with one
  argument where engine.py:2237 passes two, so that tool fails on both backends; no owner named.

Tests after both commits: test_convert_once, test_formula_nodes, test_context_core, test_entry_core,
test_discard_exempt: 77 passed, 3 skipped. The suite, the 20 workloads and the other slice files were **not** run on
either commit (the head's suite is the last run of the detached chain below).

## Detached jobs to read (both write their own end marker)
- orion, whole lra workload on ded8c3f (snapshot tree `~/sa-rust-ids-work/sa-port-269/tree-ded8c3f`, a git worktree of
  this clone): verdict is the last word of `~/sa-rust-ids-work/sa-port-269/lra-ded8c3f/end.txt`.
- pareto1, shared lease ef409716, `p1/chain.sh`: six suites with the per-test plugin `p1/clseq.py`, a line each in
  `~/sp19/sa-rust-ids-work/sa-port-269/chain.txt`, then `chain-end.txt`. Read each with
  `python3 p1/clsum.py suite-A [suite-B]` (totals, `cls:eq` by test file, the tests whose count differs).
  1. `suite-4d34c27`, 2. `suite-f848edd`, 3. `suite-f848edd-p609` (plant 609 on), 4. `suite-1a91a81`,
  5. `suite-1a91a81-p611` (plant 611 on), 6. `suite-af8cc0b` (the head's source; also this session's suite baseline).

## cls:eq (gate (3)): what is known, what the chain is to show
- The series is **722 on f42047a, 457 on f848edd, 30 on 1a91a81**. The base 9151316 has no such counter (it came with
  a5fa1f6); "722 (base)" in the brief is f42047a's number (HANDOFF-sa-port-266.md :89, -267.md :30).
- First fall: the source commits between are 4d34c27 (`is_` and `is_many` hand over the nodes) and f848edd (a registered
  instrument keeps the direct `verdict` call). Run 1 says which. **Guess, not shown:** f848edd, because before it the
  suite's `verdict` went by name through catch_count's wrapper and a second entry converted the query again, asking the
  class questions twice. If so, run 3 (plant 609) returns to about 722 and it is work removed, not a path stopped.
- Second fall: 1a91a81 is the only source commit. **Guess, not shown:** objects a discarded run left in the native
  tables gave later queries a second class object. If so, run 5 (plant 611) returns to about 457;
  `CLSEQ_TERM_PLANT=mark-skips-native:NAME` then names the table.
- Two-order check on the head (af8cc0b), `~/sa-rust-ids-work/sa-port-269/two/`: 560 rows in each order, rows equal to
  1a91a81's in both orders, orig != twin 0 and 0, flips between the orders 0; `fm:twice` 0, `fm:nosession` 0, held 0.

## Not started
- Gate (2): plant 608 caught on an independent check. Now there: test_convert_once.py's held test and the discard
  check above. Still to do: an exact `fm:again` row per workload that the bar fails on, and the same standard applied to
  every plant in the bar's plant table (no plant counted on `fm:plant_fired` alone).
- Gate (1): the per-workload "discarded" count in the report (live.py's totals already carry it).
- The relations.py fallback carrier; items 4b-4j; the bar; D, E, C.
- The standing rows of the report were not measured this session: handler multiset, plant table, inventory, kept
  shares, `_SPLIT`/`_CACHE` rows, cache_det, module-wide probes, answers against the reference, Formula callbacks,
  `rk:intern:*`, kept_product mismatch, PY_COMPILE fallback, catch counts, Group D seconds.
- A question for the planner that came up: with the dispatch memo and `_SPLIT` both rolled back, the reason given for
  leaving `_CACHE` (term_live.py `_Mark.__init__`'s comment) no longer holds as written; `_CACHE` could be rolled back
  too and its exemption dropped. Not tried; R3 stands until ruled.

## File:line map (this head)
- term/dispatch.rs: `emptied` :59, `_nt_mark` :337, `_nt_rollback` :346, `_nt_rows` :368. formula.rs: `enter_inner`
  :611, `formula_seen_rows` :768, `formula_seen_restore` :774, `formula_kept_rows` :782. adapters.rs `ad_lra_live_get`
  :267.
- context.rs: `method_of` :75, `call_from` :108, `context_session_from` :163, `verdict_from` :173. budget.rs
  `within_from` :561. Callers unchanged: entry.rs :769, :773, :795; relevance.rs :638.
- term_live.py: `_Seen` :110, `_Kept` :126, `_LraLive` :135, `NATIVE_EXTRA` :147, `_Mark` :173, `_note` :207,
  `rollback` :233, PLANT :352 (everything after :100 moved down by 39). term_discard.py: the extra stores :112.
  knowledge_live.py: `_Store` :254, added :269, removed :289. fresh.py `--formula-plant` :28, :134.
- test_discard_exempt.py: STORES :121, tests :124-:147. test_convert_once.py: the steps :154, BOTH :321, tests :335-:366.
- Everything else: HANDOFF-sa-port-268.md's map and those it names.

## Helpers and output
- orion `~/sa-rust-ids-work/sa-port-269/`: py.sh, lrafull.sh OUT, tests.sh OUT [FILES] (all take `TREE=`), skip1.sh
  NAME (plant 611 on one table, the four lra queries), lra/, disc/, two/, co-*.json (test_convert_once's rows per
  plant), p1/ (suite269.sh SHA OUT, chain.sh, clseq.py, clsum.py, 268's sum266.py, pyc266.py, wl266.sh).
- pareto1 `~/sp19/sa-rust-ids-work/sa-port-269/` (p1/, the six suite dirs, target/), trees `~/sp19/dev/sa-port-269-SHA`.
- No plant and no counter was taken (612-629, 668-669 and 649-659, 673-679 are free).
