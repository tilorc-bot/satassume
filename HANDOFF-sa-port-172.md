# Handoff sa-port-172 (step 6g(c3)-(c5), issue 323): stack bar running on pareto1, nothing landed yet

Handed off at the architect's request (about 119k context), so the session doesn't sit through a 3h wait.

## Running (detached; I stopped only my own waiter shells)
- **Stack bar on port/stack-6g-c3c5 0643e9c** (c3+c4+c5 on rust-slice 3611952), pareto1, started 14:04 UTC under
  `machine run pareto1 --shared` (orion PID 1064042). **End marker: pareto1 `~/sp19/sa-rust-ids-work/sa-port-172/bar-6g-c3c5/end.txt`**,
  written on pareto1 by the job (`~/sp19/job-sa-port-172.sh`, which runs `~/sp19/bar-sa-port-172.sh`, the same script as
  rust-spike/slice/p1/bar.sh, sha 1f9c6d928980). Then read `sum.txt`, `phases.txt` and `config.txt` there.
  - Config: S1's (sa-port-167 bar-S1) plus the twelve c3/c4/c5 rows plants (38 rows plants, the whole rows_tpl.rs PLANTS
    list) and test_relevance_core.py. BASE suite = 5c8's `sa-port-170/bar-5c8/suite`. KEPT_BASE = `sa-port-167/bar-S1`
    (11 workloads). SEED1=1. Also compare the suite against S1's rows (as 5c8 did, sum-vs-S1).
  - Done by 14:08: build, tests (701 passed, exit 0), and suite started. S1's config took 2h40m.
- **Orion plant runs**, each workload's py-vs-rust over the whole workload (short.sh, limit 100000) in its own worktree,
  so the clone is free:
  - c3+c4 (tree `~/sa-rust-ids-work/sa-port-172/tree-c3c4` at fc939a2): results in `~/sa-rust-ids-work/sa-port-172/c3c4/`,
    end `c3c4/ALL-DONE`.
  - c5 (tree `~/sa-rust-ids-work/sa-port-172/tree-c5` at 0643e9c): results in `~/sa-rust-ids-work/sa-port-172/c5/`,
    end `c5/ALL-DONE`.
  - Read with `sh ~/sa-rust-ids-work/sa-port-172/plt.sh DIR "" PLANT...` (workload=fired/verdict). Only wiring was still running.
  - Remove the two worktrees after ALL-DONE (`git worktree remove`).

## Orion results so far (fired/verdict; "-" = not finished yet)
| step | plant | core | dev | f6 | wiring |
|---|---|---|---|---|---|
| c3+c4 plain | - | MATCH | MATCH | MATCH | MATCH |
| c4 | rows-constant-value-neg | 336 DIFFER | 27 DIFFER | 24 DIFFER | 72 DIFFER |
| c3 | rows-unit-angle-shift (replaces -neg) | 33 DIFFER | 0 | 0 | - |
| c3 | rows-ipi-split-shift (replaces -neg) | 54 DIFFER | 0 | 0 | - |
| c5 plain | - | MATCH | MATCH | MATCH | MATCH |
| c5 | rows-half-tpl-flip | 32 DIFFER | 29 DIFFER | 26 DIFFER | - |
| c5 | rows-bound-tpl-neg | 120 DIFFER | 31 DIFFER | 10 DIFFER | - |
| c5 | rows-recip-tpl-neg | 0 | 0 | 0 | - |
| c5 | rows-imag-tpl-sign | 8 DIFFER | 0 | 0 | - |

- c3's other five plants (a8e2a4f's build, sa-port-163's `c3/`, in `~/sa-rust-ids-work/sa-port-172/c3-plants.txt`):
  rows-exp-arg-none caught on wiring (2); rows-irrational-false core 16 / wiring 2; rows-unit-power-drop-last core 18 /
  wiring 3; rows-pow-bound-drop-last core 144 / wiring 1; rows-ipi-rules-drop-last core 14 / wiring 3, all DIFFER; dev
  and f6 0. The old -neg pair fired (core 33/54, wiring 5/3) and MATCHed everywhere: void by construction.
- **rows-recip-tpl-neg fired 0 on core, dev and f6.** Read wiring's row and the bar's 13 workloads. If 0 everywhere, it's
  void unless a workload reaches `_recip_templates` directly (the shapes case `rows-recip-tpl-neg`, `Q.positive(2 + 3/y)`,
  reaches it: shadow:direct:_recip_templates 8 across cases). Name it in the report: void, with its reach, or caught.

## Branches (all pushed to origin)
- **port/6g-c3 = fc939a2**: 544be25 (c3), 0a7e799 + b08e689 (c4), fc939a2 (the two c3 plant renames in both lists).
- **port/6g-c5 = 0643e9c + this file**: 48d0d05 (c5 Rust, rebased clean), 0643e9c (c5 Python from c5_py.py, plus four
  shapes cases: rows-half-tpl-flip `Q.integer(x/2 + y/2)` odd x, y; rows-bound-tpl-neg `Q.positive(1 + 2*x)` integer
  nonnegative x; rows-recip-tpl-neg `Q.positive(2 + 3/y)` positive y; rows-imag-tpl-sign `Q.imaginary(I*x + I*y)`).
- **port/stack-6g-c3c5 = 0643e9c**, the tested source. Land from it: `git checkout port/stack-6g-c3c5`, then
  `bash rust-spike/slice/p1/bar.sh land 0643e9c`, read the incoming diff (5c9a, sa-port-173, may land first), then PUSH=1.
- Both plant lists match: 38 names in rows_tpl.rs PLANTS and knowledge_common_live.PLANTS.

## Evidence on orion (0643e9c's and fc939a2's builds)
- test_knowledge_core_shapes: c3+c4 19/19 (`~/sa-rust-ids-work/sa-port-172/shapes-c3c4.txt`); c5 23/23 (`shapes-c5.txt`).
- shadowcount (`shadow-c3c4.txt`, `shadow-c5.txt`), shadow:mismatch 0 in both.
  - c3+c4: shadow:direct constant_value 53, _exp_arg 16, _unit_angle 15, irrational_root 15, _pow_bound_templates 13,
    ipi_split 3, ipi_rules 2, _unit_power_units 2.
  - c5 adds _half_templates 1, _bound_templates 7, _recip_templates 8, _imag_templates 3.
- Not taken yet: the per-workload direct counts (rows:rust:NAME against rows:python:NAME and core:derived:NAME) and the
  kept counts (`rows:kept:constant_value:Float`, `rows:kept:_imag_templates:number`). Read them from the bar's
  knowledge.json files under live/ and extra/.

## Next, in order
1. After end.txt: completeness check (suite rows for every id, each workload's comparison, the plant rows, the handler
   rows), then the five bar items. If it differs from base, bisect by step: c3+c4 = fc939a2, c5 = 0643e9c.
2. Land the stack (above). Write three sections in port-6g.md (c3, c4, c5), each with its own plant table (the c2
   section's form). Note the c3 -neg pair as replaced in the same stack. `agent report`.
3. Retrace for the module count (`~/sa-rust-ids-work/sa-port-161/rc.sh OUT WL core.py,wiring.py,functions.py`, pass 1
   `[query]` lines). It hardcodes T=/home/tilo/dev/sa-port-5. Expect 14 of 32 unchanged: core.py keeps other per-query
   shells (core.py:392, :400).
4. Then the 6e/6f module shells (brief's map).

## Module count: 14 of 32, unchanged (nothing landed this session).
