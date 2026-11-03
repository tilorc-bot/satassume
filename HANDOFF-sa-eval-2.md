# HANDOFF sa-eval-2 (evaluator of the satassume speed effort)

Brief: see the launch message (role sa-eval). Coordinator architect-62 (was architect-61; reports go to architect-62); tech lead forward-chain-3b.

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
(2026-11-03 08:15 UTC) sa-eval-2 took over from sa-eval-1 (HANDOFF-sa-eval-1.md has its final state).
* Mutant FAILS the gates as planted; judge.py verified end to end (timing skipped): results/mutant-45deb0e.md.
* Pushed c20d7ec: fetch.sh takes short shas; newly failing tests get one serial rerun (wall-clock flakes listed, not counted).
* Released sa-eval-1's stale idle pareto1 lease. pareto1 base tree is at ~/sa-eval-bench/src/base.
* Reported (3db1d2c) to architect-62 + forward-chain-3b; told sa-cy-1 to submit here. sa-lra-1 was not reachable (not in ListAgents).
* Next: idle until a submission arrives; then judge (A/B path not yet exercised through judge.py, only via A/A).
* 08:29Z judging sa-node e80400e (clone ~/dev/sa-node; tag sa-node-1-e80400e), log in sa-eval-2 scratchpad judge-sa-node-1.log.
  Verdict to sa-node-2, forward-chain-3b, architect-62.
* 08:35Z sa-cy-2 0b157b9 (clone ~/dev/sa-cy): judge as TWO tags. sa-cy-2 = (P) pure; sa-cy-2C = (C) Cython-built
  (judge.py new opts --build/--remote-build/--check-modules/--ab-extra). Background chain (task bsbuutwib) waits for sa-node gates,
  then P gates (--skip-ab), then C build+gates (--skip-ab). AFTER sa-node's judge finishes, run the A/B:
  pareto.sh sync sa-cy-2-0b157b9=cands/sa-cy-2-0b157b9, then
  judge sa-cy-2C /home/tilo/dev/sa-cy 0b157b9 --skip-gates --ab-extra sa-cy-2-0b157b9 --check-modules satassume.sat.solver,satassume.engine
   --build "SATASSUME_CYTHON=1 /home/tilo/dev/sa-cy/.bvenv/bin/python setup.py build_ext --inplace -j 8"
   --remote-build 'docker run --rm --user $(id -u):$(id -g) -e HOME=/tmp -e SATASSUME_CYTHON=1 -v $PWD:/w -w /w sa-cy-build:1 python setup.py build_ext --inplace -j 8'
  Then write P's md timing from the same A/B (P rows are tree sa-cy-2-0b157b9). Verdicts to sa-cy-2 + forward-chain-3b.
