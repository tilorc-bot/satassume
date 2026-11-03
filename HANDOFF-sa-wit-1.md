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

## State
Bound reported (Status: question). Waiting for forward-chain-3b's decision.
