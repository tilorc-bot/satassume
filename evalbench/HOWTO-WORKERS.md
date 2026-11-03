# satassume speed work: how to measure and how to submit

The evaluator is the session **sa-eval-1** (harness: `~/dev/sa-eval`, branch
`evalbench`). Its numbers decide what is kept. The baseline is satassume `main` at
`9bafaa5`.

## Measure in your own clone (seconds per run)

```bash
PY=~/dev/sa-eval/.venv/bin/python          # Python 3.12, SymPy pin (~/maintenance/sympy-pin) preinstalled
$PY ~/dev/sa-eval/evalbench/dev.py ~/dev/YOUR-CLONE --base ~/dev/sa-eval/cands/base-9bafaa5
```

This prints:

* **answers**: the dev set's answers compared with 9bafaa5's, query by query. Any
  difference is listed. A candidate that changes an answer fails unless
  forward-chain-3b approves that class of change.
* **time**: medians of cold processes, base and yours alternating, split into
  queries answered None and definite ones. This runs unpinned on a shared machine,
  so treat differences under ~5% as noise. The evaluator's pinned A/B decides.
* **counters**: deterministic and noise-free, yours / base / delta. Sessions built,
  context builds (`context_builds`, `set_checks`), escalations, searches,
  `relevant`, consistency checks, cache hits, and summed solver statistics
  (`solver_conflicts`, `solver_decisions`, `solver_propagations`, clauses, vars).
  Use these to tell whether a change removed work.
* **phases** (instrumented run, s): `front` (sympy_api outside the engine),
  `build` (the set's session and its complete check), `prepare`
  (`prepare_query`, `assumption_lits`), `propagate`, `escalate`, `search`,
  `engine` (the rest of `Engine.ask`). The instrumentation wraps
  `Engine._fresh_session/_build_context/_context_session/verdict/ask/is_`
  and `Session.prepare_query/assumption_lits/escalate/query_literal`. If you
  rename one of these, the report says which; that's fine, but say so in
  your submission.

Options: `--rounds N` (default 3), `--workload dev-unique` (no repeated queries,
so no answer-memo hits), `--profile out.prof` (cProfile of the dev replay; read it
with `python -m pstats out.prof`). The dev set is 1,985 queries (1,235 unique) from
83 whole assumption sets of the recorded stream. About 45% are answered None at 9bafaa5.

Run satassume's own tests as usual (`$PY -m pytest -n 6 tests` in your clone).

## What the evaluator runs on a submission

1. **Gates** (all must hold):
   * answers identical to 9bafaa5, position by position, on the full stream
     (16,232), the battery stream (16,386), the corpus (2,863), a held-out fuzz
     set, and satsimp's refine output on a forked battery slice. Inconsistent sets'
     `ValueError` counts as an answer.
   * history independence: the unique stream in a shuffled order, and every
     unique stream query in a fresh process, gives 9bafaa5's answers.
   * the test suite: your suite passes as on 9bafaa5, and **9bafaa5's tests run
     against your package** pass as well. Don't fix a failure by editing a test.
2. **Time**: a pinned A/B on pareto1. Baseline and candidate alternate inside one
   `bench-container` lease, cold processes, 5 rounds plus a warm-up, medians,
   PYTHONHASHSEED=0. The workloads are the dev set, held-out stream sets you don't
   see, held-out battery queries, a held-out fuzz seed, the corpus, and a
   fork-per-case refine battery slice (103 cases, time inside satassume's `ask`).
   The verdict reports speedup with its per-round spread against the A/A noise
   floor in `BASELINE.md`.
3. **Counters** on the same workloads.

Don't tune to the dev set. The held-out sets are there to catch that.

## Submit

Commit in your clone, then:

```
SendMessage sa-eval-1 "candidate <clone path> <sha>: <one line: what it does>"
```

The evaluator snapshots that commit into its own worktree, so you can keep working
afterwards. The verdict goes to you and forward-chain-3b, with the full report in
`~/dev/sa-eval/evalbench/results/<worker>-<sha>.md`.
