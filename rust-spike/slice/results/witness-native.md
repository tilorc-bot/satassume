# The witness check in Rust (issue 323) — (1) the profile, (2) the port, (3) the same behaviour, (4) the plant rows, (5) S1, (6) the count rule; item 7 open

Planner's ruling for sa-port-350 (20 Nov, on sa-port-349 52bdf2d), items 1-7. This file takes them in order. State:
items 1 to 6 done (items 1 to 3 measured on b79f6657, items 5 and 6 on b7302f83, on rust-slice 6ee354f9); no bar read and nothing landed. SLICE_WITNESS stays off
by default, Python's witness.py the default and the reference, the unchanged path the default.

## (1) Profile before building, sa-port-350: 6ee354f9, quiet leases on pareto1

Leases 9bfc7252 (00:19Z to 00:23Z 20 Nov; dev and fuzz) and ed799a94 (00:33Z to 00:35Z; wiring), load at most 1.05;
bench-container, CPU 2, sa-eval-bench:1, S1's environment (sa-port-347's s1/common); 5 rounds, cold processes
alternating inside one invocation (tools350/prof350.sh, onlease350p.sh, goprof350.sh; the table by tab350.py). Tree:
the archive of 6ee354f9 with the bench .so 0982a28074215658 (786410d's build; the crate is source-equal, checked).
One digest per workload on every arm, S1's: dev 31cd0945c07f02a6, fuzz 173502b6ef285ad6, wiring a0df9fd43e5180c1.
"rust" is the slice with both Rust switches on (SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust); on = SLICE_WITNESS=1 at
cap 32 and the tree's work bound 2500.

The driver is tools350/prof350.py (tools328/wit328.py with phases). It times from its own process: the package has
no timer. Three kinds of pass: **plain** wraps only `witness.witnesses` (two clock reads per check), and its
`check s` is the check's inclusive time; **phase** wraps the phases as well; **cprof** enables cProfile only inside
`witnesses`. Seconds are medians of 5 rounds of the plain pass; the four phase columns are the phase pass's split of
its own check time (its timers add 6% to 17% to the check, "timer calls" is how many pairs of clock reads one pass
makes, so the split is a ratio and not a time). These are profile times, not S1 times.

| workload, mode | off s | on s | on/off | fires | compiled | certified | check s | share of on | fall-through s | share of on | compile | search | evaluation | guards | moves (share of on s) | timer calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev py | 0.5274 | 0.5213 | -1.1% | 776 | 535 | 173 | 0.0629 | 12.1% | 0.0493 | 9.5% | 14% | 43% | 40% | 4% | 11.6% | 27767 |
| dev rust | 0.6408 | 0.6602 | +3.0% | 776 | 535 | 173 | 0.0698 | 10.6% | 0.0540 | 8.2% | 15% | 42% | 39% | 4% | 10.1% | 27767 |
| fuzz py | 8.0565 | 5.4143 | -32.8% | 2772 | 2732 | 1284 | 0.7902 | 14.6% | 0.4920 | 9.1% | 6% | 41% | 51% | 2% | 14.3% | 206237 |
| fuzz rust | 5.8443 | 4.6582 | -20.3% | 2772 | 2732 | 1284 | 0.8453 | 18.1% | 0.5226 | 11.2% | 7% | 41% | 50% | 2% | 17.8% | 206237 |
| wiring py | 2.7055 | 2.9815 | +10.2% | 4814 | 1503 | 215 | 0.3157 | 10.6% | 0.3013 | 10.1% | 24% | 25% | 49% | 2% | 10.4% | 91850 |
| wiring rust | 3.2137 | 3.5832 | +11.5% | 4814 | 1503 | 215 | 0.3429 | 9.6% | 0.3260 | 9.1% | 25% | 26% | 47% | 2% | 9.4% | 91850 |

Columns: *fires* the calls of the check; *compiled* those
that reached the point search; *check s* inclusive seconds inside `witnesses`; *fall-through s* the part spent on
queries the check did not certify, which is what the check costs with nothing saved; *compile* from the entry of
`witnesses` to the first guard (the two `_formula` walks, the second compile of a query with pi, `_own`);
*evaluation* the probes' functions inside `_roots` plus `_holds` (the closures, Fraction and _PiPoly arithmetic, the
tables, the own assumptions at a point); *search* the rest (`_pools` without its probe evaluations, `_by_index_sum`,
the loop); *guards* `_patched`, `Engine._known_inconsistent` and `_users_knowledge`, which read the engine and stay
Python in the port; *moves* the check's time without the guards, as a share of the pass.

