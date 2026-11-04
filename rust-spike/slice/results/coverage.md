
## dev: 1985 queries, pass median 0.527 s over 7 time rounds (range 0.524 to 0.558), sampled 0.536 s, digests ['31cd0945c07f02a6']

| class | queries | None | definite | time % | None % of pass | definite % of pass |
|---|---:|---:|---:|---:|---:|---:|
| no session | 1118 | 463 | 655 | 0.9 | 0.4 | 0.6 |
| no theory | 669 | 330 | 339 | 38.9 | 24.9 | 14.0 |
| rational, no EUF | 0 | 0 | 0 | 0.0 | 0.0 | 0.0 |
| rational+EUF | 55 | 22 | 33 | 13.0 | 5.6 | 7.4 |
| rational+EUF+transfer | 35 | 16 | 19 | 10.3 | 4.9 | 5.5 |
| constants | 108 | 61 | 47 | 36.8 | 23.6 | 13.2 |
| all | 1985 | 892 | 1093 | 100 | 59.4 | 40.6 |

Share of pass, % (SymPy on stack in brackets), part by class:

| part | no session | no theory | rational, no EUF | rational+EUF | rational+EUF+transfer | constants | all |
|---|---:|---:|---:|---:|---:|---:|---:|
| sat | 0.0 (0.0) | 16.7 (0.0) | 0.0 (0.0) | 4.0 (0.0) | 3.8 (0.0) | 12.9 (0.0) | 37.4 (0.0) |
| other_sat | 0.0 (0.0) | 0.6 (0.0) | 0.0 (0.0) | 0.2 (0.1) | 0.2 (0.1) | 0.8 (0.3) | 1.8 (0.5) |
| lra_core | 0.0 (0.0) | 0.1 (0.0) | 0.0 (0.0) | 2.6 (0.0) | 1.5 (0.0) | 4.7 (0.1) | 8.9 (0.2) |
| lra_constfield | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 2.6 (0.1) | 2.6 (0.1) |
| lra_adapter | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 0.5 (0.3) | 0.3 (0.1) | 1.4 (0.7) | 2.3 (1.2) |
| relations | 0.0 (0.0) | 0.8 (0.2) | 0.0 (0.0) | 2.2 (0.6) | 2.0 (0.7) | 4.7 (1.7) | 9.7 (3.3) |
| euf | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 0.4 (0.0) | 0.2 (0.0) | 0.8 (0.0) | 1.3 (0.1) |
| euf_adapter | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 0.4 (0.3) | 0.2 (0.1) | 0.8 (0.4) | 1.4 (0.7) |
| transfer | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 0.1 (0.0) | 0.2 (0.0) | 0.1 (0.0) | 0.3 (0.1) |
| session | 0.0 (0.0) | 4.6 (0.7) | 0.0 (0.0) | 1.3 (0.2) | 1.0 (0.1) | 4.0 (0.4) | 11.0 (1.3) |
| engine | 0.0 (0.0) | 3.9 (0.5) | 0.0 (0.0) | 0.6 (0.1) | 0.4 (0.0) | 1.5 (0.1) | 6.3 (0.7) |
| knowledge | 0.0 (0.0) | 8.0 (0.9) | 0.0 (0.0) | 0.4 (0.1) | 0.3 (0.0) | 1.7 (0.2) | 10.4 (1.2) |
| outside | 0.2 (0.1) | 3.1 (1.4) | 0.0 (0.0) | 0.4 (0.1) | 0.2 (0.0) | 0.7 (0.2) | 4.6 (1.8) |
| unsampled | 0.7 (0.0) | 1.1 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 1.9 (0.0) |

Theory activity: queries in class where the theory's assert/check/propagate returned a conflict or propagation:

- rational, no EUF: 0 queries; EUF said 0; transfer said 0; LRA said 0; none said 0
- rational+EUF: 55 queries; EUF said 3; transfer said 0; LRA said 43; none said 12
- rational+EUF+transfer: 35 queries; EUF said 0; transfer said 12; LRA said 24; none said 9
- constants: 108 queries; EUF said 10; transfer said 0; LRA said 47; none said 57

Solver methods called from outside the solver: total 47,132; add_clause 13,877, ensure_vars 7,324, theories 4,589, add_internal 3,298, register_atom 3,285, propagate 2,681, implied 2,524, register_block 2,418, mention 1,673, set_inert 1,156, release 1,080, set_rule_block 918, solve 833, attach_theory 431

Theory calls from the solver: lra 52,206 (assert 3,884 check 417), euf 21,847, transfer 5,091, sharing 506. Python session or adapter frames entered during a solver call: 0. Sessions 918, _visit 2,482, _compile_patterns 2,461, escalate 490, discover 3,259, build_context 833, _is_custom 2, facts-custom 0

Most a timed pass could show, crossings free (k 12.9, k_lra 16.6, per class where measured):

| slice | queries in Rust | None q | def q | time of those queries % | moved SAT % | moved LRA % | max speedup whole | None | definite | stays 1x, k_rest for 2x: outside only | outside + SymPy-on-stack |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| P plan as written: session, solver, rational LRA | 669 | 330 | 339 | 38.9 | 16.7 | 0.1 | 1.18 | 1.23 | 1.12 | 1.82 | 2.04 |
| P+ plan plus EUF | 724 | 352 | 372 | 52.0 | 20.7 | 2.7 | 1.28 | 1.30 | 1.24 | 1.68 | 1.87 |
| P++ plus EUF and transfer | 759 | 368 | 391 | 62.3 | 24.5 | 4.2 | 1.36 | 1.37 | 1.35 | 1.57 | 1.72 |
| Q solver boundary: all sessions | 867 | 429 | 438 | 99.1 | 37.4 | 4.2 | 1.62 | 1.67 | 1.57 | 1.29 | 1.37 |

