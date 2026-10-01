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
| A, T2 | A (#53 group 5), T (group 4): the prefix query raises in both engines and the session was kept, so the next query raised too | #63: a session under which a query raised is dropped, so the next query runs in a fresh session as a fresh engine does. The mechanism of A remains; that of T is gone with #53 stage 5 |
| T1, T3, T4, T5, Gp1 | T (#53 group 4: an equality query engages transfer), G' (#42: a query links the terms it mentions) | R2, component-scoped answering (#53): a set or query with a relation splits by component, so the prefix query (`Q.eq(u, y)`, `Q.positive(w)`) is answered in its own part's session and never engages transfer in, or links a term of, the observer's session. Within one component the mechanisms of T and G' remained until #53 stage 5 |
| G7 | G (relation glue, #42) | T3 (#53): a query in a reused session whose search used branch-and-bound (here the integrality links the prefix query's relation glue left) is re-answered as a fresh engine would. The mechanism (glue switched on by an earlier relation query) is gone with #53 stage 5 |
| Gp2, S1 | G' (#42), S (#53): the relation glue a reused session got from an earlier query (S1: an interface equality later asked as a user atom) | #53 stage 5: links, the relation atoms' clauses to unary atoms and transfer are switched per query by selectors, and an equality's user-atom clauses come with the first query that mentions it |

The write-back of a parent's structural facts onto its arguments (the
carrier of C) remains; C' is its instance without a non-commutative
symbol.
