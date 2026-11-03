# FINAL READOUT: satassume speed effort (sa-eval-3, 2026-11-03 11:42Z)

The trees as they stand in the PRs, timed against main 9bafaa5 in ONE pinned A/B invocation.

## Arms
| arm | tree | what | gates |
|---|---|---|---|
| base | 9bafaa5 | main | reference |
| #321 3a7b03a | PR 321 head (a1b0285 + review fixes) | shared contextual session, SHARED_MAX 1, pure Python | PASS by sa-node-3 (not re-gated here); answers checked in this A/B |
| #320 276dab1 C | PR 320 head (0b157b9 + build-script file closing), Cython-built | optional compiled build, 18 unchanged modules | **PASS** |
| #321+#320 C | `git merge` 3a7b03a + 276dab1 = a300007 (clean, no edits), built | both PRs together | **PASS** (only the approved tests.test_engine::test_contextual_queries_build_and_discard fails) |
| lra-share+#320 C | `git merge` 4f9d931 + 276dab1 = 03ddfb0 (clean), built | MEASUREMENT ONLY: SHARE_THEORY on (LRA sessions shared; Tilo's decision) | answers identical on every gate workload; tests: tests.test_set_verdict::test_one_set_check_per_query fails (own + baseline suite) + the approved one -> gate FAIL on a counting test |
| e61e024 .pxd C | sa-cy-3 e61e024 = 0b157b9 + augmenting solver.pxd (no .py edits), built with CPPFLAGS=-DCYTHON_USE_TYPE_SPECS=1 | MEASUREMENT ONLY: typed Cython | **PASS** (C gates); pure tree = 0b157b9 + .pxd |

Gates = answers identical to 9bafaa5 on the full stream, battery, corpus, held-out fuzz and fork slice, and on the unique stream in recorded order, shuffled, and one fresh process per query; satassume's own suite and 9bafaa5's suite on the candidate. C trees: built on orion (aarch64) for the gates and on pareto1 (x86_64, image sa-cy-build:1) for timing; on both machines the compiled solver/engine/sympy_api .so was confirmed to be what loads.

## Time (pareto1, quiet lease, 7 rounds + 1 warm-up, arms rotated per round, cold processes, PYTHONHASHSEED=0)
Speedup = base time / arm time, median of the paired per-round ratios; (min..max over rounds). A/A noise at 9bafaa5: medians within 1%, single rounds within about ±6%.

| workload | metric | base median s | #321 3a7b03a | #320 276dab1 C | #321+#320 C | lra-share+#320 C | e61e024 .pxd C |
|---|---|---|---|---|---|---|---|
| dev | seconds | 0.531 | **1.09x** (1.09..1.09) | **1.20x** (1.19..1.20) | **1.30x** (1.29..1.30) | **1.52x** (1.39..1.53) | **1.33x** (1.32..1.34) |
| dev | none_s | 0.315 | **1.12x** (1.12..1.13) | **1.21x** (1.20..1.21) | **1.34x** (1.33..1.34) | **1.62x** (1.53..1.63) | **1.35x** (1.34..1.36) |
| dev | def_s | 0.215 | **1.05x** (1.04..1.05) | **1.18x** (1.17..1.19) | **1.23x** (1.22..1.24) | **1.39x** (1.23..1.40) | **1.31x** (1.30..1.32) |
| ho-stream | seconds | 2.997 | **1.05x** (1.05..1.06) | **1.22x** (1.21..1.23) | **1.27x** (1.26..1.29) | **1.64x** (1.63..1.66) | **1.37x** (1.34..1.38) |
| ho-stream | none_s | 1.936 | **1.06x** (1.05..1.07) | **1.23x** (1.22..1.24) | **1.29x** (1.28..1.30) | **1.72x** (1.71..1.74) | **1.39x** (1.36..1.39) |
| ho-stream | def_s | 1.047 | **1.04x** (1.03..1.04) | **1.21x** (1.20..1.21) | **1.24x** (1.23..1.26) | **1.52x** (1.47..1.54) | **1.35x** (1.29..1.35) |
| ho-battery | seconds | 0.630 | **1.02x** (1.02..1.03) | **1.19x** (1.18..1.19) | **1.21x** (1.12..1.22) | **1.32x** (1.31..1.33) | **1.29x** (1.28..1.30) |
| ho-battery | none_s | 0.440 | **1.03x** (1.02..1.03) | **1.19x** (1.18..1.19) | **1.22x** (1.19..1.22) | **1.31x** (1.31..1.33) | **1.30x** (1.28..1.30) |
| ho-battery | def_s | 0.187 | **1.02x** (1.01..1.03) | **1.18x** (1.17..1.19) | **1.19x** (0.96..1.20) | **1.33x** (1.30..1.35) | **1.28x** (1.27..1.29) |
| final-fuzz | seconds | 8.046 | **1.00x** (0.99..1.02) | **1.23x** (1.21..1.24) | **1.22x** (1.21..1.25) | **1.19x** (1.18..1.21) | **1.35x** (1.33..1.37) |
| final-fuzz | none_s | 6.691 | **1.00x** (0.99..1.02) | **1.23x** (1.21..1.24) | **1.23x** (1.22..1.25) | **1.19x** (1.18..1.20) | **1.35x** (1.33..1.38) |
| final-fuzz | def_s | 1.133 | **1.01x** (1.00..1.02) | **1.23x** (1.22..1.25) | **1.21x** (1.20..1.23) | **1.21x** (1.19..1.22) | **1.35x** (1.34..1.37) |
| ho-fuzz | seconds | 7.902 | **0.99x** (0.98..1.01) | **1.21x** (1.20..1.22) | **1.22x** (1.22..1.23) | **1.18x** (1.16..1.19) | **1.34x** (1.33..1.36) |
| ho-fuzz | none_s | 6.637 | **0.99x** (0.98..1.01) | **1.21x** (1.20..1.22) | **1.22x** (1.22..1.23) | **1.17x** (1.16..1.19) | **1.34x** (1.33..1.36) |
| ho-fuzz | def_s | 1.038 | **1.00x** (0.98..1.01) | **1.23x** (1.22..1.24) | **1.24x** (1.23..1.25) | **1.21x** (1.20..1.22) | **1.35x** (1.33..1.38) |
| corpus | seconds | 0.536 | **0.99x** (0.98..0.99) | **1.21x** (1.19..1.21) | **1.19x** (1.18..1.19) | **1.16x** (1.10..1.17) | **1.36x** (1.27..1.37) |
| corpus | none_s | 0.279 | **0.98x** (0.98..0.99) | **1.23x** (1.22..1.23) | **1.19x** (1.17..1.20) | **1.18x** (1.14..1.20) | **1.41x** (1.37..1.42) |
| corpus | def_s | 0.256 | **0.99x** (0.98..0.99) | **1.18x** (1.16..1.19) | **1.18x** (1.17..1.19) | **1.14x** (1.05..1.15) | **1.31x** (1.17..1.31) |
| fork-battery | ask_s | 0.771 | **1.03x** (0.98..1.08) | **1.11x** (1.07..1.12) | **1.16x** (1.10..1.16) | **1.27x** (1.21..1.33) | **1.18x** (1.13..1.24) |
| fork-battery | ask_none_s | 0.497 | **1.03x** (0.97..1.09) | **1.11x** (1.06..1.12) | **1.15x** (1.09..1.16) | **1.26x** (1.20..1.34) | **1.18x** (1.11..1.25) |
| fork-battery | refine_s | 1.234 | **1.02x** (0.99..1.05) | **1.06x** (1.03..1.07) | **1.08x** (1.05..1.09) | **1.14x** (1.10..1.17) | **1.10x** (1.07..1.13) |

