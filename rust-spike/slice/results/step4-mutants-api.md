| # | mutant | missed by replays | digest | state | fuzz answers | fuzz state |
|---|---|---|---|---|---|---|
| base | unmutated |  | no | no | no | no |
| 10 | batch flush: pending trail reaches theories newest first |  | no | no | caught: result, session 2, 8 calls | caught: theory calls, session fixed 3, 5 calls |
| 11 | batch: add_clauses in reverse |  | caught: result, session 59, 3 calls | caught: state clauses, session 17, 1 calls | caught: result, session 27, 2 calls | caught: state clauses, session 6, 1 calls |
| 12 | batch: add_internal clauses in reverse |  | no | caught: state clauses, session 18, 2 calls | caught: result, session 81, 1 calls | caught: state clauses, session 5, 2 calls |
| 13 | callback order: check, last theory first |  | no | no | caught: result, session 214, 9 calls | caught: theory calls, session 13, 5 calls |
| 14 | callback order: push_level, last theory first |  | no | no | caught: result, session 144, 5 calls | caught: theory calls, session 5, 3 calls |
| 15 | callback order: pop_level, last theory first |  | no | no | no | caught: theory calls, session 5, 3 calls |
| 16 | callback order: propagate, last theory first |  | no | no | caught: result, session 424, 11 calls | caught: theory calls, session 8, 3 calls |
| 17 | callback order: decide, last theory first |  | no | no | no | caught: theory calls, session 214, 6 calls |
| 18 | callback order: a shared variable's theories, last first |  | no | no | caught: result, session 8, 12 calls | caught: theory calls, session 8, 5 calls |
| 19 | dropped: assert_lit's conflict |  | no | no | caught: result, session fixed 3, 34 calls | caught: theory calls, session fixed 3, 33 calls |
| 20 | dropped: check's conflict |  | no | no | caught: result, session 14, 5 calls | caught: result, session 14, 5 calls |
| 21 | dropped: check's model |  | no | no | caught: result, session 52, 3 calls | caught: state tmodels, session fixed 5, 2 calls |
| 22 | dropped: propagate's first pair |  | no | no | caught: result, session fixed 3, 3 calls | caught: theory calls, session fixed 3, 4 calls |
| 23 | dropped: decide's answer |  | no | no | caught: result, session 48, 2 calls | caught: theory calls, session 48, 7 calls |
| 24 | dropped: register_atom never reaches the theory |  | no | no | caught: result, session 456, 2 calls | caught: theory calls, session fixed 3, 2 calls |
| 25 | dropped: pop_level never reaches the theory |  | no | no | caught: result, session fixed 3, 34 calls | caught: theory calls, session fixed 3, 4 calls |
| 26 | dropped: assert_lit's exception |  | no | no | caught: result, session 103, 10 calls | caught: result, session 103, 10 calls |
| 27 | conflict_of: any falsy first item, not `is False` |  | no | no | no | no |
| 28 | hook_lits: a theory's clause reversed |  | no | no | caught: result, session 240, 13 calls | caught: state learnts, session 22, 60 calls |
| 29 | stale handle: check goes to the process's latest theory at that place |  | no | no | no | no |
| 30 | stale handle: a variable keeps the process's first payload |  | no | no | no | no |
| 31 | lifetime: __traverse__ misses the theory, so a cycle never frees |  | no | no | no | no |
| 32 | theory_models: reversed |  | no | no | caught: result, session 732, 8 calls | caught: result, session 732, 8 calls |
| 33 | run: a solver fault raises ValueError, not RuntimeError |  | no | no | caught: result, session 33, 7 calls | caught: result, session 33, 7 calls |
| 34 | model: an unassigned variable reads False |  | no | no | caught: result, session fixed 5, 9 calls | caught: result, session fixed 5, 9 calls |
