# Agent report: fact-lattice theory, stage 3, the outcome on refine

- **Date:** 2026-09-25
- **Status:** measured. Stage 2 changes 4 refine answers, all correctly
  from None to False, and no scoreboard or battery outcome. Battery time is
  unchanged. With the free-Boolean option on (off by default, the owner's
  decision), 6 scoreboard losses become wins and the 124 SymPy fallbacks
  for uninterpreted relations disappear. The rule-block propagator stays:
  the engine still uses it, so `set_rule_block`/`register_block` are not
  deleted.
- **Scope:** `main` at `66871eb` (stage 2 with its tuning), merged with
  `refine-identities` at `eb106a6`, the same refine commit as the
  baseline (`2026-09-25-refine-capability-baseline.md`, `main` at
  `6b935d7`); SymPy `6379c4da69`, the refine branch's pin. Scripts as in
  the baseline report; `refine_baseline_plugin.py` gained
  `REFINE_BASELINE_ENGINE_KW` to run the suite under
  `Engine(uninterpreted="free")`.
- **Read this if:** you want to know what the fact-lattice work changed
  for refine

## Scoreboard (`tools/refine_scoreboard.py`, `tests/refine`)

| backend | baseline passed / failed | after stage 2 | after stage 2, free Booleans on |
|---|---:|---:|---:|
| sympy | 463 / 7 | (unchanged, engine-independent) | |
| satassume | 417 / 55 | 417 / 55 | **423 / 49** |
| combined | 467 / 3 | 467 / 3 | 467 / 3 |

After stage 2 every section of the scoreboard is identical to the
baseline (52 out-of-scope losses: 45 matrix, 6 relation against `pi`, 1
stale expectation). With free Booleans on, the 6 relation losses pass:
the 4 inverse-trig principal-branch tests, `test_atan_rule_at_closed_interval_endpoints`
and `test_quoted_rule_outputs`; 46 remain (45 matrix and the stale
Kronecker test).

## Answers (per-query logs, distinct queries)

Stage 2 changes 4 of 1,416 distinct satassume-backend queries (the same 4
in the combined backend), all None to False, all correct:

| query | assumptions |
|---|---|
| `Q.eq(n, 1)` | `Q.infinite(n)` |
| `Q.eq(n, 1)` | `Q.positive_infinite(n)` |
| `Q.eq(n, 1)` | `Q.negative_infinite(n)` |
| `Q.eq(zoo, 1)` | none |

Stage 0 predicted exactly this (transfer changes 4 answers in the suite,
none of which changes a test outcome).

## SymPy fallbacks in the combined backend

| | baseline | after stage 2 | free Booleans on |
|---|---:|---:|---:|
| SymPy asked, matrix | 541 | 541 | 541 |
| SymPy asked, relation no theory interprets | 124 | 124 | **0** |
| SymPy asked, inconsistent | 1 | 1 | 1 |
| **total** | **666** | **666** | **542** |
| satassume None that stands | 2,877 | 2,872 | 2,919 |

## Battery (`tools/refine_identity_scoreboard.py`, 1,736 cases)

On the Pi (quiet, interleaved, two rounds, whole command's wall time),
before = baseline tree, after = stage 2 tree:

| backend | before | after |
|---|---:|---:|
| satassume | 88.1 / 83.4 s | 84.1 / 83.9 s |
| combined | 97.9 / 97.5 s | 97.7 / 97.5 s |

Outcomes identical before and after, in every row and both rounds
(satassume 982 same as v3, 62 misses; combined 1,032, 13 misses). The
battery asks no query that transfer changes.

## What this means

The capability stage 2 adds (facts shared between equal terms, plan
section 3's rows marked 2.2) is real on the stream (15 queries) and in
SymPy's own assumption tests (1), but the refine suite and battery barely
ask such questions today: refine's handlers rarely put an equality into
the assumptions. The large refine lever of the plan is the free-Boolean
treatment of uninterpreted relations (6 scoreboard tests, all 124
relation fallbacks), which is built and off by default because it turns 36
stream answers from None into InconsistentAssumptions (SymPy itself raises
on 24 of them); that is the owner's call.

## Recipe

As in `2026-09-25-refine-capability-baseline.md` section 5, with the
merge `git merge eb106a6` on a worktree of `main`, and for the free run
`REFINE_BASELINE_ENGINE_KW='{"uninterpreted": "free"}'`. The battery ran on
the Pi with the same SymPy copy (`/work/src/sympy-6379-tmp`) and
`/work/src/bt.sh TREE BACKEND ROUND` (the local `refine_battery_time.sh`
per run).
