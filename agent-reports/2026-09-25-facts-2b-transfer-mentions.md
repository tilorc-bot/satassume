# Agent report: facts stage 2b, transfer atoms without mentions (lazy transfer atoms)

- **Date:** 2026-09-25
- **Status:** built, gates passed (see Gates); **-4.7% against `main`
  (`66871eb`) and -2.8% against `land-o4` (`fcb8605`) on the Pi**
  (`--rounds 4`; `--rounds 3`: -4.5% and -2.2%), answers
  identical to `main` (the same 15 more-definite stream answers, the same
  1 on gate2, the same ValueError set). Meets the goal (land-o4 plus this at
  least 3% faster than `main`).
- **Scope:** branch `transfer-mentions` on `land-o4`:
  `satassume/solver.py` (`register_atom(..., mention=False)`, the optional
  theory hook `decide`, counter `theory_decisions`), `satassume/transfer.py`
  (`decide`, partial-node bookkeeping, docstring), `satassume/relations.py`
  (registration without mentions, partial payloads), `satassume/theory.py`
  (contract: lazy atoms), tests (`theory_harness.py`, `test_transfer.py`,
  `test_solver_incremental.py`).
- **Read this if:** you land `land-o4` and want its laziness back in
  sessions where predicate transfer is engaged, or review the change.

## Design

The stage 2 implementer suggested registering only mentioned predicate
variables with the transfer theory and registering the rest on demand. I
did not do that; the same effect is simpler and has no on-demand path:

- **Every candidate predicate variable is still a theory atom** (the
  theory is told every value it gets on the trail, as on `main`), **but the
  registration does not mention it** (`Solver.register_atom(theory, v,
  payload, mention=False)`). Such a variable stays lazy unless a clause,
  assumption, query or another theory mentions it: no block writes to it
  above root, no decisions on it.
- **No transfer is lost.** Every literal of a block that the block did not
  imply itself (decision, assumption, clause or theory propagation, root
  unit) is on the trail and so reported to the theory, which copies it to
  every atom of its predicate in the class, lazy ones included (a theory
  propagation onto a lazy variable is an asserted literal of that block).
  Each equal term's block then asserts the same literals; its exact closure
  implies whatever the first block implies and writes it where mentioned.
  At fixpoint the atoms of one predicate in a class are all assigned
  alike, or all unassigned.
- **Models.** All-unassigned atoms are completed per block by `_fill`, a
  function of the block's assigned values. Two *full* nodes (all 33
  variables are atoms) of one class have identical assigned values, so
  they are completed alike. A *partial* node (a link-only side with only
  `polar`, a Rational node with its basis) may not be. For those, the
  theory implements a new optional hook `decide()`: called by the search
  when every non-lazy variable is assigned, before `check`, it names an
  unassigned atom of a partial node that shares a predicate with another
  atom of its class; the solver decides it in the phase its block's
  closure implies (if any). Only classes noted at a merge are scanned
  (`_multi`, stale entries dropped).
- A first version decided every such atom, full nodes included: 2,372
  extra decisions per pass, -1.2% against `main`, +0.9% against `land-o4`.
  Restricted to partial nodes: 614 `decide` calls, the final numbers below.

## Measurement

Pi, `ab.py --rounds 3 --allow-more-definite`, interleaved, SymPy pin:

| ref | ref best | cand best | change |
|---|---:|---:|---:|
| `main` 66871eb | 2.904 s | 2.773 s | -4.5% |
| `land-o4` fcb8605 | 2.835 s | 2.771 s | -2.2% |

Final code (`4c23c64`, `--rounds 4`, same flags):

| ref | ref best | cand best | change |
|---|---:|---:|---:|
| `main` 66871eb | 2.897 s | 2.761 s | **-4.7%** |
| `land-o4` fcb8605 | 2.829 s | 2.749 s | **-2.8%** |

The first version (every all-unassigned atom decided): -1.2% against
`main`, +0.9% against `land-o4` (`--rounds 3`).

Per pass (local counters, stream):

| | `main` | `land-o4` | this |
|---|---:|---:|---:|
| decisions | 64,141 | 38,570 | 36,453 |
| propagations (trail literals processed) | 740,280 | 413,900 | 398,086 |
| transfer `assert_lit` | 35,563 | 34,987 | 19,388 |
| transfer `propagate` | 8,360 | 7,558 | 5,570 |
| transfer `decide` calls (decisions it asked for) | | | 614 (71) |
| registrations with the transfer theory | 8,760 | 8,760 | 8,760 |

What is left of the transfer cost (profile diff against `transfer=False`,
same code): `_scan`, `assert_lit`, `sync_transfer` and the 8,760
registrations, each a few hundredths of a second locally.

## Gates

| gate | result |
|---|---|
| `ab.py` (Pi, against `main` and `land-o4`, `--allow-more-definite`) | answers match; the same 15 more definite on both sides, ValueError set identical (the recording's) |
| `gate2.py` (local) | strict: the same 1 change as `main` (`prime(x)` from `prime(y) & eq(x, y)`); with `--allow-more-definite`: answers match |
| differential fuzz against `main` (`dfuzz.py`/`cmp2.py`, separate processes, reused engines, 22 number kinds) | EUF seeds 100000 to 119999: 119,673 answers, **0 differ**; LRA+EUF seeds 100000 to 111999: 72,001 answers, **0 differ** |
| `test_transfer_fuzz.py` (local, by hand) | euf and lra, seeds 20000 to 21999 each: all passed, 0 `oracle_more` |
| solver fuzz (Pi), 2,000 seeds per mode | plain, block, theory, mentions, mentions-theory: all ok (theory modes now register the atoms lazily in half the seeds, with `decide`) |
| `real_theory_fuzz.py` (Pi), 1,000 seeds per mode | lra, euf, both: 0 mismatches, 0 implied-misses |
| suite (Pi, `-n 4`) | 2 failed (the known `test_shared_facts` pair), 1755 passed, 1 skipped, 3 xfailed, 1 xpassed |

New tests: `test_models_respect_transfer` (every model agrees across equal
terms on every atom, 60 fuzz seeds); `test_protocol_on_fuzz` accepts lazy
atoms at `check` and requires some; the solver fuzz's theory setup
registers lazily with a `decide` in half the seeds (coverage requires
`theory_decisions`); the Recorder asserts `decide()` is None at every
`check` (disabling the solver's `decide` call fails it at once).

## Risks

- `implied` with lazy atoms reaches only what the theory sees. For the
  transfer theory nothing is lost (argument above; the stream, gate2 and
  the differential fuzz agree with `main`). A future theory registering
  lazy atoms may propagate less through `implied`; `entails`/`solve` stay
  exact with `decide`. The solver fuzz checks only soundness of `implied`
  in its lazy-atom seeds for that reason.
- The model argument relies on `_fill` being a function of the block's
  assigned values and on full nodes having every block variable an atom.
  `test_models_respect_transfer` checks every model (search and stored
  witness) for agreement of equal terms on all atoms, lazy ones
  completed; it catches a per-block non-deterministic fill (64 failing
  seeds in 150 when planted).
- A node first registered as link-only (partial `polar`) and later made a
  full candidate keeps its `polar` atom marked partial: extra `decide`
  work only, never wrong.
