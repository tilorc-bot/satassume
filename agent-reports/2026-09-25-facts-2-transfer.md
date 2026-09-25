# Agent report: fact-lattice stage 2, predicate transfer across equal terms

- **Date:** 2026-09-25
- **Status:** implemented on branch `facts-stage2` (base `facts-theory`,
  `db8e7d8`); gates and fuzz below. Not reviewed. Timing is informational
  (local, loaded machine) and is left to the landing side.
- **Scope:** new `satassume/transfer.py` (`TransferTheory`);
  `satassume/euf.py` (merge hook `on_merge`, `members`);
  `satassume/euf_adapter.py` (`node_term`, `attach`);
  `satassume/relations.py` (engagement and session glue; the
  `uninterpreted="free"` behaviour); `satassume/engine.py` (options
  `transfer=True`, `uninterpreted="none"`, one hook in `query_literal`);
  tests `tests/test_transfer.py`, `tests/test_transfer_fuzz.py` (new),
  `tests/test_relations.py`, `tests/test_euf_adapter.py`,
  `tests/test_euf_fuzz.py` (substitution now answered); scripts
  `agent-reports/scripts/facts2_stream.py`, `facts2_gate2.py`.
- **Read this if:** you review or land stage 2, or decide on
  `uninterpreted="free"`

## Change

**What it does.** Whenever the session's EUF theory has two terms in one
congruence class (user `eq` atoms, transitivity, congruence `f(x) = f(y)`
from `x = y`, numbers: `x = 2` puts `x` in the class of the value `2`),
every one of the 33 predicates holds for one iff it holds for the other.
`Q.ne`/`distinct` follows: `eq(x, y)` with `prime(x) & noninteger(y)`
is refuted.

**Design: a propagating theory on the current representation.** The rule
block and the 33 variables per node stay as they are (stage 1's
FactTheory is not used). `TransferTheory` (`satassume/transfer.py`) is a
DPLL(T) theory whose atoms are the node-block predicate variables,
payload `(EUF term of the node, predicate index)`:

- `assert_lit` records the value and queues the term if its class has
  another member; the EUF merge hook (`EUFTheory.on_merge(retired,
  new_rep)`, called at the end of `_union`) queues the merged class;
  registering a variable queues its term.
- `propagate` scans each queued class once: per predicate the first
  assigned variable is the witness, every other variable of that
  predicate in the class gets its value with the reason
  `[P(b), ~P(a)] + [~l for l in euf.explain(a, b)]`. A variable already
  assigned the other way turns that clause into a conflict (the solver's
  `_theory_imply` handles it).
- `check` rescans every class (completeness backstop at total
  assignments). `pop_level` forgets values asserted above the level. No
  derived state is kept, so EUF's undo needs no hook: everything is
  recomputed from the current classes.

**Engagement (explicit, `Relations._engage_transfer`).** Once per session,
at the first equality atom that is not glue: a user `eq`/`ne` atom of the
assumptions or the query, or one an extension made. The links'
`eq(e, 0)` and the interface equalities of equality sharing do not
engage it, so sessions with only orderings (and every session without
relations) never attach the theory: the no-equality path pays one
attribute test in `query_literal` and nothing else. On engagement the EUF
adapter's theory is attached if it was not, the `TransferTheory` is
attached, and from then on

- every node block of the session (a scan of `VarTable.slots` from a
  cursor, `Relations.sync_transfer`, run at the end of
  `Relations.process` and at the start of `query_literal`) is registered:
  its expression is interned with `EUFAdapter.node_term` (same term ids
  as `term`, kept out of `shared_terms`, so equality sharing with LRA is
  exactly as before) and its 33 variables are registered as atoms.
  Nodes containing `nan` are skipped (EUF treats `nan` as not reflexive);
- every expression EUF interned for an atom (numbers included) is visited
  as a node (`Relations._transfer_terms`), so `x = 2` finds the facts of
  `2`.

Equalities LRA derives from inequalities are not handed to EUF (as
asked). `Engine(transfer=False)` turns the whole layer off.

**Uninterpreted relations.** `Engine(uninterpreted="free")` makes
`Relations.process` skip the final `Uninterpreted` check: an atom no
theory interprets stays a free Boolean. Default `"none"` (unchanged
behaviour).

## Measurement

Local machine, SymPy pin `ddbb536d7e`, stream `~/.cache/satassume/stream.pkl`
(13,877 queries), gate2 frozen file (2,863 queries).

### Stream (`facts2_stream.py`, one engine, in order; SymPy `ask` 10 s alarm)

