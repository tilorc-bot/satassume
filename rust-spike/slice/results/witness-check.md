# The witness check: an exact pre-session check for None answers (issue 323, prototype)

NOT LANDED, no PR. Branch `report/witness-check` (sa-port-328 to 331, 18-19 Nov), base rust-slice e5db633.
`SLICE_WITNESS` is off by default and the unchanged path is the default. With `SLICE_WITNESS=1`, a contextual query
is first given to `satassume.witness.independent`, which returns True only when it holds two exact rational points
that satisfy the assumptions and give the proposition both values; the query then returns None without a session.
No SymPy object is constructed and nothing of SymPy's is evaluated at query time: the check reads `type`, `args`,
`Rational.p`/`.q` and `assumptions0`.

**Result.** With the switch on, every answer of every workload is equal to the answer with the switch off, on both
backends. The check removes 1604 of 30482 engine queries over the 20 workloads (5.3%), 1060 of them in fuzz; 8
workloads have a certified query. Wall time at cap 32 (S1, reported, not a gate): Python dev -3.9%, fuzz -28.3%;
Rust dev +0.5%, fuzz -19.0%. **Proposal: land it in Python behind the switch, off by default, cap 32; the sized
follow-up is a Rust port of the per-call part** (section 9).

## 1. Tested SHAs and what each number rests on

| what | SHA | where |
|---|---|---|
| 20-workload gate, iv history check, cost split per call | 5e6e46a | pareto1, .so 45f63fdfb8e8523c |
| 20-workload gate from a frozen copy, dev and fuzz digests, test_witness.py, plants 749-752, repeat check | c5239b9 | orion, .so a188b7fa95f27a88 |
| S1 wall time and the certified counts | 47b7a0d | pareto1, pinned CPU 2, .so 45f63fdfb8e8523c |
| suite by id against base (e5db633) | c5239b9 | pareto0, .so 45f63fdfb8e8523c |

- c5239b9 is the function SHA. Against 5e6e46a it adds the P1 guard (section 3), the layer and the removal of the
  module-level SymPy import; against 47b7a0d, 5e6e46a changed only which derived predicates are decided (section 3),
  no workload query mentions `hermitian` or `antihermitian`, and the one dev query with a `commutative` atom does not
  reach the check, so 47b7a0d and 5e6e46a return the same value on every workload query.
- S1 is on 47b7a0d and was not re-measured after the P1 guard, which costs about 2 us per certified query (2.2 us by
  orion timeit; 159 dev and 1060 fuzz queries: about 0.35 ms and 2.3 ms, under 0.1% of either pass). The cost split
  was not re-measured on c5239b9 either.
- S1 is reported, not a gate. Shares from shared-lease runs are not wall times. In the cap table the rows other than
  32 and none are a model, not measurements.
- "Exact" rests on sa-port-325's table of the 14 basis predicates and its one-line arguments (origin
  `report/none-certify`, `exact325.py`), carried as the comments of `witness.TABLE`. Issue 247 applies: SymPy
  evaluation is not ground truth, and neither is the table; it is short enough to review.
- sa-port-328's gate on orion ran across the function change (47b7a0d to 5e6e46a in the worktree it imported from)
  and is not the gate.

## 2. The gate: answers equal, per workload

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

### Suite by id against base

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

## 4. Plants 749-752

Each is `SLICE_WITNESS_PLANT` with the switch on, c5239b9, orion, frozen copy. "Tests" is of 133: test_witness.py's
97 and the 36 of test_history.py's two tests that patch `Engine.ask` and test_public_incremental.py. Each catching check asserts behaviour and reads no plant flag.

| plant | what it breaks | caught by answers | caught by tests |
|---|---|---|---|
| 749 integer-half | `integer` is True at a half | dev digest ff3a586753ddcf94, fuzz f10fca19a50daa53 (base 31cd0945c07f02a6, 173502b6ef285ad6) | 6 fail, among them `test_integer_is_false_at_a_half` |
| 750 single | one witness is taken as a pair | dev 52d6bc53c55fc204, fuzz 92fcf1f54e0699c5 | 40 fail, among them `test_one_witness_is_not_enough` |
| 751 skip-own | the symbols' own assumptions are not read | the 20-workload gate on 5e6e46a under the plant: 6 rows differ, ground (query 15: True off, None on), zero (query 844: True, None) and core (21 queries, False off, None on), py and rust alike | 4 fail: `test_falls_through[p1-a1]`, `test_own_assumptions_bound_the_points`, `test_the_symbols_own_assumptions_count`, `test_answers_are_equal_on_and_off[27]` |
| 752 skip-patched | the P1 guard is skipped | none: dev and fuzz digests unchanged, since no workload replaces an engine method | 10 fail: 9 of the 12 cases of the P1 test, and `test_history.py::test_ddmin_shrinks_to_the_responsible_query` |