Stays: outside 6.4%, SymPy on stack outside the moved parts 9.0%. Sum of per-query medians 0.525 s.

## fuzz: 3000 queries, pass median 8.033 s over 7 time rounds (range 7.983 to 8.101), sampled 8.174 s, digests ['173502b6ef285ad6']

| class | queries | None | definite | time % | None % of pass | definite % of pass |
|---|---:|---:|---:|---:|---:|---:|
| no session | 63 | 15 | 48 | 0.0 | 0.0 | 0.0 |
| no theory | 77 | 58 | 19 | 0.2 | 0.2 | 0.0 |
| rational, no EUF | 7 | 0 | 7 | 0.0 | 0.0 | 0.0 |
| rational+EUF | 1549 | 1276 | 273 | 46.3 | 39.0 | 7.3 |
| rational+EUF+transfer | 731 | 608 | 123 | 31.7 | 27.0 | 4.6 |
| constants | 573 | 430 | 143 | 21.8 | 17.4 | 4.4 |
| all | 3000 | 2387 | 613 | 100 | 83.5 | 16.5 |

Share of pass, % (SymPy on stack in brackets), part by class:

| part | no session | no theory | rational, no EUF | rational+EUF | rational+EUF+transfer | constants | all |
|---|---:|---:|---:|---:|---:|---:|---:|
| sat | 0.0 (0.0) | 0.1 (0.0) | 0.0 (0.0) | 17.6 (0.0) | 11.8 (0.0) | 7.8 (0.0) | 37.3 (0.0) |
| other_sat | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 0.9 (0.4) | 0.5 (0.2) | 0.4 (0.2) | 1.8 (0.7) |
| lra_core | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 8.4 (0.3) | 4.7 (0.1) | 3.6 (0.1) | 16.8 (0.5) |
| lra_constfield | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 0.6 (0.0) | 0.7 (0.0) |
| lra_adapter | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 1.6 (0.8) | 1.0 (0.5) | 0.8 (0.4) | 3.3 (1.7) |
| relations | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 7.2 (2.5) | 6.0 (2.5) | 3.7 (1.4) | 16.9 (6.5) |
| euf | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 1.3 (0.0) | 1.1 (0.0) | 0.6 (0.0) | 3.0 (0.1) |
| euf_adapter | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 1.1 (0.6) | 0.8 (0.4) | 0.5 (0.3) | 2.4 (1.3) |
| transfer | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 0.1 (0.1) | 1.2 (0.0) | 0.3 (0.0) | 1.6 (0.1) |
| session | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 4.5 (0.6) | 2.6 (0.3) | 1.9 (0.3) | 9.0 (1.1) |
| engine | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 1.7 (0.2) | 0.9 (0.1) | 0.8 (0.1) | 3.5 (0.3) |
| knowledge | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 0.7 (0.1) | 0.4 (0.1) | 0.3 (0.1) | 1.5 (0.3) |
| outside | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 1.2 (0.5) | 0.6 (0.2) | 0.6 (0.3) | 2.4 (1.0) |
| unsampled | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) |

Theory activity: queries in class where the theory's assert/check/propagate returned a conflict or propagation:

- rational, no EUF: 7 queries; EUF said 0; transfer said 0; LRA said 7; none said 0
- rational+EUF: 1549 queries; EUF said 84; transfer said 0; LRA said 1443; none said 95
- rational+EUF+transfer: 731 queries; EUF said 45; transfer said 582; LRA said 709; none said 9
- constants: 573 queries; EUF said 41; transfer said 135; LRA said 539; none said 25

Solver methods called from outside the solver: total 691,126; add_clause 316,135, ensure_vars 128,990, register_atom 94,780, add_internal 33,176, set_inert 28,709, theories 20,001, register_block 16,493, propagate 12,003, implied 11,681, mention 7,974, attach_theory 6,940, release 5,044, set_rule_block 3,133, solve 2,859

Theory calls from the solver: lra 1,533,444 (assert 117,944 check 8,292), euf 728,883, transfer 402,262, sharing 8,009. Python session or adapter frames entered during a solver call: 0. Sessions 3,133, _visit 16,537, _compile_patterns 16,537, escalate 3,622, discover 58,720, build_context 2,952, _is_custom 45, facts-custom 0

Most a timed pass could show, crossings free (k 15.2, k_lra 22.1, per class where measured):

| slice | queries in Rust | None q | def q | time of those queries % | moved SAT % | moved LRA % | max speedup whole | None | definite | stays 1x, k_rest for 2x: outside only | outside + SymPy-on-stack |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| P plan as written: session, solver, rational LRA | 84 | 58 | 26 | 0.2 | 0.1 | 0.0 | 1.00 | 1.00 | 1.00 | 2.05 | 2.41 |
| P+ plan plus EUF | 1633 | 1334 | 299 | 46.5 | 17.7 | 8.4 | 1.33 | 1.34 | 1.26 | 1.55 | 1.75 |
| P++ plus EUF and transfer | 2364 | 1942 | 422 | 78.2 | 29.5 | 13.2 | 1.67 | 1.71 | 1.49 | 1.22 | 1.30 |
| Q solver boundary: all sessions | 2937 | 2372 | 565 | 100.0 | 37.3 | 13.2 | 1.90 | 1.95 | 1.70 | 1.06 | 1.08 |

Stays: outside 2.4%, SymPy on stack outside the moved parts 12.0%. Sum of per-query medians 8.006 s.
