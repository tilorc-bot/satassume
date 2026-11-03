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

## 2nd round (after sa-eval-2's verdict on e80400e: PASS mixed)

Verdict (results/sa-node-1-e80400e.md): dev 1.10x, ho-stream 1.04x, ho None 1.05x;
battery/fuzz/fork flat; corpus 0.97x SLOWER in all 5 rounds; 0 answer diffs.
forward-chain-3b: one iteration to remove the corpus regression, then PR anyway.
- Cause found (cProfile, corpus): _share_key ran theory_scope again on every keyed
  query (1,030 calls, 28 hits). Fix fbb484f: key (set, expr), scope compared
  with Session.scope only on a hit. New test pins it (planted: fails).
- Variants submitted to sa-eval-2 as one 3-tree A/B: fbb484f (node-sessions,
  SHARED_MAX 4) and a1b0285 (node-sessions-max1, SHARED_MAX 1, test_engine
  adjusted). Counters set_checks: corpus 1061/1038/1033 (base/MAX1/MAX4),
  stream-unique 4450/3295/3084, dev 833/562/500. Dev answers identical.
- PR draft: scratchpad pr.md of session 0d2b8ba0 (update key text, results).
Next: on the verdict, pick the better variant (if MAX1, merge node-sessions-max1
into node-sessions), open PR needs-human HELD, review-clean.
