# HANDOFF sa-port-168 (step 5c8, issue 323)

Branch port/5c8 on rust-slice 17442af (origin/rust-slice unmoved at 11:20 UTC). No bar has run yet. Outputs are under
~/sa-rust-ids-work/sa-port-168/ (orion).

## Done this session
- **The open zero is explained.** In this env, `sympy.ask` is SymPy's own `sympy.assumptions.ask` and never enters satassume,
  so 0 was right for that probe. satassume's `ask` (`sympy_api.ask`, which live.py and the suite use) fires every rv: counter
  (probe/shim.py).
- **Per-workload reach** (wl/, Rust, --check plain, one pass each). The answers equal 5c7's hashes: dev 31cd0945c07f02a6,
  fuzz 173502b6ef285ad6, zero d9ed3534a2093027, cert 6a09c059eb266747, budget 35bc2c4a937bebc0; loop 09238b2537e54383,
  scope 12e06b0586faee40. 0 Python solvers made.

  | counter | dev | fuzz | loop | scope | zero | cert | budget |
  |---|--:|--:|--:|--:|--:|--:|--:|
  | relevant | 989 | 2938 | 244 | 166 | 740 | 61 | 19 |
  | split_new | 83 | 1766 | 10 | 27 | 63 | 31 | 14 |
  | keys_rel | 1180 | 7222 | 13 | 39 | 933 | 117 | 93 |
  | keys_miss | 454 | 3431 | 12 | 25 | 97 | 84 | 61 |
  | const_free_miss | 10 | 1 | 0 | 0 | 3 | 26 | 0 |
  | vocab_blocks | **0** | **0** | 10 | 0 | 0 | 0 | 0 |
  | part_consistent | 104 | 0 | 0 | 0 | 25 | 0 | 0 |
  | consistent | 64 | 315 | 0 | 0 | 25 | 0 | 0 |
  | consistent_caught | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
  | br_verdict / br_parts | 2/58 | 315/0 | 0 | 0 | 11/12 | 0 | 0 |
  | br_glue, br_unsupported, py_deep | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
  | cb_formula / cb_verdict | 122/64 | 315/315 | 0 | 0 | 37/25 | 0 | 0 |
  | cb_theory_scope / cb_ext | 58/0 | 0 | 0/10 | 0 | 12/0 | 0 | 0 |
  | cb_category / cb_memo | 400/2552 | 687/11934 | 12/267 | 21/232 | 94/1786 | 2/290 | 77/126 |
  | sympy_and | 36 | 44 | 0 | 0 | 13 | 0 | 0 |
  `_vocab_blocks` is 0 on dev and fuzz, and loop reaches it, so put `loop` in WLS. `_keys` (rv_keys) is called only by tests
  (test_memos.py:137/143, test_relevance.py:312), so its reach is the suite.
- **Python callers of the 16 rows:** in the engine, only `_ask_general` sympy_api.py:579 (calls `_relevant`). Tests:
  test_relevance.py :55, :295-312, :346; test_memos.py :137, :143. tools-rust/outside.py :11-12 (names only). Python's
  `_keys_rel` is still the deep fallback (rv:py_deep, 0 everywhere).
- **Plant screen, answers only** (pl/, six workloads; fired/M = MATCH, Dn = n answers DIFFER):
  - caught: closed-keys-no-undef (zero D11), arg-keys-no-closed (zero D11), sides-keys-first-only (dev D13, fuzz D33),
    split-no-merge (dev D4, fuzz D16), split-part-first (dev D41, fuzz D4, zero D44), relevant-assume-consistent (fuzz D21,
    zero 6 msg diffs), consistent-ignore-verdict (fuzz D21, zero msg).
  - **consistent-fault is loud:** a TermFault comes up through `_ask_general` and the run stops (dev at q5, fuzz and zero too).
    Not a quiet False.
  - answer-void on all six: const-base-no-pow (dev 1 fired), const-free-no-mul, expr-keys-closed-skip, keys-empty
    (0 everywhere: test-only entry), keys-rel-no-flag, bool-keys-opaque-in (dev 6), vocab-no-derived (loop 230),
    part-consistent-true (dev 104, zero 25).
- **The state screen for those 8 was still running when I handed off** (pe/, --check entry, 6 workloads, detached, writes
  pe/done.txt). Read pe/*.cmp (the first JSON line has end_diff/stream_diff) and pe/*-*.session.json (plant_fired).
- **knowledge_quiet.py :104-108** fixed: under Rust's relevance, Python's `_consistent` code comes from PY_RELEVANCE. A raise
  inside Rust's `_consistent` isn't found by its frame walk and prints as not reached.
- **New test_relevance_core.py** (34 passed on orion). It covers the same catches as Python (a callback's Exception gives
  False on both sides and counts `rv:consistent_caught` on Rust; a BaseException goes up on both), the consistent-fault
  plant loud by a direct call, and `_keys_rel`/`_keys`/`_const_free`/`_relevant`/`_consistent` against Python's (`_py()`
  puts every wired name back while Python's side runs). Add it to TESTS.

## Next
1. Read pe/. For any plant still void under the state check, write a small workload (e.g. `relevance_wl.py`, a `live.py
   relevance` entry): part-consistent-true needs a set with an inconsistent component away from the query
   (`ask(Q.positive(x), Q.real(x) & Q.positive(y) & Q.negative(y))`: Python gives ValueError). Or name it void with its reason.
2. Classification for the TSV: all 16 are port, landed 5c8, Rust. Their reads of input terms are lazy conversion reads.
   Callbacks into conversion: `_formula`, `_applied_category`/`_is_matrix_predicate`, plus `Engine.verdict` (5c10) and
   `theory_scope` (Rust).
3. State: splits (INVENTORY-state.md :193, last reader 5c9) stays; stats (:199, never moved by a planned step) stays;
   `_KEYS`/`_CONST` (:169 "no Rust worker") stay. Their readers: relevance.rs through their methods, Python's `_keys_rel`
   deep fallback, the state/memos PROCESS registry (5c9), term_live `_Mark` (state step / conversion pass), tests
   test_memos.py:136-143, test_relevance.py:35, test_term_live.py:324, tools/relevance_fuzz.py:181. No container moved, so
   no digest switch is owed.
4. Module count: 13 of 32 on STATUS.md's list. sympy_api.py's 16 port rows are all on Rust, and its other rows are ruled
   conversion, so propose it as the 14th, footnoted with the conversion callbacks and the deep fallback, for the architect.
5. Bar: PLANTS = all 16 except consistent-fault (it aborts the run: report it from pl/, or keep it and read .err).
   WLS="loop zero cert" (+ any new workload). TESTS = 5c7's list + test_relevance_core.py. DIRECT "relations_direct.py
   300 0", N=6, BASE ~/sp19/sa-rust-ids-work/sa-port-158/bar-5c7b/suite. Check sa-port-167's stacked bar S1 on pareto1
   first (landing order).
