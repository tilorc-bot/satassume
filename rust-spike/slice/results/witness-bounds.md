# Witness bounds: the engine's exits first, and a bound on the check's work (issue 323) — the bar read and clean; lands with the commit of section (6)

**State, sa-port-349, 00:25Z 20 Nov: the bar on 82d4ddf is read and clean (section (6)); the step lands with that
section's commit by `bar.sh land 82d4ddf` onto rust-slice 2030cdc6.** No source or test changed after 82d4ddf.

State as sa-port-348 left it, 22:55Z 19 Nov: not landed, the bar running. The planner ruled B on sa-port-347's question:
the budget half of item (1) is out, the bound stays 2500. Tested source **82d4ddf** (section (5b)): its gate is
read and clean, and its bar was started at 22:48Z and is not read. The gate of 180e501 (both halves of item (1)) is
section (4). Sections (1) and (3) describe 180e501; where they speak of the budget test, (5b) supersedes them.

State as sa-port-347 left it, 20:20Z 19 Nov: rebased onto rust-slice 2030cdc6 (345's
landing): source 180e501 (43e3ee8 before the rebase, the same diff). S1 is read, section (5) below: with the switch on
the head is slower than 345's SHA on dev and fuzz beyond the spread (item (1)'s budget test, paid by every certified
call), and faster on budget and wiring. The landing rule asks for no loss on any of the four, so nothing is landed.
The gate (4) is running on pareto0 and is not read; the bar (6) is not started.

sa-port-346, branch port/witness-bounds from bfceccc9 (the tree sa-port-345 lands). Items (1), (2) and (3) are
committed; the gate (4), S1 (5) and the bar (6) are not started. SLICE_WITNESS stays off by default and the
unchanged path is the default. No SymPy construction or evaluation at query time. No Rust change: orion .so
a956b03496066671, the same as sa-port-344's. Every number below is from orion under load: counts, work and
answer digests, no S1 time.

## (1) The engine's exits before any point, 49b1efc

`witness.witnesses` (witness.py:819) compiles the query, then asks `Engine._ends_without_session` (engine.py:1860)
before `_pools`, so before any term is evaluated: True if the set has a memoized INCONSISTENT (`_verdict`) or the
query is over the discovery budget (`_within_budget`). On True the check falls through and `Engine.ask` takes that
exit itself, as with the switch off. The P1 guard (`_patched`) moved in front of that call.

The test is asked after the compile, not before it: 6582 of the 11838 calls on the 20 workloads are refused by the
compile at about 10 us each, and would otherwise pay the budget test first.

344's (a), read again with tools346/ex346.py (which exit makes the test True, py):

| exit of `Engine.ask` | calls of the check before (344) | reach the test now | what the rest do |
|---|---|---|---|
| over budget | 7 (budget) | 7, all True | |
| no-build | 462 (fuzz 40, zero 53, lra 50, value 317, f6 2) | 50, all the set's memoized INCONSISTENT (fuzz 40, zero 5, lra 5) | 412 are refused by the compile, before any point, as before |
| non-commutative | 0 | 0 | a non-commutative symbol has no value in its pool, so it was never certified |

The set's memoized Uninterpreted (`_failed`) is not asked: no call on the workloads probed (fuzz, zero, lra, f6,
value, budget, cert, core) that has one gets past the compile, so the branch would be reached by nothing.

What it costs is not yet measured on a quiet lease. `_within_budget` builds the structural cones (the templates of
every object in them), which a fall-through query pays in `Engine.ask` anyway (the second call reads `_qcones`), and
a certified query pays newly. On orion's instrumented pass the certified calls spend in the test: fuzz 0.80 s of a
15.9 s pass (py) and 0.65 of 10.4 (rust); dev 0.08 of 3.06 and 0.07 of 4.15. That is about 5% of fuzz, more than
S1's spread there (iqr 1 to 2%), so item (5)'s rule that fuzz keeps its gain against on at 345's SHA may not hold.
S1 has to say; plant 758 on the head gives the arm without the test.

State: for an over-budget query the answer, the whole of `Engine.stats` and `last_budget_limited` equal the
switch-off path's (kept test, budgets 0, 1 and 2, on a query two points certify). Not yet shown on the budget
workload's seven queries by a stats comparison of on against off: owed to the gate.

## (2) The work bound, 50d8b77

The check counts term evaluations (`_Query.spend`, witness.py:559): a point is charged the query's compiled terms
(`_Query.size`, the calls of `_term`), an evaluation of an atom for a root (`_roots`, :707) that atom's terms.
`SLICE_WITNESS_WORK`, default 2500, 0 for no bound (`WORK`, :107). Past it the check falls through. The cap of 32
points stays as a second limit.

344's "1.9 ms a point" on budget was mostly not points: the roots are looked for before the first point and cost
about 6 evaluations of an atom per symbol in it. On budget's 12 calls that reach `_pools` the work is 106,500
(median) to 495,296 evaluations, of which 32 points are about 14,500.

Work of the certified calls at cap 32, no bound (tools346/pc346.py rows, wk346.py; wk-20wl.md,
wk-fuzz-seeds-0-1-2-42.md):

