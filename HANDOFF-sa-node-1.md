# HANDOFF sa-node-1 (shared contextual sessions per (set, scope, expr))

Clone ~/dev/sa-node, branch `node-sessions` from 9bafaa5. Brief: architect-62's
launch message (owner Tilo; lead forward-chain-3b; evaluator sa-eval-2,
~/dev/sa-eval/evalbench/HOWTO-WORKERS.md). Report filed: 2a38e9a (progress).

## Bound (done)

Script: /tmp/claude-1000/-home-tilo-dev-satassume/72789d8a-80c2-4245-aa7e-969e3b0f51e9/scratchpad/bound.py
(`~/dev/sa-eval/.venv/bin/python bound.py ~/dev/sa-node dev|stream-unique`;
top-level Engine.ask keyed (set, theory_scope, expr) for unary vocabulary
propositions; orion, fractions of one pass).

| repeat-key queries, share of pass | stream-unique | dev |
|---|---:|---:|
| theory-free sessions | 10.0% (1,600 asks) | 14.3% (379) |
| LRA/EUF sessions | 22.4% (672) | 16.3% (69) |
| total | 32.4% | 30.6% |

Theory-free repeat on stream: build 3.8, prepare 2.0, escalate 1.8, search 1.5.
Reuse distance: 75% of repeats within 4 distinct keys, 82% within 32.

LRA finding: all 1,629 stream LRA sessions have integrality atoms registered
(`LRATheory._ints`), 53% branched, 50 exhausted, 40 uncertified constants. So
"theory cannot branch" (option c) covers 0%; (b) is empirical only. Decision
(forward-chain-3b, 08:2xZ): BUILD (a) only, theory-free sessions.

Follow-up for a LATER session (forward-chain-3b): measure (b) as an
off-by-default variant for Tilo: how many answers differ between shuffled
orders, fork-per-case and fresh sessions on stream, battery and fuzz, plus its
extra gain. Not in this build. Also: compose with sa-cy-2's Cython build (no
interpreter-introspection tricks).

## Build plan (a)

In engine.py only (+ tests/test_shared_sessions.py):

1. `Engine._shared`: OrderedDict key -> Session, at most `SHARED_MAX = 32`
   (LRU by insertion; reuse distance says 32 is enough; tiny memory, unlike
   #119's process-wide cones). Cleared wherever `_verdict`/`_failed` are
   dropped (`_drop_set_memos`, `_check_version`, `_settings_changed`), i.e. on
   epoch or settings change.
2. Key: `(assumptions, scope, expr)` for a contextual `P(pred, expr)` or
   `Not(P(...))` with `pred in PRED_INDEX`; scope = `theory_scope(assumptions,
   proposition, self._extensions)` (depends on pred via affine pairs, so it
   must be in the key). Pass scope into `_build_context` to avoid computing it
   twice.
3. Store after a fresh query only if the session is theory-free:
   `not s.solver.theories() and s.relations is None and s.xfer is None`,
   verdict not INCONSISTENT, no raise.
4. Reuse (`_ask_shared`): release held levels, `prepare_query`,
   `assumption_lits`, then `escalate()` if `incomplete` BEFORE any answer, then
   the same propagate / search steps as `_ask`. On InconsistentAssumptions (or
   any exception) in the shared session: drop the key and answer by the fresh
   per-query path (exact by definition).
5. Exactness argument for the PR (extends #119): F = the set's escalated
   context + the expression's whole escalated cone (a function of the key:
   escalate compiles everything parked and visits every node, the argument of
   `_decide`'s docstring); the database is F + learnts entailed by F (prepare of
   earlier predicates only ensures nodes of the same cone; no glue in a
   theory-free session; check `_ensure_twins` returns False without relation
   specs). Plain search and `consistent` have no budget. If F and A are
   consistent: fresh answer = shared answer = True iff F,A |= q, False iff
   F,A |= ~q, None otherwise (fresh: propagation on a subset is sound, its
   consistency check passes since F,A is satisfiable, an undecided query
   escalates to F and searches completely). If inconsistent: the shared session
   raises, and falls back to the fresh path.
6. Tests: query-order independence (shuffled order vs fresh engine per query,
   across engines, fork-per-case), planted bugs (no escalate before answer, no
   epoch drop, storing a theory session, no fallback on raise), LRU bound.
7. Gates: dev.py, test suite, then submit to sa-eval-2; PR needs-human, HELD.

## State (08:28Z, sa-node-1 handing off at ~140k)

- [x] bound, report 2a38e9a. NOTE: bound.py first ran with sa-eval's own
  satassume on the path (c676cfa) instead of the clone; fixed (sys.path.append
  for sa-eval). Rerun on base-9bafaa5 gave the same picture: stream repeat
  plain 8.9%, repeat LRA 25.8%; dev 13.5% / 15.8%.
- [x] forward-chain-3b: build (a) only; leave (b) as a later off-by-default
  measurement for Tilo (see above).
- [x] core build committed (engine.py: `Engine._shared`, `_ask_shared`,
  `_share_key`, `_theory_free`, `SHARED_MAX`, `_UNSHARED`; cleared in
  `_drop_cones`). dev.py: answers 1985/1985 identical; context_builds 833 ->
  473, escalations 315 -> 191, solver_vars 41k -> 28k.
- Cache size (stream-unique set_checks; base 4,450): MAX 1 -> 3,295, 2 -> 3,141,
  4 -> 3,084, 32 -> 3,001. GC time (gc.callbacks, script g.py in the
  scratchpad): base ~0.27-0.33 s; MAX 1 ~same; MAX 4 +~0.06 s; MAX 32 +~0.23 s
  (kept sessions get promoted; #119 saw the same). Chose 4. orion is far too
  loaded for pass times (5-16 s for the same run); in-run fractions say the
  shared hits cost 2.2% of the pass vs 8.9-10% for those queries at base.
- [ ] run the test suite (`$PY -m pytest -n 6 tests`) and fix fallout (stats
  counts, memo registry tests may list engine dicts: `engine_memos`).
- [ ] tests/test_shared_sessions.py: shuffled order vs fresh engine per
  query (use stream/dev slices or a hand list: same expr, several preds, under
  sets incl. an inconsistent-with-cone one), across engines, fork-per-case;
  planted bugs: no escalate in `_ask_shared`, no `_shared.clear()` in
  `_drop_cones`, `_theory_free` always True, no fallback on raise, no
  eviction (len <= SHARED_MAX).
- [ ] the exactness argument is in `_ask_shared`'s docstring; also update the
  module docstring (lines ~31-45 say every session is discarded),
  docs/design.md "History independence" and performance.md invariants (one
  paragraph each), credit #119.
- [ ] pinned timing: submit to sa-eval-2 (its pareto1 A/B decides; consider
  also SHARED_MAX 2 vs 4 there only if it is cheap for the evaluator).
- [ ] PR needs-human, review-clean, HELD for Tilo.
