| # | mutant | missed by replays | dev answers | fuzz answers | dev state | fuzz state |
|---|---|---|---|---|---|---|
| base | unmutated |  | no | no | no | no |
| 10 | batch flush: pending trail reaches theories newest first |  | no | no | caught: 196 streams, first q275; 68 end states | caught: 2969 streams, first q0; 1789 end states |
| 11 | batch: add_clauses in reverse |  | no | no | no | no |
| 12 | batch: add_internal clauses in reverse |  | no | no | caught: 509 streams, first q0; 509 end states | caught: 2884 streams, first q0; 2884 end states |
| 13 | callback order: check, last theory first |  | no | no | caught: 198 streams, first q275; 198 end states | caught: 2817 streams, first q0; 2817 end states |
| 14 | callback order: push_level, last theory first |  | no | no | caught: 198 streams, first q275 | caught: 3001 streams, first q0 |
| 15 | callback order: pop_level, last theory first |  | no | no | caught: 196 streams, first q275 | caught: 2998 streams, first q0 |
| 16 | callback order: propagate, last theory first |  | no | no | caught: 198 streams, first q275; 4 end states | caught: 3011 streams, first q0; 61 end states |
| 17 | callback order: decide, last theory first |  | no | no | no | no |
| 18 | callback order: a shared variable's theories, last first |  | no | no | no | no |
| 19 | dropped: assert_lit's conflict |  | caught: 6 answers, first q466 | caught: 185 answers, first q9 | caught: 6 answers, first q466; 79 streams, first q278; 79 end states | caught: 185 answers, first q9; 26 session counts; 2425 streams, first q0; 2425 end states |
| 20 | dropped: check's conflict |  | no | caught: 3 answers, first q1544 | caught: 27 streams, first q278; 27 end states | caught: 3 answers, first q1544; 506 streams, first q6; 506 end states |
| 21 | dropped: check's model |  | no | no | caught: 198 streams, first q275; 198 end states | caught: 2817 streams, first q0; 2817 end states |
| 22 | dropped: propagate's first pair |  | no | no | caught: 95 streams, first q277; 95 end states | caught: 2696 streams, first q0; 2696 end states |
| 23 | dropped: decide's answer |  | no | no | caught: 1 streams, first q1791; 1 end states | caught: 31 streams, first q103; 31 end states |
| 24 | dropped: register_atom never reaches the theory |  | caught: 30 answers, first q348 | caught: 481 answers, first q2 | caught: 30 answers, first q348; 198 streams, first q275; 198 end states | caught: 481 answers, first q2; 36 session counts; 3018 streams, first q0; 2978 end states |
| 25 | dropped: pop_level never reaches the theory |  | caught: 142 answers, first q275 | caught: 2510 answers, first q0 | caught: 142 answers, first q275; 70 session counts; 196 streams, first q275; 158 end states | caught: 2510 answers, first q0; 1545 session counts; 3011 streams, first q0; 2792 end states |
| 26 | dropped: assert_lit's exception |  | no | no | no | no |
| 27 | conflict_of: any falsy first item, not `is False` |  | no | no | no | no |
| 28 | hook_lits: a theory's clause reversed |  | no | no | caught: 49 streams, first q348; 47 end states | caught: 1603 streams, first q0; 1599 end states |
| 29 | stale handle: check goes to the process's latest theory at that place |  | no | no | no | no |
| 30 | stale handle: a variable keeps the process's first payload |  | caught: 193 answers, first q355 | caught: 2588 answers, first q4 | caught: 193 answers, first q355; 25 session counts; 187 streams, first q355; 186 end states | caught: 2588 answers, first q4; 99 session counts; 3045 streams, first q2; 3025 end states |
| 31 | lifetime: __traverse__ misses the theory, so a cycle never frees |  | no | no | no | no |
| 32 | theory_models: reversed |  | no | no | no | no |
| 33 | run: a solver fault raises ValueError, not RuntimeError |  | no | no | no | no |
| 34 | model: an unassigned variable reads False |  | no | no | no | no |