| | certified | median | 90% | 99% | max | lost at 2000 | lost at 2500 | lost at 8400 |
|---|---|---|---|---|---|---|---|---|
| dev | 173 | 34 | 114 | 222 | 354 | 0 | 0 | 0 |
| fuzz 424242 | 1284 | 294 | 700 | 1308 | 1980 | 0 | 0 | 0 |
| fuzz seeds 0, 1, 2, 42 | 5241 | 287 to 300 | 633 to 696 | 1178 to 1212 | 2282 | 3 | 0 | 0 |
| wiring | 231 | 34 | 286 | 8356 | 8356 | 16 | 16 | 0 |
| the other 16 workloads | 156 | | | | 434 | 0 | 0 | 0 |

Chosen: 2500, above the 100th percentile of dev and fuzz 424242 (1980) and of the four other seeds (2282).
Certifications before -> after: dev 173 -> 173, fuzz 1284 -> 1284, all 20 workloads 1844 -> 1828; the 16 lost are
wiring's (231 -> 215), sign questions on one long sum at 8138 to 8356 evaluations each. A bound of 8400 loses none
of the 1844 but leaves wiring's fall-through work nearly as it is:

| fall-through work (term evaluations) | no bound | at 2500 | at 8400 |
|---|---|---|---|
| budget | 2,298,460 | 30,000 | 100,800 |
| wiring | 2,834,560 | 856,780 | 2,488,944 |
| fuzz | 1,149,338 | 1,149,292 | 1,149,338 |
| dev | 55,144 | 55,144 | 55,144 |

Answer digests with the switch on, py and rust (both Rust switches), on 43e3ee8: dev 31cd0945c07f02a6, fuzz
173502b6ef285ad6, budget 35bc2c4a937bebc0, wiring a0df9fd43e5180c1: 344's digests (tools346/pc1-sum.txt).

