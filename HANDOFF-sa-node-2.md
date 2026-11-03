# HANDOFF sa-node-2 (continues HANDOFF-sa-node-1.md)

Core: e80400e (sa-node-1), submitted to sa-eval-2 by forward-chain-3b; verdict pending.

Done by sa-node-2:
- tests/test_shared_sessions.py (10 tests): shuffled orders (in order, reversed,
  group-shuffled, pairwise interleaved, random) with SHARED_MAX default and huge,
  3 engines taking turns, fork-per-case from a warm parent, raise fallback,
  a cone inconsistent with the set (PR #119's unsat-cone extension), theory
  session not kept, bound, epoch, settings.
- Planted bugs (scratchpad mutate.sh, copies of the package): no escalate ->
  5 tests fail; no _shared.clear -> 2; theory kept -> 1; no fallback -> 1;
  no eviction -> 2; key without expr -> 1 (bound only: answers stay exact,
  cones are conservative extensions).
- 9bafaa5's tests/test_engine.py::test_contextual_queries_build_and_discard pins
  #97's build-per-query; forward-chain-3b OK'd updating it, strict (== counts per
  key), stated first in the PR body; it told sa-eval-2 this one base-test
  failure is expected.
- Docs: engine module/ask/_context_session docstrings, _ask_shared credit
  (PR #119 / issue #116), design.md "History independence", performance.md
  invariants. ENGINE_MEMOS NOT extended (9bafaa5's test_memos pins len 11).

Next: full suite green -> commit, push -> on sa-eval-2 pass: PR needs-human,
review-clean, HELD for Tilo.