| engine | same | more definite | new ValueError | lost ValueError | less definite | contradiction |
|---|---:|---:|---:|---:|---:|---:|
| `Engine()` (transfer on, default) | 13,862 | **15** | 0 | 0 | 0 | 0 |
| `Engine(uninterpreted="free")` (transfer on) | 13,328 | 513 | 36 | 0 | 0 | 0 |

The 15 are the 15 of stage 0's `transfer` oracle (15 distinct queries).
SymPy's `ask` agrees on 6, says None on 8, raises ValueError on 1:

| # | query | assumptions | now | SymPy | by hand |
|---:|---|---|---|---|---|
| 4395 | `zero(x)` | `eq(x, pi/2)` | False | None | correct |
| 4396 | `extended_real(x)` | `eq(x, pi/2)` | True | None | correct |
| 4398 | `real(x)` | `eq(x, pi/2)` | True | None | correct |
| 4400 | `extended_real(x)` | `eq(x, 2)` | True | None | correct |
| 4401 | `zero(sin(x))` | `eq(x, 2)` | False | None | correct (sin 2 != 0) |
| 4402 | `real(x)` | `eq(x, 2)` | True | None | correct |
| 12043 | `eq(n, 1)` | `~integer(n)` | False | False | |
| 12102 | `eq(n - 1, 1)` | `~integer(n)` | False | False | |
| 12154 | `eq(n, k)` | `integer(n) & nonnegative(n) & k > n` | False | None | correct (k > n) |
| 12157 | `eq(k, n - 1)` | same | False | None | correct (k > n > n - 1) |
| 12176 | `eq(k, 1)` | `integer(n) & negative(n) & ~integer(k)` | False | False | |
| 12178 | `eq(n, k)` | same | False | ValueError | correct; the assumptions are consistent (n = -1, k = 1/2), SymPy's error is its own |
| 12274 | `eq(k, 1)` | `integer(x) & negative(x) & ~integer(k)` | False | False | |
| 12300 | `eq(x, 1)` | `~integer(x)` | False | False | |
| 12547 | `eq(k, 1)` | `integer(n) & nonnegative(n) & k > n & ~integer(k)` | False | False | |

With `uninterpreted="free"`: 513 more definite (458 distinct changed
queries with the errors): SymPy agrees on 394, None on 25, timeout on 2,
ValueError on 1 (12178 above). The 25 SymPy-None ones checked by hand,
all correct: 11 are `integer(±im(x)/pi)` or `integer(im(x)/(2*pi))` for a
real `x` (True: `im(x) = 0`), `imaginary(x - 2*pi*floor(...))` for real
`x` (False), `zero(x)` under `x > 0 & x < pi` and similar (False),
`negative(x)` under `x >= 0 & ...` (False), `extended_real(Abs(x)/pi +
1/2)` (True), and the 6 transfer rows 4395 to 4402 above. The 2
timeouts are 12154 and 12157. **The 36 new ValueErrors** come from 3
assumption sets, each plainly inconsistent without any equality:
`negative(x) & positive(x) & t > -pi/2 & t < pi/2 & ...` (15 + 15) and
`positive(x) & zero(x) & ...` (6); SymPy raises on 24 and answers the
unrelated proposition on 12 (as stage 0 found). Nothing lost.

### New ValueErrors (transfer, default engine)

None on the stream, none on gate2, and none lost. New ones arise where
the assumptions are inconsistent only under equality; the unit tests
(`test_inconsistent_under_equality`) pin two new ones and one that the
base already raised through LRA:

| assumptions (query `real(x)`) | base engine | SymPy `ask` | now |
|---|---|---|---|
| `eq(x, y) & prime(x) & noninteger(y)` | True | True | ValueError |
| `eq(x, 2) & odd(x)` | True | True | ValueError |
| `eq(x, y) & positive(x) & negative(y)` | ValueError already (LRA) | True | ValueError (unchanged) |

SymPy does not check these assumption sets for consistency under
equality (it has no substitution), so it answers the query; they are
genuinely inconsistent.

### gate2 (`tools/gate2.py --allow-more-definite`)

2,863 records, changed 0, **1 more definite** (out of scope group
`relation`): `prime(x) | prime(y) & eq(x, y)` with real `x, y`, frozen
None, now True, SymPy None (it is SymPy's `test_equality_failing`,
XFAIL there); correct by hand. With `uninterpreted="free"`
(`facts2_gate2.py --free`): the same single change.

### `tools/ab.py REF CAND --rounds 1 --allow-more-definite`

REF = `facts-theory` (`db8e7d8`), CAND = this branch: answers match,
cand 15 more definite (the table above), none dropped or flipped.
Informational time on the loaded local machine: ref 5.56 s, cand 5.67 s
(+2%, one round, noise level here).

