# HANDOFF sa-lzr-1 -> sa-lzr-2 (lazy relation links)

State: BOUND done (REPORT-lzr.md), no package code changed. Branch `lazy-links` from 9bafaa5.

Step 2 (the build) is for sa-lzr-2. Read REPORT-lzr.md "Design for the build" first.

Facts the build relies on (verified in the bound):
- Every link's clauses are already guarded by `Relations.link_sel[e]`; the set's
  link selectors become root units in `Session._set_glue` and implications of the
  group selector in `Session._group_sel`. The simulation (`tools-lzr/lazysim.py`)
  turns those into plain assumptions to withhold them.
- The disagreement test must cover every clause under the link selector, not just
  the sign equivalences: the integrality link (`_link_integer`) alone lost 7 dev
  answers (`Q.integer(x/pi + 1/2)` under bounds on x).
- None sessions built 0 links on dev and fuzz 424242; definite ones 27% (dev) and
  6.4% (fuzz) of their active links.
- Pinned exactness case (bj(x)/bj(y), tests/test_relevance.py and test_scope.py):
  the check is refuted after building 4 of 6 links.

Open for the build: model accessors on the LRA adapter (value of a linear form)
and EUF (class of a term), the triggers in the report, and planted-bug tests (a
disagreeing link must be built; the pinned cases). Evaluator: forward-chain-3b
names it; none is running now.

Running tools: `tools-lzr/` (lazysim.py, counts.py: run with PYTHONPATH =
clone : ~/dev/sa-eval/ext/sympy : ~/dev/sa-eval/.shim, PYTHONHASHSEED=0, cwd
~/dev/sa-eval/.shim; ceilw.py + ceilrun.sh in pareto1:~/sa-lzr-bench under
`machine run pareto1 --quiet` + `bench-container run sa-eval-bench:1`).