Expected on wiring, not measured: at 2500 the check keeps about 0.25 s of its 0.795 s there (344's (b)), against
about 0.07 s that its certifications save, so on would still read several percent above off; item (5)'s rule for
wiring may not hold at any bound that keeps dev's and fuzz's certifications. S1 has to say.

## (3) Plants, 43e3ee8

| plant | what it does | caught by | fired (orion, py, the seven tests named) |
|---|---|---|---|
| 758 `check-first` | points before the engine is asked (witness.py:849) | 4 failed: the over-budget test [0], [1], [2] and the INCONSISTENT-set test | 11 |
| 759 `skip-work` | the bound is passed over (witness.py:564) | 2 failed: the two work-bound tests | 183 |

No workload reaches a difference under 758: the seven over-budget queries of budget are not certified, so answers
and counters are the same with the check first. Under 759 wiring's certified count reads 231, not 215: answers the
same. The bar's rows (suite and workloads, fired from counter 740) are owed.

## (4) The gate on 180e501, read by sa-port-348

Started by sa-port-347 (`tools347/go347.sh 180e501 2030cdc6 01e8ca74`), pareto0, shared lease 3ca5f4f4, 19:34Z to
21:30Z 19 Nov; end marker "END 0" (go347.sh:18). Every tree ran the pareto venv .so cad764d46471b1c6 (no Rust
change); witness.py b16c1ed1679d30c5. Rows on orion under ~/sa-rust-ids-work/sa-port-347 (job-180e501,
jobb-180e501). 180e501 holds both halves of item (1): by the planner's ruling B these answers are evidence, and the
gate of the landed source is section (5b)'s.

| | 180e501 (base 2030cdc6) |
|---|---|
| suite by id, Rust: on / off / base | 6316 ids, 126 / 127 failed / 6309 ids, 127 failed |
| suite by id, Python: on / off / base | 0 failed in all three (6275 / 6275 / 6268 passed) |
| ids in one tree only | 7, all tests/test_witness.py (this step's tests) |
| on against off, outcome differs | Rust 1 id (the planted-history test, below); Python 0 |
| off against base, outcome differs | 0 ids, both backends |
| quiet catches recorded | Rust 49 in 9 ids, Python 10 in 7 ids: on, off and base |
| iv, 64 runs off + 64 on | failing ids differ off against on in 0 runs |
| digests, dev and fuzz | 31cd0945c07f02a6, 173502b6ef285ad6: off and on, py and rust |
| certified at cap 32 and 2500, dev / fuzz | 173 / 1284, py and rust |
| 20 workloads, py and rust, off and on, at 2500 | 0 answers and 0 messages differ in the 40 rows; against 343's rows of 01e8ca74, 80 cells, answers and messages equal |
| the same at SLICE_WITNESS_WORK=8400 | 80 cells, answers and messages equal |
| the 20 workloads' cells | exit code 0 and an empty error file in all 80 (and in the 80 at 8400) |
| queries that reach a solver, 20 workloads, off / on at 2500 / on at 8400 | 27466 / 25757 / 25741, py and rust: the 16 are wiring's lost certifications |
| fuzz seeds 0, 1, 2, 42 under 4 hash seeds (evalbench py and rust, harness, harness-custom) | rows equal on every run, 0 differ, at 2500 and at 8400 |
| certified on the seeds: evalbench / harness / harness-custom | 20964 of 43988 / 4 of 2908 / 0 of 2424, at 2500 and at 8400 (the rows of 01e8ca74: the same) |

Exceptions on the seeds are equal off and on (ValueError 2748, 472 and 808). The zero workload records 7 raises at
entry (`entails`) in each of its four cells, as on 01e8ca74.

**budget's over-budget queries (bs.txt, bs347.py).** 15 of budget's 28 rows are over budget by
`last_budget_limited` (rows 0 to 13 and 27), the same 15 off and on. On each of them the answer, the message,
`last_budget_limited`, the rise of `budget_limited`, the whole of `Engine.stats` and the moved ids are equal on
against off: 15 of 15, and 28 of 28 over all rows, py and rust, at 2500, at 8400 and under check-first. The last
row's stats read `budget_limited` 15 and `witness_certified` 0 on both sides. The rows of 01e8ca74, before this step,
read the same, so this comparison cannot tell the head from the base on this workload: none of the 15 is certified
with or without item (1). What tells them apart is the kept test (tests/test_witness.py:636).

**Known base rows, by id.** Rust base fails 127 ids (cause 672c421, not this step's), the list of
witness-reasons.md (5): test_lra_fuzz.py 43, test_solver_incremental.py 36, test_solver.py 14, test_theory_hooks.py
10, test_euf.py 7, test_euf_fuzz.py 4, test_solver_real_theories.py 3, test_writeback_provenance.py 3,
test_transfer.py 2, and one each in test_public_incremental.py (the planted-history test), test_relations.py,
test_lra_exhaustion.py, test_verify_integration.py and test_template_tables.py. The off-row fails the same 127 ids;
the on-row those less the planted-history test. iv: Rust fails test_transfer.py::test_models_respect_transfer and
::test_protocol_on_fuzz in 16 of 32 runs, off and on (known: witness-check.md:111 and :199); Python 0 of 64.

`tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence` (the known id()-reuse
failure; not edited): the Rust on-row passed it once; off failed `assert 1 == 2` and base `assert 0 == 2` at :204.
a28c548's method (pre/rep/rep-sum.txt), 20 runs a cell on 180e501:

| | switch off | switch on |
|---|---|---|
| Rust, the test | 0 of 20 pass (14x `assert 0 == 2`, 6x `assert 1 == 2`) | 0 of 20 (16x, 4x) |
| Rust, keep-alive | 20 of 20 | 20 of 20 |
| Python, the test | 20 of 20 | 18 of 20 (2x `assert 1 == 2`) |
| Python, keep-alive | 20 of 20 | 20 of 20 |

The plain test fails, the keep-alive variant passes 80 of 80, and Python is at its base rate (a28c548: 2 and 6 in
50): the signature of [137e], a test artifact.

Plants on 180e501 (python, switch on; pre/dig/dig.jsonl, pre/tw/*.log; 193 tests a row: test_witness.py's 157 and
the 36 that patch `Engine.ask`). Without a plant test_witness.py passes 157 in each of the four cells (py and rust,
off and on) and the patch row 36, off and on.

| plant | dev digest, certified | fuzz digest, certified | failed of 193 |
|---|---|---|---|
| none | 31cd0945c07f02a6, 173 | 173502b6ef285ad6, 1284 | 0 |
| 758 check-first | MATCH, 173 | MATCH, 1284 | 4 |
| 759 skip-work | MATCH, 173 | MATCH, 1284 | 2 |
| 755 pi-sign | MATCH, 171 | DIFFER f2dbc80bca7b0658, 1232 | 11 |
| 756 pi-rational | MATCH, 173 | MATCH, 1284 | 10 |
| 757 pi-enclosure | MATCH, 173 | MATCH, 1284 | 9 |
| 749 integer-half | DIFFER ff3a586753ddcf94, 184 | DIFFER f10fca19a50daa53, 1292 | 6 |
| 750 single | DIFFER a5700e23ddbf22c0, 503 | DIFFER eb82d95f09e005c6, 2349 | 49 |
| 751 skip-own | MATCH, 173 | MATCH, 1284 | 6 |
| 752 skip-patched | MATCH, 173 | MATCH, 1284 | 7 |
| 754 skip-users | MATCH, 173 | MATCH, 1284 | 6 |

758 and 759 are caught by tests only, as (3) says: no workload reaches a difference under either on dev or fuzz.
Under pi-sign fuzz reads 1232 certified and another digest than on 01e8ca74 (1234, f92b35588dda34ba): two of the
plant's certifications no longer happen on this tree. Which of the two changes takes them is not traced; the plant is
still caught, by fuzz and by 11 tests.

## (5) S1, sa-port-347: 180e501 against 2030cdc6, quiet lease on pareto1

Lease 9e0c7e81, 19:34Z to 20:04Z 19 Nov, load at most 1.26; bench-container, CPU 2, sa-eval-bench:1; 12 rounds, the
12 arms alternating inside one invocation per pair of workloads (tools347/onlease347.sh, time347.sh; read by
med347.py, whole output in tools347/s1-med.txt; this table by tab347.py). Bench .so 0982a28074215658 on every Rust
arm (786410d's build; the crate is source-equal). One digest per workload on all arms: dev 31cd0945c07f02a6, fuzz
173502b6ef285ad6, budget 35bc2c4a937bebc0, wiring a0df9fd43e5180c1. "rust" is the slice with both Rust switches on.
Median wall time in seconds; base = 2030cdc6, head = 180e501; on = SLICE_WITNESS=1 at cap 32; cf = on with
SLICE_WITNESS_PLANT=check-first (item (1)'s test taken out); 8400 = on with SLICE_WITNESS_WORK=8400. A star: beyond
the spread by med342.py's rule (the ratio of the medians outside the larger interquartile share, and the same sign in
at least 10 of the 12 rounds).

| workload, mode | base off | base on | head off | head on (2500) | head cf | head 8400 | head on / base on | cf / base on | 8400 / base on | head on / head off | base on / base off | largest iqr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev py | 0.5331 | 0.5214 | 0.5322 | 0.5340 | 0.5263 | 0.5336 | +2.4%* | +0.9%* | +2.3%* | +0.3% | -2.2%* | 1.2% |
| dev rust | 0.6433 | 0.6570 | 0.6474 | 0.6728 | 0.6649 | 0.6725 | +2.4%* | +1.2%* | +2.4%* | +3.9%* | +2.1%* | 1.7% |
| fuzz py | 8.0824 | 5.4239 | 8.0716 | 5.7059 | 5.4595 | 5.6987 | +5.2%* | +0.7% | +5.1%* | -29.3%* | -32.9%* | 1.3% |
| fuzz rust | 5.8316 | 4.6441 | 5.8069 | 4.9642 | 4.6791 | 4.9388 | +6.9%* | +0.8% | +6.3%* | -14.5%* | -20.4%* | 1.0% |
| budget py | 0.4743 | 1.6930 | 0.4745 | 0.4917 | 0.4939 | 0.5040 | -71.0%* | -70.8%* | -70.2%* | +3.6%* | +257.0%* | 0.9% |
| budget rust | 0.3178 | 1.5389 | 0.3184 | 0.3315 | 0.3343 | 0.3439 | -78.5%* | -78.3%* | -77.7%* | +4.1%* | +384.2%* | 0.6% |
| wiring py | 2.7410 | 3.4757 | 2.7391 | 3.0361 | 3.0407 | 3.3931 | -12.6%* | -12.5%* | -2.4%* | +10.8%* | +26.8%* | 1.1% |
| wiring rust | 3.2402 | 4.0524 | 3.2381 | 3.5925 | 3.5945 | 3.9732 | -11.3%* | -11.3%* | -2.0%* | +10.9%* | +25.1%* | 1.5% |

What each arm counted on one py pass (arm347.py, not a time): certified dev 173 on every arm, fuzz 1284 on every arm,
budget 0, wiring 231 on base and at 8400 and 215 at 2500 and under cf; the cf arm's plant fired 535 (dev), 2772
(fuzz), 19 (budget) and 1503 (wiring) times.

Read against the planner's landing rule for this step:

- **On at the head against on at 345's SHA, no worse on any of the four: does not hold.** dev +2.4% (py) and +2.4%
  (rust), fuzz +5.2% and +6.9%, each slower in 12 rounds of 12. budget is 71% and 78% faster, wiring 12.6% and 11.3%.
- **budget or wiring gain beyond the spread: holds**, both.
- **dev and fuzz keep their gains, on against off: fuzz keeps a smaller one, dev py loses its.** fuzz -29.3% (py) and
  -14.5% (rust) at the head, against -32.9% and -20.4% at 345's SHA. dev py +0.3% (within the spread) against -2.2%;
  dev rust +3.9% against +2.1% (it had no gain to keep).
- On against off on budget and wiring, the finding for the default: budget +3.6% (py) and +4.1% (rust), from +257%
  and +384%; wiring +10.8% and +10.9%, from +26.8% and +25.1%. Both are still beyond the spread.

Where the loss on dev and fuzz comes from: item (1)'s test. `Engine._within_budget` builds the structural cones, and
a certified call pays that newly (a fall-through call pays it in `Engine.ask` anyway). Head on against head cf: fuzz
+4.5% (py) and +6.1% (rust), dev +1.5% and +1.2%; that is the 5% of (1) above in S1 terms, 0.25 s (py) and 0.29 s
(rust) of fuzz. With the test taken out (cf against base on) fuzz reads +0.7% and +0.8%, within the spread, and dev
+0.9% and +1.2%, just beyond it: the work count of item (2). On budget and wiring the test changes nothing that can be
measured (cf against on: budget -0.5% and -0.8% the other way, wiring within the spread): the work bound alone gives
budget and wiring their gains.

The bound, 2500 against 8400 (the planner's rule: the lower sum of the four workloads; 8400 if within the spread):
the sum per round is 9.770 s at 2500 against 10.140 s at 8400 on py (-3.6%), 9.556 s against 9.920 s on rust (-3.7%),
lower in 12 rounds of 12 on both, with an interquartile share of at most 0.9%. So **2500**, beyond the spread. All of
the difference is wiring (+11.8% and +10.6% at 8400) and budget (+2.5% and +3.7%); dev and fuzz are within the
spread. The price is wiring's 16 certifications (231 -> 215). The constant is not changed, so the tested source stays
180e501; the comment at witness.py:104 does not yet say how it was chosen (owed with whatever source change follows
the planner's answer, or as a comment-only commit before the bar).

## (5b) Ruling B applied, sa-port-348: source 82d4ddf

The planner ruled B on report 25f6298 (20:07Z 19 Nov): the budget half of item (1) goes, the work bound stays at
2500, and dev's loss against 345's SHA is an accepted, named exception to the landing rule. 82d4ddf does that:

- `witness.witnesses` asks `Engine._known_inconsistent(assumptions)` (engine.py:1860; `_ends_without_session` with its
  budget half and its `proposition` argument gone): the version check and one `_verdict` read. `_within_budget` is no
  longer called by the check, so a certified call no longer pays the structural cones.
- What that changes with the switch on: an over-budget query that two points certify is certified. Its answer is
  None either way; it is now counted in `stats["witness_certified"]` and not in `stats["budget_limited"]`, and
  `last_budget_limited` is False, where 180e501 left both to the engine. This is 2030cdc6's behaviour again. No
  workload has such a query: budget's 15 over-budget rows are equal on against off in every field, below.
- Plant 758 `check-first` stays, with the INCONSISTENT read as its site.
- The comment at `WORK` (witness.py:104) says how 2500 was chosen.
- No Rust change; harness/state.py is not touched.

Tests, by id (tests/test_witness.py, 157 before and after):

- removed with the hunk: `test_a_query_over_the_budget_is_the_engines_as_with_the_switch_off[0]`, `[1]`, `[2]`. Its
  assertion was that answer, `Engine.stats` and `last_budget_limited` are equal on against off for an over-budget
  query that two points certify, which only the budget test gave.
- in its place, what still holds of it: `test_a_query_over_the_budget_still_answers_none[0]`, `[1]`, `[2]`, the same
  query and budgets: None off and on; off counts it as budget limited, on as certified.
- `test_a_set_the_engine_knows_inconsistent_tries_no_point` stays as it is, and is now plant 758's only catch (it
  failed 4 under the plant on 180e501: this test and the three removed ids).
- No other test is touched.

orion, 82d4ddf, .so a956b03496066671: test_witness.py, test_sympy_api.py, test_layering.py, test_history.py,
test_sympy_boundary.py and test_budget_cone.py, 429 passed in each of the four cells (python and rust backend, switch
off and on). Under check-first 1 failed of 193 (the INCONSISTENT-set test), under skip-work 2 (the two work-bound
tests).

**What the INCONSISTENT read costs (orion under load, one py pass, a count and a rough time, not S1; ki348.py).** dev:
535 calls, none True, 0.8 ms of a 0.81 s pass. fuzz: 2772 calls, 40 True, 9.7 ms of an 8.41 s pass, the timer's own
cost included. That is 0.1% of either pass, well inside S1's spread (1.0 to 1.7%), so the check-first arm of (5),
which skips this read too, is read as B's time. No new S1 was run, by the ruling.

**Condition 2, the default path.** With the switch off neither changed function is called, so the off rows of (5)
are B's: head off against 345 off reads dev -0.2% (py) and +0.6% (rust), fuzz -0.1% and -0.4%, budget +0.0% and
+0.2%, wiring -0.1% and -0.1%, each within the spread (tools347/s1-med.txt, block A).

**The dev exception, named.** With the switch on, dev is slower than at 345's SHA: +0.9% (py, 0.5263 s against
0.5214 s) and +1.2% (rust, 0.6649 s against 0.6570 s), slower in 12 rounds of 12 (the cf arm of (5)). The cause is
item (2), the work count: `_Query.spend` is called once per point and once per evaluation of an atom for a root, and
the compile counts the terms. On the instrumented pass under the same lease (tools347/s1-med.txt, the wit rows; not
an S1 time) the check's own time on dev rises from 0.0615 s to 0.0659 s a pass on py and from 0.0674 s to 0.0727 s on
rust, cf against base on; per call the median goes from 56.5 to 63.2 us (py) and from 63.6 to 71.0 us (rust), a
certified call from 69.1 to 75.6 us and from 81.3 to 88.6 us. That 4.4 ms and 5.3 ms is most of the 4.9 ms and
7.9 ms between the wall medians. dev has no query near the bound (its largest certified call is 354 evaluations),
so it pays the count and gets nothing back; budget and wiring get the count's whole gain. fuzz pays the same count
(0.7790 s to 0.8106 s, py) and reads +0.7% and +0.8%, within the spread.

**Certified at 2500 against 8400** (S1's arm pass, arm347.py, and the gate's digest rows): dev 173 and 173, fuzz
1284 and 1284; on the gate's seed runs of (4) (seeds 0, 1, 2 and 42 under four hash seeds, evalbench) 20964 and 20964. The bound takes certifications from wiring only (215
against 231).

**The gate on 82d4ddf (condition 1).** A frozen copy of 82d4ddf against base 2030cdc6, pareto0, shared lease
1758122d, 21:39Z to 22:47Z 19 Nov, "END 0" (tools348/stage348.sh, go348.sh:18; job347.sh, then jobb348.sh). .so
cad764d46471b1c6 on every tree; witness.py 49d02b0abb2ba388, engine.py 7b84c4966d87a31d. Rows on orion under
~/sa-rust-ids-work/sa-port-348 (job-82d4ddf, jobb-82d4ddf). The arm at 8400 was not run again: condition 1 does not
ask for it and (4) reads it on 180e501.

| | 82d4ddf (base 2030cdc6) |
|---|---|
| suite by id, Rust: on / off / base | 6316 ids, 127 / 127 failed / 6309 ids, 127 failed: the same 127 ids in all three, the known base rows of (4) |
| suite by id, Python: on / off / base | 0 failed in all three (6275 / 6275 / 6268 passed) |
| ids in one tree only | 7, all tests/test_witness.py |
| on against off, and each against base, outcome differs | 0 ids, both backends |
| quiet catches recorded | Rust 49 in 9 ids, Python 10 in 7 ids: on, off and base |
| iv, 64 runs off + 64 on | failing ids differ off against on in 0 runs; Rust fails test_transfer.py's two known ids in 16 of 32 runs, off and on; Python 0 of 64 |
| digests, dev and fuzz | 31cd0945c07f02a6, 173502b6ef285ad6: off and on, py and rust |
| certified, dev / fuzz | 173 / 1284, py and rust |
| 20 workloads, py and rust, off and on | 0 answers and 0 messages differ in the 40 rows; against 343's rows of 01e8ca74, 80 cells, answers and messages equal |
| the 20 workloads' cells | exit code 0 and an empty error file in all 80 |
| queries that reach a solver, 20 workloads, off / on | 27466 / 25757, py and rust, as on 180e501 |
| budget's over-budget rows (bs.txt) | the same 15 off and on; answer, message, `last_budget_limited`, the rise of `budget_limited`, `Engine.stats` and moved ids equal on 15 of 15, and on 28 of 28 rows, py and rust, and under check-first |
| fuzz seeds 0, 1, 2, 42 under 4 hash seeds | rows equal on every run, 0 differ; 128 runs, exit code 0 |
| certified on the seeds: evalbench / harness / harness-custom | 20964 of 43988 / 4 of 2908 / 0 of 2424 |

On 82d4ddf the budget rows do tell something: the check now reaches the over-budget queries, and none of budget's 15
is certified (`witness_certified` 0, `budget_limited` 15 on both sides). The planted-history test failed in all three
Rust rows this time; a28c548's method on 82d4ddf (pre/rep/rep-sum.txt, 20 runs a cell): Rust 0 of 20 off and on (19x
`assert 0 == 2`, 1x `assert 1 == 2` each), keep-alive 20 of 20 off and on; Python 18 of 20 off and 19 of 20 on
(`assert 1 == 2`), keep-alive 20 of 20: the signature of [137e]. The zero workload records 7 raises at entry in each
of its four cells, as on the base.

Plants on 82d4ddf (python, switch on; 193 tests a row; without a plant test_witness.py passes 157 in each of the four
cells and the patch row 36 off and on). Digests and certified counts are those of (4)'s table in every row.

| plant | dev | fuzz | failed of 193 (on 180e501) |
|---|---|---|---|
| 758 check-first | MATCH, 173 | MATCH, 1284 | 1 (4): the INCONSISTENT-set test |
| 759 skip-work | MATCH, 173 | MATCH, 1284 | 2 (2) |
| 755 pi-sign | MATCH, 171 | DIFFER f2dbc80bca7b0658, 1232 | 11 (11) |
| 756 pi-rational | MATCH, 173 | MATCH, 1284 | 10 (10) |
| 757 pi-enclosure | MATCH, 173 | MATCH, 1284 | 10 (9) |
| 749 integer-half | DIFFER, 184 | DIFFER, 1292 | 7 (6) |
| 750 single | DIFFER, 503 | DIFFER, 2349 | 49 (49) |
| 751 skip-own | MATCH, 173 | MATCH, 1284 | 6 (6) |
| 752 skip-patched | MATCH, 173 | MATCH, 1284 | 10 (7) |
| 754 skip-users | MATCH, 173 | MATCH, 1284 | 6 (6) |

Every plant is caught. The rows that read one more than on 180e501 (pi-enclosure, integer-half) hold
test_public_incremental.py, whose planted-history test fails on Python in 1 or 2 runs of 20; which id it was is not
read. skip-patched reads 10 as on 01e8ca74, against 7 on 180e501; not traced (likely the three tests of a replaced
`_within_budget`, which 180e501's budget test still called under the plant).

## (6) The bar on 82d4ddf, read by sa-port-349

pareto0, shared lease 9d4bce81 (1 h 16 m, exit 0), 22:48Z 19 Nov to 00:05Z 20 Nov, started by sa-port-348
(tools348/gobar348.sh, job348bar.sh): `p1/bar.sh` of 82d4ddf on the frozen branch origin/bar/witness-bounds-82d4ddf,
N=6, phases tests, suite, live, plants, extra, suiteplants, fmrows, sum. Rows: pareto0
~/sp19/sa-rust-ids-work/sa-port-348/bar; the small files on orion ~/sa-rust-ids-work/sa-port-348/bar; the reads below
on orion in ~/sa-rust-ids-work/sa-port-349 (suite-by-id.txt by tools349/byid349.py, wall.txt by tools336/wall336.py,
rep/). BASE is the last landing's bar suite (sa-port-344's, on bfceccc9). Read as witness-reasons.md (7) read
bfceccc9's.

The bar is valid: gobar-end.txt `END 0 END 0 2026-11-20T00:05:26Z cad764d4 82d4ddf3`; source.txt 82d4ddf3; build.txt
and so-loaded.txt have .so cad764d46471b1c6 in all seven phases; the eight phases exit 0; 72 test files exit 0;
direct.txt ends `exit 0`; "suite: no rows" is absent; the 123 error files of the workload runs are empty. The launcher
had no SLICE_ variable. env-summary.txt (the /proc watcher on the suite rows' processes): the plain suite none,
`witness:on` SLICE_WITNESS=1, the two plant rows SLICE_WITNESS=1 and their SLICE_WITNESS_PLANT.

**Plain suite (Rust, switch off: the default path).** 6316 ids: 127 failed, 6148 passed, 23 skipped, 18 xfailed.
Against BASE (6309 ids): new 7, all tests/test_witness.py and all passed
(`test_a_query_over_the_budget_still_answers_none[0]`, `[1]`, `[2]`,
`test_a_set_the_engine_knows_inconsistent_tries_no_point`,
`test_past_the_work_bound_the_check_falls_through_and_the_engine_answers`,
`test_the_default_work_bound_leaves_a_long_sum_to_the_engine`, `test_the_work_is_the_terms_evaluated`); gone 0;
changed outcome 0. The 127 are BASE's 127 by id, the known base rows of (4): test_lra_fuzz.py 43,
test_solver_incremental.py 36, test_solver.py 14, test_theory_hooks.py 10, test_euf.py 7, test_euf_fuzz.py 4,
test_solver_real_theories.py 3, test_writeback_provenance.py 3, test_transfer.py 2, and one each in
test_public_incremental.py, test_relations.py, test_lra_exhaustion.py, test_verify_integration.py and
test_template_tables.py. The three ids ruling B removed,
`test_a_query_over_the_budget_is_the_engines_as_with_the_switch_off[0]`, `[1]`, `[2]`, were never on rust-slice, so
they are not in BASE and do not read as gone. Handler rows 39 in 2 tests, the same multiset as BASE, and 0 ids whose caught rows differ from BASE, in each of the four suite
rows; the rows' catch counters are `rv:consistent_caught` 45 and `ctx:caught` 1 in all four and in BASE; TermFault 0.
The per-id count of quiet catches (Rust 49 in 9 ids, Python 10 in 7) is the gate's, (5b): the bar's copy on orion
holds no per-id rows.

**Workloads, switch off.** dev and fuzz MATCH py against py, py against rust and both end-state rows (answers
31cd0945c07f02a6 and 173502b6ef285ad6); the 15 extra workloads: 30 rows MATCH. Kept and refused shares equal BASE's
on all 17. Handler files of the workload runs: 0 rows each. fm rows: 20 workloads, 0 differ; the two fm plants are
caught (4 and 3 differ, exit 1).

**`witness:on`** (Rust with the switch on). Against Python with the switch on: MATCH on all 17 workloads, and every
difference count of the 17 comparisons is 0 (answers, messages, sessions, end states, stream, stats, moved state,
cache keys and values, native stores). Against Python with the switch off: answer_diff 0 and msg_diff 0 on all 17;
sessions differ where the check certified (fuzz 1273, wiring 215, dev 178, core 92, zero 52, transfer:7:60 2,
transfer2:3:40 1, cert 1, the other nine 0). That the switch was on in these rows: queries that made a solver, off ->
on, are dev 867 -> 697, fuzz 2937 -> 1756, wiring 5628 -> 5413, core 1634 -> 1542, zero 654 -> 611, the same number
on the Python reference and on the Rust row. Against 345's bar the only change is wiring, 5397 -> 5413: the 16
certifications the work bound gives up (231 -> 215, section (2)). budget: 17 and 17, nothing certified. Suite row: 127
failed, the plain suite's 127 by id, 0 ids change.

**The step's plants**, each with the switch on. Workload rows against Python with the switch on; suite rows against
this bar's plain suite. Fired is counter 740 (`witness.FIRED`), which reads 0 in the plain and `witness:on` rows.

| plant | fired on workloads | workload rows | fired in the suite | suite row |
|---|---|---|---|---|
| 758 check-first | fuzz 2772, wiring 1503, dev 535, core 186, zero 105, cert 61, budget 19, transfer:7:60 14, transfer2:3:40 6; 0 on the other 8 | MATCH on all 17 | 16929 | 128 failed; 1 id `passed -> failed`: `tests/test_witness.py::test_a_set_the_engine_knows_inconsistent_tries_no_point` |
| 759 skip-work | budget 48681, wiring 47834, fuzz 2; 0 on the other 14 | DIFFER on wiring (answers 0, messages 0; 16 sessions, 322 stats rows, 16 moved: `witness_certified` 231 against 215, 5397 queries make a solver against 5413); MATCH on the other 16 | 70002 | 128 failed; 2 ids `passed -> failed`: `tests/test_witness.py::test_past_the_work_bound_the_check_falls_through_and_the_engine_answers` and `::test_the_default_work_bound_leaves_a_long_sum_to_the_engine`; 1 id `failed -> passed`: the planted-history test, below |

Both plants fire and both are caught by a check that does not read the plant's flag (P2): the kept tests count the
points tried (a patched `witness._holds`), read `Engine.stats` and set `witness.WORK` themselves. check-first changes
no workload row, as (3) and the handoff expected: it is reached by nine workloads, but a set the engine knows
INCONSISTENT has no point that satisfies it, so with the points tried first nothing is certified and the engine
raises as before; only the points tried differ, which the kept test asserts and no workload row records. It is caught
by its kept test only. skip-work changes no answer (answers a0df9fd43e5180c1 on wiring, off and under the plant); it
is caught on wiring by the state comparison and in the suite by the two kept tests. On budget it fires 48681 times
and the row MATCHes: none of budget's over-budget queries is certified with or without the bound.

**The planted-history test** (`test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence`,
the known id()-reuse failure, not edited): failed in BASE and at :204 in three of this bar's four suite rows (plain
`assert 1 == 2`, `witness:on` `assert 0 == 2`, check-first `assert 1 == 2`) and PASSED in the skip-work row: the one
outcome of the bar that is not a plant's catch. Because it showed, a28c548's method was run for that row
(tools349/rep349.sh, gorep349.sh; pareto0, shared lease c6f4e865, 00:09Z 20 Nov; sa-port-348's frozen tree of 82d4ddf,
.so cad764d46471b1c6, witness.py 49d02b0abb2ba388; Rust, switch on, one fresh process a run, 20 runs a cell, the plant
read back as set in its 40 runs):

| Rust, switch on | under skip-work | no plant, side by side |
|---|---|---|
| the test | 0 of 20 pass (17x `assert 0 == 2`, 3x `assert 1 == 2`) | 0 of 20 (14x, 6x) |
| keep-alive | 20 of 20 | 20 of 20 |

The signature of [137e], as (5b) read it on this source without a plant (Rust 0 of 20 off and on, keep-alive 20 of
20; Python 18 and 19 of 20): the test fails at :204 with N < 2, the keep-alive variant is clean, and the plant makes
no difference to it. Run alone the test did not pass once on Rust in these cells; the pass is a draw of the suite row
under xdist, as the gate of 180e501 had one in its on-row (section (4)). It is a footnote on the skip-work row, which
stays caught by its two kept tests; it is not counted as a catch.

**State differences with the switch on, explained (not in the answer gate).** (a) Queries the check certifies make
no session: the session counts above. (b) The planner's word on sa-port-348's handoff: with the switch on, an
over-budget query that two points certify reports `last_budget_limited` False and counts as `witness_certified`, not
as `budget_limited`; a certified None is undecided, not cut off (kept test
`test_a_query_over_the_budget_still_answers_none`). No workload of the bar has such a query: budget's rows are equal
on against off in (5b). (c) The owed look at `Engine._ends_without_session` filling `_kids`, `_cones` and `_qcones`
is settled by ruling B: the function is gone at 82d4ddf, `_known_inconsistent` reads `_verdict` after the
version check and sets no flag and no counter, and the `witness:on` rows' end states and moved state equal Python's on all 17.

**Wall times** (tools336/wall336.py; one machine, shared lease, rows of a phase side by side). Total 76 m 36 s:
tests 2 m 27 s, suite 1 m 52 s, live 14 m 33 s, plants 8 m 24 s, extra 42 m 53 s, suite plants 5 m 29 s, fmrows
0 m 58 s. Suite rows: plain 1 m 53 s, `witness:on` 1 m 49 s, check-first 1 m 50 s, skip-work 1 m 50 s. Workload rows,
seconds:

| row | sum of 17 | fuzz | budget | rootof | wiring | value | dev | f6 | zero | core | the other 8 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| witness:on | 1549 | 428 | 321 | 280 | 248 | 67 | 57 | 48 | 36 | 24 | 40 |
| witness:check-first | 1541 | 431 | 321 | 281 | 248 | 67 | 46 | 48 | 36 | 24 | 39 |
| witness:skip-work | 1536 | 430 | 321 | 281 | 246 | 67 | 44 | 48 | 36 | 24 | 39 |

The other 8: transfer2:3:40 11, transfer:7:60 9, opaque 8, loop 6, scope 3 (2 under the plants), cert 2, cls 1, twin
0. 345's bar read 1699 for its `witness:on` row (fuzz 470, budget 356, rootof 302, wiring 271, dev 61). These are not
the speed measure and are not compared as one: S1 is section (5), and there is none on 82d4ddf, by the ruling.

**Landing.** Nothing in the bar is new against BASE or against sections (4), (5) and (5b), and no source or test
changed after 82d4ddf (`git diff --name-only 82d4ddf HEAD` outside results/ and the HANDOFF files is empty). The step
lands with this commit by `bar.sh land 82d4ddf`, whose guard compares satassume/ and rust-spike/slice/ outside
results/ between 82d4ddf and the landing commit.

## Owed, named here

- A cheaper budget test for the check is not a step (the planner's ruling B). Its trigger, for
  OWED-satassume-rust.md: a workload with an over-budget query that the check certifies slowly. None of the 20
  workloads has one today (budget's 15 over-budget queries are not certified, and cost at most 2500 evaluations each).
- With the switch on, an over-budget query that two points certify is counted as certified and not as budget
  limited (kept test `test_a_query_over_the_budget_still_answers_none`).
- 758 check-first changes no workload row of the bar (section (6)): caught by its kept test only.
- harness/state.py (shared) changed: `WORK` classified.
