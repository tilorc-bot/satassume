# Agent report: performance round 3, the propagator, lazy atoms and witness reuse; what was dropped

- **Date:** 2026-09-25
- **Status:** round complete. Four items landed (`5d6ee73`, `b9f2151`,
  `747fb0e`, `2069884`), six measured and dropped, one bundle (the hot
  loops) landed unreviewed by mistake and reverted the same day (see
  section 5). Tracking issue #11. Baseline was `main` at `895a6c2` (end of
  round 2, report `2026-09-25-perf-round-2-report.md`).
- **Scope:** `satassume/solver.py`, `engine.py`, `compile.py`,
  `theory.py`; `tests/test_solver_incremental.py`, `test_solver.py`,
  `test_lazy_atoms.py`, `test_theory_hooks.py`; the per-item reports
  `2026-09-25-perf3-*.md` and scripts under `agent-reports/scripts/`
- **Read this if:** you want the engine's speed after this round, why
  the propagator returned half its estimate, or what the two follow-up
  plans start from

## 1. Result

Replay of the refine stream (`tools/refine_replay.py`, 13,877 `ask`
calls), cold pass, `tools/ab.py`, interleaved against an untouched
`895a6c2`:

| machine | reference | `main` at `2069884` | change |
|---|---:|---:|---:|
| local (2 cores, `--rounds 2`) | 3.480 s | 2.927 s | **-15.9%** |
| Pi, per item, reviewers' runs (`--rounds 2` or `3`) | | | B2a -7.1%, A2 -8.6% on top, D -5.6% on top |

Cumulatively since the September rounds began: 10.1 s (`cbb971f`) to
4.2 s (round 1) to 3.5 s (round 2) to 2.9 s (round 3), about 3.4 times
faster than two rounds ago. Every answer identical on both gates
(`ab.py`: 13,877 recorded answers; `gate2.py`: 2,863 of SymPy's own
assumption-test queries, 0 changed). Suite: 1697 passed plus the 2 known
`test_shared_facts` failures (1668 at the baseline; 29 new tests).

## 2. What landed (one commit each, numbers in the message)

| item | commit | what | own gain (Pi, reviewer) |
|---|---|---|---:|
| B2a | `5d6ee73` | a node block's 33 `P` atoms created lazily; only 16.9% of the 293,700 per pass were ever read | -7.1% |
| A1 | `b9f2151` | the unary rule block as a solver propagator (`set_rule_block`/`register_block`): shared tables, int-encoded reasons materialized only in conflict analysis; rules-as-clauses vs propagator fuzz in plain and theory modes | +0.6% unused (within noise) |
| A2 | `747fb0e` | the engine installs the block per session instead of emitting 79 clauses per node | -8.6% (-14.7% cumulative) |
| D | `2069884` | witness reuse: the last two models per solver, re-validated against everything added since (clauses, root literals, blocks, theory registrations) before a search; the model kept as a slice; two fixes from review | -5.6%, -5.2% (Pi, first version); -7.8% locally with the slice |

Each was read and re-run by a separate Opus reviewer before landing; the
risks are in issue #11. The D review found a real gap (a stored model
reused after a second theory registered a variable the first already
had, since the atom count did not change) and it was fixed with a
registration counter, plus a second gap the new fuzz exposed (a
propagating theory not asked to propagate after a root-fixed variable
was registered).

## 3. What was measured and dropped

| item | bound / A/B | why | report |
|---|---:|---|---|
| B3 memo and API overhead | 1.5% | 2 µs per memo hit; `_registry_state` already on the version counter | `perf3-B3-memo-api-overhead.md` |
| B1 wasted first attempt on a polluted session | 3.3% own (ceiling 6.0 to 8.0%) | wasted and useful attempts look the same beforehand; the early-cone variant that preserves answers gets 3.3% | `perf3-B1-polluted-first-attempt.md` |
| B4 collector and allocation | measured | 9.4 to 10.2% before A2, 3.7 to 4.4% after; 85% of what it walks is solver lists; no engine-side cut over 0.5% | `perf3-B4-gc-and-allocation.md` |
| B5 profile after A2 | measured | no engine-side item over its line (template filter memo 1.6 to 2.2%) | `perf3-B5-profile-after-A2.md` |
| B6 answer-memo subsumption | 3% with checks kept (7.2% without) | skipping the consistency and scope checks would make 251 `None` answers definite and mask an inconsistent set | `perf3-B6-memo-subsumption.md` |
| C hot loops | -6.8% as a bundle of six; -2.4 to -3.2% after two low-gain, less readable cuts were reverted | the two reverted cuts were worth 3 to 4 points only in combination; the model slice moved into D | `perf3-C-hot-loops.md` |

## 4. What the round taught

- **The propagator delivered half its estimate** (8.6% against 18 to
  21%). The estimate treated the rule clauses' share of watch-list visits
  as removable; in CPython the fixed cost per processed literal
  dominates, and the propagator still processes the same 829,000 block
  literals per pass. A hook replaces work; only not doing the work
  removes it. That observation is the premise of the fact-lattice plan.
- **Search produces almost no definite answers on this stream.** Of
  3,192 searches per pass, 3,130 end with both models found; 62 end
  unsat. Propagation is where True and False come from. Search is 38% of
  the pass.
- **The remaining cost is structural.** Session construction and the
  cone path are about 23% of the pass by parts that exist only because
  sessions are separate, and every item that attacked a part measured
  under 5% (clone 1.6%, LRU 0.7%, early cone 3.3%, subsumption 3%).
- **Per-item reviews caught two real defects** (the D gap; a
  module-level mutable table in C shared between solvers) and one
  readability regression, which is what they are for.

## 5. A process error, corrected

The pre-review versions of C and D were staged on local `main` for
review, and two report-only commits pushed later carried them to
`origin/main` unreviewed (`7bd278f`, `ce2f5ec`). Both were reverted the
same day (`dc8228c`, `3e1feaf`) and the reviewed D landed on top
(`2069884`); the end state is exactly the reviewed tree (verified by an
empty diff against the solver agent's branch, plus the suite and both
gates). The Pi session working from that window was told to rebase. The
lesson for the landing helper: never push `main` while unreviewed
commits are staged on it; stage on a branch instead.

## 6. What comes next

Two plans on `main`, written for a fresh agent, with a changed acceptance
rule (answers may become more definite, never contradict; identical
error set):

- `2026-09-25-fact-lattice-theory-plan.md`: unary facts as a
  lattice-valued theory keyed by EUF term; capability first (predicate
  transfer across equalities, the relation losses of the refine
  scoreboard), speed conditional on the never-read fraction of implied
  literals. Started on the Pi on 2026-09-25 (tmux session `facts`,
  branch `facts-theory`, bundles under `/work/src/bundles/`).
- `2026-09-25-global-solver-evaluation-plan.md`: one persistent solver
  with selector literals and scoped termination; certain removable share
  23%, conditional up to 37%; stage 0 measures the ceilings first.

Beyond those, the levers are a compiled core for the solver's hot loops
(the C report estimates 1.4 to 1.6 s for the pass) and asking fewer
questions on the refine side.
