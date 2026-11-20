# HANDOFF sa-port-366: the per-term construction level's removal (issue 323)

Branch port/level-removal in clone ~/dev/sa-port-7, worktree ~/sa-rust-ids-work/sa-port-366/wt, from
origin/port/skeleton-removal f5c1f3f4 (the base of the gate and of S1). Source commit d9dad21; tools 3289df2.
**Tested SHA: 3289df20** (later commits touch only results/ and this file). Nothing is landed. Handed off at
23:35Z 20 Nov at the architect's word (context), with S1 and the gate running detached; nothing of them is read yet.

## .so hashes
- 3289df20: orion aarch64 0f7ab524fb91861a (the worktree's sa_solver.so); x86-64 venv **87fed7167ce606e0** (the gate's
  and the bar's; orion copy ~/sa-rust-ids-work/sa-port-366/so/sa_solver-3289df20.so), x86-64 bench **450665d47908c768**
  (S1's, in pareto1's bench tree); both in so/so-3289df20.txt and staged-3289df20.txt.
- f5c1f3f4 (base): venv a653fd4179da9161, bench 4ae7f5cf1dbbca07 (both sa-port-363's builds, reused; stage366.sh
  checks the venv hash), orion aarch64 fcf0524571e0cea9 (my archive: ~/sa-rust-ids-work/sa-port-366/base-tree).

## File:line map, rechecked on f5c1f3f4 before editing (364's map held but for three lines)
- convert.py:27 the import; :270 `T_TUPLE, 6`; :279 the skeleton row's `T_NONE, T_INT, 0, T_INT, 0`; :305 the call.
- term/walk.rs:165 the field `constructed_nc`; :271 its lookup; :794 the arity token (364: "near the top of term_row");
  :826 the skeleton row's tokens; :865-869 the call and the two tokens.
- term/table.rs:143 `pub level: u8`; :313 `r.tuple(&strings, 6)`; **:335** `level: int(&f[5])? as u8` (364 had :338).
- term/algebra.rs:102, :123, :158 the three `level: 0`.
- term/py.rs **:327** the doc of `row`, **:342** `r.level` (364 had :334, :349).
- term_shadow.py:27 the import, :128 the destructuring, :167-168 the check. Its other `row` reads (:243, :288, :293,
  :299, :301, :346, :405) use indexes 0 to 4.
- term_live.py:490 (row[0], row[1]); term_history.py:78, :83 (row[4], row[:5]). Unchanged.
- lazy_probe.py:25, :79: an offline survey of which reads can evaluate; it holds the FUNCTION by name, not the per-term
  level. Left as it is (the engine still reads the function on demand).
- Stay, untouched: engine.py:165 `_construction_level` (callers :2044, :2090), entry.rs:577-579 `construction_level`
  (callers :623, :683), satassume/knowledge/domain.py.

## Step 1, the readers (rg over the whole tree, on f5c1f3f4)
Patterns: `constructed_noncommutative|constructed_nc|construction_level`; `\.level\b|level:` in solver_rs/src;
`\.row\(` in *.py, *.sh, *.rs, *.md; `'level'|"level"`; `f\[5\]|T_TUPLE, 6`.
- The per-term level's readers: term/py.rs:342 (`TermTable.row`'s sixth field) and, through it, term_shadow.py:128 and
  :167-168 (`bad('level', ...)`), a check. No Rust code reads `TermRow.level`. No test, tool or bar script reads it.
- One test read the ROW'S SHAPE: test_convert_walk.py::test_reserved_bit_is_zero (bits at row[-3]); it now reads the
  bits at row[-1] and asserts the arity 5. No Status: question on readers.