Own against inclusive (the cprof pass; cProfile charges every Python call, so this is call-weighted time under the
check, not wall time): witness.py's own frames are 58% (dev), 44% (fuzz) and 47% (wiring) of the time under the
check; fractions.py 17%, 32%, 24%; builtins (isinstance, all, set.add, and the profiler's own switch at 5%) 23%, 21%,
26%; engine.py 0.1% to 0.3%; everything else at most 3.1%. The same on py and rust within one point. So in wall
terms the check's own share of a Rust pass is about 6% (dev), 8% (fuzz), 4.5% (wiring), against the inclusive 10.6%,
18.1% and 9.6% of the table; the callees are Fraction arithmetic and builtins, which the port moves with it.

What one phase pass counted (round 1, the same on py and rust): term evaluations charged (`spend`) dev 63,337, fuzz
1,610,808, wiring 911,664; queries past the work bound dev 0, fuzz 2, wiring 294; second compiles for pi dev 42,
fuzz 530, wiring 0; points decided (`_holds`) dev 11,447, fuzz 61,692, wiring 30,278.

Read against the stop rule ("if the share that would move can't plausibly beat the S1 spread on wiring and on Rust
dev, stop"):

- **wiring, rust: 9.4% of the pass would move**, against an S1 interquartile share of 1.5% (witness-bounds.md (5);
  1.2% here). The check's inclusive time, 0.343 s, is nearly all of wiring's cost of the switch (on against off
  +0.37 s, +11.5%): 95% of it is spent on the 4,599 queries it does not certify.
- **dev, rust: 10.1% would move**, against 1.7% (0.8% here). On against off is +3.0% here because the 173 certified
  queries save their sessions; the check itself costs 0.070 s of a 0.660 s pass, 0.054 s of it on fall-through.
- fuzz, the control: 17.8% (rust), 14.3% (py) would move.
- The check's own time is 7% to 11% longer in a Rust pass than in a Python pass on the same queries (dev 0.0698 s
  against 0.0629 s, fuzz 0.845 against 0.790, wiring 0.343 against 0.316); compile, search and evaluation each carry
  it (round 1's raw phase seconds: the tools350 rows). The profile does not say why.

The first pass also asked for wiring by evalbench's name, which it does not have (32 KeyError lines in its err.txt, no
row written); prof350.py now loads it as tools342/qt342.py does, and the second lease ran it. No other error output.

**So the stop rule does not trigger, and the port goes ahead.** A native check at a tenth of Python's time would give
about 8% to 9% on wiring and on Rust dev; it needs a factor of about 1.2 on either only to pass the spread. What does not move: the guards, 2% to 4% of the check (0.1% to 0.4% of a pass).

What the reading of the code adds (not measured): under the slice the query's native term table already exists when
the check runs (`term_live._ask` converts before it calls `sympy_api._ask`), so a native check needs no walk of its
own; and the table is there under either walker. HANDOFF-sa-port-350.md has the design notes and the file:line map.

## (2) The port, sa-port-351 (338e6a30) and sa-port-352 (6746bfe3): SLICE_WITNESS_RUST=1

`solver_rs/src/witness.rs` (1036 lines after 352's pass for lines the reference does not need) behind the hook
`satassume.witness.NATIVE`, set by the slice's `witness_live.py`. The switch acts only with SLICE_WITNESS=1 and
SLICE_CONVERT=rust, as ruled; the code does not need the tie (test_witness_native.py passes under the Python walker
too), so a later step can drop it with a gate of its own. No new crate: one Rat over BigInt (`term/rat.rs` gained sub,
div, pow, bit lengths and sign) and the Q[pi] enclosure as exact rational bounds. No float in any decision, and no
SymPy construction or evaluation at query time. "Exact" rests on 325's 14-predicate table and 2030cdc6's Q[pi]
arguments (issue 247: SymPy's evaluation is not ground truth), which the native table mirrors
(test_the_native_table_is_pythons, test_the_native_definitions_are_the_rules).

- Native: the compile on the query's own term ids (choice B: the `P` formula is read once and each atom side is one
  lookup in the query's `ids`), the pools, the search, and the second decision on the two points. Nothing is kept
  across queries: the compiled query dies with the call (test_nothing_native_outlives_the_call). The enclosure's
  powers are a `OnceLock` static and `witness_live._CLASSES` and `_OWN` are module constants: none is query state.
- Python, by design (P1): `witness._patched`, `Engine._known_inconsistent` and `witness._users_knowledge`, each at
  the place witness.py calls it.
- **B's lookup is `==` plus an exact type check.** `ids` matches by hash and `==`, so a Python `int` or `bool` side
  finds an Integer's row (`{Integer(3): 1}.get(3)` is 1), while witness.py leaves such a side undecided. The found
  row's object must have the side's own type; otherwise the whole query goes to witness.py (`wn:fallback:type`).
  Plant 763 removes the comparison.
- To witness.py, each counted: `wn:fallback:miss` (a side not in the table), `:type` (above), `:shape` (a formula
  shape that is not mirrored), `:off` (no table, a witness.py plant set, or a replaced function of witness.py: (3)).
- `_roots` visits a probe's symbols in index order where Python follows its set's order; the charges within a probe
  are equal per symbol, and the per-call work comparison below confirms it. A certified query makes one table read per
  symbol (`symbol_facts`, memoized) where witness.py read `assumptions0`, so SLICE_TERM_COUNTS read counts can differ
  from a run under the Python check; Engine.stats does not.

## (3) The same behaviour, sa-port-352 and sa-port-353: source b79f6657

.so: orion e0365239348de148, pareto venv 37b7560e245df518, bench 0b6f073f5c5a600b (the crate is unchanged since
6746bfe3 and both pareto builds of b79f6657 reproduce 352's hashes). Tools: tools352 (run with S=sa-port-353), rows
under ~/sa-rust-ids-work/sa-port-353.

**Two failures by id came with the port, and both are fixed in b79f6657.**
- `tests/test_history.py::test_module_state_inventory_is_classified` (every cell: `witness.NATIVE` unclassified).
  NATIVE is now in harness/state.py's MODULE_CONFIG, next to the check's switch: one slot that holds None or a
  backend's entry function, set at install from the environment, written by no query.
  `tests/test_history.py::test_the_witness_checks_native_hook_is_configuration` asserts that across a certified and a
  fall-through query.
- `tests/test_witness.py::test_a_set_the_engine_knows_inconsistent_tries_no_point` (`assert 0 > 0`), the one id the
  native cell failed beyond the Python check's cell on 6746bfe3. It is a native-path failure: the test counts points
  through a wrapper it puts in place of `witness._holds`, which the native path never calls. The hook now compares
  witness.py's own functions and classes (23 names: all but the two entry points and the guards, which witness.py
  calls by name anyway) with what they were at import, by identity, before its compile. One replaced sends the query
  to witness.py (`wn:fallback:off`): what a test or an instrument put there is called, as P1 has it for a user's
  method. Plant 764 `wn-skip-own` passes the comparison over and fails
  test_a_replaced_function_of_witness_py_is_called. The cost is 23 dictionary reads per call of the check; they are
  reads of witness.py's module dictionary, not calls. The new rule also showed that
  test_the_work_bound_trips_on_the_same_evaluation would have compared witness.py with itself (it kept a subclass in
  place of `witness._Query`; plant 761 was no longer caught): the test now restores `_Query` first and asserts that
  the native search ran. An instrument of ours that must keep the native path on re-reads `_OWN` after installing
  (diff352.py does).

**Per query, the 20 workloads and fuzz seeds 0/1/2/42** (job352a.sh on b79f6657, orion; the table is identical to
352's on 6746bfe3). Arm diff runs every call of `witnesses` natively and then by witness.py and compares the result,
the two points, the points tried, and where the native side compiled the size, pi and the work charged: 0 mismatches
in 23,156 calls. Arms native against python (cmp352.py), per query: the answer, Engine.stats (witness_certified among
them), last_budget_limited and every `witnesses` result (the certified set with its points): 0 queries differ on all
24; the three arms' answer digests are equal.

| workload | queries | calls | certified | diff: mismatches | compiled | searched | lookups | fallback miss/type/shape/off | share | digests equal | per query differ |
|---|---|---|---|---|---|---|---|---|---|---|---|
| lra | 1500 | 1115 | 1 | 0 | 21 | 16 | 1999 | 0/0/0/334 | 30.0% | True | 0 |
| f6 | 2902 | 4 | 0 | 0 | 0 | 0 | 8 | 0/0/0/0 | 0.0% | True | 0 |
| wiring | 6512 | 4814 | 215 | 0 | 1503 | 1503 | 34626 | 0/0/0/0 | 0.0% | True | 0 |
| scope | 169 | 166 | 0 | 0 | 0 | 0 | 0 | 0/0/0/0 | 0.0% | True | 0 |
| dev | 1985 | 776 | 173 | 0 | 535 | 535 | 3032 | 0/0/0/0 | 0.0% | True | 0 |
| fuzz | 3000 | 2772 | 1284 | 0 | 2697 | 2657 | 19501 | 75/0/0/0 | 2.7% | True | 0 |
| ground | 18 | 14 | 4 | 0 | 14 | 14 | 80 | 0/0/0/0 | 0.0% | True | 0 |
| port | 19 | 19 | 0 | 0 | 19 | 19 | 94 | 0/0/0/0 | 0.0% | True | 0 |
| loop | 420 | 244 | 0 | 0 | 0 | 0 | 0 | 0/0/0/0 | 0.0% | True | 0 |
| zero | 854 | 699 | 52 | 0 | 105 | 100 | 2408 | 0/0/0/0 | 0.0% | True | 0 |
| cert | 61 | 61 | 1 | 0 | 61 | 61 | 636 | 0/0/0/0 | 0.0% | True | 0 |
| budget | 28 | 19 | 0 | 0 | 19 | 19 | 171 | 0/0/0/0 | 0.0% | True | 0 |
| core | 1636 | 299 | 95 | 0 | 186 | 186 | 566 | 0/0/0/0 | 0.0% | True | 0 |
| opaque | 2546 | 30 | 0 | 0 | 0 | 0 | 60 | 0/0/0/0 | 0.0% | True | 0 |
| rootof | 5187 | 368 | 0 | 0 | 0 | 0 | 736 | 0/0/0/0 | 0.0% | True | 0 |
| value | 3742 | 636 | 0 | 0 | 0 | 0 | 1590 | 0/0/0/0 | 0.0% | True | 0 |
| twin | 2 | 2 | 0 | 0 | 0 | 0 | 4 | 0/0/0/0 | 0.0% | True | 0 |
| transfer:7:60 | 60 | 60 | 2 | 0 | 14 | 14 | 190 | 0/0/0/0 | 0.0% | True | 0 |
| transfer2:3:40 | 40 | 40 | 1 | 0 | 6 | 6 | 144 | 0/0/0/0 | 0.0% | True | 0 |
| cls | 72 | 21 | 0 | 0 | 0 | 0 | 36 | 0/15/0/0 | 71.4% | True | 0 |
| fuzz0 | 3000 | 2753 | 1320 | 0 | 2696 | 2661 | 19284 | 57/0/0/0 | 2.1% | True | 0 |
| fuzz1 | 3000 | 2752 | 1322 | 0 | 2694 | 2659 | 19294 | 58/0/0/0 | 2.1% | True | 0 |
| fuzz2 | 3000 | 2750 | 1316 | 0 | 2688 | 2654 | 19322 | 62/0/0/0 | 2.3% | True | 0 |
| fuzz42 | 3000 | 2742 | 1283 | 0 | 2686 | 2659 | 19139 | 56/0/0/0 | 2.0% | True | 0 |

totals: calls 23156, fallbacks 657, diff mismatches 0, queries that differ 0; .so ['e0365239348de148']

**Fallbacks to witness.py, and why.** dev, wiring and budget: 0, so the bar the planner set (dev and wiring) holds.
- fuzz 2.7% (75 of 2772), seeds 2.0% to 2.3%: all `miss`, a side that is not in the query's table (a derived or
  scaffolded form).
- lra 30.0% (334 of 1115): all `off`, and all are the second run of a query the slice refused. On lra the slice
  refuses 456 queries mid-run (scaffold: rebuilt form differs from Rust 187, mul: factors share a base 188, mul: a
  coefficient beside a numeric-base power 35, algebra: holds an infinity, nan or Float 42, termwise 3, lra callback 1),
  rolls each back and runs it again on Python as `_Refused`, which has no table by design ("a consumer stays on
  Python"). 334 of those second runs reach the check, which then has nothing to look sides up in. The first, discarded
  run did use the native check. So on lra the native check saves nothing on a refused query.
- cls 71.4% (15 of 21): all `type`, and none is an int or a bool. Each is a side `f(a)`, `g(a)` or `h(a)` whose
  class is another `Function('f')` object than the row's: same name, `==`, not the same object (5 calls per name;
  ~/sa-rust-ids-work/sa-port-353/why_type.py). witness.py does nothing different with such a side (it returns None on
  all 15: an applied undefined function is not evaluated); it is only that the exact type test cannot tell an equal
  class with another identity from the int against Integer case. **cls gets no gain from this port**; it certifies
  nothing on cls either way (0 of 21).
- every other workload: 0.

**R5, a discarded run** (disc352.sh on b79f6657; fresh.py --term terms --lra --full --discard with the native check
on; identical to 352's table): dev 1985 rollbacks checked, 1985 clean; lra 1957 of 1957; fuzz 3000 of 3000; only the
exempt _CACHE is left; answers and session digests equal a plain run's on all three. The discarded runs held native
work (discard minus plain: dev 727 compiles and 521 searches, fuzz 1209 and 1175, lra 622 and 11). The plant
--no-rollback: 300 checked, 0 clean. term_discard.py wraps Engine.verdict, which the P1 guard takes for a user's
method, so **fresh.py (a shared harness file) changed**: with SLICE_WITNESS_RUST=1 only, it reads the convert and
native switches and accepts that wrapper as an instrument (`witness.accept`); otherwise it is untouched.

**The suite by id** (pareto0, shared lease 49c6c9c8, suite352.sh; cells nat, wit, off on b79f6657 and base on
6ee354f9, Rust backend, 6317 ids, 6316 on base):

| cell | switches | failed | passed | quiet catches (engine.py:1906) |
|---|---|---|---|---|
| nat | SLICE_WITNESS=1 SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust SLICE_WITNESS_RUST=1 | 127 | 6149 | 49 |
| wit | the same without SLICE_WITNESS_RUST | 127 | 6149 | 49 |
| off | none | 127 | 6149 | 49 |
| base | none, 6ee354f9 | 127 | 6148 | 49 |

The failed ids are the same 127 in all four cells: this invocation's base rows (test_lra_fuzz 43,
test_solver_incremental 36, test_solver 14, test_theory_hooks 10, test_euf 7, test_euf_fuzz 4,
test_solver_real_theories 3, test_writeback_provenance 3, test_transfer 2, and one each in test_template_tables,
test_relations, test_verify_integration, test_public_incremental and test_lra_exhaustion). The only id not on base is
the new test, which passes. The planted-history test
(`tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence`, :204,
`assert N == 2` with N < 2: the known id()-reuse failure, [137e]) fails in all four cells, base among them, so no
row flips and a28c548's repeat method was not run here. The nat cell ran the native check (34,199 compiles, 16,364
searches, 5,292 found; fallbacks miss 4, off 451); wit, off and base show no native counter.

**iv** (iv352.sh on b79f6657, 64 runs with the Python check and 64 with the native one): 0 runs differ in failing ids
or pass/fail counts. The Rust-backend runs that fail (16 per switch) fail the same two base ids in both
(tests/test_transfer.py::test_models_respect_transfer and ::test_protocol_on_fuzz); the Python-backend runs all exit
0. nat runs made 14,368 native compiles and 5,792 searches (fallbacks type 252, off 48); wit runs none.

## (4) Plants 760-764 and their bar rows, sa-port-353 (the bar itself is item 7)

Rows (tools353/job353bar.sh, through bar.sh's penv): `witness:on` (Python's witness.py, the reference), `wnative:on`
(no plant) and one row per plant, each with SLICE_WITNESS=1 SLICE_CONVERT=rust SLICE_WITNESS_RUST=1, as workload rows
and as suite rows; after the bar the job runs test_witness_native.py under each plant on the bar's tree (kept.txt).
No kept test reads a plant's flag: each compares the native side with witness.py on the same input, or reads the
fallback counters (P2).

| plant | site | what it does | fired dev / fuzz | dev, fuzz against Python | caught by |
|---|---|---|---|---|---|
| 760 wn-integer-half | witness.rs `pred` | a wrong table entry: integer at 1/2 | 403 / 343 | DIFFER, DIFFER | the workload rows; test_the_native_table_is_pythons, test_the_native_check_is_pythons_per_query |
| 761 wn-work-one | witness.rs `spend` | the work bound trips one evaluation early | 0 / 0 | MATCH, MATCH | test_the_work_bound_trips_on_the_same_evaluation |
| 762 wn-skip-patched | witness_live.py `native` | the P1 guard `witness._patched` passed over | 535 / 2697 | MATCH, MATCH | test_a_users_method_on_the_engine_is_left_to_the_engine |
| 763 wn-int-side | witness.rs `side` | the lookup's type check passed over | 3032 / 19426 | MATCH, MATCH | test_a_python_int_side_goes_to_python |
| 764 wn-skip-own | witness_live.py `_replaced` | a replaced function of witness.py passed over | 776 / 2772 | MATCH, MATCH | test_a_replaced_function_of_witness_py_is_called |

The numbers are an orion run of bar.sh's plants command on the worktree at this commit (tools353/rows353.sh; not the
bar and not a timing); `wnative:on` gives MATCH on both. Why a kept test and no workload:
- 761 fires only when a query's work count lands exactly on WORK (2500), and no query of dev or fuzz does (fired 0).
  The kept test sets WORK to the query's own count.
- 762: no workload puts a user's method on the engine. Its site is in witness_live.py because the guards stay Python
  by ruling (P1); that hook is the native path's entry, called once per query before the search.
- 763: no query of dev or fuzz has a Python int or bool as an atom side.
- 764: no workload replaces a function of witness.py; tests/test_witness.py does, so its suite row is expected to
  fail test_a_set_the_engine_knows_inconsistent_tries_no_point (to be read in the bar).

**The fired route for 762 and 764** (the planner asked which): their sites count in `witness_live.FIRED`, and that
reaches the bar through plant_count.py (a `wnative` entry, the suite rows) and through the session report's
`witness_plant_fired`, to which session_live.py's `_write_report` now adds it (the workload rows; **session_live.py
is a shared file**, changed by 3 lines). 760, 761 and 763 tick the crate's `rel:plant_fired`.

