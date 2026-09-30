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

The mechanism of G (the glue is switched on by the first relation query
of a session) remains; see `../README.md`, G7.  The write-back of a
parent's structural facts onto its arguments (the carrier of C) remains
too; C' is its instance without a non-commutative symbol.
