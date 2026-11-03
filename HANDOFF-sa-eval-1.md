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
