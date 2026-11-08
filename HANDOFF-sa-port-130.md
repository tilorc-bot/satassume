# HANDOFF sa-port-130 (step 6d, issue 323)

Branch port/6d, head = the commit adding this file, on rust-slice d91ee15 (nothing landed on rust-slice since).
**Tested source of the running bar: 9f2f34d** (this handoff commit changes only docs: HANDOFF, results/port-6d.md draft).

## Bar running (don't restart it)
pareto1, `machine run pareto1 --shared --wait 4h -r "sa-port-130 bar step 6d on 9f2f34d"`, launcher PID in
orion `~/sa-rust-ids-work/sa-port-130/bar-pid`, launcher log `~/sa-rust-ids-work/sa-port-130/bar-launcher.txt`.
Rows: pareto1 `~/sp19/sa-rust-ids-work/sa-port-130/` (phases.txt, done.txt, sum.txt, direct.txt, tests.txt, suite,
live, extra, suite-*). Env: pareto1 `~/sp19/bar-sa-port-130-env.sh` (BASE sa-port-123/suite; PLANTS the 13 common-*;
WLS f6 value rootof core opaque; SUITE_PLANTS zero; TESTS 6g's 14 files; DIRECT dispatch_direct.py, common_direct.py,
and common_direct.py with each of the 13 plants, each expected exit 1). Build passed (.so febab913).
Wait on it with a background until-loop on `ssh pareto1 test -f ~/sp19/sa-rust-ids-work/sa-port-130/done.txt` (or the
launcher PID's exit), not a pgrep loop.

## Done
- Classification: table.py 0 Python calls per query on dev (2 passes), core, f6, value, rootof, opaque, fuzz, before and
  after the port; core reaches ipi on Rust (core:ipi_rules 28, core:kept 0). Traces ~/sa-rust-ids-work/sa-port-130/trace/
  post-*.txt (each call tagged with the query's kept reason).
- Planner's ruling received (addenda/sa-port-kept-reasons-ruling.txt): out-of-scope and refused are named kept reasons;
  table.py and _common.py count whole (footnotes: kept paths only; const_value). 11 of 32 after a clean 6d bar.
- After the port the only _common.py code on non-kept queries is const_value (dev pass 1 5,089, pass 2 0); all else of
  _common.py runs only on kept queries. Compiled.__init__<-knowledge_live is 0 (Common.make_compiled, 9f2f34d).
- Shadow (registry_count.py --shadow) on all 7 workloads: 0 differences (counts in port-6d.md); fires on a plant.
- common_direct.py: 0 differences unplanted; each of the 13 plants caught (exit 1), rows
  ~/sa-rust-ids-work/sa-port-130/common_direct_plants.txt. So the void-on-workloads plants (expected: max-cache-off,
  key-shape-off, maybe pattern-key-type/const-key-type) are caught by common_direct.py.
- Raised counts per workload equal pre-port (dev 0, core 5, f6 2, value 318, rootof 0, opaque 0, fuzz 207).
- results/port-6d.md drafted; placeholders BAR_SECTION, KEPT_SHARES, CONST_VALUE, LANDED_SHA to fill.

## Left
1. Read the bar (sum.txt etc.) and state the five items in port-6d.md's BAR_SECTION, in port-6g.md's form: suite by id
   vs sa-port-123's rows (three numbers, passed split by firing), dev/fuzz and the 5 workloads MATCH, plant table (fires
   per workload, caught; void ones named with what catches them: common_direct.py, suite-* runs), handler multiset vs
   base, differences.
2. Ruling's conditions: share of queries kept per reason (out-of-scope, refused, each named exception) on each workload
   against base (term_live COUNTS kept:<reason> and refused/refused:<reason>; the base is rust-slice d91ee15, e.g. run
   registry_count.py on a d91ee15 worktree, or read the bar's session reports if they carry the counts); any rise is a
   finding even on MATCH. const_value fire count per workload (trace/post-*.txt: `common:python:const_value` plus the
   direct const_value<- rows), and whether it's memoized per term per query: Rust calls it only on a _CACHE miss (per
   pattern key, cross-query within an epoch, common.rs:329-352); the direct calls from wiring/functions/convert/core/
   knowledge_live (knowledge_live.py:119, :329) are not memoized here: say so, a speed item for later.
3. port-ownership.md: the _common.py 17 row (:57) and partials row (:117) -> landed 6d; table.py's rows -> counts whole,
   kept paths only; TSV to match. Module count 11 of 32 with the footnotes and the kept-share line.
4. `PUSH=` unset first: `sh rust-spike/slice/p1/bar.sh land 9f2f34d`, read the incoming diff (rebase rule: full rerun only
   if it changes code the run executes), then `PUSH=1 sh rust-spike/slice/p1/bar.sh land 9f2f34d`. Commit the report with
   tested and landed SHAs; `agent report` Status: done; SendMessage the architect.
