# combo-r3: round-3 combined measurement (MEASUREMENT, superseded by FINAL-READOUT.md)

Requested by forward-chain-3b via architect-63 (09:40Z). Trees built with a clean `git merge --no-ff 0b157b9` (no conflicts, no edits):
* `combo-node-cy-1d6712b` = a1b0285 (sa-node-2, SHARED_MAX 1) + 0b157b9 (Cython build), compiled (18 .so; engine.py, changed by a1b0285, is in the compiled list)
* `combo-lra-cy-4c9cf02` = 4f9d931 (sa-lrashare-1, SHARE_THEORY on, measurement only) + 0b157b9, compiled

## Gates (orion, C built; .so load-checked on orion and pareto1)
| tree | answers (stream, battery, corpus, ho-fuzz, fork, unique, shuffled, fresh process) | tests |
|---|---|---|
| combo-node-cy | all identical | only the approved tests.test_engine::test_contextual_queries_build_and_discard fails -> PASS |
| combo-lra-cy | all identical | tests.test_set_verdict::test_one_set_check_per_query fails (own + baseline suite), plus the approved one in the baseline suite. Counting tests, not answers; 4f9d931 itself was never gated |

Per-tree gate reports: results/combo-node-cy-1d6712b.md, results/combo-lra-cy-4c9cf02.md.

## Pinned A/B (pareto1, quiet lease, one invocation, 5 rounds + 1 warm-up, cold processes, PYTHONHASHSEED=0)
| workload | metric | base median s | a1b0285+0b157b9 C | 4f9d931+0b157b9 C |
|---|---|---|---|---|
| dev | seconds | 0.532 | **1.30x** (1.29..1.30) | **1.53x** (1.52..1.53) |
| dev | none_s | 0.316 | **1.35x** (1.33..1.35) | **1.63x** (1.62..1.63) |
| dev | def_s | 0.216 | **1.24x** (1.23..1.24) | **1.40x** (1.40..1.40) |
| ho-stream | seconds | 2.999 | **1.27x** (1.26..1.28) | **1.64x** (1.63..1.66) |
| ho-stream | none_s | 1.937 | **1.29x** (1.28..1.30) | **1.72x** (1.71..1.74) |
| ho-stream | def_s | 1.046 | **1.24x** (1.24..1.25) | **1.52x** (1.51..1.54) |
| ho-battery | seconds | 0.632 | **1.21x** (1.21..1.23) | **1.32x** (1.31..1.33) |
| ho-battery | none_s | 0.440 | **1.22x** (1.21..1.24) | **1.31x** (1.31..1.32) |
| ho-battery | def_s | 0.188 | **1.21x** (1.19..1.23) | **1.33x** (1.32..1.36) |
| ho-fuzz | seconds | 7.947 | **1.21x** (1.20..1.22) | **1.18x** (1.17..1.19) |
| ho-fuzz | none_s | 6.676 | **1.21x** (1.20..1.22) | **1.18x** (1.17..1.19) |
| ho-fuzz | def_s | 1.041 | **1.23x** (1.22..1.24) | **1.21x** (1.21..1.23) |
| corpus | seconds | 0.536 | **1.19x** (1.18..1.26) | **1.17x** (1.16..1.22) |
| corpus | none_s | 0.279 | **1.19x** (1.18..1.26) | **1.19x** (1.18..1.23) |
| corpus | def_s | 0.256 | **1.19x** (1.18..1.26) | **1.15x** (1.14..1.20) |
| fork-battery | ask_s | 0.768 | **1.14x** (1.11..1.21) | **1.23x** (1.21..1.27) |
| fork-battery | ask_none_s | 0.495 | **1.14x** (1.09..1.22) | **1.21x** (1.20..1.26) |
| fork-battery | refine_s | 1.230 | **1.08x** (1.05..1.11) | **1.12x** (1.10..1.14) |

| workload | queries | base digest stable | a1b0285+0b157b9 C | 4f9d931+0b157b9 C |
|---|---|---|---|---|
| dev | 1985 | yes | same | same |
| ho-stream | 13626 | yes | same | same |
| ho-battery | 1101 | yes | same | same |
| ho-fuzz | 3000 | yes | same | same |
| corpus | 2863 | yes | same | same |
| fork-battery | None | yes | same | same |

rounds: 5 (warm-up excluded); medians of paired ratios; range = min..max speedup over rounds.

The stream (dev, ho-stream) is satassume's home ground: its corpus was recorded from the same SymPy tests. ho-fuzz has been used for every judgement tonight, so it counts as seen.