### Plan section 3 table, rows of layer 2.2 (`tests/test_transfer.py`)

| query | before | now |
|---|---|---|
| `positive(y)` given `eq(x, y) & positive(x)` | None | True |
| `positive(f(y))` given `eq(x, y) & positive(f(x))` | None | True |
| `prime(x)` given `eq(x, 2)` | None | True |
| `eq(x, y)` / `ne(x, y)` given `prime(x) & noninteger(y)` | None | False / True |
| `integer(y)` given `eq(x, y) & even(x)` | None | True |
| last row (uninterpreted relation) | None | unchanged by default; with `"free"` the rest answers |

(`ask(Q.eq(x, y), Q.positive(x) & Q.negative(y))` was already False
through LRA on the base; it stays False.)

## Gates

| gate | result |
|---|---|
| transfer fuzz, `euf` setup (`tests/test_transfer_fuzz.py`, exact comparison with the explicit-clause oracle), seeds 0 to 4,199 | pass: 23,175 answers identical (8,327 definite), 1 inconsistent-assumptions difference (seed 750, see Risks) |
| transfer fuzz, `lra` setup (LRA + EUF, soundness), seeds 0 to 3,999 | pass: 22,089 answers identical (7,919 definite), 0 where the oracle is more definite |
| mutation check: the same fuzz with transfer off on the engine side | fails on 29 of seeds 0 to 99 (the fuzz sees transfer) |
| theory protocol (`tests/theory_harness.Recorder` + `check_protocol` around every `TransferTheory` of 40 fuzz seeds, `test_transfer.py::test_protocol_on_fuzz`) | pass |
| `tests/test_solver_incremental.py`, modes plain / block / theory, 4,000 seeds each | pass (solver unchanged; run as required) |
| `tests/test_solver_real_theories.py`, `REAL_THEORY_SEEDS=4000` | pass (4 modes) |
| `tests/test_euf_fuzz.py` + `test_euf.py`, `EUF_FUZZ_EXAMPLES=1000` | pass (72, 2 xfail as baseline) |
| suite (split in two runs) | baseline: 2 known failures in `test_shared_facts`, everything else passes (1,728 passed + `test_transfer_fuzz.py` 12) |
| `tools/ab.py` (`facts-theory` vs branch, `--rounds 1 --allow-more-definite`) | answers match, 15 more definite |
| `tools/gate2.py --allow-more-definite` | changed 0, 1 more definite |

Tests changed: `test_relations.py::test_equality_failing` was an xfail
(SymPy's `test_equality_failing`) and now passes; its third assertion
used symbols declared real, for which `imaginary(y)` is inconsistent by
itself (the base engine says so too), so that line now expects
inconsistent and a plain-symbol twin expects True.
`test_euf_adapter.py::test_engine_equality_failing_is_not_wrong` now
requires True; the reference-flaw note `30327-substitution-scope` says
the engine answers these.

Stream engagement (informational): 135 of 1,657 sessions of one pass
attach the transfer theory; they register 28,479 predicate variables
and it propagates 2,495 literals.

## Risks and known gaps

- **Propagation-decided queries under inconsistent assumptions.** The
  engine checks the assumptions only by propagation (`implied`) when
  propagation decides the query, and searches otherwise. Transfer moves
  some queries from search to propagation, so under assumptions whose
  inconsistency only search finds, a query that used to raise
  ValueError can now get a definite (vacuous) answer. The fuzz found one
  such case (`x = 1 & f(x) = 1 & f(y) = 1/2 & (x = 2 | y = f(x))`,
  `imaginary(f(x))`: False, the oracle raises). None on either gate (0
  lost ValueErrors). The same holds in the other direction (transfer
  finds an inconsistency by propagation where the oracle's propagation
  answers). This is the engine's existing contract, not new to transfer.
- Transfer follows EUF classes only: equalities LRA derives
  (`x <= y & y <= x`) are not transferred (as asked), and EUF has no
  arithmetic or AC (`x*(y + 1)` and `x*y + x` are unrelated).
- Every node block of an engaged session is registered (33 theory atoms
  per node), and every EUF atom term is visited as a node with its full
  templates: the cost of equality sessions grows with the session. Only
  sessions with a non-glue equality atom pay.
- The facts cache receives root-level transfers; they rest on root-level
  (context-free) equalities only, since assumptions are selector-guarded.
  The reused-engine fuzz checks that nothing contextual leaks.
- `uninterpreted="free"` changes 36 stream answers from None to
  ValueError (all genuinely inconsistent); off by default until decided.
