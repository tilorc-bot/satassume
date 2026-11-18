# Facts built against facts read: full counts (issue 323; sa-port-321, read-only)

Output of `tools319/sum320.py dev=dev.cnt fuzz=fuzz.cnt` on the count run described in `capi-attribution.md`, section (b):
46750d4 with the scratch count patch, +rust+frames, pareto1 under a shared lease, one run each. Counts of facts, not
times. "n/m": not marked. [p]: a lower bound; a check refuted inside `implied()` leaves no proof mark.
Built-but-unread ("never visited") is an upper bound in hindsight, not a saving.

### dev

Solvers 918 (born in the query 78, in build_context 840, in its check 0), from 4717 count lines. Entries: solve_int 1930, assume 2999, propagate 2681, entails by a live trail 141, by a trail that is not live 0, root conflicts 0. Context solvers that never reached solve_int: 6.

| clauses, by where they were added | built | query: visited | query: reason | query: proof | check: visited | check: reason | check: proof [p] | any phase: visited | any: reason | any: proof | never visited |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| build_context (phase 1) | 12838 | 7219 (56.2%) | 3852 (30.0%) | 633 (4.9%) | 10607 (82.6%) | 5819 (45.3%) | 205 (1.6%) | 11778 (91.7%) | 7135 (55.6%) | 815 (6.3%) | 1060 |
| its complete check (phase 2) | 3311 | 1336 (40.4%) | 349 (10.5%) | 4 (0.1%) | 1823 (55.1%) | 297 (9.0%) | 0 (0.0%) | 2219 (67.0%) | 447 (13.5%) | 4 (0.1%) | 1092 |
| the query (phase 0) | 35620 | 26378 (74.1%) | 8773 (24.6%) | 330 (0.9%) | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) | 26378 (74.1%) | 8773 (24.6%) | 330 (0.9%) | 9242 |
| learnt | 657 | 281 (42.8%) | 457 (69.6%) | 183 (27.9%) | 41 (6.2%) | 164 (25.0%) | 73 (11.1%) | 289 (44.0%) | 583 (88.7%) | 256 (39.0%) | 368 |
| other (theory, explanations) | 15 | 0 (0.0%) | 0 (0.0%) | 7 (46.7%) | 0 (0.0%) | 0 (0.0%) | 8 (53.3%) | 0 (0.0%) | 0 (0.0%) | 15 (100.0%) | 15 |

| variables, by the phase that made them | built | query: visited | query: reason | query: proof | check: visited | check: reason | check: proof [p] | any phase: visited | any: reason | any: proof | never visited |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| build_context (phase 1) | 22489 | 10162 (45.2%) | 8735 (38.8%) | 1015 (4.5%) | 12039 (53.5%) | 8744 (38.9%) | 596 (2.7%) | 16352 (72.7%) | 12633 (56.2%) | 1467 (6.5%) | 6137 |
| its complete check (phase 2) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| the query (phase 0) | 18725 | 15000 (80.1%) | 12141 (64.8%) | 543 (2.9%) | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) | 15000 (80.1%) | 12141 (64.8%) | 543 (2.9%) | 3725 |

| unit clauses, by the phase that added them | built | query: visited | query: reason | query: proof | check: visited | check: reason | check: proof [p] | any phase: visited | any: reason | any: proof | never visited |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| build_context (phase 1) | 169 | 0 (0.0%) | n/m | 2 (1.2%) | 122 (72.2%) | n/m | 0 (0.0%) | 169 (100.0%) | n/m | 2 (1.2%) | 0 |
| its complete check (phase 2) | 1397 | 0 (0.0%) | n/m | 12 (0.9%) | 1397 (100.0%) | n/m | 41 (2.9%) | 1397 (100.0%) | n/m | 51 (3.7%) | 0 |
| the query (phase 0) | 1435 | 1435 (100.0%) | n/m | 85 (5.9%) | 0 (0.0%) | n/m | 0 (0.0%) | 1435 (100.0%) | n/m | 85 (5.9%) | 0 |

| rule blocks (marks are not split by the phase that built them) | built | query: visited | query: reason | query: proof | check: visited | check: reason | check: proof [p] | any phase: visited | any: reason | any: proof | never visited |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| all (built in phase 0/1/2: 1180/1238/0) | 2418 | 2068 (85.5%) | 1868 (77.3%) | 131 (5.4%) | 1234 (51.0%) | 556 (23.0%) | 49 (2.0%) | 2417 (100.0%) | 2069 (85.6%) | 168 (6.9%) | 1 |

