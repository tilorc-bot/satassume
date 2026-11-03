# REPORT: what do B&B exhaustions cost? (sa-lat-1)

sa-lat-1, 2026-11-03. Branch `lattice` from 9bafaa5, no source change. Bound only: **under 5%
on every workload, so no build.**

## Method

`lat-tools/cost_child.py SPEC MODE` runs one cold pass, times every `LRATheory._check`, flags
those that exhaust `BRANCH_BUDGET` (`stats["exhausted"]` grows), and records per-query times.
MODE `latds` installs sa-bb-1's (c2) prototype (`lat-tools/proto_hook.py`, the lattice span test
plus derived-integral slacks branched first, from `bb-tools/patch_child.py` on `bb-budget`)
under the same timer. `run_pinned.sh`: pareto1, quiet lease, bench-container (cpu 2,
sa-eval-bench:1 image), PYTHONHASHSEED=0, 3 rounds, base and prototype alternating. Fuzz seed
424242 (not a held-out seed). Raw data: `lat-tools/cost-pareto1.jsonl`; `summ.py` prints the
table. Medians over rounds:

| workload | pass (s) | exhausting checks | in them | all LRA checks | queries with one | prototype saves on those queries | prototype whole pass |
|---|---:|---:|---:|---:|---:|---:|---:|
| dev | 0.543 | 16 | **0.9%** | 3.2% | 5.5% | 0.3% | 0.997x |
| stream | 3.417 | 50 | **0.4%** | 3.8% | 2.5% | 0.1% | 0.987x |
| battery | 3.784 | 48 | **0.35%** | 4.0% | 2.5% | 0.5% | 0.985x |
| fuzz 424242 | 8.068 | 277 | **1.3%** | 4.1% | 8.8% | -0.2% | 0.967x |

("in them" = time inside exhausting `_check` calls / pass time. "queries with one" is the whole
time of the queries that contain an exhausting check, session build included: a ceiling on
any downstream effect. "saves on those queries" pairs each such query's base and prototype
time.) Answers: identical on dev, stream and battery; fuzz differs by the 1 more-definite
answer sa-bb-1 found.

## Why it is small

`BRANCH_BUDGET` is 16 nodes, and the problems have 1-2 term variables: an exhausting check is
16 tiny simplex calls, 0.3-0.4 ms. All of LRA `_check` is 3-4% of every pass. The fuzz
workload's ~2.7 ms per None query is not spent in B&B: exhausting checks are 1.3% of fuzz
and the queries that contain one are 8.8%, and the prototype recovers none of the latter
(those queries are dominated by their session build, propagation and search, which stay).
The prototype's span test, run on every check with integrality literals, costs more than it
saves: 1-3% slower on every workload.

## Recommendation

Do not build (c2) for speed: the bound is 0.35-1.3%, and what is recoverable is at most
0.5%. Its only remaining value is the one in REPORT-bb.md: about 8x fewer exhaustions, so
a smaller empirical hazard for shared LRA sessions, which are off by default (Tilo's
decision). A clean (c2) would cost about 85 lines, run the span test on about a quarter of
checks, and make 1 fuzz answer in 3,000 more definite (needs-human). Build it only if Tilo
turns LRA sharing on and wants the hazard cut.
