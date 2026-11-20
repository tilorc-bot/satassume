# HANDOFF sa-port-363: the converted formula skeleton's removal (issue 323)

Branch port/skeleton-removal in clone ~/dev/sa-port-5, worktree ~/sa-rust-ids-work/sa-port-363/wt, from rust-slice
966268c. Head when written: the commit holding this file. **Tested SHA: f5c1f3f4** (source c400113 plus tools363's gate
scripts; later commits touch only results/ and this file). Nothing is landed. Items 1 to 3 of the ruling are done, 4 is
half done, 5 (gate) and 6 (S1) are RUNNING detached, 7 (bar, land) is not started.

## .so hashes
- f5c1f3f4: x86-64 venv a653fd4179da9161 (pareto0 gate), x86-64 bench 4ae7f5cf1dbbca07 (pareto1 S1), orion aarch64
  fcf0524571e0cea9 (the worktree's sa_solver.so).
- 966268c (base; crate source-equal to 00535462, checked by stage363.sh): venv 0f78ac2962f34b3a, bench 8b8041d3fe6223c2,
  orion aarch64 4d8921d9c510e99f (my copy: ~/sa-rust-ids-work/sa-port-363/base-tree, a git archive of 966268c).

## Item 1, the readers (done). rg patterns, over the whole tree minus *.md/*.txt/*.json/*.log
- `\[['"]formula['"]\]|\.get\(['"]formula['"]|['"]formula['"]`
- `\.formula\(\)|\.formula\b(?!s)` (pcre2)
- `\.tables\b|tables\[|tables\.(get|items|keys|values)`
- `\bformula\b` in term/table.rs and term/py.rs; `convert\.formula|formula_top|py_formula|_ORIGINAL\[.formula`
Readers of the skeleton at 966268c, all of them:
1. term/py.rs:292 (TermTable's constructor requires the table) -> term/table.rs:346 parses it -> term/py.rs:311
   `TermTable.formula()`, whose one caller is term_shadow.py:623 `check_formula` (with `rebuild` :249). A check.
2. Generic readers of every table, which name no table: convert_diff.py:131-136 (the differential compares each table
   of the two walkers) and term_history.py:69 (a sha256 of all tables but `reads`). Neither needs the table.
No reader answers a query. No Status: question on readers.

## Item 2, side effects (found; the per-query proof is the running gate)
- **A refusal depends on the walk that built the skeleton**: `convert.formula` raising `Unsupported` is what makes
  `convert` return `Kept('out-of-scope')` (convert.py, in `convert`; walk.rs's entry likewise). So the walk is KEPT
  as a scope check that builds nothing ("keep exactly that side effect"). On dev it fires 24 times in 1,221
  conversions, the same on base and head under both walkers (orion smoke, below).
- 'too-deep': Python's `formula` recursed through a generator expression under `tuple()`; the check keeps a generator
  expression under `any()`, so RecursionError comes at the same nesting: converted at 496, too-deep at 497, for the
  proposition and the assumptions, both walkers, base and head (deep363.py, ~/sa-rust-ids-work/sa-port-363/deep-*.json,
  byte-equal; the same file has 9 out-of-scope inputs, outcomes equal).
- Encoding the skeleton (`w.enc((fp, fa), form)`) added only strings (tags, predicate and relation names) to
  `strings`: every Basic in it was already walked, and it holds no value that counts as `opaque`. So string ids in
  `terms`/`settings` shift; counts, raised, ids, objects and n_terms cannot. The gate checks this per query.
- Counters: 741 cv:formula and 743 cv:fallback:depth count the scope check (native, and past DEPTH 100 Python's), so
  both STAY; 743 is not skeleton-only. 744 is `_template_name`'s and is untouched.

## Item 3, the removal (done, commit c400113; 6 files, 72 insertions, 123 deletions)
- convert.py: `_rel` and `formula` (the block after `_CONNECTIVE`) return nothing; `_CONNECTIVE` is the classes
  only; in `convert`: no `form`, no `w.enc((fp, fa), form)`, no `formula=` in `tables`; WALK_PLANTS loses
  'formula-and-as-or' (13).
- walk.rs: `rel_parts` (:1076), `formula` (:1091), `formula_top` (:1171) return `()`; the entry's `in_scope` closure
  (:1257); no `form`, no `tables["formula"]`; PLANT_FORMULA gone, PLANT_ENTRY's comment (:124).
- table.rs: the `formula` field, parameter and parse gone. py.rs: `req(tables, "formula")` and the getter gone.
- term_shadow.py: `rebuild`, `check_formula`, `_outcome` gone; `check_scope` (:600) is what is left of the check:
  a converted query is one `to_formula` has a formula for (it keeps the shadow's to_formula calls and COUNTS['formula']).
- test_convert_walk.py: ALL_PLANTS loses 772.
- **Plants: 772 (formula-and-as-or) removed with its kept test test_plant_is_caught[772]. 771 (entry-no-assumptions)
  is KEPT with test_plant_is_caught[771]**: its site is now the assumptions' scope check, which stays, and the kept
  test still catches it (input `(Q.positive(x), 5)`: 'out-of-scope' against 'non-basic'). This departs from the
  ruling's "771/772 go", because the ruling took the whole walk to be unread; say so in the report. 743 stays (above).
- Shared files changed: none outside the convert component (convert.py, term/walk.rs, term/table.rs, term/py.rs,
  term_shadow.py, test_convert_walk.py).
- Seen, not touched, new for the architect's list: cargo warns "field `settings` is never read" at term/table.rs:152
  (the Settings row is encoded by both walkers and parsed, and no Rust code reads it; whether Python reads
  `tables['settings']` is not traced). Whether it was a warning on base is not checked.
- Orion: test_convert_walk.py 33 passed (34 on base minus [772]; [700-too-deep] and [771] passed);
  test_lazy_reads.py + test_knowledge_lazy.py 81 passed, 5 skipped.

## Item 4, plant 769 (power-rows-drop-last): half done
- What its site computes: `_Walk.power_rows` (convert.py :307) lists the ids of the terms whose `as_base_exp` can
  split. Readers: table.rs sets `has_power` from it (:340); `TermTable::power_of` (:468) returns None
  without it; `power_of` is called by algebra.rs:690 (the key of a DERIVED Add: `sort_key` of an input term is read
  from Python and never gets there) and by py.rs `TermTable.power` (term_shadow.py's check_table, term_history.py).
  So **it is read by something that can answer (derived terms' sort keys): 769 stays**, and it owes its P2 line.
- The P2 line's evidence comes from the gate: cmp363.py prints `power [conversions that asked a power read, reads]`
  per workload (counts are read at the query's end, no forced read). On dev (orion smoke) it is [0, 0] under both
  walkers: no query of dev asks a power row at all. Read the column in job-f5c1f3f4/gate/cmp.txt for all 24 rows;
  if it is 0 everywhere, the line is "no workload builds a derived Add whose key needs a factor's power split; only
  the kept test and the differential's forced reads reach a power row" (P2: unreached code needs a workload, or it
  is a removal candidate: that is a question for the planner, not this step's to remove).

## Items 5 and 6: RUNNING detached (both launched ~18:30Z 20 Nov)
- **Gate**: tools363/go363.sh f5c1f3f4 966268c (orion pid 553981 at launch). End marker
  **~/sa-rust-ids-work/sa-port-363/go-end.txt, written by tools363/go363.sh:11** ("END rc time"). It ran stage363.sh
  (done: stage-f5c1f3f4.txt "END staged"), then job363.sh on pareto0 under one shared lease (about 2 hours; its own
  end file pareto0:~/sp19/sa-rust-ids-work/sa-port-363/job-f5c1f3f4/end.txt, job363.sh:15), then copies the small
  files to ~/sa-rust-ids-work/sa-port-363/job-f5c1f3f4. Read, by head and rg only:
  - gate/end.txt: one line with GATE-DIFF (48 rows, want 48 EQUAL; walk-EQUAL 24/24; rc0 96/96), GATE-LIVE (60 rows,
    want 60 MATCH; rc0 40/40), convdiff (differences 0, exit 0), 771 (differences > 0, exit 1).
  - gate/cmp.txt: BASE against NEW per workload and walker (answers, Engine.stats, bl, refusals, counts, raised,
    terms per query; 740-746, term_live counts and RAISED, lifetime per pass). gate/cmp-walk.txt: NEW py against rust.
  - gate/livecmp.txt: live.py --check entry rows BASE against NEW (answers, sessions, Engine.stats, moved ids) for
    cells py, cpy, crust on the 20 workloads.
  - gate/kept.log, kept-exit.txt; convdiff/total.txt, convdiff/answers.txt; convdiff-771/total.txt.
  - suite-{rust,py,off}-{new,base}-rust/: compare failed ids new against base per cell (tools359/byid359.py reads
    359's cell names, so adapt or compare the id lists directly); known rows by id: the planted-history test at
    tests/test_public_incremental.py:204 ([137e]: run a28c548's repeat check, tools362/rep362.sh and gorep362.sh,
    each time it shows), and the known base failures of the brief.
  - iv/: 128 runs, SLICE_CONVERT=rust against =py (tools359's reading: tab359.py).
  - Quiet failures (engine.py's except Exception around the complete check): count them from the rows as
    measured-next.md (4) does and show the counter fires (SLICE_PLANT_HANDLER=complete_check). R5 (discard): the
    bar's term_discard rows.
- **S1**: tools363/gos1363.sh f5c1f3f4 966268c (orion pid 554833). End marker
  **~/sa-rust-ids-work/sa-port-363/gos1-end.txt, written by tools363/gos1363.sh:17**. Quiet lease on pareto1,
  bench-container CPU 2, 12 rounds, dev+fuzz and budget+wiring, 12 arms (BASE and NEW x py-on32 control, cpy-off,
  cpy-on32, rust-off, rust-on32, rust-nat; cpy = the slice under Python's walker). Read s1/med.txt (med363.py: NEW
  against BASE per workload and arm, med342's rule). Landing rule: no workload worse beyond the spread; report gains.
- If a marker is missing an hour past its expected end (gate ~21:00Z, S1 ~19:40Z): check the pid, `machine ls`, and
  the job's own end file on the pareto.

## Item 7, not started
- Bar: derive tools363's bar job from tools361/job361bar.sh, gobar361.sh, chain361.sh (one end marker); CONVERT_PLANTS
  and the convert:NAME rows WITHOUT formula-and-as-or. p1/bar.sh needs no edit (it lists no walker plant itself).
  Probe count: tools361/gopc361.sh and pctab361.py (21 of 32 expected). Then bar.sh land, the guard, PUSH=1, rule [91].
- Results file to write: rust-spike/slice/results/skeleton-removal.md (readers, side effects, removal, 769, the gate
  table, S1, the bar, the plant table), in measured-next.md's shape.
- `git push` here goes to origin/port/skeleton-removal (the upstream was set to it; the branch was created from
  origin/rust-slice). Never push rust-slice except through bar.sh land.

## Orion smoke (not the gate)
dev, tools359/diff359.py on base-tree and wt, cmp363.py: py EQUAL and rust EQUAL (1,985 queries, 1,221 conversions,
kept out-of-scope 24, reads 618, raised 0, digest 31cd0945c07f02a6 both; rust cv:entry 1221, cv:formula 2418).