- 750: 30 tests failed on f46e40e and 40 on c5239b9. The 10 more are the 9 P1 cases and test_ddmin: the plant's
  early return now comes before the guard, which c5239b9 moved to the end.
- 751: dev and fuzz cannot reach it. Fuzz declares no symbol (0 of 3000 queries), and dev has 12 queries whose
  symbol's own assumptions exclude a candidate value, none of which changes the certified set. Three other workloads
  reach it, as the gate under the plant shows.
- 752 is a kept-test catch. No workload reaches it because no workload replaces `ask`, `verdict`,
  `_context_session` or `_within_budget`. The 3 `verdict` cases pass under the plant because that query's verdict
  calls come from relevance, before the check.

## 5. Measures

S1 (47b7a0d, sa-port-328's quiet lease on pareto1, pinned CPU 2, 12 rounds, load <= 1.16, one digest per workload
over all 144 rows), median seconds:

| | off | cap 32 | no cap |
|---|---|---|---|
| dev, Python | 0.5318 | 0.5113 (-3.9%) | 0.6409 (+20.5%) |
| dev, Rust | 0.6538 | 0.6570 (+0.5%) | 0.7872 (+20.4%) |
| fuzz, Python | 8.0716 | 5.7886 (-28.3%) | 6.6789 (-17.3%) |
| fuzz, Rust | 5.9141 | 4.7887 (-19.0%) | 6.2133 (+5.1%) |

Rust is `SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust`. There is no S1 for the other 18 workloads.

Counts (identical py and rust, 47b7a0d, 5e6e46a and c5239b9). The check is called at most once a query: dev 776,
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

Every failure is at `test_public_incremental.py:204`. Plain fails, keep-alive is clean, and the off rate is the
same: the flake's shape, so it is the known id()-reuse failure, reported by id and not edited. On f46e40e the same
table read 0 of 20 and 1 of 20 for Rust plain and 20 of 20 in the other six cells. One earlier row differs:
sa-port-329's run on 5e6e46a (pareto1, plain only, before the P1 guard) had Python at 20 of 20 off and 18 of 20 on,
both failures `assert 1 == 2` at the same line. It had no keep-alive cell, so it classifies nothing alone, and
the 40 Python plain on-runs on f46e40e and c5239b9 did not repeat it.

## 8. The one test that fails with the switch on

`tests/test_sympy_api.py::test_in_scope_query_returns_none_only_when_undecided`, on both backends:

    assert out_of_scope(Q.positive(y), Q.real(y)) is None
    assert ask(Q.positive(y), Q.real(y), eng) is None
    assert eng.stats['queries'] == 1

It fails at the third line, `assert 0 == 1` (`:210`); the answer on the second line is None as before. That is state,
not an answer: `stats['queries']` is incremented inside the engine's own methods, and a certified query never calls
them, so the engine's counter counts it nowhere. The test uses the counter to show the None came from the engine
and not from the scope filter. README.md and docs/ do not state the counter as a contract (docs/testing.md only says
to check the query log's totals against it, and a certified query is in neither). A landing with the switch on by default would
have to decide whether a certified query is counted, and where; with the switch off the test passes.

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

- S1 and the cost split on c5239b9 (the P1 guard).
- The iv history check on c5239b9 (run on 5e6e46a only).
- Whether a certified query is counted in `Engine.stats` (section 8), before the switch could be the default.
- Detection of user-registered templates (decision (f) covers `extensions` only).
- The quiet-handler counter in the gate runs was not shown to fire (section 2).
- No bar was run: nothing here was landed.

## 11. Where the numbers are

- Handoffs: `~/sa-rust-ids-work/sa-port-328/HANDOFF-sa-port-328.md`, `sa-port-329/HANDOFF-sa-port-329.md`,
  `sa-port-330/HANDOFF-sa-port-330.md`.
- Gate 5e6e46a: pareto1 `~/sa-rust-ids-work/sa-port-329/job/gate/` (`answers.txt`, `rc.txt`); under plant 751
  `job/gate-751/answers.txt`. Gate c5239b9: orion `~/sa-rust-ids-work/sa-port-330/c5239b9/gate/`; digests `dig/`,
  tests and plants `tw/`, repeat check `rep/rep-sum.txt`.
- Suite by id: orion `~/sa-rust-ids-work/sa-port-331/job-c5239b9/` (`suite-cmp.txt`; rows from pareto0
  `~/sp19/sa-rust-ids-work/sa-port-331/job-c5239b9/`), `job-f46e40e/suite-cmp.txt`; 5e6e46a's: `sa-port-329/job/suite-cmp.txt`.
- iv: `sa-port-329/job/iv-cmp.txt`. S1: `sa-port-328/timing-r1`. Cost split and reasons: `sa-port-329/cnt/ana.txt`.
  Cap: `sa-port-330/cap/cap.txt`.
- Tools: `rust-spike/slice/results/tools328/` (`*328*`, `*329*`, `*330*`, `*331*`).