## (5) S1, sa-port-354: b7302f83 against 6ee354f9, quiet lease on pareto1

Lease ed51ef36 (04:51Z to 05:13Z 20 Nov, 22 minutes), load at most 1.19; bench-container, CPU 2, sa-eval-bench:1
(Python 3.12.15), S1's environment (sa-port-350's s1/common); 12 rounds, cold processes, 9 arms alternating inside
one invocation with the order rotated each round (tools354/time354.sh, onlease354.sh, gos1354.sh; the table by
med354.py, kept as tools354/s1-med.txt). Trees: the archive of b7302f83 with its own bench .so 0b6f073f5c5a600b
(stage352.sh rebuilt it and the pareto venv .so 37b7560e245df518: both hashes as on b79f6657, the crate is unchanged)
and the archive of 6ee354f9 with 0982a28074215658. "rust" is the slice with both Rust switches on; off is
SLICE_WITNESS=0, on32 SLICE_WITNESS=1 at cap 32 with Python's witness.py, **nat** on32 plus SLICE_WITNESS_RUST=1. The
timed driver is tools342/qt342.py, which wraps nothing of witness.py, so the native path stays on (`_replaced`). One
digest per workload on all 9 arms: dev 31cd0945c07f02a6, fuzz 173502b6ef285ad6, budget 35bc2c4a937bebc0, wiring
a0df9fd43e5180c1. After the rounds one counted pass per workload and arm (tools354/wn354.py): the nat arm holds
`witness_live.native` and counts `wn:compile` 776 on dev, 2,772 on fuzz, 19 on budget, 4,814 on wiring; every other
arm has no hook; certified is 173, 1,284, 0 and 215 on every switch-on arm, native or not.