| relation rows, by kind (read = any clause, variable, unit or atom it emitted is marked) | made | emitted | query: visited | query: reason | query: proof | check: visited | check: reason | check: proof [p] | any phase: visited | any: reason | any: proof | never visited |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| user eq atom | 38 | 35 | 31 (88.6%) | 22 (62.9%) | 3 (8.6%) | 10 (28.6%) | 10 (28.6%) | 0 (0.0%) | 35 (100.0%) | 26 (74.3%) | 3 (8.6%) | 0 |
| queued atom interpreted | 1501 | 1507 | 1310 (86.9%) | 1255 (83.3%) | 228 (15.1%) | 957 (63.5%) | 921 (61.1%) | 212 (14.1%) | 1507 (100.0%) | 1479 (98.1%) | 388 (25.7%) | 0 |
| top entry | 396 | 87 | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) | 87 (100.0%) | 0 (0.0%) | 0 (0.0%) | 87 (100.0%) | 0 (0.0%) | 0 (0.0%) | 0 |
| pending link | 375 | 375 | 330 (88.0%) | 328 (87.5%) | 65 (17.3%) | 227 (60.5%) | 227 (60.5%) | 56 (14.9%) | 375 (100.0%) | 375 (100.0%) | 119 (31.7%) | 0 |
| all kinds | 2310 | 2004 | 1671 (83.4%) | 1605 (80.1%) | 296 (14.8%) | 1281 (63.9%) | 1158 (57.8%) | 268 (13.4%) | 2004 (100.0%) | 1880 (93.8%) | 510 (25.4%) | 0 |

The query itself added 35620 clauses, 18725 variables, 1435 units and 1180 rule blocks; it visited 26378 (74.1%) of its own clauses, reason 8773 (24.6%), proof 330 (0.9%). Learnt clauses: 657.

Totals, dev: build_context added 12838 clauses (+3311 in its check), 22489 variables, 169 units, 1238 rule blocks; 2310 relation rows made, 2004 emitted. The query visited 7219 (56.2%) of build_context's clauses, used 3852 (30.0%) as a reason and 633 (4.9%) in a proof; the complete check visited 10607 (82.6%), reason 5819 (45.3%), proof 205 (1.6%) [p].

### fuzz

Solvers 3133 (born in the query 178, in build_context 2955, in its check 0), from 20581 count lines. Entries: solve_int 8249, assume 14286, propagate 12003, entails by a live trail 68, by a trail that is not live 0, root conflicts 0. Context solvers that never reached solve_int: 94.

| clauses, by where they were added | built | query: visited | query: reason | query: proof | check: visited | check: reason | check: proof [p] | any phase: visited | any: reason | any: proof | never visited |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| build_context (phase 1) | 229988 | 163315 (71.0%) | 76400 (33.2%) | 5946 (2.6%) | 202490 (88.0%) | 87226 (37.9%) | 6819 (3.0%) | 211369 (91.9%) | 110520 (48.1%) | 12323 (5.4%) | 18619 |
| its complete check (phase 2) | 34905 | 23171 (66.4%) | 7886 (22.6%) | 261 (0.7%) | 24539 (70.3%) | 6560 (18.8%) | 149 (0.4%) | 27826 (79.7%) | 9793 (28.1%) | 400 (1.1%) | 7079 |
| the query (phase 0) | 409391 | 345735 (84.5%) | 130776 (31.9%) | 4379 (1.1%) | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) | 345735 (84.5%) | 130776 (31.9%) | 4379 (1.1%) | 63656 |
| learnt | 37724 | 25283 (67.0%) | 29617 (78.5%) | 4760 (12.6%) | 1761 (4.7%) | 10159 (26.9%) | 2442 (6.5%) | 25484 (67.6%) | 35101 (93.0%) | 7156 (19.0%) | 12240 |
| other (theory, explanations) | 640 | 0 (0.0%) | 0 (0.0%) | 357 (55.8%) | 0 (0.0%) | 0 (0.0%) | 278 (43.4%) | 0 (0.0%) | 0 (0.0%) | 635 (99.2%) | 640 |

