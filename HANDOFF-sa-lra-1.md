# HANDOFF sa-lra-1 (LRA per-decision cost; idle-theory count)

Branch `lra-cost` from 9bafaa5 in ~/dev/sa-wit. No engine code changed. Scripts and raw
data in `lra-bound/` (WIP, not for a PR). Run as in HANDOFF-sa-wit-1.md (its .venv).

## Method
Sampling profiler (`lra-bound/samp.py`, `samp2.py`): a thread reads the main thread's stack
every ~1 ms; one light wrapper on `Solver._solve` tags samples by solve class. A solve is
"lra-idle" when LRA is attached and its `stats` conflicts, propagations and branches are
unchanged over the solve (it never conflicted, propagated or branched). perf is not allowed
on orion (perf_event_paranoid 4); wrapper timing (`b1.py`, `b2.py`) inflates ~2-4x, so only
its counts are used. Orion was loaded (load 11-12); the shares agree across 6 runs (below).
Stream /home/tilo/dev/rete-impl/data/stream.pkl (16,232 queries). Counts in `cnt.py`.

## BOUND (shares of the pass, 6 runs, spread in brackets)
- LRA-session solves 17.8% [16.8-18.6]: 12,318 solves, 5.7 decisions, 0.47 conflicts each.
  Plain solves 3.9% [3.2-5.4] for 21,258 solves at 3.9 decisions. Per decision LRA solves cost
  6.2x a plain one (confirms sa-wit-1).
- Inside LRA solves (3 runs pooled): LRA assert minus simplex 2.9%, B&B `_branch` 2.0%,
  `_propagate` (unit) 2.7%, `_backtrack` 1.4% (plain-session level 0.4%), `_theory_sync` own
  1.5%, simplex 1.1%, check's model (`_concrete`/`_model`) 1.1%, LRA propagate 1.1%,
  transfer 0.8%, push/pop 0.5%, `_pick_branch` 1.0%.
- All frames in lra.py: 13.7% [12.8-14.8], of which 5.2% outside solves (build-time
  `register_atom`: `_register_atom`, `_var_of_form`, `_lin`, `_slack`, `_register_integral`
  about 4.4%, and propagation outside search).
- Leaf in fractions.py or abc `__instancecheck__` under an LRA frame: 5.9% [5.4-6.4];
  constfield (Elements) 1.6%.
- Idle: 6,372 of 12,318 LRA solves (52%) are idle, 4.9% [4.5-5.8] of the pass. At plain cost
  they would be 0.8%: ORACLE ceiling 3.9%. Idle is known only afterwards (0.17 Boolean
  conflicts per idle solve; the theory still decides consistency); no predictor known.
- Counts (`cnt.py`): 12,854 atom bounds, 85% integral rationals, 15% Elements, 11 other
  fractions. 3,618 checks: all have integrality literals (B&B runs in every check), 52% are
  in sessions with Elements (`_fields`), 55% have rows, 72% have disequalities.

## Options (none >=5%)
1. Integers for integral bounds/values instead of Fraction: ceiling the 5.9% Fraction share;
   realistic 3-4% (half the checks are in Element sessions, where arithmetic stays mixed), and
   invasive: `type(c) is not Fraction` is the "has constants" test throughout lra.py, and every
   `/` would have to stay exact (int/int is a float). Not built.
2. Scoping LRA off idle solves: oracle ceiling 3.9%, no predictor. Not built.
3. Lazy check model (skip `_concrete` when no disequalities; `theory_models` has no reader in
   the engine, only tests): <=1.1%, and 72% of checks have disequalities. Not built.

## Decisions
- Status: question (bound <5%); recommendation: no build in this scope. The LRA cost is spread
  over Python call overhead and exact arithmetic, not one mechanism; the compiled-core item
  (performance.md, "Measured, not started") is where this cost would move.
