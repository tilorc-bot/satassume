# Fixed repros

History-dependent answers that no longer differ on `main`: the long-lived
engine and a fresh one now answer the final query the same.  Kept as
regression tests (`test_fixed_repro_stays_fixed` in `tests/test_history.py`
fails if they differ again); run from the repository root,
`python -m harness repro harness/repros/fixed/NAME.json` prints
`still_differs`.

| repro | family | fixed by |
|---|---|---|
| G1-G6 | G (relation glue, #42) | #51: sign facts on two sums reach LRA, so a fresh session proves the observers too |
| C, C2, C3, C4, C4b, C5 | C (#47: a non-commutative factor made a product never zero) | #54: sound Mul/Pow templates for non-commutative factors |
| R1-R4 | R (#53 group 6: the fact caches and the sessions survived registration changes) | #63: every engine cache and session is keyed on the registry epoch, which every registration and unregistration bumps |
| A, T2 | A (#53 group 5), T (group 4): the prefix query raises in both engines and the session was kept, so the next query raised too | #63: a session under which a query raised is dropped, so the next query runs in a fresh session as a fresh engine does. The mechanisms of A and T remain (T1, T3, T4 stay pinned) |

The mechanism of G (the glue is switched on by the first relation query
of a session) remains; see `../README.md`, G7.  The write-back of a
parent's structural facts onto its arguments (the carrier of C) remains
too; C' is its instance without a non-commutative symbol.