| variables, by the phase that made them | built | query: visited | query: reason | query: proof | check: visited | check: reason | check: proof [p] | any phase: visited | any: reason | any: proof | never visited |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| build_context (phase 1) | 183402 | 132079 (72.0%) | 118787 (64.8%) | 14665 (8.0%) | 146633 (80.0%) | 122983 (67.1%) | 16970 (9.3%) | 163824 (89.3%) | 143637 (78.3%) | 28116 (15.3%) | 19578 |
| its complete check (phase 2) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| the query (phase 0) | 181955 | 166494 (91.5%) | 146682 (80.6%) | 11610 (6.4%) | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) | 166494 (91.5%) | 146682 (80.6%) | 11610 (6.4%) | 15461 |

| unit clauses, by the phase that added them | built | query: visited | query: reason | query: proof | check: visited | check: reason | check: proof [p] | any phase: visited | any: reason | any: proof | never visited |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| build_context (phase 1) | 389 | 0 (0.0%) | n/m | 0 (0.0%) | 335 (86.1%) | n/m | 0 (0.0%) | 389 (100.0%) | n/m | 0 (0.0%) | 0 |
| its complete check (phase 2) | 8276 | 0 (0.0%) | n/m | 273 (3.3%) | 8276 (100.0%) | n/m | 974 (11.8%) | 8276 (100.0%) | n/m | 1201 (14.5%) | 0 |
| the query (phase 0) | 2444 | 2444 (100.0%) | n/m | 0 (0.0%) | 0 (0.0%) | n/m | 0 (0.0%) | 2444 (100.0%) | n/m | 0 (0.0%) | 0 |

| rule blocks (marks are not split by the phase that built them) | built | query: visited | query: reason | query: proof | check: visited | check: reason | check: proof [p] | any phase: visited | any: reason | any: proof | never visited |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| all (built in phase 0/1/2: 9047/7446/0) | 16493 | 15184 (92.1%) | 14866 (90.1%) | 1429 (8.7%) | 7324 (44.4%) | 6991 (42.4%) | 1238 (7.5%) | 16376 (99.3%) | 15971 (96.8%) | 2449 (14.8%) | 117 |

| relation rows, by kind (read = any clause, variable, unit or atom it emitted is marked) | made | emitted | query: visited | query: reason | query: proof | check: visited | check: reason | check: proof [p] | any phase: visited | any: reason | any: proof | never visited |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| user eq atom | 888 | 888 | 846 (95.3%) | 788 (88.7%) | 309 (34.8%) | 204 (23.0%) | 178 (20.0%) | 29 (3.3%) | 888 (100.0%) | 804 (90.5%) | 330 (37.2%) | 0 |
| queued atom interpreted | 36397 | 36398 | 33177 (91.2%) | 30754 (84.5%) | 8184 (22.5%) | 20532 (56.4%) | 18380 (50.5%) | 5035 (13.8%) | 36139 (99.3%) | 33701 (92.6%) | 11948 (32.8%) | 259 |
| top entry | 5236 | 322 | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) | 322 (100.0%) | 0 (0.0%) | 0 (0.0%) | 322 (100.0%) | 0 (0.0%) | 0 (0.0%) | 0 |
| pending link | 9405 | 9405 | 8633 (91.8%) | 8632 (91.8%) | 2036 (21.6%) | 5192 (55.2%) | 5038 (53.6%) | 1505 (16.0%) | 9405 (100.0%) | 9251 (98.4%) | 3398 (36.1%) | 0 |
| all kinds | 51926 | 47013 | 42656 (90.7%) | 40174 (85.5%) | 10529 (22.4%) | 26250 (55.8%) | 23596 (50.2%) | 6569 (14.0%) | 46754 (99.4%) | 43756 (93.1%) | 15676 (33.3%) | 259 |

The query itself added 409391 clauses, 181955 variables, 2444 units and 9047 rule blocks; it visited 345735 (84.5%) of its own clauses, reason 130776 (31.9%), proof 4379 (1.1%). Learnt clauses: 37724.

Totals, fuzz: build_context added 229988 clauses (+34905 in its check), 183402 variables, 389 units, 7446 rule blocks; 51926 relation rows made, 47013 emitted. The query visited 163315 (71.0%) of build_context's clauses, used 76400 (33.2%) as a reason and 5946 (2.6%) in a proof; the complete check visited 202490 (88.0%), reason 87226 (37.9%), proof 6819 (3.0%) [p].