Median seconds of 12 rounds (the interquartile range of every arm is 0.3% to 1.7% of its median):

| workload | base py off | base py on32 | base rust off | base rust on32 | head py off | head py on32 | head rust off | head rust on32 | head rust nat |
|---|---|---|---|---|---|---|---|---|---|
| dev | 0.5324 | 0.5233 | 0.6440 | 0.6610 | 0.5329 | 0.5225 | 0.6464 | 0.6632 | **0.6192** |
| fuzz | 8.0641 | 5.4324 | 5.8466 | 4.6429 | 8.0662 | 5.4237 | 5.8309 | 4.6392 | **4.1637** |
| budget | 0.4744 | 0.4932 | 0.3182 | 0.3346 | 0.4743 | 0.4940 | 0.3172 | 0.3338 | **0.3316** |
| wiring | 2.7340 | 3.0396 | 3.2370 | 3.5665 | 2.7421 | 3.0391 | 3.2557 | 3.5839 | **3.3850** |

"Beyond the spread" is med342.py's rule, unchanged: the ratio of the medians is outside 1 by more than the larger
interquartile share of the two arms, and the first arm is slower (or faster) in at least 10 of the 12 paired rounds.

**The landing rule holds.** Rust-on with the native check against Rust-on at 6ee354f9 (head rust nat / base rust
on32):

