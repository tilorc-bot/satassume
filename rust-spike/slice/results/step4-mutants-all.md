### Boundary mutants, step 4

c: caught. API columns are the fuzzer: digest and state on step 1's corpus, then answers and state on fuzz sessions. Live columns are the real engine.

| # | mutant | API digest | API state | API fuzz answers | API fuzz state | nested | live dev answers | live fuzz answers | live dev state | live fuzz state | columns catching |
|---|---|---|---|---|---|---|---|---|---|---|---:|
| 10 | batch flush: pending trail reaches theories newest first | no | no | c | c | c | no | no | c | c | 5 |
| 11 | batch: add_clauses in reverse | c | c | c | c | no | no | no | no | no | 4 |
| 12 | batch: add_internal clauses in reverse | no | c | c | c | no | no | no | c | c | 5 |
| 13 | callback order: check, last theory first | no | no | c | c | c | no | no | c | c | 5 |
| 14 | callback order: push_level, last theory first | no | no | c | c | c | no | no | c | c | 5 |
| 15 | callback order: pop_level, last theory first | no | no | no | c | c | no | no | c | c | 4 |
| 16 | callback order: propagate, last theory first | no | no | c | c | c | no | no | c | c | 5 |
| 17 | callback order: decide, last theory first | no | no | no | c | c | no | no | no | no | 2 |
| 18 | callback order: a shared variable's theories, last first | no | no | c | c | c | no | no | no | no | 3 |
| 19 | dropped: assert_lit's conflict | no | no | c | c | c | c | c | c | c | 7 |
| 20 | dropped: check's conflict | no | no | c | c | c | no | c | c | c | 6 |
| 21 | dropped: check's model | no | no | c | c | c | no | no | c | c | 5 |
| 22 | dropped: propagate's first pair | no | no | c | c | c | no | no | c | c | 5 |
| 23 | dropped: decide's answer | no | no | c | c | no | no | no | c | c | 4 |
| 24 | dropped: register_atom never reaches the theory | no | no | c | c | c | c | c | c | c | 7 |
| 25 | dropped: pop_level never reaches the theory | no | no | c | c | c | c | c | c | c | 7 |
| 26 | dropped: assert_lit's exception | no | no | c | c | no | no | no | no | no | 2 |
| 27 | conflict_of: any falsy first item, not `is False` | no | no | no | no | c | no | no | no | no | 1 |
| 28 | hook_lits: a theory's clause reversed | no | no | c | c | c | no | no | c | c | 5 |
| 29 | stale handle: check goes to the process's latest theory at that place | no | no | no | no | c | no | no | no | no | 1 |
| 30 | stale handle: a variable keeps the process's first payload | no | no | no | no | c | c | c | c | c | 5 |
| 31 | lifetime: __traverse__ misses the theory, so a cycle never frees | no | no | no | no | c | no | no | no | no | 1 |
| 32 | theory_models: reversed | no | no | c | c | c | no | no | no | no | 3 |
| 33 | run: a solver fault raises ValueError, not RuntimeError | no | no | c | c | no | no | no | no | no | 2 |
| 34 | model: an unassigned variable reads False | no | no | c | c | no | no | no | no | no | 2 |

Not caught by any column: none. Not caught by a live column: 11, 17, 18, 26, 27, 29, 31, 32, 33, 34 (10 of 25).

### The 10 solver mutants, step 3's sweep on the same crate

| # | mutant | dev digest | fuzz digest | dev state | fuzz state | API answers | API state |
|---|---|---|---|---|---|---|---|
| 0 | level sort: ties flip | no | no | 49 streams, first q348 | 1,603 streams, first q0 | caught | caught |
| 1 | explain: last best wins | no | no | 6 streams, first q364 | 300 streams, first q9 | caught | caught |
| 2 | `_mention` order | no | no | no | no | no | caught |
| 3 | no var_inc decay | no | no | 133 streams, first q278 | 2,573 streams, first q0 | caught | caught |
| 4 | watch: blocker-style keep | no | no | 321 streams, first q0 | 2,739 streams, first q0 | caught | caught |
| 5 | ring: None as false | no | no | no | no | caught, `fixed 5` only | caught, `fixed 5` only |
| 6 | `_fill` growth | no | no | no | no | caught | caught |
| 7 | `_learn` bump order | no | no | no | no | no | caught, hand-set `_cla_inc` |
| 8 | decisions not counted on -1 | no | no | 876 streams, first q0 | 2,913 streams, first q0 | caught | caught |
| 9 | theory unit reason as learnt | no | no | no | no | no | caught |
