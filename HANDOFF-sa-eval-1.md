# HANDOFF sa-eval-1 (evaluator of the satassume speed effort)

Brief: see the launch message (role sa-eval). Coordinator architect-61; tech lead forward-chain-3b.

## Layout (~/dev/sa-eval, branch `evalbench`, pushed to tilorc-bot/satassume)
* `evalbench/` harness (README in each module docstring); BASELINE.md, HOWTO-WORKERS.md there.
* local only (in .git/info/exclude): `.venv` (py3.12 + sympy pin via sympy_pin.pth), `ext/sympy`
  (copy of ~/maintenance/sympy-pin, rev in ext/sympy.rev), `ext/satsimp` (95c9340), `secret/fuzz_seed.txt`
  (held-out fuzz seed; sha256 in BASELINE.md), `cands/` (worktrees: base-9bafaa5 + one per candidate),
  `baseline-answers/9bafaa5/` (gate reference, from `gates.py --record`), `gate-results/`, `bench-results/`.
* pareto1: `~/sa-eval-bench` (synced by `evalbench/pareto.sh sync`), image `sa-eval-bench:1`.

## Judge a submission
`cd ~/dev/sa-eval && .venv/bin/python -m evalbench.judge WORKER CLONE SHA --note "..."` (gates ~8 min on orion,
then A/B ~10 min on pareto1 under a quiet lease) -> evalbench/results/WORKER-SHA.md; commit+push; send verdict
to worker and forward-chain-3b.

## State
(2026-11-03 08:00 UTC, sa-eval-1 handing off at its context limit, on architect-61's instruction)

Done and pushed (`evalbench` 74665d7):
* split.json (dev: 83 sets, 1,985 queries), replay/counters/phases, forkq, cold_battery, gates, ab,
  summarize, pareto.sh, fetch.sh, judge.py, dev.py, BASELINE.md, HOWTO-WORKERS.md.
* Baseline recorded: baseline-answers/9bafaa5/ (answers + 6,083-pass test outcomes); counters in
  evalbench/baseline-counters-9bafaa5.json; dev answers in evalbench/dev-answers-9bafaa5.jsonl.
* A/A on pareto1 CPU 2 (bench-results/aa-9bafaa5/): medians agree within 1%, single rounds within about ±6%.
  Rule: faster = median >= 1.02x and every round's ratio < 1. Baseline is history-independent (0 diffs).

Not done / next steps:
1. The mutant gate run (`gate-results/mutant-test`, log in sa-eval-1's scratchpad mutant.log) was
   still in its second test phase (9bafaa5's tests against the mutant's package). The answer
   digests already differ as expected. Once gates.json is written, confirm the FAIL lines and diff
   listing, then optionally write results/mutant-test.md. If the run died, re-run:
   `.venv/bin/python -m evalbench.gates cands/mutant-test --out gate-results/mutant-test`.
2. `judge.py` has not run end to end yet (its compare path depends on step 1). Exercise it on the first
   submission, or on the mutant with `--skip-gates` after renaming gate-results/mutant-test to
   gate-results/mutant-<sha>.
3. Then serve submissions: judge -> commit results/*.md -> push -> SendMessage the worker and forward-chain-3b.
   A candidate that changes any answer FAILS unless forward-chain-3b approves that class of change.
Gotchas: child processes run with cwd=.shim (sa-eval is itself a satassume checkout, so `-m` would
otherwise import the wrong package). The container mounts read-only, so trees are byte-compiled first.
The pareto1 governor is powersave.