Workloads: **dev** = 1,985 stream queries (whole assumption sets; the workers' dev set). **ho-stream** = the held-out 13,626 stream queries (split by set before any candidate). **ho-battery** = 1,101 battery queries not in the stream. **final-fuzz** = a NEW fuzz seed made at readout time (10:47Z), never shown to any worker (sha256 of secret/final_fuzz_seed.txt: `ecf151eaa1d8e91bc2d64415b5e9f733b04bdea26426003d64e99ae6527174b6`); 3,000 queries, 4 of which coincide with ho-fuzz. **ho-fuzz** = the held-out fuzz seed used for every judgement tonight, so it counts as seen. **corpus** = satassume's corpus, 2,863 queries. **fork-battery** = 103 battery cases, one forked process per case (assume-eval style): ask_s = time inside ask, refine_s = the refine call.

## Answers (every arm, every workload, every round: answer digest vs base)
| workload | queries | base digest stable | #321 3a7b03a | #320 276dab1 C | #321+#320 C | lra-share+#320 C | e61e024 .pxd C |
|---|---|---|---|---|---|---|---|
| dev | 1985 | yes | same | same | same | same | same |
| ho-stream | 13626 | yes | same | same | same | same | same |
| ho-battery | 1101 | yes | same | same | same | same | same |
| final-fuzz | 3000 | yes | same | same | same | same | same |
| ho-fuzz | 3000 | yes | same | same | same | same | same |
| corpus | 2863 | yes | same | same | same | same | same |
| fork-battery | 103 cases | yes | same | same | same | same | same |

## Reading
* **Both PRs together (#321+#320 C): 1.27x on the held-out stream (None 1.29x), 1.22x on the new fuzz seed, 1.21x on the held-out battery, 1.19x on the corpus, 1.16x inside ask on the fork slice; dev 1.30x.** Every round is faster in total time on every workload (one ho-battery round was 4% slower on its definite answers alone). Answers are identical everywhere.
* #320 alone (compiled) gives ~1.2x across the board: 1.22x held-out stream, 1.23x new fuzz, 1.21x corpus, 1.11x fork ask. This is the bulk of the gain off the stream.
* #321 alone (pure Python) helps on the stream: dev 1.09x, held-out stream 1.05x (None 1.06x), battery 1.02x, fork ask 1.03x (within noise). It is neutral on fuzz (1.00x) and ~1% slower on the corpus (0.99x, slower in every round). On top of #320 it adds 1.27/1.22 = ~4% on the held-out stream, nothing on fuzz, and costs ~2% on the corpus (1.19x vs 1.21x).
* Measurement arms: lra-share+#320 is the fastest on the stream (held-out 1.64x, None 1.72x) but slower than #320 alone on fuzz and corpus (1.19x / 1.16x); its own counting test fails, and LRA sharing is Tilo's decision (see sa-bb's REPORT-bb.md on exactness). Typed Cython (e61e024) is the fastest everywhere off the stream: 1.37x held-out stream, 1.35x new fuzz, 1.36x corpus. That is +10-13% over untyped #320 for 64 lines of solver.pxd.
* **The stream (dev, ho-stream) and the corpus are satassume's home ground**: its corpus was recorded from the same SymPy tests. The new fuzz seed is the only workload nobody has seen. On it, the PR pair gives 1.22x, all from the compiled build.

Raw rows: bench-results/ab-final/ab-final.jsonl (local). Gate reports: results/final-320C-276dab1.md, results/final-merge321-320C-a300007.md, results/final-lra-320C-03ddfb0.md, results/sa-cy-3C-e61e024.md. Merged trees were made with `git merge` only. Table: `python -m evalbench.readout`.
