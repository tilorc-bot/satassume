# HANDOFF sa-port-131 (step 6d, issue 323)

Branch port/6d, rebased twice: on scope (803d073) and then on 5c6 (rust-slice **1401d1f**). **Tested source of the
running bar: c69cd6a** (= 9f2f34d's code + 1325cc2's test fix, rebased). The commit adding this file is docs only.
The architect has sa-port-133 and sa-port-136 holding rust-slice pushes until 6d lands (expected around 05:40 UTC). Tell
the architect when you land, or if the bar slips well past 05:40.

## Bar running (don't restart it unless rust-slice moves with code the run executes)
pareto1, `machine run pareto1 --shared --wait 4h -r "sa-port-131 bar step 6d on landing source c69cd6a"`, launcher
PID orion `~/sa-rust-ids-work/sa-port-131/bar-pid`, log `bar-launcher.txt` there. Rows: pareto1
`~/sp19/sa-rust-ids-work/sa-port-131/` (phases.txt, done.txt, sum.txt). Env `~/sp19/bar-sa-port-131-env.sh`: BASE
`sa-port-134/bar-5c6/suite` (5c6's landing rows), WLS `f6 value rootof core opaque scope`, the 13 common-* PLANTS,
SUITE_PLANTS zero, TESTS 6g's 14 files + test_scope_core.py, DIRECT as sa-port-130's. Wait with a background until-loop
on `ssh pareto1 test -f sp19/sa-rust-ids-work/sa-port-131/done.txt`.
Stopped bars, kept as interim rows: sa-port-130's on 9f2f34d (tests/direct done: 3 stale test failures, all 13
common_direct plants exit 1) and `~/sp19/sa-rust-ids-work/sa-port-131-stopped-3624226/` (on scope's rebase;
`sum-interim.txt`: suite new 0 gone 0 changed 0, 5,958 passed = 5,957 no firing + 1 firing
test_ci_stream_reports_only_what_replays, handler multiset = base (34 `_ok`, 4 `_rb_clauses`, 1 Already mutably
borrowed), dev/fuzz and all 6 WLS MATCH, plants as below; suiteplants cut off by the stop: ignore its ge2-drop row).

## Done
- **Test fix 1325cc2 (now c69cd6a):** 9f2f34d failed 3 of its own 419 slice tests (asserted knowledge_live's
  `common:resolve`/`common:pattern`, which Rust's facts/units bypass). The assertions now read Rust's `Common` counts.
  419 passed on orion; 426 on the 3624226 bar (with test_scope_core.py).
- **Kept shares (ruling 1)**, script `~/sa-rust-ids-work/sa-port-131/kept_shares.py` (pareto1 copy
  `~/sp19/kept_shares-sa-port-131.py LABEL=FILE...`, reads `*-rust.knowledge.json`: term_live COUNTS are shared with
  knowledge_live's). Denominator converted + kept:*. Base d91ee15 (sa-port-125/bar-A2/live) for dev/fuzz, 6g(a)'s
  e5c78e9 (sa-port-123/extra) for the five extras (dev/fuzz on both are identical). Base and the 3624226 interim are
  **identical on every workload, no rise**: dev out-of-scope 24 of 1,221 (1.97%); fuzz, core, rootof 0; f6 refused 13
  of 2,902 (0.45%: algebra Float 10, lra callback on derived term 1, scaffold rebuilt form differs 2); value refused 15
  of 3,717 (0.40%, Float); opaque refused 7 of 2,546 (0.27%: infinity/nan 5, holds inf/nan/Float 2); scope 0 of 169
  (no base for scope before scope's step; compare with sa-port-126/bar-scope2/extra if wanted). Re-read on the final
  rows, against 5c6's (sa-port-134/bar-5c6/live) as well.
- **const_value (ruling 2)**, from sa-port-130's traces (`~/sa-rust-ids-work/sa-port-130/trace/post-*.txt`), pass 1,
  Rust's callback `common:python:const_value` / all traced calls: dev 4,605 / 5,089 (pass 2: 0 / 0), core 28,473 /
  29,152, f6 7,906 / 8,611 (249 on refused reruns), value 11,922 / 20,228 (178 refused), rootof 0 / 8, opaque 834 / 932
  (74 refused), fuzz 2,310 / 2,560. Memo standing: Rust calls it only on a `_CACHE` miss (per pattern key, cross-query
  within a registry epoch, common.rs:322-352), and once per (slot, pred) that resolve reads, with no memo inside a
  miss; the direct callers (wiring, functions, convert, core, knowledge_live, special, nodes) have no per-term
  per-query memo of their own, but every caller is 0 on dev pass 2. So it's a speed item for later, not a count question.
- **Plants (interim, 3624226; restate from the final sum.txt):** caught on workloads: compiled-swap, consts-of-skip,
  facts-drop, rule-drop (not fuzz/rootof/scope), units-drop (not value/scope). Fire 0 everywhere (void): equiv-one,
  ge2-drop, key-shape-off, lits-flip, max-cache-off, wide-drop; fire but MATCH: pattern-key-type, const-key-type (the
  cached value's type, never read differently). All 8 void ones are caught by common_direct.py (exit 1 each), and the
  suite-* runs (SUITE_PLANTS zero) fire 0 in the suite.
- **Ownership TSV script** `~/sa-rust-ids-work/sa-port-131/own_tsv.py TSV SHA`: changes 42 rows (17 `6d` _common rows
  + units -> `landed 6d SHA`, Rust; 5 of 6c's partial rows' finisher -> done; const_value -> named callback; table.py's
  18 -> `counted whole 6d SHA (kept paths only)`). Tested on a copy. Rerun it on the rebased TSV (5c6 changed rows).

## Left
1. When done.txt appears: read sum.txt and fill port-6d.md's BAR_SECTION in port-6g.md's form (tested c69cd6a, base
   sa-port-134/bar-5c6/suite), KEPT_SHARES and CONST_VALUE from the above, and fix its header (tested c69cd6a on
   1401d1f) and the "Module count" paragraph: **11 of 32** (7 + registry.py + `__init__.py` + table.py + `_common.py`;
   relations.py pending on adapters part B), footnotes table.py kept paths only, `_common.py` const_value,
   realroots/value_units; the kept-share line. Say the test fix and the two rebases.
2. port-ownership.md: rows `_common.py` :57 (and :54 units, :56 const_value), table.py :69, partials `_common.py`
   row (:119) -> landed 6d; header note "Updated by 6d" with the count and the kept-share line. TSV via own_tsv.py.
3. `sh rust-spike/slice/p1/bar.sh land c69cd6a` (no PUSH); if rust-slice is still 1401d1f, the incoming diff is empty.
   Then `PUSH=1 ...`, commit the report with the landed SHA, push to rust-slice, `agent report` Status: done, and
   SendMessage the architect (who is holding two sessions' pushes).
