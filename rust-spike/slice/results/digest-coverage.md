# Snapshot digest coverage per landed step, 5c9a to 59e9d15, plus (iii)(b) rest at ba1ca22 (issue 323)

Read-only audit: nothing was built or rerun. Line numbers are those of the SHA named in the row (`git show SHA:rust-spike/slice/FILE`).
Three digest mechanisms exist. **(1) live** = live.py + livecmp.py, the bar's "state MATCH" (live, plants and extra phases):
per query and per solver `state.digest` of the SAT solver + EUF dump (state.py `dump_py` :51, `with_euf` :182, `digest` :214),
`state.lra_of` (:262), the call stream, and from 5c10d on `rec["eng"]` (the default engine's stats items and
`last_budget_limited`). It reads no memo registry, no Engine memo, no fact store and no Relations container.
**(2) memo_check** = `memo_check.py WL rust OUT.json` and `--cmp`: after one whole pass, on the default engine only, the
registry rows, the engine memos and fact stores, stats. It is not called from `p1/` at any SHA checked (0 hits of
`git grep memo_check SHA -- rust-spike/slice/p1` at 5122f71, 73c10d3, 0f8af2c, 64031f6, 27873ac, 088b86b, 8ff9116, cec872d,
d21abb6, ce1092c, 6f9c44a, ba1ca22), so every "switch digest MATCH on N workloads" was run by hand on orion; the reports say
each compared **base Rust (the previous landed build, containers still Python objects) against the step's Rust**, not Python
against Rust (port-5c9b.md:75-78 gives the reason: `_SPLIT`'s len differs Python vs Rust). **(3) step tests** =
`test_*_core.py` / `test_lra_slot.py`, Python against Rust in separate processes on small query lists, with test-only
`*_snapshot` exports; they run in the bar's `tests` phase only when named in TESTS (bar.sh :70 default is
test_session_limits.py; the reports' "N passed (previous files plus X)" lines say they were added).

| Step | landed SHA (tested SHA) | containers moved | in the step's snapshot digest (which; keys / values / order; when; workloads) | moved but not in any digest | digest code at that SHA (file:line) | ran in the bar? |
|---|---|---|---|---|---|---|
| 5c9a | e0ec542 (5122f71) | none from Python: `SPEC_ROWS`, `ENCLOSURES` were Rust-native already, now shown as registry views (port-5c9a.md:131-132) | (2): registry rows (owner, name, registry key, **len**, stamp) of non-native memos; native views are **skipped**; views vs `memo_snapshot` = (name, key, size, len). Sizes only. End of pass; dev, fuzz, loop, zero, cert | keys and values of both tables (sizes only) | memo_check.py:26-35 (skip :31-32), :92-95; memos.rs:161 | by hand (2). live reads no registry (port-5c9a.md:78) |
| 5c9b | 2553a68 (73c10d3) | `_WANT`, `_SPLIT`, `_NEIGH`, `_CLOSED`, `_SYMPY_ATOMS` (dicts) | (2): same row, now counting moved views: **len and stamp only**; end of pass; dev, fuzz, loop, zero, cert, scope. (3) test_procmemo_core: `_SPLIT`'s lens at its bound and after clear, and `neighbourhood()`'s results for every predicate (so `_NEIGH`'s content by its function) | **keys and values of `_WANT`, `_SPLIT`, `_CLOSED`, `_SYMPY_ATOMS`**; `_NEIGH`'s keys as stored; order of all five | memo_check.py:26-35 (:31, :34); memos.rs:195; test_procmemo_core.py:42-43, :59-61 | (2) by hand; (3) in tests phase (port-5c9b.md:53-54) |
| 5c9c | 2d12e81 (0f8af2c) | `_kids`, `_qcones`, `_glue_adapters`, `_xbasis` (dicts), `splits` (AnswerMemo) | (2) `em_sizes`, `em_content` (sorted), `em_order`: **keys and values** by `_canon`, insertion order (one PYTHONHASHSEED); end of pass; six workloads (no budget). (3) test_engmemo_core: the same rows on cert_wl and small cases | `_glue_adapters` **values** (type name only) | memo_check.py:30, :33-46, :49-56, :144-146; engmemo.rs:344; test_engmemo_core.py:60, :71, :80, :90 | (2) by hand; (3) tests phase (port-5c9c.md:66-67) |
| 5c10a | 67d108d (64031f6) | `cache.store`, `custom_cache.store` (dict of node -> facts dict) | (2) `factcache_rows`: node keys, each node's (fact, value) items in their order, node insertion order; end of pass; six workloads. (3) test_factcache_core: store rows on hand-made engines | none found (`custom_cache.store` is filled on fuzz only, port-5c10a.md:128) | memo_check.py:62-68, :175-178; factcache.rs:435; test_factcache_core.py:57, :65, :90, :99 | (2) by hand; (3) tests phase (:66) |
| 5c10b | 4215655 (27873ac) | `_failed`, `_verdict`, `_context_sessions` (dicts) | (2) joined to ENGMEMOS: keys, values, order; end of pass; six workloads, where `_failed` is 0 rows and `_context_sessions` 0 rows on all six (port-5c10b.md:97-104), so only `_verdict` has content. (3) test_context_core: `_verdict` and `_failed` as (str(k), str(v)), sizes of all three | `_failed` keys/values on any workload (test cases only); `_context_sessions` content (always empty) | memo_check.py:33-34, :53-60, :179-182; engmemo.rs:351; test_context_core.py:38-39, :66-67 | (2) by hand, from a copy of memo_check.py (:88-91); (3) tests phase (:59) |
| 6g(c3)-(c5) | eac4537 (af63d20) | none (template rows from the query's table; port-6g.md has no state or digest line) | none; live state MATCH only | - | - | live |
| 5c10c | b384ec1 (088b86b) | `_cones` (dict), `_constructing` (set) | (2) joined (CONEMEMOS): `_cones` keys, values, order; end of pass; six workloads. `_constructing` is **empty at every sample** (end of pass, end of query; :113). (3) test_cones_core: `_kids`, `_cones` rows on cert_wl and budget cases; `_constructing` sorted, after queries; a reentrant read mid-query through `is_` (answers, not members) | **`_constructing`'s members while a query runs** (the only time it has any) | memo_check.py:35-36, :55-65, :188; engmemo.rs:442; test_cones_core.py:53, :63-64, :73, :84, :104-105 | (2) by hand, copy of memo_check.py; (3) tests phase (:70-71) |
| 5c10d | 9529850 (8ff9116) | `Engine.stats` (12 counters), `last_budget_limited` | **(1) live**: `rec["eng"]` = stats items in order + flag, after every query, compared as `stats_diff`; seven workloads. (2) `stats` after the pass + view vs `st_snapshot`; seven workloads. (3) test_entry_core: the same after each query on cert_wl, budget_wl | none | live.py:447; livecmp.py:36; memo_check.py:195-198; entry.rs:836; test_entry_core.py:61, :73 | **live** (the only step whose moved state the bar's state MATCH reads); (2) by hand; (3) tests phase (:71-72) |
| 6g(c6)-(c9) | 2742b66 (cec872d) | none | none; live state MATCH | - | - | live |
| state part 1 | a8a4bae (d21abb6) | lra_live `_memoized`'s reads -> the adapter's per-query slot `LraQuery` (new Rust state; `_INTERPRETED` unchanged) | (3) test_lra_slot: every exported slot entry (kind, arg, flag -> result), **key and value**, against lra_live's own function on the same query, and one sha256 over all; inside the Rust process; cert_wl plus a few queries (1,484 entries). (1) only through `lra` text | nothing of the slot on a live workload | test_lra_slot.py:95-109, :131; adapters.rs:223 | (3) tests phase (port-state-memoized.md:67); no memo_check |
| state part 2 (i) | c3d0999 (8ee1fac) | none (`integer_form` of a non-Expr side; slot unchanged) | test_lra_slot's slot digest as part 1 (port-state-relations.md:161-163) | - | as part 1 | tests phase |
| 6i(a) | 693fef9 (b11b5a2) | none (port-6i-a.md:191-194) | none; live state MATCH on 13 | - | - | live |
| state part 2 (ii) | 9e10f0d (997a54f) | handles, not containers: `Session.xfer`, `Relations.xfer` / `xfer_sel` / `_xadapter`, a copy of `Session.solver` | **no export digest** ("No separate export digest was taken for these three handles", port-state-relations.md:234-235). test_xfer_core pins the record methods' write sequence field by field on one hand-made session, Rust only (no Python run to compare) | all of them, as state | test_xfer_core.py:50-58 | tests phase (TESTS += test_xfer_core.py, HANDOFF-sa-port-202.md:37); live end states |
| (iii) first part | cac82a9 (ce1092c) | none (function `glue_objects_plain`; the default engine rewrap) | not stated in the report; test_glue_plain compares glue sets as function results | - | - | tests phase; live |
| S2 | 80665b5, landed fd367ce (bb92b07) | the rule block's tables (NVARS, CLAUSES, MODELS): source moved from solver.py to a generated Rust file / block.rs | (3) test_rule_tables: the tables Rust hands out == Python's `_rule_tables` (clauses, closure, nvars), whole values; engine block and random blocks. (1) through the solver's end state, 13 workloads | none | test_rule_tables.py:28-43, :64-79 (at fd367ce) | tests phase (port-s2.md:34-35); live |
| harness install order | db7130a (d77d3db) | none (harness only) | - | - | - | - |
| (iii)(a) + (iii)(b) first move | c822173 (022630c) | Relations' seven scalar cursors `_xtcur`, `_xhn`, `_xhseen`, `_xslot`, `_xterm`, `_xnsides`, `_xsides_n` | (3) test_relc_core: all seven values, **after every query**, Python's attributes vs `relc_snapshot`; WLS transfer:7:60, transfer2:3:40, fuzz:200, scope (469 queries) | nothing of the cursors on a full live workload | test_relc_core.py:21, :23, :59-72, :74; session.rs:1448 | tests phase (HANDOFF-sa-port-213.md:20, -217.md:14; bar clean per -221.md:4). The report section :329 still says UNBARRED/UNLANDED |
| 6i(b) | c59bb1a | none new (port-6i-b.md:294-297) | none; live state MATCH on 13 | - | - | live |
| 6i(c) | 59e9d15 (6f9c44a) | none (port-6i-c.md:235-238) | none; live state MATCH on 13 | - | - | live |
| NOT LANDED: (iii)(b) rest | ba1ca22 (checked-out tree; bar on 0576370 not clean) | Relations' nine sets, fifteen dicts, four work lists, keyed by RelKeys | (3) test_rs_core: nine sets, members sorted by repr, after every query. test_rd_core: fifteen dicts, items in insertion order, **keys and values** by masked repr, after every query. test_rl_core: four lists at every `_interpret` / `_link` call and at the end, plus dicts and sets at the end. All on WLS transfer:7:60, transfer2:3:40, fuzz:200, scope | under plant 409 `rk-class-split` (two equal `Function` classes keyed apart): only `_twin` reaches it, and its rows hold the nine sets and the **keys only** of the fifteen dicts, no values, no lists. 409 is in no PLANTS list of the three files (rs :28, rd :25, rl :28), so no WLS digest ever runs under it; the test's own check is on `_tv`'s keys (:292-296). No digest runs on the bar's live workloads; live reads none of these containers (HANDOFF-sa-port-232.md:23: dev, fuzz and five more MATCH on the bar that lost eight suite answers) | test_rs_core.py:27, :29, :82, :89; `_twin` :163-220, rows :214, test :285-296; test_rd_core.py:23-24, :41-46, :85, :91; test_rl_core.py:62-66, :105-107, :114; session.rs:1567, :1601, :1636 | tests phase on the unlanded bars (HANDOFF-sa-port-225.md:42, -228.md:38); not live |

How far back the gap goes: **keys or values of a moved container have been outside every digest since 5c9b (2553a68)**, the
first step that moved Python containers: its digest row is (owner, name, registry key, len, stamp), so `_WANT`, `_SPLIT`,
`_CLOSED` and `_SYMPY_ATOMS` were compared by size only (5c9a's two tables likewise, but they were not moved from Python).
5c9c to 5c10c do digest keys, values and order, with two holes (`_glue_adapters`' values by type name; `_constructing` only
when empty); 5c10d is fully covered; (ii) at 9e10f0d took no export digest at all; the unlanded step has the 409 hole.
**The bar's state MATCH has never read a moved container except 5c10d's stats and flag** (live.py:447): it covered none at
5c9a to 5c10c and none from state part 1 on (S2's tables and part 1's slot reach it only through solver end state and LRA
text). The only container digests on the full live workloads were memo_check's by-hand passes (base Rust against step Rust),
5c9a to 5c10d; **since state part 1 (a8a4bae) no digest of moved containers has run on a full live workload by any means**,
only on the tests' small lists (cert_wl; transfer:7:60, transfer2:3:40, fuzz:200, scope).

Not established:
- bb92b07 (S2's tested SHA) is not an object in this clone; S2's lines are fd367ce's.
- The bars' TESTS lists and outputs are outside the repo; tests-phase membership is taken from the reports' "N passed (previous files plus X)" lines and the HANDOFF plans, not from a config.txt.
- memo_check was never run on budget before 5c10d (each report's "Also not run"), and on scope not at 5c9a.
- Whether `_child`'s nine-set digest moves under plant 409: not run here; the code shows only that no WLS digest is parametrized with 409.
- Whether any memo_check pass compared MODE py against MODE rust: the reports quote base Rust against step Rust only.
- The uncommitted changes in this tree (live.py, livecmp.py, moved_digest.py, twin_wl.py) were not audited; ba1ca22's lines come from `git show`.

## Draft extension on this branch (sa-port-238, not wired into any bar, not landed)
moved_digest.py, read by live.py into each row (`moved`, `moved_eng`) and compared by livecmp.py (`moved_diff`); workload
`twin` (twin_wl.py); test_moved_digest.py. Small local runs on orion at ba1ca22 (.so sha256 bfc06f0cd68a), output in
orion ~/sa-rust-ids-work/sa-port-238/ (trio.sh WL):
- twin: Python against Rust MATCH (2 `Relations`, 23 containers filled on each side); with `rk-class-split` (409) armed
  DIFFER, first moved containers `_tv` and the cursors, answer True against None, rel:plant_fired 13.
- transfer:7:60: MATCH (64 `Relations`, 3 engine points); armed MATCH with rel:plant_fired 0, so the plant is void there.
- Run time on transfer:7:60, one run each on shared orion: Python 27.0 s against 25.6 s with SLICE_MOVED=0, Rust 13.5 s
  against 12.2 s.
Open on the clean build, printed by livecmp.py every run and outside its verdict: `_SPLIT`'s rows differ (twin 2 against 4,
transfer:7:60 174 against 182; cause not read); the insertion order of `_SPLIT`, `_WANT`, `_CLOSED` and `_SYMPY_ATOMS`
differs under one hash seed. Not read by the extension: 5c9a's native tables (no row of that name on Python), the lra
`_memoized` slot, the (ii) handles. The table above was compiled from git history by a subagent and was not line-checked.
