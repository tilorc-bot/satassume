# HANDOFF sa-eval-3 (evaluator of the satassume speed effort)

Brief: launch message (role sa-eval). Coordinator architect-63; tech lead forward-chain-3b (fc-3b).
Layout and the basic judge command: HANDOFF-sa-eval-2.md sections "Layout" and "Judge a submission" (still valid).
NEW RULE (architect-63): record each verdict with `agent report --status progress -m ...` BEFORE sending it.

## Done (all pushed on branch evalbench)
* sa-node-2 a1b0285 PASS faster, fbb484f PASS mixed (results/sa-node-2-*.md, d6869b7).
* combo-r3 measurement (results/combo-r3.md).
* FINAL-READOUT.md (evalbench/, 6940722): 6 arms, one pareto1 invocation, 7 rounds, incl. NEW secret fuzz seed
  (workload `final-fuzz`, secret/final_fuzz_seed.txt, made 10:47Z; never tell workers the seed).
* sa-cy-3 e61e024 (typed solver.pxd, C) PASS faster, 1.35-1.37x off-stream (results/sa-cy-3C-e61e024.md).
* sa-bb-1 and sa-lat-1 stopped without submitting.

## LAST JOB, then STOP: sa-cy-4 step-2 measurement (extended .pxd typing vs e61e024)
Submission arrives as "candidate /home/tilo/dev/sa-cy <SHA>: ...". Read its build command; for e61e024 it was
`CPPFLAGS=-DCYTHON_USE_TYPE_SPECS=1 SATASSUME_CYTHON=1 python setup.py build_ext --inplace --force` (CPPFLAGS, NEVER
CFLAGS: CFLAGS drops -O3). Already built on pareto1 (~/sa-eval-bench/src/): base, sa-cy-3C-e61e024, final-320C-276dab1 (untyped C).
Recipe (copy evalbench/recipes/final-readout.sh into your scratchpad, set S, edit trees), concretely:
1. `evalbench/fetch.sh /home/tilo/dev/sa-cy SHA sa-cy-4C` -> cands/sa-cy-4C-SHA. `git diff --stat e61e024 SHA` (expect .pxd only;
   if .py files changed, note it in the verdict).
2. `evalbench/pareto.sh sync sa-cy-4C-SHA=cands/sa-cy-4C-SHA` BEFORE any local build (else .so/build/ get synced; harmless but messy).
3. pareto1 build: rsync setup.py pyproject.toml README.md into pareto1:sa-eval-bench/src/T/, then
   `machine run pareto1 --shared -r "..." -- 'cd sa-eval-bench/src/T && docker run --rm --user $(id -u):$(id -g) -e HOME=/tmp
   -e SATASSUME_CYTHON=1 -e CPPFLAGS=-DCYTHON_USE_TYPE_SPECS=1 -v $PWD:/w -w /w sa-cy-build:1 python setup.py build_ext --inplace --force -j 8'`
   expect 18 .so; load-check (ssh pareto1 docker run ... importlib, see recipe) -> solver/engine/sympy_api must be x86_64 .so.
4. A/B (quiet lease, ~12 min for 4 arms): `ROUNDS=7 WORKLOADS=dev,ho-stream,ho-battery,final-fuzz,ho-fuzz,corpus,fork-battery
   evalbench/pareto.sh ab ab-sa-cy-4C-SHA base final-320C-276dab1 sa-cy-3C-e61e024 sa-cy-4C-SHA`
5. orion gates in parallel (~13-18 min): `.venv/bin/python -m evalbench.judge sa-cy-4C /home/tilo/dev/sa-cy SHA --skip-ab
   --build "CPPFLAGS=-DCYTHON_USE_TYPE_SPECS=1 SATASSUME_CYTHON=1 /home/tilo/dev/sa-cy/.bvenv/bin/python setup.py build_ext --inplace --force -j 8"
   --check-modules satassume.sat.solver,satassume.engine --note "..."`
6. Render: same judge with `--skip-gates --reuse-ab` (reads bench-results/ab-sa-cy-4C-SHA/ab-sa-cy-4C-SHA.jsonl).
   Wide table + digest check: `.venv/bin/python -m evalbench.readout bench-results/ab-sa-cy-4C-SHA/ab-sa-cy-4C-SHA.jsonl
   --arm final-320C-276dab1="#320 C untyped" --arm sa-cy-3C-e61e024="e61e024 .pxd" --arm sa-cy-4C-SHA="sa-cy-4"`; append it to
   results/sa-cy-4C-SHA.md; state speedup vs e61e024 = ratio of the two columns. Say the stream/corpus are home ground; final-fuzz is unseen.
7. Commit + push; `agent report --status progress -m "..."`; SendMessage verdict to sa-cy-4 + forward-chain-3b + architect-63. Then STOP.

## State
* 12:15Z PLAN CHANGE (architect-63, fc-3b OK): sa-eval-3 does NOT judge sa-cy-4. On arrival: reply "sa-eval-4 takes it",
  forward the line to architect-63, record it here, report (handoff), stop. sa-eval-4 runs the recipe above.