| workload | medians | per round, median (quartiles) | slower in | larger iqr | |
|---|---|---|---|---|---|
| dev | -6.3% | -6.2% (-6.4%, -5.8%) | 0 of 12 | 0.6% | faster beyond the spread |
| fuzz | -10.3% | -10.0% (-10.7%, -9.9%) | 0 of 12 | 1.5% | faster beyond the spread |
| budget | -0.9% | -1.0% (-1.4%, -0.7%) | 0 of 12 | 0.5% | faster beyond the spread |
| wiring | -5.1% | -5.0% (-5.6%, -4.6%) | 0 of 12 | 0.8% | faster beyond the spread |

Faster beyond the spread on wiring, and no worse on any of the four. Against the profile's "before" in (1), what
would move was 10.1% of Rust dev, 9.4% of Rust wiring and 17.8% of Rust fuzz: the port takes 6.3%, 5.1% and 10.3%
of the wall time. The rest of that share is still there as the guards, the hook, the lookups and the table's symbol
reads ((6)), and the native search itself.

**The unchanged paths stay within the spread**, head against base in the same mode and switch, all 16 rows: py off
+0.1%, +0.0%, -0.0%, +0.3% (dev, fuzz, budget, wiring); py on32 -0.1%, -0.2%, +0.2%, -0.0%; rust off +0.4%, -0.3%,
-0.3%, +0.6%; rust on32 +0.3%, -0.1%, -0.2%, +0.5%. The sum over the four workloads per round: -0.0% to +0.2% on
each of those four arms.

