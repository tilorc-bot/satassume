| # | mutant | nested | suite |
|---|---|---|---|
| base | unmutated | no | ... |
| 10 | batch flush: pending trail reaches theories newest first | caught: in-check, seed 1 | ... |
| 11 | batch: add_clauses in reverse | no | ... |
| 12 | batch: add_internal clauses in reverse | no | ... |
| 13 | callback order: check, last theory first | caught: in-check, seed 1 | ... |
| 14 | callback order: push_level, last theory first | caught: in-check, seed 1 | ... |
| 15 | callback order: pop_level, last theory first | caught: in-check, seed 1 | ... |
| 16 | callback order: propagate, last theory first | caught: in-check, seed 1 | ... |
| 17 | callback order: decide, last theory first | caught: in-check, seed 1 | ... |
| 18 | callback order: a shared variable's theories, last first | caught: in-check, seed 1 | ... |
| 19 | dropped: assert_lit's conflict | caught: in-check, seed 1 | ... |
| 20 | dropped: check's conflict | caught: in-check, seed 1 | ... |
| 21 | dropped: check's model | caught: in-check, seed 1 | ... |
| 22 | dropped: propagate's first pair | caught: in-assert, seed 2 | ... |
| 23 | dropped: decide's answer | no | ... |
| 24 | dropped: register_atom never reaches the theory | caught: in-check, seed 1 | ... |
| 25 | dropped: pop_level never reaches the theory | caught: in-check, seed 1 | ... |
| 26 | dropped: assert_lit's exception | no | ... |
| 27 | conflict_of: any falsy first item, not `is False` | caught: odd, seed 5 | ... |
| 28 | hook_lits: a theory's clause reversed | caught: in-assert, seed 2 | ... |
| 29 | stale handle: check goes to the process's latest theory at that place | caught: in-check, seed 1 | ... |
| 30 | stale handle: a variable keeps the process's first payload | caught: in-check, seed 1 | ... |
| 31 | lifetime: __traverse__ misses the theory, so a cycle never frees | caught: in-check, seed 1 | ... |
| 32 | theory_models: reversed | caught: in-check, seed 1 | ... |
| 33 | run: a solver fault raises ValueError, not RuntimeError | no | ... |
| 34 | model: an unassigned variable reads False | no | ... |
