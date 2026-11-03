# HANDOFF sa-wit-1 (cross-session witness reuse)

Branch `wit-reuse` from 9bafaa5. Coordinators: architect-61 (launch), forward-chain-3b (lead).
No engine code changed. Scripts and raw data in `wit-bound/` (WIP, not for the PR).

## Environment
- `.venv` (uv, Python 3.12, mpmath 1.3.0, pytest, hypothesis, z3): run with
  `PYTHONHASHSEED=0 PYTHONPATH=.:/home/tilo/maintenance/sympy-pin .venv/bin/python ...`
- Stream: /home/tilo/dev/rete-impl/data/stream.pkl (16,232 queries; its recorded answers are old:
  1,066 differ from 9bafaa5 with or without instrumentation, so compare runs to each other).

## BOUND (step 1), orion unpinned, plain pass 5.24 s
`wit-bound/bound1.py` (results b4.json): per search (ring miss) in a contextual session, would a
model from an earlier session of the same (set, scope) satisfy the call after completion over the
new variables (propagation over the clauses/blocks added after the context + greedy decisions, no
backtracking; theory atoms not validated)?

- Determinism: 3,367 of 3,367 rebuilds of a (set, scope) matched the first build's fingerprint
  (clauses, root trail, blocks, node->var map, counts): numbering of the context coincides.
- Searches: set checks 4,449 (plain 2,933 = 0.03 s; theory 1,516 = 0.35 s); query 5,446
  (plain 3,172 = 0.15 s, 48 us each; theory 2,274 = 0.71 s, ~310 us each).
- Covered: identical earlier set check 2,529 plain (0.03 s) + 838 theory (0.21 s); query
  plain 2,606 (0.13 s), theory 818 (0.27 s, 75% with new theory atoms, unvalidated).
  Gross upper 0.64 s (12%).
- Exactness: every LRA session has integrality atoms; branch-and-bound budget is path dependent
  (lra.py), exhaustion seen in ~60 searches. Skipping a search changes the path of every later
  search in the session, so in theory sessions only a search with no search after it (suffix) may
  be replaced; the set check never qualifies.
- Exact-safe: plain all positions 0.124 s (2.4%) + theory suffix 0.22 s (4.2%, 0.178 s of it needs
  theory validation of new atoms) = 6.6% gross. Check cost measured 0.37 s (plain, 145 us per hit
  vs 48 us per search replaced) + 0.18 s (theory). Net <= ~3% even with a 3x faster check.
- => below 5%: not built.

## Alternatives measured
- Flip (`bound2.py`, c1.json): second model of a None from the first, query literal flipped and
  its block repaired: 532 of 1,272 plain second searches (0.019 s gross, check 0.021 s), 57 of
  ~1,030 theory ones. ~0.
- Where search time goes (`tparts.py`): `_solve` 23.6% of the pass (set checks included),
  `_tpropagate` 14.0%, LRA `check` 3.9%, LRA `assert_lit` 4.1%. LRA-session searches cost ~6x
  plain ones per search with about the same decisions (~8) and conflicts (<1).

- LRA branch and bound (`lrab.py`, pass 5.51 s): LRA `_check` in total ~0.19 s (3.4%);
  checks that branched 0.136 s (2.4%, 2,219 branches over 1,267 checks), of which own-term
  integrality atoms decided False at an integral point (neg-only) 0.019 s. Not a target.
- cProfile of the pass (`prof.py`, 14.8 s profiled): `_search` 3.07 s, of it `_tpropagate`
  1.61 s (`_theory_sync` 1.41 s: LRA `assert_lit` 0.67 s, LRA `propagate` 0.20 s, transfer
  `propagate` 0.15 s, sync overhead 0.18 s tottime) and `_theory_check` 0.61 s (LRA check 0.57).
  `relations.process` 5.0 s (34%) is in the build (sa-rel-1's area).

## Decisions
- forward-chain-3b (after report 61e0709): drop cross-session reuse; add a row to
  performance.md's "What was measured and dropped" table with the numbers above (in the eventual
  PR or a docs-only commit on this branch; NOT done yet). Suggested row:
  `| witness reuse across sessions of one (set, scope) | 12% gross, 6.6% exact-safe, under 3% net | integrality makes branch and bound path dependent in every LRA session: only a session's last search may be replaced; the check costs about 3x the plain searches it replaces |`
- GO on LRA per-decision and final-check cost. New scope: satassume/theories/lra/* and the
  solver's theory interface (_tpropagate, _theory_sync, _theory_check, register_atom's theory
  path). sa-rel-1 may touch other parts of solver.py (_grow, clause insertion, add_clause):
  message it with the functions you will edit BEFORE editing.

## State (wound down on architect-61's context limit)
Nothing built. Next steps for a successor:
1. forward-chain-3b's ask: per session with LRA, count sessions where LRA engages (its tax:
   atom registration, assert/propagate/check, push/pop) but never propagates, conflicts or
   refutes anything (e.g. integrality atoms that never matter); time that LRA work in those
   sessions. Wrap per LRATheory instance: assert_lit returning a conflict, propagate returning
   non-empty, check returning (False, ...), plus inclusive times of assert_lit/propagate/check/
   push_level/pop_level and the solver's _theory_sync overhead. If large, scoping the theory
   more tightly may beat making it faster.
2. Bound per-decision LRA cost: assert_lit (_assert_kind + incremental _simplex) is ~4% of the
   pass, theory sync overhead ~1-3%; look for work repeated per level (e.g. assert at a level
   that the held levels already had).
3. Bound >= 5% then build, A/B, submit to sa-eval-1; report each bound (agent report,
   SendMessage architect-61 + forward-chain-3b).
