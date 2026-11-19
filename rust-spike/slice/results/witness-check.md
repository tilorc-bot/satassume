# The witness check: an exact pre-session check for None answers (issue 323, prototype)

LANDED on rust-slice as 29c5a0db (11:26Z 19 Nov, sa-port-339: 81e6561e's source, after the planner's ruling on section
12's question; this file was written before that), no PR. Branch
`port/witness-check` (sa-port-328 to 339, 18-19 Nov), on rust-slice 32ba9a3. Tested SHAs: the bar, S1, digests and iv
on 786410d (also origin `bar/witness-check-786410d`); the suite by id, the order runs, the plants on test_witness.py
and the repeat check on **81e6561e, the SHA to land** (786410d plus two test-only commits; guarded source identical,
so the same build). Venv .so cad764d46471b1c6, bench .so 0982a28074215658.
`SLICE_WITNESS` is off by default and the unchanged path is the default, except that `Engine.stats` now has a 13th
key, `witness_certified`, which is 0 with the switch off (a change to the default path's visible state; section 3).
With `SLICE_WITNESS=1`, a contextual query is first given to `satassume.witness.independent`, which returns True only
when it holds two exact rational points that satisfy the assumptions and give the proposition both values; the query
then returns None without a session. No SymPy object is constructed and nothing of SymPy's is evaluated at query
time: the check reads `type`, `args`, `Rational.p`/`.q` and `assumptions0`. The Rust change is entry.rs: KEYS has 13
entries and `ent_record_certified` counts a certified query without a tick.

**Result on 786410d (sa-port-337, 19 Nov).** Dev and fuzz answers are equal with the switch on and off, on both
backends, and S1 holds: fuzz -28.2% Python and -19.2% Rust, dev -2.7% Python and +1.1% Rust (inside the spread).
The two things that stopped sa-port-337 are closed: (1) the 7 order-dependent ids of tests/test_witness.py are fixed
in tests only (32c167ee, 81e6561e; section 8), and (2) sa-port-337's rerun of the bar on 786410d ended `END 0` with
the .so loaded and is read in section 12. **One thing is open** (section 12): the bar's `suite-witness:on` row on
786410d shows the 7 ids and none of the 21 the planner expected there, so the planner's condition for landing is not
met as written, and the landing waits for a ruling.

Sections 6, 7's table and 9 are from the earlier SHAs named in them and were not redone. Earlier result, for the 20
workloads (5e6e46a and c5239b9): every answer equal on and off on both backends; the check removes 1604 of 30482
engine queries (5.3%), 1060 of them in fuzz; 8 workloads have a certified query. Proposal: section 9.

## 1. Tested SHAs and what each number rests on

| what | SHA | where |
|---|---|---|
| suite by id on/off/base, dev and fuzz digests, test_witness.py, plants 749-752 and 754, repeat check, iv (128 runs) | 786410d against base 32ba9a3 | pareto0, shared lease, .so cad764d46471b1c6 (base: c20c326f) |
| S1 wall time, the check's cost a call, `_users_knowledge` a certified call | 786410d | pareto1, quiet lease 00bc95e0, pinned CPU 2, bench .so 0982a28074215658 |
| the bar (witness:on rows on 17 workloads, plant rows, suite rows) | 786410d | pareto0; sa-port-336's is void, sa-port-337's rerun not read here (section 10) |
| 20-workload gate, iv history check, cost split per call | 5e6e46a | pareto1, .so 45f63fdfb8e8523c |
| 20-workload gate from a frozen copy, the cap, reasons | c5239b9 | orion, .so a188b7fa95f27a88 |
| S1 with no cap | 47b7a0d | pareto1, pinned CPU 2, .so 45f63fdfb8e8523c |

- 786410d is the function SHA: da6eb2ee (the users'-knowledge guard d52129da with plant 754, the 13th stats key and
  entry.rs) plus p1/bar.sh and bar_sum.py. The 20-workload gate was not rerun on it; dev and fuzz were (section 2),
  and the bar's witness:on rows are the other 15 workloads' check.
- c5239b9 is the function SHA. Against 5e6e46a it adds the P1 guard (section 3), the layer and the removal of the
  module-level SymPy import; against 47b7a0d, 5e6e46a changed only which derived predicates are decided (section 3),
  no workload query mentions `hermitian` or `antihermitian`, and the one dev query with a `commutative` atom does not
  reach the check, so 47b7a0d and 5e6e46a return the same value on every workload query.
- S1 is the landing measure and was re-measured on 786410d with both guards in (section 5). Shares from shared-lease
  runs are not wall times. In the cap table the rows other than 32 and none are a model, not measurements.
- "Exact" rests on sa-port-325's table of the 14 basis predicates and its one-line arguments (origin
  `report/none-certify`, `exact325.py`), carried as the comments of `witness.TABLE`. Issue 247 applies: SymPy
  evaluation is not ground truth, and neither is the table; it is short enough to review.
- sa-port-328's gate on orion ran across the function change (47b7a0d to 5e6e46a in the worktree it imported from)
  and is not the gate.

## 2. The gate: answers equal, per workload

### 786410d: dev and fuzz digests, test_witness.py, the suite by id, iv

All on pareto0 under one shared lease (go336.sh, ended 08:51:42Z 19 Nov, `END 0`), from the staged tree of 786410d
(`tree.txt`, `pre-source.txt`: .so cad764d46471b1c6, witness.py 090625c1).

Digests (`pre/dig/dig.jsonl`, 18 rows, `err.txt` empty):

| workload | queries | digest off | digest on | check called | certified |
|---|---|---|---|---|---|
| dev | 1985 | 31cd0945c07f02a6 | 31cd0945c07f02a6 | 776 | 159 |
| fuzz (seed 424242) | 3000 | 173502b6ef285ad6 | 173502b6ef285ad6 | 2772 | 1060 |

Python and Rust give the same digest, calls and certified counts in every cell, and the digests are the base's. With
the switch off the check is called 0 times.

tests/test_witness.py alone, one process (`pre/tw/tw-*.log`): 102 passed on python and on rust, switch off and on.

Suite by id (suite331.sh; the bar's derandomized hypothesis profile, 3 workers an arm, six arms at once: on
`SLICE_WITNESS=1`, off `=0`, base 32ba9a3 with the variable unset):

| backend | arm | ids | passed | failed |
|---|---|---|---|---|
| python | base | 6159 | 6118 | 0 |
| python | off | 6261 | 6220 | 0 |
| python | on | 6261 | 6213 | 7 |
| rust | base | 6159 | 5991 | 127 |
| rust | off | 6261 | 6093 | 127 |
| rust | on | 6261 | 6086 | 134 |

23 skipped and 18 xfailed in every arm. The 102 ids off and on have and base lacks are tests/test_witness.py.

- **Off against base:** 0 ids differ, on python and on rust. The rust base's 127 failures are the same 127 ids in
  the off arm. By file: test_lra_fuzz.py 43, test_solver_incremental.py 36, test_solver.py 14, test_theory_hooks.py
  10, test_euf.py 7, test_euf_fuzz.py 4, test_writeback_provenance.py 3, test_solver_real_theories.py 3,
  test_transfer.py 2, and 1 each in test_lra_exhaustion.py, test_template_tables.py, test_verify_integration.py,
  test_relations.py and test_public_incremental.py (the planted-history test, the known id()-reuse failure). They
  are the base's and were not read here.
- **On against off: 7 ids differ, the same 7 on both backends, all in tests/test_witness.py** (on failed, off
  passed): `test_registered_knowledge_falls_through`, the five cases of
  `test_a_users_knowledge_falls_through_and_the_engines_answer_is_used`, and
  `test_on_skips_the_session_and_counts_the_query`. **The switch is not the cause; the order of tests in a worker
  is** (section 8). No answer of an older test moved, and no id outside test_witness.py differs.
- `test_sympy_api.py::test_in_scope_query_returns_none_only_when_undecided`, which failed with the switch on up to
  c5239b9, passes: a certified query is now counted in `stats['queries']` (da6eb2ee).
- No row was needed in harness/state.py or tests/test_memos.py for the 13th stats key or for `_TEMPLATES` and
  `_THEORIES`: tests/test_memos.py and the state checks pass in all four arms of 786410d.
- State, on against off, as ids whose recorded state differs: python `py_made` 103. Rust `rust_made` 91, `lra` 55,
  `session` 789; the rust `session` counters also differ in 801 ids between off and base, two runs of code that is
  the same on that path (mostly `pm:key_eq`, which follows the order of tests in a worker), so 789 is at that noise
  level. A certified query builds no session, so `py_made`, `rust_made` and `lra` are expected to differ.
- Quiet catches (`engine.py`'s `except Exception` around the complete check) are equal id by id in all three arms:
  rust 49 in 9 ids, python 10 in 7 ids. Handler rows: rust 39 in every arm, python 0. The counter does fire here,
  which is what makes the equality mean something.

iv history check (iv336.sh, 64 run names x off/on, `iv-cmp.txt`): 0 runs whose failing ids differ off against on.
Python: rc 0 in all 64. Rust: `test_transfer.py::test_models_respect_transfer` and `::test_protocol_on_fuzz` fail in
16 runs with the switch off and the same 16 with it on, as on 5e6e46a.

### The 20-workload gate (5e6e46a and c5239b9; not rerun on 786410d)

Each workload runs through `live.py --check entry` four times: py and rust (`SLICE_CONVERT=rust
SLICE_TERM_FRAMES=rust`), each with `SLICE_WITNESS=0` and `=1`; `ans328.py` compares answers and messages per query,
on against off. Two runs of the gate:

- **5e6e46a, pareto1** (staged tree, shared lease, ended 00:31:17Z 19 Nov): `GATE answers equal`; answer_diff 0 and
  msg_diff 0 in all 40 rows; rc 0 in all 80 runs.
- **c5239b9, orion, from a frozen copy** (git archive plus the .so, never the worktree; ended 02:45:03Z 19 Nov):
  `GATE answers equal`; answer_diff 0 and msg_diff 0 in all 40 rows; rc 0 in all 80 runs; 0 of 80 stderr files
  non-empty. Its table is byte-identical to pareto1's.

Engine queries, off -> on (py = rust in every row, and the same on both SHAs). The drop shows the gate is not void:
the check did certify.

| workload | queries | engine queries off -> on | removed |
|---|---|---|---|
| lra | 1500 | 1561 -> 1561 | 0 |
| f6 | 2902 | 2900 -> 2900 | 0 |
| wiring | 6512 | 5628 -> 5397 | 231 (4.1%) |
| scope | 169 | 197 -> 197 | 0 |
| dev | 1985 | 883 -> 724 | 159 (18.0%) |
| fuzz (seed 424242) | 3000 | 3031 -> 1971 | 1060 (35.0%) |
| ground | 18 | 32 -> 28 | 4 |
| port | 19 | 75 -> 75 | 0 |
| loop | 420 | 384 -> 384 | 0 |
| zero | 854 | 714 -> 662 | 52 (7.3%) |
| cert | 61 | 87 -> 87 | 0 |
| budget | 28 | 26 -> 26 | 0 |
| core | 1636 | 1634 -> 1539 | 95 (5.8%) |
| opaque | 2546 | 2372 -> 2372 | 0 |
| rootof | 5187 | 4784 -> 4784 | 0 |
| value | 3742 | 5817 -> 5817 | 0 |
| twin | 2 | 0 -> 0 | 0 |
| transfer:7:60 | 60 | 116 -> 114 | 2 |
| transfer2:3:40 | 40 | 152 -> 151 | 1 |
| cls | 72 | 89 -> 89 | 0 |
| all 20 | | 30482 -> 28878 | 1604 (5.3%); without fuzz 544 of 27451 (2.0%) |

Dev and fuzz digests on c5239b9 (orion, `pre330.sh`): dev 31cd0945c07f02a6, fuzz 173502b6ef285ad6, on = off, py =
rust, equal to base and to 5e6e46a's (orion py; pareto1 py and rust). The check fires on 776 dev and 2772 fuzz queries
and certifies 159 and 1060, the same on both backends. The Rust rows record 0 discarded runs. The gate's quiet-handler
files hold 0 rows in all 80 runs; I did not show that counter fire on a planted raise in the gate, so that zero says
little. In the suite the counters do fire and are equal across arms (below).

### Suite by id against base, earlier: c5239b9

c5239b9 and base e5db633, pareto0 (staged trees, shared lease 77dcab26, 03:09Z to 03:16Z 19 Nov, pareto0 otherwise
unleased), the bar's derandomized hypothesis profile, 3 workers an arm, six arms at once: on (`SLICE_WITNESS=1`), off
(`=0`) and base (unset), on rust and python. Every arm imported its own staged tree (`tree.txt`).

| backend | arm | ids | passed | failed |
|---|---|---|---|---|
| python | base | 6159 | 6118 | 0 |
| python | off | 6256 | 6215 | 0 |
| python | on | 6256 | 6214 | 1 |
| rust | base | 6159 | 5992 | 126 |
| rust | off | 6256 | 6088 | 127 |
| rust | on | 6256 | 6088 | 127 |

23 skipped and 18 xfailed in every arm. The 97 ids off and on have and base lacks are tests/test_witness.py.

- **Off against base:** python 0 ids differ. Rust 1 id differs:
  `test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence` (off failed with
  `assert 1 == 2` at :204, base passed), the known id()-reuse flake by the repeat check of section 7. The six
  structure tests that failed with the switch off on 5e6e46a pass.
- **On against off:** `test_sympy_api.py::test_in_scope_query_returns_none_only_when_undecided` fails with the switch
  on, on both backends (`assert 0 == 1`; state, not an answer: section 8). On rust the planted-history test also
  differs, the other way: on passed, off failed. `test_history.py::test_ddmin_shrinks_to_the_responsible_query`,
  which failed with the switch on on 5e6e46a, passes: the P1 guard.
- **On against base:** the stats test only, on both backends.
- The 126 failures of the rust base are the same ids in all three rust arms (no other id differs); they are the
  base's and were not read here.
- State, on against off, as ids whose recorded state differs: rust `session` 753, `rust_made` 125, `lra` 69; python
  `py_made` 123. A certified query builds no session, so this is expected.
- Quiet catches (`engine.py`'s `except Exception` around the complete check) are equal in all three arms: rust 49 in
  9 ids, python 10 in 7 ids. Handler rows: rust 39 in every arm, python 0.

The same run on f46e40e (pareto1, sa-port-330's, 01:02Z; c5239b9 differs from it in one hunk of witness.py, the
guard moved to the end) against 329's pareto1 base rows gave the same ids: on against off the stats test only, off
against base the planted-history test only on rust (`assert 0 == 2`) and nothing on python.

### iv history check (5e6e46a only; not rerun on c5239b9)

pareto1, 64 run names x off/on: no moved id, 0 runs whose failing ids differ off against on. Python: rc 0 in all 64.
Rust: `test_transfer.py::test_models_respect_transfer` and `::test_protocol_on_fuzz` fail in the 16 fwd5/rev5 runs,
off and on alike.

## 3. What the check is, and the decisions in it

`satassume/witness.py` (new) and a few lines in `satassume/sympy_api.py`: the call sits in `_engine_ask`
just before `eng.ask`, which is Python on both paths, so it runs before Python's `Engine.ask` and before Rust's
entry alike. The check itself has no Rust part. The one Rust change is the counter of section 8 (sa-port-333,
da6eb2ee): `entry.rs`'s `EngineStats` is a view of exactly Python's stats keys, so `KEYS` is 13 with
`witness_certified` last, and `ent_record_certified` is Rust's `Engine._record_certified` (`queries` +1,
`witness_certified` +1; no tick of its own and no plant: the second counter is the count of its calls).
`SLICE_WITNESS_CAP` (default 32; 0 = no cap, limit 2000) bounds the points
tried. The soundness argument and its six assumptions are the module docstring; the first is that the engine's
definite answers are sound, and where they are not, the check can replace a wrong definite answer by None, which is
what the gate compares.

sa-port-328's decisions:
- (a) It evaluates the formula `to_formula` makes (P atoms over the input terms), not convert.py's tables, because the
  pure-Python path has no tables. A Rust port would read the term table's rows instead.
- (b) `eq` and `lt` atoms are decided by comparing two rationals. By the planner's ruling they are entries of the
  table: `TABLE` has 16 entries, the 14 basis predicates and these two.
- (c) Derived predicates by `rules.DEFINITIONS`; narrowed by 329, below.
- (d) Undecided is strict: any undecided atom leaves the point unused (325's evaluator was Kleene).
- (e) Points are rational only, so no infinity and no complex point; certify rates are below 325's.
- (f) It falls through when `eng.extensions` has any registration. Up to c5239b9 that was the only entry point
  looked at; sa-port-333 (d52129da) found the others and the check now falls through on each (assumption 5 of the
  module docstring): `extensions.register` on the default registry while the engine uses another (it still decides
  `sympy_api`'s scope), `TemplateRegistry.register` and `.lazy` (a user's module registers like a built-in one, with
  no epoch bump), `Engine(templates=...)` and the `Engine.templates` setter, `Engine(relations=...)` and
  `Engine.relation_specs`. The slice adds no entry point (`session_live.register_instrument` registers our
  instruments only). Whose a template or an adapter is, is read off its `__module__` (the package's
  `knowledge.templates.` and `theories.`; a backend's replacements keep the module of what they replace: on Rust after
  the dev workload, 34 templates, none outside the package). `_users_knowledge` is asked last, next to the P1 guard,
  so only a query about to be certified pays for it, and it writes nothing: it scans the loaded templates on each
  such call, uncached (cost in section 5). Kept test
  `test_a_users_knowledge_falls_through_and_the_engines_answer_is_used`, 5 cases, one per entry point.
- (g) Contextual queries only. A query none of whose assumption conjuncts is relevant is asked without assumptions
  and never reaches the check.

sa-port-329's ONE_WAY decision, a deviation from the planner's ruling (2). The ruling: use a definition only where
it is two-way, and make any one-way entry undecided. `TWO_WAY` holds the 16 derived predicates SymPy's own rule base
states or entails in both directions (`test_two_way_definitions_follow_from_sympys_rules` checks the split by model
counting over SymPy's rule strings). Three are one-way only. By the letter all three become undecided; 329 made
only `antihermitian` undecided and kept `hermitian` and `commutative` True at a rational. The planner accepted it,
with this reason: at a rational point the one-way rule's own direction (real implies hermitian; every number is
commutative) gives True exactly, and False never arises there; making `commutative` undecided would turn the check
off everywhere, since every Symbol's `assumptions0` holds `commutative: True`.

The P1 rule (formula ruling P1, added on c5239b9). `GUARDED` = `ask`, `verdict`, `_context_session`,
`_within_budget`. If one of them is on the instance's `__dict__`, or the class's attribute is not in `ACCEPTED`,
the check falls through, so a user's method is called and its answer used exactly as with the switch off. Our own
instruments register through `accept()`: `sympy_api` at import (Python's methods), `session_live.install` (Rust's
replacements) and `catch_count.install` (our `verdict` instrument, both backends). The guard runs last, after the
pair is verified, so only a query about to be certified pays for it. Kept test
`test_a_users_method_on_the_engine_is_called_and_its_answer_is_used`, 12 cases (4 names x class, instance,
subclass).

The layer. `witness.py` imports no SymPy; `sympy_api` gives it the six classes it compares types with
(`witness.bind`), and unbound, every term is undecided. Layer "witness" is 7 (sympy_api 8). sa-port-330 read "the
existing boundary module" in the planner's ruling as `sympy_api`, and the planner accepted that reading. The six
structure tests that failed on 5e6e46a with the switch off pass on c5239b9, off and on, on both backends.

Shared files touched: `rust-spike/slice/session_live.py` (+4 lines), `rust-spike/slice/catch_count.py` (+3),
`harness/state.py` (+6, classification rows), `tests/test_layering.py` (LAYERS).

## 4. Plants 749-752 and 754

Each is `SLICE_WITNESS_PLANT` with the switch on, 786410d, pareto0, python (`pre/tw/plant-*.log`, `pre/dig`).
"Tests" is of 138: test_witness.py's 102 and the 36 of test_history.py's two tests that patch `Engine.ask` and
test_public_incremental.py (36 passed with no plant, switch off and on). Each catching check asserts behaviour and
reads no plant flag. With no plant the digests are dev 31cd0945c07f02a6 and fuzz 173502b6ef285ad6.

| plant | what it breaks | caught by answers | caught by tests |
|---|---|---|---|
| 749 integer-half | `integer` is True at a half | dev digest ff3a586753ddcf94, fuzz f10fca19a50daa53 (certified 170 and 1068, not 159 and 1060) | 6 fail, among them `test_integer_is_false_at_a_half` |
| 750 single | one witness is taken as a pair | dev 52d6bc53c55fc204, fuzz 92fcf1f54e0699c5 (certified 461 and 1906) | 45 fail, among them `test_one_witness_is_not_enough` |
| 751 skip-own | the symbols' own assumptions are not read | not by dev or fuzz (digests unchanged); the 20-workload gate on 5e6e46a under the plant: 6 rows differ, ground (query 15: True off, None on), zero (query 844: True, None) and core (21 queries, False off, None on), py and rust alike | 4 fail: `test_falls_through[p1-a1]`, `test_own_assumptions_bound_the_points`, `test_the_symbols_own_assumptions_count`, `test_answers_are_equal_on_and_off[27]` |
| 752 skip-patched | the P1 guard is skipped | none: dev and fuzz digests unchanged, since no workload replaces an engine method | 11 fail: 9 of the 12 cases of the P1 test, `test_history.py::test_ddmin_shrinks_to_the_responsible_query`, and the planted-history test of test_public_incremental.py |
| 754 skip-users | the users'-knowledge guard is skipped | none: dev and fuzz digests unchanged, since no workload registers a template, a lazy module, an adapter or a function | 5 fail: the five cases of `test_a_users_knowledge_falls_through_and_the_engines_answer_is_used` (template, lazy, templates-function, adapter, default-registry) |

- 754 is a kept-test catch. No workload reaches it because no workload gives the engine knowledge of its own. Two of
  its five cases (template, templates-function) assert an answer that differs: the user's unsound template makes the
  engine answer True where the check would certify None.
- 752: the eleventh failure is the planted-history test, which had passed under this plant on c5239b9. It is the
  test with the known id()-reuse failure (section 7), one run, so it is not counted as a catch.
- The bar's plant rows (749 and 750 by answers on workloads, 751, 752 and 754 by kept tests in their suite rows)
  are not read: section 10.
- 750: 30 tests failed on f46e40e, 40 on c5239b9 and 45 on 786410d. The 10 more on c5239b9 are the 9 P1 cases and
  test_ddmin: the plant's early return comes before the guards at the end. The 5 more on 786410d are the five
  users'-knowledge cases, for the same reason.
- 751: dev and fuzz cannot reach it. Fuzz declares no symbol (0 of 3000 queries), and dev has 12 queries whose
  symbol's own assumptions exclude a candidate value, none of which changes the certified set. Three other workloads
  reach it, as the gate under the plant shows.
- 752 is a kept-test catch. No workload reaches it because no workload replaces `ask`, `verdict`,
  `_context_session` or `_within_budget`. The 3 `verdict` cases pass under the plant because that query's verdict
  calls come from relevance, before the check.

## 5. Measures

**S1 on 786410d, the landing measure** (sa-port-336's quiet lease 00bc95e0 on pareto1, 08:39Z to 08:46Z 19 Nov,
pinned CPU 2, i5-13600T, bench .so 0982a28074215658, 12 rounds, load 1.06 to 2.36 falling in the first two minutes,
`err.txt` empty, one digest per workload over all rows: dev 31cd0945c07f02a6, fuzz 173502b6ef285ad6). Seconds:

| | off: median (min to max) | cap 32: median (min to max) | on against off |
|---|---|---|---|
| dev, Python | 0.5309 (0.5268 to 0.5357) | 0.5168 (0.5124 to 0.5203) | -2.7% |
| dev, Rust | 0.6446 (0.6373 to 0.6485) | 0.6517 (0.6442 to 0.6561) | +1.1% |
| fuzz, Python | 8.0622 (7.9857 to 8.1387) | 5.7847 (5.7438 to 5.8457) | -28.2% |
| fuzz, Rust | 5.8474 (5.7513 to 5.9115) | 4.7252 (4.6821 to 4.8156) | -19.2% |

- Fuzz gains beyond the spread on both backends: the slowest on-run is faster than the fastest off-run by 2.14 s
  (Python) and 0.94 s (Rust).
- Dev on Python gains beyond the spread (the ranges do not overlap). Dev on Rust is 7.1 ms slower by the median with
  overlapping ranges (off reaches 0.6485, on starts at 0.6442; each arm's own range is 11 to 12 ms): not a loss
  beyond the spread.
- The check on this run (`med.txt`, py / rust): dev 776 calls, 44.4 / 49.1 ms, median 49 / 56 us a call, certified
  159; fuzz 2772 calls, 507 / 544 ms, median 178 / 191 us, certified 1060.
- `_users_knowledge` (`uk.jsonl`, same lease) runs once per certified call and nowhere else:

| | calls | total a pass | median us a call (90%, max) | scan at the end |
|---|---|---|---|---|
| dev, Python | 159 | 1.05 ms (0.20% of the pass) | 6.2 (8.5, 9.7) | 34 templates in 32 classes, 17 lazy, 2 specs |
| dev, Rust | 159 | 1.29 ms (0.20%) | 8.1 (9.0, 13.9) | the same |
| fuzz, Python | 1060 | 5.13 ms (0.09%) | 5.2 (5.5, 8.6) | 7 templates in 7 classes, 23 lazy, 2 specs |
| fuzz, Rust | 1060 | 5.95 ms (0.13%) | 5.6 (6.0, 11.0) | 8 templates in 8 classes, 22 lazy, 2 specs |

  So the uncached scan is not what S1 turns on, and no memo or generation counter was added.

Earlier S1, with the no-cap arm (47b7a0d, sa-port-328's quiet lease on pareto1, pinned CPU 2, 12 rounds, load <=
1.16), median seconds:

| | off | cap 32 | no cap |
|---|---|---|---|
| dev, Python | 0.5318 | 0.5113 (-3.9%) | 0.6409 (+20.5%) |
| dev, Rust | 0.6538 | 0.6570 (+0.5%) | 0.7872 (+20.4%) |
| fuzz, Python | 8.0716 | 5.7886 (-28.3%) | 6.6789 (-17.3%) |
| fuzz, Rust | 5.9141 | 4.7887 (-19.0%) | 6.2133 (+5.1%) |

Rust is `SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust`. There is no S1 for the other 18 workloads.

Counts (identical py and rust, 47b7a0d, 5e6e46a, c5239b9 and 786410d). The check is called at most once a query: dev 776,
fuzz 2772. Certified at caps 4, 8, 16, 32, none: dev 106, 137, 156, 159, 163; fuzz 382, 603, 806, 1060, 1491.

Cost per call (5e6e46a, sa-port-329's quiet lease, 3 rounds, median per call), py / rust:

| | calls | total ms | median us |
|---|---|---|---|
| dev cap 32, whole check | 776 | 41.9 / 47.3 of a 513 / 661 ms pass | 47 / 56 |
| certified | 159 | 9.4 / 11.1 | 57 / 68 |
| fell through, no point tried | 283 | 2.6 / 3.3 | 8 / 10 |
| fell through after a search | 334 | 29.9 / 32.9 | 72 / 80 |
| fuzz cap 32, whole check | 2772 | 492.2 / 528.0 of a 5772 / 4793 ms pass | 174 / 187 |
| certified | 1060 | 200.5 / 215.5 | 169 / 182 |
| fell through, no point tried | 544 | 5.3 / 6.2 | 9 / 11 |
| fell through after a search | 1168 | 286.5 / 306.3 | 226 / 240 |

So 77% of the check's time on dev and 59% on fuzz goes to calls that fall through (32.5 of 41.9 ms and 291.8 of
492.2 ms, Python). With no cap the check costs 168.3
/ 175.6 ms on dev and 2658.6 / 2754.3 ms on fuzz, nearly all of it in search fall-throughs (dev 155.6 / 160.5 ms;
fuzz 2178.2 / 2242.4 ms, median 2.3 ms).

Nones by reason (329's `ana329.py`, against 325's 368 dev / 2157 fuzz Nones of class (i)). Certified at cap 32: 157
/ 986; with no cap 161 / 1383. Not certified at cap 32:

| reason | dev | fuzz |
|---|---|---|
| a constant pi | 82 | 372 |
| a function | 41 | 0 |
| no relevant conjunct, so no call (decision (g)) | 41 | 142 |
| every candidate tried, no rational pair | 33 (True side only 18, False only 7, neither 8) | 260 (187, 67, 6) |
| found after point 32 | 4 | 397 |
| infinity, zoo or nan | 4 | 0 |
| limit 2000 | 4 | 0 |
| I | 2 | 0 |

Extensions and own assumptions: 0 in both. Of all None answers (dev 892, fuzz 2387) the check certifies 159 and
1060; dev's largest other reason is 449 answer-memo hits, which make no engine call.

## 6. The cap

`tools328/cap330.py` (method in its docstring): a per-call line through the two measured arms. The 32 and none rows
reproduce S1; **the other rows are a model, not measurements**. Net % of the off wall time:

| cap | dev py | dev rust | fuzz py | fuzz rust |
|---|---|---|---|---|
| 4 (model) | -1.4 | +1.5 | -8.3 | -4.0 |
| 8 (model) | -3.4 | +0.4 | -15.0 | -9.2 |
| 16 (model) | -4.4 | +0.0 | -21.0 | -13.7 |
| 32 (measured) | -3.9 | +0.5 | -28.3 | -19.0 |
| 64 (model) | -2.5 | +1.5 | -34.8 | -23.9 |
| 128 (model) | -0.4 | +3.2 | -35.9 | -23.6 |
| none (measured) | +20.5 | +20.4 | -17.3 | +5.1 |

**Recommendation: keep 32** (accepted by the planner). 16 is equal on dev within S1's spread and costs fuzz 5 to 7
points; 64 gains fuzz 5 to 6 points and costs dev 1 to 1.4.

What makes dev break even. Python dev is already below (-3.9%). Rust dev pays 47.3 ms for the check and saves 44.0 ms
of engine time over the 159 certified queries, so it needs 3.3 ms less, 10% of what the 334 search fall-throughs
cost. Under cap 32 the fall-through cost is mostly a fixed part per call, the formula compile and the pools: its
fitted median is 77 to 86 us on dev and 125 to 134 us on fuzz. A lower cap therefore saves little on dev (model: cost
41.8 ms at 32, 38.0 at 16, 34.3 at 4) and loses certified queries on fuzz. Rust dev breaks even only with a cheaper
fixed part, and that is what a Rust port of the compile and pools would supply (section 9).

## 7. The repeat check: the known id()-reuse flake

`test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence`, a28c548's method, 20 fresh
processes a cell, c5239b9, orion, frozen copy (all 160 runs imported the frozen tree; the switch read True in the 80
on-runs):

| backend | cell | switch off | switch on |
|---|---|---|---|
| Rust | plain | 0 of 20 pass (17x `assert 0 == 2`, 3x `assert 1 == 2`) | 2 of 20 pass (12x `assert 0 == 2`, 6x `assert 1 == 2`) |
| Rust | keep-alive | 20 of 20 | 20 of 20 |
| Python | plain | 20 of 20 | 20 of 20 |
| Python | keep-alive | 20 of 20 | 20 of 20 |

The same on 786410d (pareto0, `pre/rep/rep-sum.txt`, 20 runs a cell): Rust plain 0 of 20 off (13x `assert 0 == 2`,
7x `assert 1 == 2`) and 0 of 20 on (12x, 8x); Rust keep-alive 20 of 20 off and on; Python keep-alive 20 of 20 off and
on; Python plain 20 of 20 off and **19 of 20 on** (1x `assert 1 == 2` at :204). The Python on-cell has the flake's
shape too (plain fails, keep-alive is clean), and it is the second time Python fails it only with the switch on
(5e6e46a below: 18 of 20). Reported by id; not edited.

Every failure is at `test_public_incremental.py:204`. Plain fails, keep-alive is clean, and the off rate is the
same: the flake's shape, so it is the known id()-reuse failure, reported by id and not edited. On f46e40e the same
table read 0 of 20 and 1 of 20 for Rust plain and 20 of 20 in the other six cells. One earlier row differs:
sa-port-329's run on 5e6e46a (pareto1, plain only, before the P1 guard) had Python at 20 of 20 off and 18 of 20 on,
both failures `assert 1 == 2` at the same line. It had no keep-alive cell, so it classifies nothing alone, and
the 40 Python plain on-runs on f46e40e and c5239b9 did not repeat it.

## 8. Tests that fail with the switch on, and the 7 that fail after a leaked template

After this section was written the 7 were fixed in tests only (32c167ee and 81e6561e) and a second effect of the
same fixture was found, 21 ids of two later files; both are in section 12, with the runs on 81e6561e.

**The stats test passes now.** `tests/test_sympy_api.py::test_in_scope_query_returns_none_only_when_undecided` failed
with the switch on up to c5239b9 (`assert 0 == 1` on `eng.stats['queries']`: a certified query was counted nowhere).
Since da6eb2ee a certified query is counted in `stats['queries']` and by itself in the new `stats['witness_certified']`
(`Engine._record_certified`; entry.rs `ent_record_certified`, no tick). The 13th key is on the default path too,
where it is 0.

**Seven ids of tests/test_witness.py depend on what ran before them in the process** (found by sa-port-337 in
786410d's suite by id; not fixed, because this step lands only): `test_registered_knowledge_falls_through`, the five
cases of `test_a_users_knowledge_falls_through_and_the_engines_answer_is_used`, and
`test_on_skips_the_session_and_counts_the_query`. Each first asserts that a query is certified. Two older tests, both
on rust-slice and on main before this branch, register a template of their own on the default `registry` and leave
it there:

- `tests/test_templates.py::test_template_key_error_is_not_read_as_inconsistent` (`:672`, with the comment "its
  template stays registered, harmlessly"),
- `tests/test_p4_review.py::test_reregistered_template_key_does_not_reuse_compiled_pattern` (`:26`, `:33`).

After either, `witness._users_knowledge` is True for every engine in that process (a template whose module is not
the package's: decision (f), d52129da), the check falls through for every query, and the seven assertions fail.
That is the guard doing what it was written to do; what is wrong is that the seven tests assume a clean registry.

- It does not depend on the switch. On orion, python, one process, either leaking test followed by test_witness.py:
  7 failed, 96 passed with `SLICE_WITNESS=0` and with `=1`; test_witness.py first: 103 passed with both
  (`~/sa-rust-ids-work/sa-port-337/order/min-*.log`, `rev-*.log`).
- In the suite by id it showed as "on against off" only because xdist put the files in different workers: in both
  on-arms a leaking test ran in the worker that later ran the seven (python: the test_p4_review one, all 7 in that
  worker; rust: the test_p4_review one before 1 of them and the test_templates one before the other 6); in both
  off-arms the leaking tests ran in workers that never ran test_witness.py. The same 3-worker suite with the switch
  off, or the bar's 6-worker suite rows, can fail the same 7 ids on another distribution.
- Consequence for the switch itself: in a process where a user's template is registered the check certifies
  nothing, so after either test the rest of that worker's suite runs the unchanged path even with the switch on.

Possible fixes, for a working step (none made here): the seven tests restore the default registry before their
first assertion (the `users_knowledge` fixture already restores it afterwards), or the two older tests remove what
they register. The first touches only this branch's test file.

Other state that differs with the switch on (module docstring): the engine's memos and caches are not filled by a
certified query, and `last_budget_limited` stays False for a certified query that is over the discovery budget.

## 9. Proposal: land it in Python, behind the switch, off by default

One proposal of the three (land it in Python, port it to Rust, "not supported"): **land it in Python** as it is on
c5239b9, `SLICE_WITNESS` off by default, cap 32, the unchanged path the default.

The numbers behind it:
- No answer moves: 20 workloads x py/rust on two SHAs and two machines, 160 runs, answer_diff 0 and msg_diff 0 in
  every row; dev and fuzz digests equal to base; iv no moved id.
- It pays where queries are independent: fuzz -28.3% (Python) and -19.0% (Rust) wall time, 1060 of 3031 engine
  queries removed. On dev, Python gains 3.9% and Rust loses 0.5%: 159 of 883 engine
  queries removed, the saving spent on the 617 calls that fall through. In the other 18 workloads it removes 385 of
  26568 engine queries (1.4%), and there is no S1 for them.
- Off, the query path is unchanged: with the switch off the suite differs from base only in the new test file
  (and, on Rust, the known id()-reuse flake).
- Each of the four plants is caught by an independent check, three of them by workload answers.

Why not the default yet: Rust dev does not break even, the stats test (section 8) needs a decision, S1 is not
re-measured on c5239b9, and user-registered templates are not detected (decision (f)).

Why not "not supported": the answers hold and the fuzz gain is large on both backends. Why not "port it to Rust"
as the step itself: the Python module is the reference a port is compared against, as `_Walk` is for
`SLICE_CONVERT=rust`, so it lands first either way.

This is a new optimization on the Python path as well, in `satassume/` proper. It constructs and evaluates nothing
of SymPy's and changes no input. Whether main takes it is Tilo's decision.

### The follow-up, sized: the per-call part in Rust

What it is for. Under cap 32 the check's cost is mostly the fixed part of each call, the formula compile and the
pools (fitted median 77 to 86 us on dev, 125 to 134 us on fuzz), paid by certified and fall-through calls alike.
The port replaces it; the cap stays 32.

What moves: `witness.py` `_pred`, `_term`, `_formula` (the compile), `_own`, `_roots`, `_pools` (the pools), the
index-sum search and `_holds`: lines 227 to 511, 285 lines of Python. The three tables (16 + 16 + 3 entries) stay
one source, read from the Python module. The entry stays in `sympy_api._engine_ask`, so both backends reach it.

What the crate already has: exact rationals (`num-bigint`, `term/rat.rs`), a walker that reads SymPy objects by
type and args without evaluating (`term/walk.rs`, the convert step), and P1's `method_of` rule (`context.rs`).

Size (my estimate, not a measurement): 600 to 800 lines of Rust behind a third switch value (`SLICE_WITNESS=rust`,
with `=1` the Python reference). The convert step, a comparable walk over the same objects, was 764 lines in one
file. Two worker sessions: one for the port with a differential against the Python check (same certified set and
same pair per call, on the 776 dev and 2772 fuzz calls and the other 18 workloads), one for the plants at the Rust
sites, the bar and S1.

What it can gain (derived from S1 on 47b7a0d and the cost split on 5e6e46a, not measured): the engine time the
certified queries save is 62.4 / 44.0 ms on dev and 2773.9 / 1653.3 ms on fuzz (py / rust). A check that cost
nothing would therefore give dev -11.7% / -6.7% and fuzz -34.4% / -28.0%; those are the bounds. Rust dev needs only
3.3 of its 47.3 ms back to break even, so a port that halves the check's cost on dev puts Rust dev near -3% (arithmetic on the same numbers). S1 on the
port decides.

## 10. Owed, and not done

The bar named below as not read is read in section 12.

- **Not landed.** sa-port-337 was a land-only step and stopped with Status: question on the two items below.
- **The 7 order-dependent ids of tests/test_witness.py** (section 8) need a test change, which a land-only step does
  not make.
- **The bar on 786410d is not read.** sa-port-336's bar (pareto0, 08:52Z to 09:35Z 19 Nov) wrote `END 0` but is
  void: job336bar.sh copied the .so into the bar's clone before the clone had `rust-spike/slice` checked out (`cp:
  cannot create regular file`, bar-launch.log), no phase checks for the .so, and every phase exited 0. Its direct.txt
  reads `ModuleNotFoundError: No module named 'sa_solver'`, its suite has no rows, and every "py vs rust" cell is
  empty. Only its Python cells are real: dev and fuzz py against py MATCH with the base digests. sa-port-337
  relaunched it as tools337/job337bar.sh (the branch is checked out before the copy, and the job stops with `END
  so-missing` unless the copied .so hashes to cad764d46471b1c6) at 09:42Z 19 Nov under shared lease 34a14557; end
  marker orion `~/sa-rust-ids-work/sa-port-337/gobar-end.txt`. Its witness:on rows, plant rows 749-752 and 754,
  quiet-handler rows and wall time per row (`python3 tools/wall336.py bar/bar`) are for the next step to read. Its
  suite rows can show the 7 ids above, by distribution.
- The planted-history test failed 1 of 20 plain runs on Python with the switch on, and 0 of 20 with it off (section
  7). It has the id()-reuse shape; whether the switch raises its rate on Python is not measured beyond these 20.
- OWED, to be named in the report: `Engine.stats`' 13th key on the default path; `ent_record_certified` has no tick;
  bar.sh's witness rows have no plant-fired counter (their catches are answers and kept tests) ([147]).
- The 20-workload gate was not rerun on 786410d (dev and fuzz were); the cap table and the reasons table are from
  the earlier SHAs.
- Main taking the check, and the 13th stats key with it, is Tilo's decision.

## 11. Where the numbers are

- 786410d (sa-port-336's jobs, read by sa-port-337), orion `~/sa-rust-ids-work/sa-port-336/`: suite by id
  `job-786410d/suite-cmp.txt` and `suite-{on,off,base}-{python,rust}/` (rows from pareto0
  `~/sp19/sa-rust-ids-work/sa-port-336/`); digests `job-786410d/pre/dig/dig.jsonl`; tests and plants
  `job-786410d/pre/tw/`; repeat check `job-786410d/pre/rep/rep-sum.txt`; iv `job-786410d/iv-cmp.txt`; S1
  `timing-r1/med.txt`, `uk.jsonl`, `env.txt`, `load.txt`; the void bar `bar/` and `bar-launch.log`.
- sa-port-337, orion `~/sa-rust-ids-work/sa-port-337/`: the order reproductions `order/`; the bar rerun `bar/`,
  `gobar-end.txt`, `bar-launch.log` (pareto0 `~/sp19/sa-rust-ids-work/sa-port-337/`).
- Handoffs: HANDOFF-sa-port-333.md and HANDOFF-sa-port-336.md at the branch root (file:line maps);
  `~/sa-rust-ids-work/sa-port-328/HANDOFF-sa-port-328.md`, `sa-port-329/HANDOFF-sa-port-329.md`,
  `sa-port-330/HANDOFF-sa-port-330.md`.
- Gate 5e6e46a: pareto1 `~/sa-rust-ids-work/sa-port-329/job/gate/` (`answers.txt`, `rc.txt`); under plant 751
  `job/gate-751/answers.txt`. Gate c5239b9: orion `~/sa-rust-ids-work/sa-port-330/c5239b9/gate/`; digests `dig/`,
  tests and plants `tw/`, repeat check `rep/rep-sum.txt`.
- Earlier suites by id: orion `~/sa-rust-ids-work/sa-port-331/job-c5239b9/` (`suite-cmp.txt`),
  `job-f46e40e/suite-cmp.txt`; 5e6e46a's: `sa-port-329/job/suite-cmp.txt`.
- Earlier iv: `sa-port-329/job/iv-cmp.txt`. Earlier S1: `sa-port-328/timing-r1`. Cost split and reasons:
  `sa-port-329/cnt/ana.txt`. Cap: `sa-port-330/cap/cap.txt`.
- Tools: `rust-spike/slice/results/tools328/` (`*328*`, `*329*`, `*330*`, `*331*`), `tools336/`, `tools337/`.

## 12. sa-port-339: 81e6561e's suite by id, the 786410d bar, and the plants on 81e6561e

Outputs: orion `~/sa-rust-ids-work/sa-port-338/job-81e6561e` (suite by id, order runs), `~/sa-rust-ids-work/
sa-port-337/bar/bar` (the bar), `~/sa-rust-ids-work/sa-port-339` (`orion/out`, `p1`: the plants and the repeat check;
`workers-337bar.txt`). Tools: results/tools339.

### The test-only fix (32c167ee, 81e6561e) and the 21 ids

`git diff --stat 786410d..81e6561e` outside results and HANDOFF files: tests/test_p4_review.py, tests/test_templates.py
and tests/test_witness.py; 0 files under satassume/ or rust-spike/slice/ source. The two older tests now take their
own classes' keys off the default registry in a `finally`; test_witness.py has an autouse fixture that takes every
user's template and declared module off the default registry before each test and puts them back, and one kept test,
`test_a_template_left_on_the_default_registry_makes_the_check_fall_through` (103 ids, was 102). No assertion changed.

786410d's `users_knowledge` fixture also put back a copy of the registry's lists taken before `register()` loaded the
built-in modules, so after the `[template]` case the templates of rootof, special, nodes and limits were gone for the
rest of the process: 21 ids fail after it in one process on 786410d (18 of tests/test_notmpl_limits.py, 3 of
tests/test_rootof.py; results/tools338/lost-templates-786410d-ids.txt), 0 on 81e6561e. `TemplateRegistry` has no
unregister; other test files that restore the registry by copy were not searched for.

### Suite by id on 81e6561e against base 32ba9a3 (pareto1, shared lease, 3 workers a suite)

| backend | on | off | base | on against off | off against base |
|---|---|---|---|---|---|
| python | 6221 passed, 0 failed | 6221 passed, 0 failed | 6118 passed, 0 failed | 0 ids differ | 0 ids differ |
| rust | 6094 passed, 127 failed | 6095 passed, 126 failed | 5991 passed, 127 failed | 1 id differs | 1 id differs |

The 103 ids of tests/test_witness.py are absent on base and pass in all four cells. The one Rust id is
`test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence` (base failed `assert 0 ==
2`, off passed, on failed `assert 1 == 2`): the known id()-reuse failure, classified again below. Quiet handler
catches: rust 49 in 9 ids and 39 handler rows in each of on, off and base; python 10 in 7 ids and 0 rows in each.

The 24 one-process order runs of test_templates.py, test_p4_review.py and test_witness.py on 81e6561e (rust and
python, switch off and on; the two once-leaking tests first, last, interleaved, and three shuffles): 538 passed and
the seven 7 of 7 in every run; no NOT-PASSED line.

### The repeat check on 81e6561e (a28c548's method, pareto1, 20 fresh processes a cell)

| backend | cell | switch off | switch on |
|---|---|---|---|
| Rust | plain | 0 of 20 pass (15x `assert 0 == 2`, 5x `assert 1 == 2`) | 0 of 20 pass (18x, 2x) |
| Rust | keep-alive | 20 of 20 | 20 of 20 |
| Python | plain | 20 of 20 | 19 of 20 (1x `assert 1 == 2`) |
| Python | keep-alive | 20 of 20 | 20 of 20 |

Every failure is at `test_public_incremental.py:204`; plain fails and keep-alive is clean, so it is the known
id()-reuse failure, reported by id and not edited. All 160 runs imported the staged tree and .so cad764d4; the
switch read True in the 80 on-runs. Python fails it only with the switch on, 1 of 20, as on 786410d (section 7).

### The bar on 786410d (sa-port-337's rerun, pareto0, 09:42Z to 11:12Z 19 Nov, `END 0`)

The bar is valid: build.txt has the clone's .so at cad764d4, direct.txt ends `exit 0`, "suite: no rows" is absent, 72
test files exit 0, every phase exit 0.

- Plain suite (rust, switch off): 127 failed, 6093 passed; against base (sa-port-334's bar suite) new 102 (test_witness.py),
  gone 0, changed outcome 0. The 127 are the base's rows by id: test_lra_fuzz.py 43, test_solver_incremental.py 36,
  test_solver.py 14, test_theory_hooks.py 10, test_euf.py 7, test_euf_fuzz.py 4, test_writeback_provenance.py 3,
  test_solver_real_theories.py 3, test_transfer.py 2, and 1 each in test_verify_integration.py, test_template_tables.py,
  test_relations.py, test_public_incremental.py (the planted-history test) and test_lra_exhaustion.py. Handler rows 39
  in 2 tests, the same multiset as base; TermFault 0.
- Live: dev and fuzz MATCH py against py, py against rust, and both end-state rows (answers 31cd0945c07f02a6 and
  173502b6ef285ad6); the 15 extra workloads: 30 rows MATCH. Handler files of the workload runs: 0 rows each.
- `witness:on` (rust with the switch on against Python with the switch on): MATCH on all 17 workloads; against
  Python with the switch off, answer_diff 0 and msg_diff 0 on all 17 (sessions differ where the check certified,
  161 on dev). The witness rows have no plant-fired counter (their `fired` column is 0 by construction; owed, [147]).
- Plant rows on workloads: 749 integer-half DIFFER on dev, fuzz, core, wiring, zero (answers 12, 3, 15, 7, 1);
  750 single on dev, fuzz, budget, core, transfer:7:60, wiring, zero (627, 208, 9, 49, 8, 645, 102); 751 skip-own on
  core and zero (21, 1); 752 skip-patched and 754 skip-users MATCH on all 17, as section 4 says they must.

Suite rows with the switch on, against the bar's plain suite, by worker (`rows.PID.jsonl` is in run order; tools339/
workers339.py, workers-337bar-786410d.txt):

| row | changed ids | which worker ran what |
|---|---|---|
| suite (off) | 0 | both leaking tests in one worker with no test_witness.py id; `[template]` in a worker with none of the 21 |
| witness:on | 7, the seven of section 8, all `passed -> failed` | one worker ran test_p4_review.py's leaking test (position 568) and then all 102 ids of test_witness.py (837 to 938); none of the 21 ran in that worker, so **0 of the 21 show** |
| 749 integer-half | 25 | no leaking test before any test_witness.py id; 6 of test_witness.py fail, the same 6 as on 81e6561e below |
| 750 single | 297 | a leaking test before 90 of the ids; caught by answers in any case |
| 751 skip-own | 12 | a leaking test before 90 of the ids: the 7, plus `test_falls_through[p1-a1]` and `test_own_assumptions_bound_the_points` |
| 752 skip-patched | 3 | `test_history.py::test_ddmin_shrinks_to_the_responsible_query` fails (its worker ran it before any leaking test: a clean catch). The 12 P1 cases ran after test_templates.py's leaking test in their worker and **all pass under the plant**: the leaked template made the check fall through, so the plant was masked. `[default-registry]` fails there from the leak |
| 754 skip-users | 6 | the five users'-knowledge cases fail, but in a worker that ran a leaking test first, where they fail with no plant too (the witness:on row): **this row does not show the plant caught** |

In no row did any of the 21 ids run after `[template]` in its worker, so the 21 fail nowhere in this bar. The
planted-history test flips `failed -> passed` in the 749, 752 and 754 rows and stays failed in the others (the flake
above). So on 786410d the bar's suite rows show 752 caught by test_ddmin only and do not show 754 caught; that is the
leak, and the next table is the evidence for the plants.

### test_witness.py under each plant on 81e6561e, SLICE_WITNESS=1, one process

| plant | orion, python | pareto1, python | pareto1, rust (.so cad764d4) |
|---|---|---|---|
| none (switch on) | 103 passed | 103 passed | 103 passed |
| none (switch off) | 103 passed | 103 passed | 103 passed |
| 749 integer-half | 6 failed | 6 failed | 6 failed |
| 750 single | 45 failed | 45 failed | 45 failed |
| 751 skip-own | 4 failed | 4 failed | 4 failed |
| 752 skip-patched | 9 failed (the 9 P1 cases) | 9 failed | 9 failed |
| 754 skip-users | 6 failed (the five users'-knowledge cases and the new kept test) | 6 failed | 6 failed |

Each plant fails at least one kept test and the file passes with no plant, on both backends. Every run printed the
frozen tree it imported, the switch and the plant. Outside test_witness.py, test_ddmin also fails under 750 and 752
(python and rust).

### Wall times of the bar (wall336.py; one machine, shared lease, rows of a phase side by side)

Total 90 m 07 s: tests 2 m 23 s, suite 1 m 53 s, live 14 m 47 s, plants 11 m 11 s, extra 48 m 09 s, suite plants
10 m 46 s, fmrows 0 m 57 s. Suite rows 1 m 45 s to 1 m 53 s each. `witness:on` workload rows, seconds: fuzz 605,
budget 393, rootof 374, wiring 320, value 89, dev 65, f6 63, zero 48, core 31, transfer2:3:40 14, transfer:7:60 12,
opaque 10, loop 7, scope 4, cert 2, cls 2, twin 0 (sum 2039; the plant rows sum 1438 to 2026). These are not the
speed measure: S1 (section 5) is.

### What is open

The planner's condition for this landing: a question if the bar's suite rows show anything other than the 21 ids
and the known base rows. They show the 7 instead of the 21. The 7 are the ids of section 8, they fail only in
workers that ran a leaking test first, and on 81e6561e they pass in 24 order runs and in the suite by id on both
backends. Whether that meets the condition is the planner's to say; nothing is landed.
