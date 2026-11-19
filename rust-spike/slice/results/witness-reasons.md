# Witness reasons: raising how many Nones the check certifies (issue 323) — exact pi: gate, S1 and bar read; lands with section (7)'s commit

sa-port-340 to 345, branch port/witness-reasons from rust-slice 29c5a0db. Done: (0), (1), (2a), the (3) simulation,
exact pi (2), the plants (4) 755 to 757, the raises (ii), (2b) reverted (c4d6e92c), the gate (5), S1 (6) and the bar
(7). The step lands on rust-slice with the commit that added section (7), by `bar.sh land bfceccc9` (sa-port-345, 19
Nov); if that commit is not on origin/rust-slice, the step has not landed. No PR.

Tested SHAs and .so: base 29c5a0db; the gate and S1 on 01e8ca74 (satassume source c4d6e92c); the bar on bfceccc9
(01e8ca74 plus harness/state.py e2088c05, tools and handoffs). Pareto venv .so cad764d46471b1c6 (338's build of
29c5a0db's crate; no Rust change since), bench .so 0982a28074215658, orion .so a956b03496066671. SLICE_WITNESS is off
by default and the unchanged path is the default. No SymPy construction or evaluation at query time. "Exact" rests on
325's 14-predicate table plus (2)'s arguments: (T) pi is transcendental and (E) the fixed 50-decimal enclosure (issue
247: SymPy evaluation is not ground truth). Certified at cap 32, 29c5a0db -> 01e8ca74: dev 159 -> 173, fuzz 1060 ->
1284 (uncapped, 342's rows: 163 -> 177, 1491 -> 1819). S1 (pareto1, quiet leases only, section (6)), head against
base with the switch on: dev +0.7% py and +0.6% rust (within the spread), fuzz -7.0% and -2.6% (faster), budget and
wiring within. The bar's rows and wall times: section (7). Known base rows by id: section (5). The Rust port of the
per-call compile and pools follows this step and is not started.

## (0) Ride-alongs, read-only, on 29c5a0db

Count probe (tools340/pc340.sh, pareto1, shared lease; 20 workloads, 30,753 queries; 40 of 40 rows ref 0 run 0
cmp 0). Cells: w0 SLICE_WITNESS unset, w1 SLICE_WITNESS=1; Python frames and Python walker in both.

| file | w0 calls | w1 calls |
|---|---|---|
| witness.py | 340 (7 functions; 17 a process, at import) | 17,091,747 (32 functions) |
| convert.py | 14,559,922 | 14,338,985 |
| term_live.py | 8,497,075 | 7,549,762 |
| session_live.py | 764,616 | 713,993 |
| lra_adapter.py | 289,052 | 254,869 |
| formula.py | 183,111 | 166,306 |
| engine.py | 255,617 | 261,885 |
| sympy_api.py, wiring.py, knowledge_live.py, knowledge_core_live.py, knowledge_common_live.py, compile.py, templates/__init__.py | equal in both cells | |

With the switch off witness.py runs nothing per query, so it does not enter the table and the count stays 21 of 32.
With the switch on it is a per-query Python module: 17.1 M calls, most in `_term`'s closures (11.1 M), the table's
lambdas (2.4 M) and `_own`'s (1.2 M); by workload budget 8.39 M, wiring 5.92 M, fuzz 2.04 M, core 0.32 M, dev 0.23 M.
If the switch becomes the default it enters as a 33rd, uncounted module. The w0 cell was not compared file by file
with 334's rows.

[138b] diagnostic (tools340/s7n0-340.sh, pareto0): the suite as a convert:* bar row but under -n 0 (one process).

| run | suite | TermFault in the log | tests/test_s7_trig.py::test_numbers_sound[cos] |
|---|---|---|---|
| SLICE_CONVERT=rust, SLICE_CONVERT_PLANT=enc-int-no-sign | 243 failed, 5977 passed, 421 s | 86 | PASSED |
| SLICE_CONVERT=rust, no plant | 127 failed, 6094 passed, 459 s | 0 | PASSED |

In pytest's own order the id passes with and without the plant, so its failure in 335's bar row came from the xdist
worker's order.

## (1) bar.sh debt, commit 1f6ddb5b

- [148] bar.sh checks before every phase but build and sum that sa_solver imports from the clone; otherwise
  void.txt, done.txt "VOID ...", exit 3. Check on pareto1 (tools340/barchk340.sh): a fresh clone with no .so,
  phases `tests sum`: done.txt reads "VOID ... phase tests: sa_solver does not import from .../sa_solver.so:
  ModuleNotFoundError". The exit code is in barchk-end.txt ("void N"), not read yet.
- [146] Cause: plant_count.py read only the crate's `rel:plant_fired`; term, dispatch, knowledge and witness plants
  never move it, and the dispatch's count reaches Python at an atexit flush, after the plugin's last reading. Now
  every kind's counter is read and summed test by test. Orion, bar-style suite rows on a subset (-n 2 or 4):

  | row | result | fired |
  |---|---|---|
  | no plant | 183 passed | every counter 0 |
  | SLICE_WITNESS=1 | 183 passed | every counter 0 |
  | witness plant `single` | 55 failed | witness 262 |
  | witness plant `integer-half` | 8 failed | witness 1768 |
  | term plant `mark-wrong-pattern` | 183 passed | term 3 |
  | session plant `dispatch-nan-arg-on` (753) | 39 failed of 366 | plant:fired 432; rel:plant_fired 0, the old line's reading |
  | session plant `dispatch-opaque-off` | 366 passed | plant:fired 1 |
  | session plant `drop-ensure-demand` | 366 passed | rel:plant_fired 136,728 |
  | session plant `knowledge-no-query-drop` | 7 failed of 366 | knowledge 176, session 176 |

  A convert:* row has no counter (the Rust walker's `planted()` does not count); bar_sum.py prints that instead of 0.
  OWED, new: a fired counter for the Rust walker's plants 670-674 (walk.rs), a Rust change, not made here.
- [147] witness.py counts each planted site that finds its plant set (FIRED, counter 740; PLANT[0] is a str
  subclass only when SLICE_WITNESS_PLANT is set). Orion, dev workload rows on Rust: witness:on 0, witness:single
  922, witness:skip-own 493 (`witness_plant_fired` in the session report).
- tests/test_witness.py + test_sympy_api.py + test_layering.py: 215 passed in each of python/rust x off/on (orion).
- The bar-level check of [146] and [147] (build, tests, suite, live, plants, six suite rows) was still running on
  pareto1 at the handoff: read `sum.txt` under ~/sp19/sa-rust-ids-work/sa-port-340-fired there.

## (2a), (2b) and (3): counts before any change to the check (tools340/cnt340.py, ana340.py; ana340-29c5a0db.txt)

One uncapped pure-Python pass per workload, joined by query with 329's reasons rows: same calls (776 / 2772), same
digests, same certified counts (163 / 1491), and every self-check in cnt340.py held.

(2a) pi-blocked queries of 325's class (i) Nones with both witnesses (82 dev, 372 fuzz), by what stands in them:

| | dev | fuzz |
|---|---|---|
| pi only under Add, Mul and non-negative integer literal powers, nothing else undecided: the most (2) can recover | 19 (23.2%) | 372 (100%) |
| pi only outside functions, but the base of another power (not in Q[pi]) | 15 (18.3%) | 0 |
| pi outside a function, and a function also in the query | 47 | 0 |
| pi and another constant | 1 | 0 |

Both bounds are above 5% of the class, so (2) is not skipped. On all None answers: dev 19 of 101, fuzz 404 of 404.

(2b) Of the no-rational-pair rows (dev 37 with the 4 at limit 2000, fuzz 260) none holds a pi, as a leaf or inside
a function. A query without pi has no constant in Q[pi] outside Q, so (2b) resolves 0 of these rows by
construction; it can only help inside the pi class.

(3) Certified within 32 points on the same class, by pool order (h head, r roots, c constants, t tail):

| order | dev (368) | fuzz (2157) |
|---|---|---|
| hrct, the current order | 157 | 986 |
| rhct, roots first | 154 (-0.8%) | 1001: 150 of the 397 gained, 135 lost, +0.7% |
| rcht | 154 | 999 (+0.6%) |
| crht, constants first | 153 | 892 (-4.4%) |
| chrt | 153 | 887 (-4.6%) |

No order lifts the count by 5% of the class, so (3) is not implemented. All 397 fuzz pairs found after point 32
(and dev's 4) are queries of two symbols; the order of the tuples, not of the pools, was not simulated.

## (1') The barchk job, read by sa-port-341

pareto1, 1f6ddb5b, .so cad764d46471b1c6 loaded in every phase (so-loaded.txt), ended 12:54:01Z 19 Nov:
`END void 3 fired 0`.

- Void bar: exit 3; done.txt and void.txt read "VOID ... phase tests: sa_solver does not import from .../sa_solver.so".
- "plant fired in the suite": witness:single 25,094 (witness); witness:integer-half 1,587,916 (witness);
  term:mark-wrong-pattern 347 (term); dispatch-nan-arg-on 4,751 (plant:fired); convert:enc-int-no-sign "no counter";
  witness:on "no plant in this row", every counter 0.
- Plants table, fired: witness:on 0 and 0 (dev, fuzz), witness:single 922 and 3,812 (DIFFER), witness:skip-own 493
  and 2,228 (MATCH on the workloads; its kept test catches it).

Nothing was wrong, so no fix commit.

## sa-port-341: exact pi (2) and plants (4), committed, not gated

Head a0849b10 (source), orion only so far; the gate (5), S1 (6) and the bar (7) have not run, and the reasons table
after the change is not measured. HANDOFF-sa-port-341.md has the order and the map.

- ecf2ff12: with the switch on, an own assumption undecided at a proposed value (a prime symbol and a constant above
  10**6) raised `_Undecided` out of the query on 29c5a0db; the value is now left out. A bug of the landed check,
  unreached with the switch off.
- 49e30f57: values in Q[pi] (`_PiPoly`), `PI_TABLE` with one argument an entry from (T) pi is transcendental and
  (E) `_PI_LO < pi < _PI_LO + 10**-50` (50 decimals, OEIS A000796; proved again in the tests from Machin's formula),
  `_sign` undecided when the bounds do not exclude 0, two compiles so a query without pi runs the old closures,
  pi inside a function undecided, (2b) through `_roots`.
- a0849b10: plants 755 pi-sign, 756 pi-rational, 757 pi-enclosure. tests/test_witness.py, one process, orion:
  148 passed without a plant; 11, 12 and 8 failed under the three, among them one test each that compares answers
  with the switch on and off and never reads the plant.

## sa-port-342: the raises (planner (ii)), and the reasons table after the change; the gate's jobs started, not read

Tested SHA dfb544e6 (source a0849b10, tests ef0b1335, tools342), base 29c5a0db. No Rust change, so both trees run the
venv .so cad764d46471b1c6. Everything in this section is orion, pure Python, frozen archives of the two commits.

**(ii) Every raise of witness.py (ef0b1335, tests only, no source change).** The module has two exception classes,
`_Undecided` and its subclass `_NeedPi`, and 23 raise statements, each naming one of the two
(`test_the_check_raises_only_its_own_undecided` reads this from the source). They are raised either while compiling
(caught at `witnesses`' `except _Undecided`, the `_NeedPi` of the first compile one level in) or while evaluating a
closure, and closures are called from three places only: `_roots` (try at :697), `_pools`' own-assumption call (try at
:750, the [151] fix) and `_holds` (try at :781). The rest of `_pools` adds, subtracts and divides by 2, which raises
nothing. `test_every_raise_of_the_check_is_caught_before_the_query_returns` runs one case per raise statement under a
line trace of the module: 20 raise lines are reached by 20 cases through `ask` or `witnesses` (answers equal off and on,
nothing raised), and three that no query reaches are executed directly: `_PiPoly.__truediv__` and `__rtruediv__` (the
check divides only by a non-zero rational) and `_pred`'s definition branch (no definition names polar). A raise
added without a case fails the test. With the [151] fix taken out (a copy of the tree, `except ZeroDivisionError` in
`_pools`) the test fails, with ecf2ff12's own test. Nothing new was found to fix.

tests/test_witness.py, one process: 150 passed; with test_sympy_api.py and test_layering.py 262 passed, switch off and
on. Under the plants: pi-sign 11, pi-rational 12, pi-enclosure 9 (the new test is one of them), single 58 failed of 150.

**The reasons table, before and after (tools342/cnt342.py, ana342.py; ana342-dfb544e6.txt has every row).** One pass
per workload, cap and tree with the switch on; the answers and the calls of the check are the same in all six runs of
a workload.

| | dev, cap 32 | dev, uncapped | fuzz, cap 32 | fuzz, uncapped |
|---|---|---|---|---|
| calls of the check | 776 | 776 | 2772 | 2772 |
| certified, 29c5a0db | 159 | 163 | 1060 | 1491 |
| certified, dfb544e6 | 173 (+14) | 179 (+16) | 1283 (+223) | 1826 (+335) |
| `atom: constant pi`, 29c5a0db -> dfb544e6 | 160 -> 0 | 160 -> 0 | 544 -> 0 | 544 -> 0 |
| the 160 / 544 calls now compiled in Q[pi]: certified | 14 | 16 | 223 | 335 |
| ... the same without (2b) (no `_PiPoly` root proposed) | 14 | 14 | 224 | 328 |
| calls outside the pi class whose row changed | 0 | 0 | 0 | 0 |

Of dev's 160 pi calls 70 now stop at `atom: type Pow` (1/pi, sqrt(pi), a power with pi), 26 at floor, 12 at tan, 6
at I, 4 at sin and cos; 28 or 26 end without a pair. On fuzz all 544 compile and 321 (cap 32) or 209 (uncapped) end
without a pair. **(2b) at the default cap gains nothing: 0 on dev and -1 on fuzz** (a root takes a place among the
first 32 points); uncapped it gains 2 on dev and 7 on fuzz. It is committed and gated as it is; whether it stays is
the planner's.

**Started, not read (detached, tools342/go342.sh):** a on pareto0 (suite by id on/off/base, pre342.sh with plants
755-757, iv) and b on pareto1 (gate330.sh on both trees with xans342.py, and the planner's (i): fz342.py on both
trees, harness streams and evalbench fuzz, seeds 0 1 2 42 under hash seeds 0 1 2 42, 256 runs). An orion smoke of
fz342.py (seed 1, hash seed 0, the worktree): rows equal off and on in the three kinds; the harness stream compiles
almost nothing (1 of 172 calls; 40 reach the pi compile), evalbench certifies 1322 of 2752 calls. HANDOFF-sa-port-342.md
says where the end markers are.

**Sizing only, not S1** (orion, one cold run each, py, dfb544e6, qt342.py): budget 0.79 s off, 2.76 s on; wiring
4.17 s off, 5.48 s on. The quiet-lease run (6) measures this at both SHAs.

## sa-port-343 and 344: (2b) reverted; (5) the gate on dfb544e6 and on 01e8ca74, read

**(2b) reverted (c4d6e92c, the planner's ruling on sa-port-342's report).** A symbol takes rational values only: no
root in Q[pi] is proposed. Exact pi stays. test_witness.py + test_sympy_api.py + test_layering.py: 262 passed, switch
off and on (orion). The reasons table at the default cap is now the row "without (2b)" of the table above, and the
gate's digest rows confirm it: **certified at cap 32, 29c5a0db -> 01e8ca74: dev 159 -> 173, fuzz 1060 -> 1284** (with
(2b), dfb544e6: 173 and 1283). Uncapped, by sa-port-342's rows and not run again: dev 163 -> 177, fuzz 1491 -> 1819.

Tested SHAs: dfb544e6 (with (2b); rows under orion ~/sa-rust-ids-work/sa-port-342) and **01e8ca74** (satassume source
c4d6e92c, without (2b); rows under ~/sa-rust-ids-work/sa-port-343), each against base 29c5a0db. No Rust change since
the base, so every tree runs the pareto venv .so cad764d46471b1c6. pareto0, one shared lease a job (tools342/job342.sh,
tools343/jobb343.sh). The head bfceccc9 adds e2088c05 (harness/state.py only), tools and handoffs to 01e8ca74.

| | dfb544e6 | 01e8ca74 |
|---|---|---|
| suite by id, Rust: on / off / base | 6309 ids, 129 failed, on and off / 6262 ids, 127 failed | 6309 ids, 127 / 128 failed / 6262 ids, 127 failed |
| suite by id, Python: on / off / base | 2 failed, on and off / 0 failed | 1 failed, on and off / 0 failed |
| ids in one tree only | 47, all tests/test_witness.py | 47, all tests/test_witness.py |
| on against off, outcome differs | 0 ids, both backends | Rust 1 id (the planted-history test, below); Python 0 |
| against base, outcome differs | 2 ids, both backends, on and off | 1 id, both backends, on and off; and the planted-history test on Rust on |
| quiet catches recorded | Rust 49 in 9 ids, Python 10 in 7 ids: on, off and base | the same |
| iv, 64 runs off + 64 on | failing ids differ off against on in 0 runs | 0 runs |
| digests, dev and fuzz | 31cd0945c07f02a6, 173502b6ef285ad6: off and on, py and rust | the same four |
| certified at cap 32, dev / fuzz | 173 / 1283 | 173 / 1284 |
| 20 workloads, py and rust, off and on | answers equal on both trees; 80 cells, answers and messages equal | the same |
| fuzz seeds (4 seeds, 4 hash seeds; evalbench py and rust, harness, harness-custom) | rows equal on every run; 0 differ | rows equal on every run; 0 differ |
| certified on the seeds: evalbench / harness / harness-custom | 20960 of 43988 / 4 of 2908 / 0 of 2424 | 20964 / 4 / 0 (base 17400 / 0 / 0) |

The ids against base:

- `tests/test_history.py::test_module_state_inventory_is_classified` fails on both SHAs, both backends, on and off
  (the check's `FIRED`, `PI_TABLE`, `_LO`, `_HI`, `_BAD_LO`, `_BAD_HI` were not classified). Fixed by e2088c05
  (harness/state.py, a shared file, 2 hunks; not in the gate's SHA). On the head bfceccc9 (orion, .so
  a956b03496066671): test_history.py, test_sympy_boundary.py, test_witness.py and test_layering.py, **377 passed in
  each of the four cells** (python and rust backend, switch off and on).
- `tests/test_sympy_boundary.py::test_static_check_passes_on_the_package` failed on dfb544e6 only (a `# sympy-boundary`
  comment one line away from its read, in (2b)'s code); gone with c4d6e92c.
- `tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence` (the known
  id()-reuse failure; not edited). On 01e8ca74 the Rust on-row passed it once (base and off failed, `assert 0 == 2` and
  `assert 1 == 2` at :204), and it failed on **Python** in the gate's two patch rows (pre342.sh:32-33: the tests that
  patch `Engine.ask`, one process, switch off and on; `assert 0 == 2`). a28c548's method each time it shows:

| 20 runs a cell, 01e8ca74 (pre/rep/rep-sum.txt) | switch off | switch on |
|---|---|---|
| Rust, the test | 0 of 20 pass (19x `assert 0 == 2`, 1x `assert 1 == 2`) | 0 of 20 (16x, 4x) |
| Rust, keep-alive | 20 of 20 | 20 of 20 |
| Python, the test | 18 of 20 (2x `assert 1 == 2`) | 20 of 20 |
| Python, keep-alive | 20 of 20 | 20 of 20 |

| the patch row, Python, 12 runs a cell (tools344/rep344.sh, rep-sum-patch-row.txt) | switch off | switch on |
|---|---|---|
| 01e8ca74, the row as the gate runs it | 10 of 12 (2x `assert 0 == 2` at :204) | 10 of 12 (2x) |
| 01e8ca74, the planted-history test replaced by the keep-alive variant | 12 of 12 | 12 of 12 |
| 29c5a0db, the row | 10 of 12 (2x `assert 0 == 2`) | 12 of 12 |
| 29c5a0db, keep-alive | 12 of 12 | 12 of 12 |

  The base fails the row at the same rate, the keep-alive variant passes every run (80 of 80 and 48 of 48), and Python
  is at its base rate
  (a28c548: 2 and 6 in 50): the signature of [137e], a test artifact. dfb544e6's repeat check read Rust 0 of 20 off and
  on, keep-alive 20 of 20, Python 20 of 20 in all four cells.

Known base rows, by id. Rust base fails 127 ids (cause 672c421, not this step's): test_lra_fuzz.py 43,
test_solver_incremental.py 36, test_solver.py 14, test_theory_hooks.py 10, test_euf.py 7, test_euf_fuzz.py 4,
test_solver_real_theories.py 3, test_writeback_provenance.py 3, test_transfer.py 2, and one each in
test_public_incremental.py (the planted-history test), test_relations.py, test_lra_exhaustion.py,
test_verify_integration.py and test_template_tables.py. On 01e8ca74 the Rust off-row fails those 127 and the inventory
test; the on-row those less the planted-history test, and the inventory test. iv: Rust fails
test_transfer.py::test_models_respect_transfer and ::test_protocol_on_fuzz in 16 of 32 runs, off and on, both SHAs
(known: witness-check.md:111 and :199); Python 0 of 64.

Plants on 01e8ca74 (python, switch on; `pre/dig/dig.jsonl`, `pre/tw/*.log`, 186 tests a row: test_witness.py and the
tests that patch `Engine.ask`):

| plant | dev digest, certified | fuzz digest, certified | failed of 186 |
|---|---|---|---|
| none | 31cd0945c07f02a6, 173 | 173502b6ef285ad6, 1284 | 0 (test_witness.py alone: 150 passed, py and rust, off and on) |
| 755 pi-sign | MATCH, 171 | DIFFER f92b35588dda34ba, 1234 | 11 |
| 756 pi-rational | MATCH, 173 | MATCH, 1284 | 10 |
| 757 pi-enclosure | MATCH, 173 | MATCH, 1284 | 9 |
| 749 integer-half | DIFFER, 184 | DIFFER, 1292 | 6 |
| 750 single | DIFFER, 503 | DIFFER, 2349 | 59 |
| 751 skip-own | MATCH, 173 | MATCH, 1284 | 6 |
| 752 skip-patched | MATCH, 173 | MATCH, 1284 | 10 |
| 754 skip-users | MATCH, 173 | MATCH, 1284 | 6 |

pi-sign moves the certified count on dev (173 -> 171) without moving dev's answers: on 01e8ca74 its workload catch is
fuzz only (on dfb544e6 it was DIFFER on both). pi-rational and pi-enclosure are caught by tests only, as on dfb544e6.
Nothing else differs on the head.

## sa-port-344: (6) S1 on 01e8ca74 against 29c5a0db, and the planner's (a), (b), (c)

pareto1, quiet leases only: ea798437 (sa-port-343: tools343/onlease343.sh, bench-container on CPU 2, sa-eval-bench:1,
bench .so 0982a28074215658, 8 arms SHA:MODE-WITNESS, 12 rounds; `s1/med-s1.txt`, `s1/med-bw.txt` under
~/sa-rust-ids-work/sa-port-343) and b5a7cd65 (sa-port-344: the per-call rows again, below). Pinned wall time, median
of 12, seconds; digests equal in every arm (dev 31cd0945c07f02a6, fuzz 173502b6ef285ad6, budget 35bc2c4a937bebc0,
wiring a0df9fd43e5180c1).

| | py off | py on | rust off | rust on |
|---|---|---|---|---|
| dev, 29c5a0db | 0.5342 | 0.5203 | 0.6493 | 0.6560 |
| dev, 01e8ca74 | 0.5326 | 0.5238 | 0.6498 | 0.6597 |
| fuzz, 29c5a0db | 8.0929 | 5.8295 | 5.8561 | 4.7605 |
| fuzz, 01e8ca74 | 8.1074 | 5.4198 | 5.8437 | 4.6357 |
| budget, 29c5a0db | 0.4753 | 1.6919 | 0.3178 | 1.5449 |
| budget, 01e8ca74 | 0.4753 | 1.6923 | 0.3183 | 1.5432 |
| wiring, 29c5a0db | 2.7453 | 3.4694 | 3.2552 | 4.0475 |
| wiring, 01e8ca74 | 2.7469 | 3.4752 | 3.2577 | 4.0511 |

**Head against base, the landing rule.** On: dev +0.7% py and +0.6% rust, within the spread (larger iqr 1.2% and
1.8%); fuzz **-7.0% py and -2.6% rust, beyond the spread, faster** (0 of 12 rounds slower); budget +0.0% and -0.1%,
wiring +0.2% and +0.1%, within the spread. Off: all eight within the spread (-0.3% to +0.2%). So dev and fuzz show no
loss against on-at-29c5a0db and pi does not make budget or wiring worse: **the landing rule holds.** The check's own
seconds rise with what it now compiles (dev 0.044 -> 0.062 s py, fuzz 0.507 -> 0.788 s; fuzz compiles 2772 of 2772
calls, before 2228) and fuzz still gains, by the 224 sessions not built.

**On against off: a finding about the landed check, the same at both SHAs, not a block.** budget +256% py (0.475 ->
1.692 s) and +385% rust; wiring +26.5% py and +24.4% rust; dev -1.7% py (beyond the spread, faster), +1.5% rust
(within); fuzz -33.2% py, -20.7% rust.

**The per-call rows were taken again (tools344/pc344.py), because tools343/pc343.py's py rows are void for certified
calls.** pc343.py wraps `Engine.ask` and `Engine._within_budget` in py mode and did not register the wrappers with
`witness.accept`, so the check's last guard (`_patched`, witness.py:841, the P1 guard) took them for a user's methods:
every py row read certified 0 (cx343's 20 workloads, timing-pc's py rows, and the orion sizing in
HANDOFF-sa-port-343.md), while rust mode, which sets no wrapper on the engine, read wiring 231. pc344.py registers
them; its py rows give dev 173, fuzz 1284 and wiring 231, the gate's and rust mode's counts. It also records, per
call, the calls of `_holds` (points decided) and the time before `_pools` (the per-call compile). The guard is asked
last, so pc343's times of the check stand; its exits and certified counts do not. Rows:
~/sa-rust-ids-work/sa-port-344/s1/timing-pc (3 cold passes, both trees, py and rust; summary tools344/pc-sum.txt by
pcsum344.py) and ~/sa-rust-ids-work/sa-port-344/cx (counts; pareto0).

**(a) Where the check runs.** `_engine_ask` calls it (sympy_api.py:1136) when the switch is on and the query has
assumptions: after the relevance layer's answer memo (`_ask_general`, sympy_api.py:586-599: a hit never reaches the
check) and before `Engine.ask`, so before every cheap exit of the engine: non-commutative atoms (engine.py:2222), the
budget test (`_within_budget` :2225, then `_over_budget` :1860), a memoized INCONSISTENT or Uninterpreted of the set
(`_context_session` :1876, `_build_context_memoized` :1893). Calls per workload on 01e8ca74 (py, cap 32), by what
followed; "no-build" is `Engine.ask` ending without `_build_context`:

| workload | queries | calls of the check | do not reach `_pools` | certified | session | no-build | over-budget | noncommutative |
|---|---|---|---|---|---|---|---|---|
| dev | 1985 | 776 | 241 | 173 | 603 | 0 | 0 | 0 |
| fuzz | 3000 | 2772 | 0 | 1284 | 1448 | 40 | 0 | 0 |
| budget | 28 | 19 | 0 | 0 | 12 | 0 | 7 | 0 |
| wiring | 6512 | 4814 | 3311 | 231 | 4583 | 0 | 0 | 0 |
| core | 1636 | 299 | 113 | 95 | 204 | 0 | 0 | 0 |
| zero | 854 | 699 | 594 | 52 | 594 | 53 | 0 | 0 |
| lra | 1500 | 796 | 774 | 1 | 745 | 50 | 0 | 0 |
| cert | 61 | 61 | 0 | 1 | 60 | 0 | 0 | 0 |
| ground | 18 | 14 | 0 | 4 | 10 | 0 | 0 | 0 |
| port | 19 | 19 | 0 | 0 | 19 | 0 | 0 | 0 |
| transfer:7:60 | 60 | 60 | 46 | 2 | 58 | 0 | 0 | 0 |
| transfer2:3:40 | 40 | 40 | 34 | 1 | 39 | 0 | 0 | 0 |
| value | 3742 | 636 | 636 | 0 | 319 | 317 | 0 | 0 |
| rootof | 5187 | 368 | 368 | 0 | 368 | 0 | 0 | 0 |
| loop | 420 | 244 | 244 | 0 | 244 | 0 | 0 | 0 |
| scope | 169 | 166 | 166 | 0 | 166 | 0 | 0 | 0 |
| opaque | 2546 | 30 | 30 | 0 | 30 | 0 | 0 | 0 |
| cls | 72 | 21 | 21 | 0 | 21 | 0 | 0 | 0 |
| f6 | 2902 | 4 | 4 | 0 | 2 | 2 | 0 | 0 |
| twin | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| all 20 | 30753 | 11838 | 6582 | 1844 | 9525 | 462 | 7 | 0 |

Of the 9994 calls that fall through, 9525 go on to a session, 462 end in the engine without one and 7, all on
budget, are refused as over budget. No workload has a non-commutative query that reaches the check.

**(b) The per-call cost on budget and wiring** (01e8ca74, py, median of 3 passes a call; 29c5a0db is within 0.3% on
every line, and rust mode reads 3% to 5% more in the check).

| | calls | seconds in the check | median | 90% | max | points decided: median, 90% |
|---|---|---|---|---|---|---|
| budget, certified | 0 | | | | | |
| budget, fall-through | 19 | 1.188 of the pass's 1.653 | 72.4 ms | 158.4 ms | 158.5 ms | 32, 32 |
| ... over-budget | 7 | 0.844 (the engine after it: 0.065) | 121.0 ms | 158.5 ms | 158.5 ms | 32 |
| ... session | 12 | 0.344 (the engine after it: 0.272) | 14.6 ms | 72.6 ms | 75.5 ms | 32 |
| wiring, certified | 231 | 0.046 | 58.5 us | 127.4 us | 2.03 ms | 5, 11 |
| wiring, fall-through | 4583 | 0.749 of the pass's 3.44 (the engine after it: 2.130) | 9.4 us | 118.7 us | 2.68 ms | 0, 32 |
| ... do not reach `_pools` | 3311 | 0.046 | | | | 0 |
| ... end under the cap | 770 | 0.062 | | | | 21435 in all |
| ... run to the cap of 32 | 502 | 0.640 | | | | 32 |

Top 10 on budget, query index in `budget_wl.queries()` and milliseconds in the check: 5 (158.5), 6 (158.4), 4
(145.7), 27 (121.0), 11 (87.2), 13 (86.9), 12 (86.7), 26 (75.5), 24 (72.6), 25 (72.4): 1.065 s of 1.188 s; the first
seven are the over-budget ones. Top 10 on wiring: indices 6251, 6250, 6252, 6249, 6247, 6248, 6246, 6269, 6275, 6302,
2.66 to 2.68 ms each, 0.027 s of 0.795 s: sign questions on one long sum, all at the cap, no tail. The compile is
0.4% of the check's time on budget (5 ms) and 0.032 s on wiring's 1503 compiled calls; the time is the points. All 19
calls on budget decide the 32 points of the cap at 1.9 ms a point (sums of about 200 symbols in exact rationals) and
certify nothing. What the 32 points return (tools344/hv344.py, orion, counts): budget 5 calls with no point
satisfying the assumptions, 9 with the proposition True at every satisfying point, 5 False at every one; wiring's
502: 259, 151 and 92.

**(c) What would make the fall-through cheap without a query-time cache.** Two bounds, both functions of the query
alone. First, the engine's budget test before the check. The seven over-budget queries on budget (indices 4, 5, 6,
11, 12, 13 and 27 of `budget_wl.queries()`) take 0.844 s of the check's 1.188 s, 87 to 158 ms each, and
`Engine.ask` then refuses each: four in 0.09 to 0.41 ms, and 12, 13 and 27 in 13 to 36 ms (on that path the only
work is the second budget test and the set's memoized verdict, engine.py:2233). `_within_budget` (engine.py:1814) is
decided from the structure of the query, the registry and the settings, before any session, so it can run before the
check, and for an over-budget query the check cannot change the answer: the engine returns None (or raises for a set
that fits the budget and is INCONSISTENT) and a certified answer is None as well. What would change is the flag: an
over-budget query the check certifies today would be counted `budget_limited` and not `witness_certified`; on the
gate's 20 workloads there is none (7 over-budget calls, 0 certified). It stays inside P1, since `_within_budget` is
one of the guarded methods. Not measured: the cost of the test alone on the calls that pass it; a fall-through pays
it in `Engine.ask` already, so unless the result is handed on it runs twice there, and the 1844 certified calls pay
it newly. Second, a bound on the search's work in place of the point count. After the reorder what is left is calls
that decide all 32 points and find no pair: 12 on budget (0.344 s) and 502 on wiring (0.640 s of 0.795 s), 81% and
more of the check's time on both, and their cost is points times formula size (1.9 ms a point on budget, 38 us on
wiring). The compiled size is known after a compile that costs under 5% of the check, so the cap can be on points
times size: small formulas keep 32 points (on fuzz med-s1.txt's row of points tried reads median 7, 90% 26, max 32), and a
200-term sum gets a few. What that costs in certified answers per workload has to be read from the reasons counter before it is
chosen; it is not measured here.

## sa-port-345: (7) the bar on bfceccc9, read

pareto0, shared lease 096a1000 (1 h 21 m, exit 0), 17:16Z to 18:37Z 19 Nov, started by sa-port-344
(tools344/gobar344.sh, job344bar.sh): `p1/bar.sh` of bfceccc9 on the frozen branch origin/bar/witness-reasons-bfceccc9,
N=6, phases tests, suite, live, plants, extra, suiteplants, fmrows, sum. Rows: pareto0
~/sp19/sa-rust-ids-work/sa-port-344/bar; the small files on orion ~/sa-rust-ids-work/sa-port-344/bar; the two reads
below in orion ~/sa-rust-ids-work/sa-port-345 (suite-by-id.txt, wall.txt). BASE is the last landing's bar suite
(sa-port-337's, on 786410d). Read as section 12 of witness-check.md read 786410d's.

The bar is valid: gobar-end.txt `END 0 END 0 2026-11-19T18:37:03Z cad764d4 bfceccc9`; source.txt bfceccc9; build.txt
and so-loaded.txt have .so cad764d46471b1c6 in all seven phases; the eight phases exit 0; 72 test files exit 0;
direct.txt ends `exit 0`; "suite: no rows" is absent. The launcher had no SLICE_ variable. env-summary.txt (the
/proc watcher on the suite rows' processes): the plain suite none, `witness:on` SLICE_WITNESS=1, the three plant rows
SLICE_WITNESS=1 and their SLICE_WITNESS_PLANT.

**Plain suite (Rust, switch off: the default path).** 6309 ids: 127 failed, 6141 passed, 23 skipped, 18 xfailed.
Against BASE (6261 ids): new 48, all tests/test_witness.py and all passed (this step's 47 and 81e6561e's kept test,
which is on rust-slice and not in BASE's SHA); gone 0; changed outcome 0. The 127 are the base's 127 by id (the list
in section (5)). `test_history.py::test_module_state_inventory_is_classified`, which failed on the gate's SHA, passes
(e2088c05 is in bfceccc9). Handler rows 39 in 2 tests, the same multiset as BASE; quiet catches recorded in the rows
49, the same in each of the five suite rows; TermFault 0.

**Workloads, switch off.** dev and fuzz MATCH py against py, py against rust and both end-state rows (answers
31cd0945c07f02a6 and 173502b6ef285ad6); the 15 extra workloads: 30 rows MATCH. Kept and refused shares equal BASE's
on all 17. Handler files of the workload runs (157 files, the step rows included): 0 rows each. fm rows: 20
workloads, 0 differ; the two fm plants are caught (4 and 3 differ, exit 1).

**`witness:on`** (Rust with the switch on). Against Python with the switch on: MATCH on all 17 workloads. Against
Python with the switch off: answer_diff 0 and msg_diff 0 on all 17; sessions differ where the check certified (fuzz
1273, wiring 231, dev 178, core 92, zero 52, transfer:7:60 2, transfer2:3:40 1, cert 1, the other nine 0). That the
switch was on in these rows: queries that made a solver, off -> on, are dev 867 -> 697, fuzz 2937 -> 1756, wiring
5628 -> 5397, core 1634 -> 1542, zero 654 -> 611, the same number on the Python reference and on the Rust row. On the
nine workloads where nothing is certified the row shows nothing but its command line. Suite row: 127 failed, 0 ids
change against the plain suite; test_witness.py 150 passed.

**The step's plants**, each with the switch on. Workload rows against Python with the switch on; suite rows against
this bar's plain suite, every changed id `passed -> failed`:

| plant | fired on workloads | workload rows | fired in the suite | suite row |
|---|---|---|---|---|
| 755 pi-sign | dev 379, fuzz 6986, cert 2632 | DIFFER on fuzz (answers 24, messages 9, answers f92b35588dda34ba, the gate's digest) and on dev (answers 0, messages 0; 3 sessions and 1640 stats rows: 699 queries make a solver against 697); MATCH on the other 15 | 17212 | 143 failed; 16 ids: test_witness.py 11, test_lra_constants.py 3, test_lra_constant_coefficients.py 1, test_relevance.py 1 |
| 756 pi-rational | 0 on all 17: no workload reaches it | MATCH on all 17 | 216 | 137 failed; 10 ids, all test_witness.py |
| 757 pi-enclosure | dev 974, fuzz 13407, cert 1641 | MATCH on all 17 | 52899 | 137 failed; 10 ids: test_witness.py 9, test_lra_constants.py 1 |

The counts in test_witness.py (11, 10, 9) are section (5)'s on 01e8ca74. pi-sign's workload catch by answers is fuzz
only, as section (5) says; the bar's dev row differs in sessions and stats (section (5) reads certified 173 -> 171),
not in answers. pi-rational and pi-enclosure change no workload answer and are caught by kept tests only; pi-rational
fires on no workload at all, so its site is reached by the suite only (a footnote under P2). test_witness.py's tests
turn the switch on themselves and do not read the plant flag.

**The planted-history test** (`test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence`,
the known id()-reuse failure, not edited): failed in BASE and in all five suite rows, at :204 (`assert 0 == 2` in the
plain, `witness:on` and pi-sign rows, `assert 1 == 2` in the pi-rational and pi-enclosure rows), so no outcome
changes in this bar. The repeat check by a28c548's method for this source is section (5)'s (01e8ca74, which differs
from bfceccc9 in harness/state.py only): Rust plain 0 of 20, keep-alive 20 of 20; it was not run again.

**Wall times** (tools336/wall336.py; one machine, shared lease, rows of a phase side by side). Total 80 m 59 s:
tests 2 m 28 s, suite 1 m 54 s, live 14 m 21 s, plants 9 m 04 s, extra 44 m 40 s, suite plants 7 m 34 s, fmrows
0 m 57 s. Suite rows: plain 1 m 54 s, `witness:on` 1 m 50 s, pi-enclosure 1 m 54 s, pi-rational 1 m 56 s, pi-sign
1 m 54 s. Workload rows, seconds:

| row | sum of 17 | fuzz | budget | rootof | wiring | value | dev | f6 | zero | core | the other 8 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| witness:on | 1699 | 470 | 356 | 302 | 271 | 74 | 61 | 53 | 40 | 27 | 45 |
| witness:pi-sign | 1699 | 480 | 357 | 307 | 271 | 74 | 46 | 53 | 40 | 27 | 44 |
| witness:pi-rational | 1704 | 480 | 359 | 302 | 272 | 74 | 52 | 53 | 40 | 27 | 45 |
| witness:pi-enclosure | 1694 | 472 | 356 | 305 | 271 | 74 | 51 | 53 | 40 | 27 | 45 |

The other 8: transfer2:3:40 12 (11 under pi-sign), transfer:7:60 11, opaque 9, loop 6, scope 3, cert 2, cls 2, twin
0. These are not the speed measure: S1 (section (6)) is.

**Landing.** Nothing in the bar is new against BASE or against sections (5) and (6), and no source or test changed
after bfceccc9 (`git diff --name-only bfceccc9 HEAD` outside results/ and the HANDOFF files is empty). The step lands
with this commit by `bar.sh land bfceccc9`, whose guard compares satassume/ and rust-spike/slice/ outside results/
between bfceccc9 and the landing commit.

## Owed, named here

- A fired counter for the Rust walker's plants (above).
- 756 pi-rational fires on no workload of the bar (section (7)): caught by test_witness.py only.
- tools343/pc343.py and cx343.sh: py rows void for certified calls (section (6)); use tools344/pc344.py.