**On against off** (the default question), same tree and mode, medians; every row is beyond the spread:

| workload | rust: native check on / off | rust: Python's check on / off | py: Python's check on / off |
|---|---|---|---|
| dev | **-4.2%** (0 of 12 slower) | +2.6% | -2.0% |
| fuzz | **-28.6%** (0 of 12) | -20.4% | -32.8% |
| budget | **+4.5%** (12 of 12 slower) | +5.3% | +4.2% |
| wiring | **+4.0%** (12 of 12) | +10.1% | +10.8% |
| the four summed | **-15.2%** | -8.2% | -19.8% |

With the native check the switch turns from a cost into a gain on Rust dev, keeps and widens fuzz's gain, and still
costs on budget and wiring: wiring's cost falls from +10.1% to +4.0%, budget's is nearly unchanged (+5.3% to +4.5%;
budget makes 19 calls of the check, each reading the assumptions of about 200 symbols ((6)), and certifies none). So the check is not free
on the two workloads where it certifies little or nothing, with or without the port. Native against Python's check
in the head's own tree (rust nat / rust on32): dev -6.6%, fuzz -10.2%, budget -0.7%, wiring -5.6%, each beyond the
spread.

## (6) The count rule, sa-port-354: b7302f83, 20 workloads

Probe: tools354/pc354.sh with pcby354.py (sys.monitoring PY_START per code object; nothing of witness.py is wrapped
or replaced, so `_replaced` sees witness.py's own objects), pareto0, shared lease 0239cde5, 04:53Z to 04:55Z 20 Nov;
the staged trees of b7302f83 (.so 37b7560e245df518) and 6ee354f9 (.so cad764d46471b1c6); 20 workloads, 30,753
queries; 80 of 80 rows ref 0 run 0 cmp 0 (the answers equal Python's under the same SLICE_WITNESS). Cells: **d0**
every switch unset (the default), **w1** SLICE_WITNESS=1 SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust (Python's
witness.py on the path the native check needs), **nat** w1 plus SLICE_WITNESS_RUST=1. Table by tools354/pctab354.py
(kept as tools354/pc-tab.txt; launched by gopc354.sh). The hook is `witness_live.native` in all 20 nat rows and None in every
w1 and d0 row; `wn:compile` is 11,415 over the 20; certified is equal per workload in w1 and nat (1,828 in all).

**witness.py's Python calls do not drop to 0; they drop by 97.7%.** Calls of witness.py's own code:

| | w1 (Python's check) | nat (the native check) | per call of the check, w1 / nat |
|---|---|---|---|
| the 20 workloads | 5,441,984 (50 functions) | 127,039 (48 functions) | 447.6 / 10.4 |
| dev | 288,516 | 2,281 | 371.8 / 2.94 |
| fuzz | 2,919,751 | 85,572 | 1,053.3 / 30.9 |
| budget | 63,349 | 78 | 3,334.2 / 4.11 |
| wiring | 1,456,700 | 11,367 | 302.6 / 2.36 |

What remains on a native query is 2 to 4 calls of witness.py per call of the check, by ruling (the guards stay
Python, P1): `independent` 1, `witnesses` 1, `_patched` 1 when the query compiles to a handle (dev 535 of 776,
wiring 1,503 of 4,814, budget 19 of 19) and `_users_knowledge` 1 when a pair is found (dev 173, wiring 215). On dev
that is 776 + 776 + 535 + 173 = 2,260, plus 21 calls a process at import. Fuzz and lra keep more because their
fallback queries run witness.py whole: fuzz's 75 of 2,772 (`wn:fallback:miss`) make 75,951 of its 85,572 calls, lra's
334 of 1,115 (`wn:fallback:off`, no table) 19,194 of its 21,471. Those four functions are called exactly as often in
nat as in w1 on dev, fuzz, budget, wiring and lra. witness.py does not count as a 0-call module.

The hook's own Python (witness_live.py): `native`, `_replaced` and `_classes`, one call each per call of the check
(34,679 over the 20: 11,749 + 11,415 + 11,415, plus 5 a process at import). On loop and scope the check returns at
its extensions test before the hook (244 and 166 calls, 0 native), as it does without the hook.

**Boundary reads**, not witness.py calls:
- `wn:lookup`, the reads of `q.ids` by hash and `==`: 65,881 over the 20; dev 3,032, fuzz 19,501, budget 171,
  wiring 34,626.
- `_replaced`'s dictionary reads, 23 per call (`len(_OWN)` is 23): 11,415 calls, 262,545 reads; dev 17,848, fuzz
  63,756, budget 437, wiring 110,722. These are inside S1's times in (5).
- The table's symbol reads, which the earlier sections named but did not count: `symbol_facts` reads a symbol's
  `assumptions0` through convert.py (the input layer) once per query and symbol, where witness.py's `_own` read it
  itself. Against w1 that is 22,351 more `_Walk._read_symbol` reads and 156,457 more convert.py calls over the 20 (7
  Python calls a read: `_Walk.read`, `_read_symbol`, one lambda of `rust_walk` and four of `_RustWalk`); wiring
  84,462, fuzz 35,028, budget 27,678, dev 4,900. No other probed file differs between w1 and nat. It is the input
  being read, so it stays Python, but 7 calls a read is the walker's dispatch and a cheap reduction for a later step.

**The `_replaced` fallback is 0 on every workload** (the planner asked for the split): `_replaced` runs only past
the no-table and plant tests, and a False from it is followed by `witness_compile`. Its calls equal `wn:compile` in
all 20 rows (11,415 in total), so it never returned True, and `wn:fallback:off` (334, all on lra) equals the native
calls that never reached it (1,115 - 781: no table). The other fallbacks are as in (3): cls 15 of 21 (`type`), fuzz
75 of 2,772 (`miss`), dev, wiring and budget 0.

**The probe count stays 21 of 32.** In d0 every probed file has the same count on b7302f83 as on 6ee354f9, per
workload and function (13 files, 30,753 queries; witness.py 420 in both, 21 a process at import). The one
difference is witness_live.py's 5 calls a process at install (`<module>`, a generator, `from_env`, `install`,
`plant`), none per query. With the switch off nothing of this step runs per query. With SLICE_WITNESS on, witness.py
remains a per-query Python module outside the 32, with 2 to 4 calls per call of the check in place of 300 to 3,300.

Not done: item 7 (the bar and the landing). S1 and the count probe were taken on b7302f83, the commit of item 4; the
commits after it add results and tools only, so the bar's tested SHA is b7302f83.
