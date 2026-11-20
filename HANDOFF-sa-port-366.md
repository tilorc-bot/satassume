# HANDOFF sa-port-366: the per-term construction level's removal (issue 323)

Branch port/level-removal in clone ~/dev/sa-port-7, worktree ~/sa-rust-ids-work/sa-port-366/wt, from
origin/port/skeleton-removal f5c1f3f4 (the base of the gate and of S1). Source commit d9dad21; tools 3289df2.
**Tested SHA: 3289df20** (later commits touch only results/ and this file). Nothing is landed.

## .so hashes
- 3289df20: orion aarch64 0f7ab524fb91861a (the worktree's sa_solver.so); x86-64 venv and bench: ~/sa-rust-ids-work/
  sa-port-366/so/so-3289df20.txt (stage366.sh writes it).
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

## Step 3, the removal (d9dad21; 9 files, +14/-28)
convert.py, term/walk.rs (5-field rows, no call), term/table.rs, term/algebra.rs (no field), term/py.rs (`row` is a
7-tuple: args, content, key, free, bits, closed, power), term_shadow.py (the level row and its import),
test_convert_walk.py (above), TERMS-INTERFACE.md:54 and PORT-INVENTORY.md:43, :152 (the level is not a per-node fact).
Plants: none sat on the level; none added. Shared files changed: none outside the convert component.
Orion: test_convert_walk.py + test_lazy_reads.py + test_knowledge_lazy.py 114 passed, 5 skipped.

## Running detached (launched 23:06Z 20 Nov): tools366/chain366.sh 3289df20 f5c1f3f4
All on pareto1 (pareto0 runs sa-port-370's bar). End marker **~/sa-rust-ids-work/sa-port-366/chain-end.txt, written by
chain366.sh's last line**. In order:
1. stage366.sh -> stage-3289df20.txt ("END staged ..."), so/so-3289df20.txt.
2. gos1366.sh (S1, one quiet lease, 12 rounds, 12 arms as 363's) -> gos1-end.txt (gos1366.sh:17), s1/med.txt.
3. go366.sh (the gate under one shared lease: job366.sh = gate366.sh, suite366.sh, tools359/iv359.sh) -> go-end.txt
   (go366.sh:11); files copied to ~/sa-rust-ids-work/sa-port-366/job-3289df20. Read as HANDOFF-sa-port-363.md says,
   plus gate/lvl.txt (48 rows, want calls-raised 0 everywhere), gate/lvl-plant.txt, and convdiff-672 (plant
   term-row-no-number: differences > 0, exit 1) in place of 363's convdiff-771.

## Left
- Read S1 and the gate. Write rust-spike/slice/results/level-removal.md (skeleton-removal.md's shape).
- When sa-port-370 has landed: rebase onto origin/rust-slice; show `git diff --stat f5c1f3f4 <landed> -- satassume
  rust-spike/slice/*.py solver_rs` empty (else rerun the gate against the landed SHA). If 370 does not land: Status: question.
- Bar: copy 370's bar job (its copy of tools361/job361bar.sh, gobar361.sh, chain361.sh) with the SHA, paths and row
  names changed; one end marker. Probe count against 21 of 32. bar.sh land, the guard, PUSH=1, rule [91].