## Step 2, side effects of the per-term call (found by reading domain.py:35-383, counted by tools366/lvl366.py)
- It writes no memo and no counter (`_NONCOMM` is `_noncommutative`'s). Its one write is `domain._UNDEFINED_KEYS`, a
  constant filled once a process by `_plain_undefined` (:301); the engine's own read fills it the same way.
- A raise in it is NOT a refusal: convert's caller turns it into `TermFault('conversion: ...')` (term_live.py:312),
  which leaves `ask` (shown by LVL366_PLANT=2000 on dev under both walkers: the pass ends at query 790, rc 1).
- Orion, dev, base f5c1f3f4: 4,515 level calls a pass under each walker (364's number), 0 raised, 0 queries with a
  raise, 0 conversions filling _UNDEFINED_KEYS; on the removal the global is absent. cmp363.py base against new: EQUAL
  under py and under rust (1,985 queries, 1,221 conversions, kept out-of-scope 24, raised 0, digest 31cd0945c07f02a6).
  All 24 workloads: the gate's step 5 (gate/lvl.txt, gate/lvl-plant.txt).

## Step 3, the removal (d9dad21; 9 files, +15/-29)
convert.py, term/walk.rs (5-field rows, no call), term/table.rs, term/algebra.rs (no field), term/py.rs (`row` is a
7-tuple: args, content, key, free, bits, closed, power), term_shadow.py (the level row and its import),
test_convert_walk.py (above), TERMS-INTERFACE.md:54 and PORT-INVENTORY.md:43, :152 (the level is not a per-node fact).
Plants: none sat on the level; none added. Shared files changed: none outside the convert component.
Orion: test_convert_walk.py + test_lazy_reads.py + test_knowledge_lazy.py 114 passed, 5 skipped.

## Running detached (launched 23:06Z 20 Nov): tools366/chain366.sh 3289df20 f5c1f3f4 (orion pid 713202, setsid)
All on pareto1 (pareto0 runs the skeleton removal's bar). No waiter shell of 366 is left; no subagent was started.
**TRAP: the chain runs its scripts from this worktree (wt/rust-spike/slice/results/tools366). Do not rebase, check out or
edit tools366 here until chain-end.txt exists**; bash reads a running script from the file. The pareto1 job itself runs
from the staged copy (~/sp19/sa-rust-ids-work/sa-port-366/s1/tools on pareto1).
End markers, each with the line that writes it (grep-checked on 3289df20):
- stage: ~/sa-rust-ids-work/sa-port-366/stage-3289df20.txt, stage366.sh's `fin` (:20, called last at :44). DONE:
  "END staged 3289df20 f5c1f3f4 2026-11-20T23:07:51Z".
- S1: **~/sa-rust-ids-work/sa-port-366/gos1-end.txt, gos1366.sh:17** (`END rc time`; :8 `fin` writes it on a staging
  failure). On pareto1 the lease script's own marker is ~/sa-rust-ids-work/sa-port-366/s1/end.txt, onlease366.sh:24.
  One quiet lease, bench-container CPU 2, 12 rounds, 12 arms (BASE and NEW x py-on32, cpy-off, cpy-on32, rust-off,
  rust-on32, rust-nat), dev+fuzz then budget+wiring. At 23:30Z: timing-s1 (dev, fuzz) DONE 23:25:09, timing-bw running;
  expected end about 23:50Z. Read ~/sa-rust-ids-work/sa-port-366/s1/med.txt (tools366/med366.py, 363's unchanged but
  for names: NEW against BASE per workload and arm). Rule: no workload worse beyond the spread; report the gain
  (about 1.4-3.5% expected in the cpy and rust arms; py-on32 is the control and runs no walker).
- gate: **~/sa-rust-ids-work/sa-port-366/go-end.txt, go366.sh:11** (`END rc time`; :7 writes it if the staging marker
  is missing). It starts when S1 ends, under one shared lease (job366.sh: gate366.sh, suite366.sh, tools359/iv359.sh,
  about 2 to 3.5 hours). On pareto1: ~/sp19/sa-rust-ids-work/sa-port-366/job-3289df20/end.txt (job366.sh:15),
  gate/end.txt (gate366.sh:59), gate/diff-end.txt (:39), gate/live-end.txt (:49), suites-end.txt (suite366.sh:26).
  The small files are copied to ~/sa-rust-ids-work/sa-port-366/job-3289df20 by go366.sh:10.
- the chain: **~/sa-rust-ids-work/sa-port-366/chain-end.txt, chain366.sh:11** (:8 on a staging failure).
- If a marker is missing an hour past its expected end (S1 ~23:50Z, gate ~03:00Z): `ps -eo pid,etimes,args | grep
  "[c]hain366"`, `machine ls`, and the pareto1 markers above.

## Reading the gate (job-3289df20; by head and rg only; HANDOFF-sa-port-363.md on origin/rust-slice or
origin/port/skeleton-removal has the meaning of each file)
- gate/end.txt, one line: GATE-DIFF rows 48, want EQUAL 48, walk-EQUAL 24/24, rc0 96/96; GATE-LIVE rows 60, want MATCH
  60, rc0 40/40; convdiff differences 0 and exit 0; 672 (plant term-row-no-number, in place of 363's 771): differences
  > 0 and exit 1; LVL rows 48, raised0 48, rc0 48/48 (the two planted passes end rc 1 by design and are not in that
  count).
- gate/cmp.txt (BASE against NEW per workload and walker: answers, Engine.stats, bl, refusals, counts, raised, terms;
  `life.alive` alone is reported, not compared: alive_gc is the leak check, ruling on 365), gate/cmp-walk.txt,
  gate/livecmp.txt (moved ids), gate/kept.log and kept-exit.txt (33 passed expected).
- gate/lvl.txt: step 2 per workload and walker on BASE: want `calls-raised 0 queries-with-a-raise 0` in all 48 rows;
  report level-calls per pass (dev 4,515; 364 has fuzz 28,853, budget 7,472, wiring 63,184) and
  queries-filling-UNDEFINED_KEYS. gate/lvl-plant.txt: dev with the 2000th call raising: calls-raised 1 and TermFault
  in the .err (the false-zero proof for `raised`).
- suite-{rust,py,off}-{new,base}-rust: failed ids new against base per cell; known rows by id: the planted-history
  test at tests/test_public_incremental.py:204 ([137e]: run tools362/rep362.sh and gorep362.sh each time it shows) and
  the brief's known base failures. iv/: 128 runs (tools359/tab359.py).
- Quiet catches (engine.py's except Exception around the complete check): count from the rows as measured-next.md (4)
  does, and show the counter fires (SLICE_PLANT_HANDLER=complete_check).

## Left
1. Read S1 and the gate (above). Any DIFFER, or S1 worse beyond the spread: Status: question.
2. Write rust-spike/slice/results/level-removal.md in skeleton-removal.md's shape: readers, side effects, the removal,
   the gate table, S1 with the gain, then the bar and the plant table.
3. Once the skeleton removal has landed on rust-slice AND chain-end.txt exists: `git fetch origin`, rebase
   port/level-removal onto origin/rust-slice; show `git diff --stat f5c1f3f4 <landed> -- satassume rust-spike/slice/*.py
   rust-spike/slice/solver_rs` EMPTY (then the gate and S1 stand, the base being source-equal); otherwise rerun the gate
   against the landed SHA (chain366.sh NEW <landed>: stage366.sh:21 refuses a base whose source differs from f5c1f3f4,
   so change that line and the base .so paths :18-19 first). If the rebase changes nothing under satassume,
   rust-spike/slice/*.py and solver_rs on our side either, the rebased tree's source equals 3289df20's: show it with
   `git diff --stat 3289df20 <rebased> -- satassume rust-spike/slice/*.py rust-spike/slice/solver_rs
   rust-spike/slice/test_convert_walk.py` (empty) and the staged venv .so 87fed7167ce606e0 stays the bar's .so. If the
   skeleton removal does not land: Status: question.
4. Bar, after the skeleton removal's bar has ended (rule [91]): copy the bar job that landed it (its copy of
   tools361/job361bar.sh, gobar361.sh, chain361.sh; on rust-slice after the landing) to tools366 with only the SHA,
   paths, row names and branch name changed, and show the diff against the source scripts. The bar tests the head of
   origin/bar/<name>-SHA (gobar361.sh:8): push that branch first. CONVERT_PLANTS as landed (no formula-and-as-or, 771 a
   kept-test catch). ONE end marker, written by gobar's last line; check the real exit about 1 h after the expected end
   ([137d]). From the bar: R5 (term_discard rows), R1/H2, the quiet-catch count with its planted proof, the plant table.
5. Probe count: tools361/gopc361.sh and pctab361.py, against 21 of 32 (`constructed_noncommutative` is no longer called
   by the walkers: say whether that moves the count).
6. bar.sh land, the guard, PUSH=1, rule [91]; check `git log origin/rust-slice` first. Tell the architect when
   rust-slice moves.
7. For the report, also: shared files changed (none outside the convert component; test_convert_walk.py's
   test_reserved_bit_is_zero changed); new for the architect's list: none found by 366.
