# Handoff sa-port-191 (6g(c6) bar running; 6g(c7)-(c9) built, not barred), issue 323

## 6g(c6): bar running on pareto1
- Tested source **7890bf3** (port/stack-6g-c3c5) = rust-slice b384ec1 (5c10c) + 1f0d3bc (c6 source) + 7890bf3 (results/ only).
  This handoff commit is results/ only (guard-excluded), so `bar.sh land 7890bf3` still applies.
- Bar: pareto1 `~/sp19/sa-rust-ids-work/sa-port-191/bar-6g-c6/`, **end.txt written by the job** (`exit N <time>`).
  Started 23:47Z under shared lease aa0ee91f (orion launcher pid 1397878, output ~/sa-rust-ids-work/sa-port-191/machine-run.out).
  Config: `~/sa-rust-ids-work/sa-port-191/job.sh` = sa-port-187 job3.sh + the four c6 plants + test_cones_core.py (5c10c);
  BASE = 5c10c's suite (`sa-port-189/bar-5c10c/suite`), KEPT_BASE = bar-6g-c3c5r3. At 00:30Z: build, tests (759 passed),
  suite (5,991 passed, 127 failed, 23 skipped, 18 xfailed, same totals as base), live done 23:57Z; plants phase (118 plant cmps).
- Orion evidence on 7890bf3 (~/sa-rust-ids-work/sa-port-191/): tests.txt 759 passed / 3 skipped; plantshape.txt (the three
  shapes plants caught by the shadow; rows-unary-drop-last has no shapes case, caught on f6/core per sa-port-190);
  shadow.txt (29 cases, mismatch 0); dispatch-direct.txt (plain exit 0 BAD 0; dispatch-user-off BAD 1 exit 1; ignores-epoch
  BAD 3; redefines-off BAD 2); rc-{dev,f6,core,wiring}.txt (module count 14 of 32 unchanged; `_pi_trig` and `pi_split` gone
  from the per-query trace).
- Report draft: results/c6-section-draft.md (fill @@BAR@@, @@SUITEPLANTS@@, @@INCOMING@@/@@OTHERS@@; move it into
  port-6g.md as the 6g(c6) section, delete the draft and this file at landing).

## 6g(c7)-(c9): built on port/6g-c7 (02d4304, pushed), on 7890bf3; one stack of three
- c7 `_cosh_shift` (Family::CoshShift, `_cosh_shift_split` via tf6 `f6_cosh_shift_split` on the query table, `tt_mut`),
  c8 `_exp_ipi` (Family::ExpIpi, ipi_split + tcore ipi_rules), c9 `parts_of_round_templates` (Family::PartsOfRound,
  `wiring._attributed` copies the tag). Plants: rows-cosh-shift-parity, rows-cosh-plain-none, rows-exp-ipi-drop,
  rows-exp-const-key-none, rows-round-skip, rows-round-key-none. 11 shapes cases (40 total). offline_data.json regenerated.
- Orion (~/sa-rust-ids-work/sa-port-191/): tests-c7c9.txt 770 passed / 3 skipped; shapes 40 passed; plantshape all six FAIL
  planted. quick9/: f6, core, wiring, dev py vs rust MATCH. Plants: cosh-plain-none caught f6 (fired 50), core (1), dev (1);
  cosh-shift-parity caught f6 (8); exp-ipi-drop caught core (14), wiring (1); round-skip caught f6 (24); round-key-none
  caught f6 (8); exp-const-key-none fires core 1 but MATCH (key-only plant: caught by its shapes case only).
  Counts: f6 rows:rust:_cosh_shift_split 130, _cosh_shift 80 (rules 8), parts_of_round 24, rows:python:_cosh_shift 0;
  core _exp_ipi 56, ipi_split 163 (rows:python:ipi_split 3, core:_pi_split 3, was 57); dev parts_of_round 6, _exp_ipi 1.
- rc9/: per-query Python left in functions.py: slotted `_unary` (f6 86, dev 31), `nary` (f6 48), `_in_unit_interval_units`
  (f6 18); wiring.py: the slotted `_unary` lambdas (dev 31, f6 134); `_attributed` gone; core.py: derived splits,
  `_unit_power_units` 15, ipi_split 3. No module newly counts.
- Bar config ready: ~/sa-rust-ids-work/sa-port-191/job-c7c9.sh (BASE = bar-6g-c6/suite, branch port/6g-c7). Before it:
  rebase port/6g-c7 on rust-slice once c6 has landed, rebuild, force-push port/6g-c7, copy job-c7c9.sh to pareto1
  `~/sp19/sa-rust-ids-work/sa-port-191/` (or your own dir, editing OUT), launch as job.sh was.
