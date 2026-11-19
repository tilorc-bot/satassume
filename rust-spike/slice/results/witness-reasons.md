# Witness reasons: raising how many Nones the check certifies (issue 323) — IN PROGRESS, NOTHING LANDED

sa-port-340, branch port/witness-reasons from rust-slice 29c5a0db. Items (0), (1), (2a) and the (3) simulation are
done; exact pi (2), (2b), the plants (4), the gate (5), S1 (6) and the bar (7) are not. HANDOFF-sa-port-340.md has
the order and the map.

Tested SHAs and .so: base 29c5a0db (source-equal to 81e6561e in satassume/, tests/ and rust-spike/slice outside
results/), pareto .so cad764d46471b1c6 (338's venv build, and the same hash from the bar's own build of 1f6ddb5b),
orion .so a956b03496066671. Head 1f6ddb5b changes no Rust. SLICE_WITNESS is off by default and the unchanged path is
the default. No SymPy construction or evaluation at query time. "Exact" rests on 325's 14-predicate table (issue
247: SymPy evaluation is not ground truth); (2)'s arguments are not written yet. S1 has not been run.

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

## Owed, named here

- A fired counter for the Rust walker's plants (above).
- The exit code of the void bar and the bar-level fired lines, unread at the handoff.
