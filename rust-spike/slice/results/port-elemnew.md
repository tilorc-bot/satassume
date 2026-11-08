# Element._new step: interpret's memo and results off Python (issue 323)

By sa-port-159 (part 1, a360067 after rebase; was dbcda83) and sa-port-160 (parts 2 and 2b), 8 Nov. Planner's C2 ruling
(b): port `Element._new` by taking interpret's memo and results off Python, in its own step after C2. It follows the
state ruling: Rust numbers in payloads, and a Rust `Element` pyclass only where Python reads.

## What moved
- **Part 1 (sa-port-159):** `Num::to_py` (constfield.rs) returns the Rust `Element` pyclass (`PyElem`, end of
  constfield.rs) where it called `Element._new`. `==`, `!=`, `bool`, `hash` and `repr` run on Rust (counters 172-174);
  any other read is the named callback `cf:elem_py_read` (171), which builds the Python Element once per value. The term
  table's `lra_*` memo holds Rust values (`LraMemo`, term/py.rs) and builds the Python result per call (175/176 hit/miss).
- **Part 2 (e2dcace):** the pyclass has `sign()` (`Elem::sign`, counted 177 `cf:elem_sign`), and `constfield.sign` calls
  it for a value that isn't an Element, Fraction or int. The pure-Python default's path is unchanged.
- **Part 2b (5b705df):** the last 100 `Element._new` on dev came from Rust itself: relations_core.rs's port of
  `_order_infinite` called Python's `relations.sign` on an `order_sides` memo coefficient (found by a profile hook:
  `session_live.py:292 _rel_interpret` -> `sa_solver.rel_interpret` -> `constfield.sign`, 100 on dev). A pyclass
  coefficient's sign is now read on Rust (`Elem::sign`), counted 178 `rel:elem_sign`. Undecided returns early, as before.
  So `cf:elem_sign` is 0 on every workload: part 2's Python route is kept only as a guard for other Python readers.
- **Part 2b plant (62a6723, sa-port-162):** plant **123 `rel-elem-sign-flip`** reads a pyclass coefficient's sign negated
  in that branch (a wrong value). Planner's ruling (8 Nov ~09:40): dev reaches the branch 100 times, so the plant must
  be caught on dev. It is (Plants).
- **Shared-file changes:** session_live.py (plant names 118-123), session.rs (counters 170-178), relations_core.rs
  (plants 118-123, the 2b branch), term/py.rs (`LraMemo`), constfield.py `sign` (a `sign()` method of a value that isn't
  an Element, Fraction or int; the pure-Python default never takes it). New step test: test_elem_pyclass.py (27 tests).
- **Numbers this step holds:** counters 170-178, plants 118-123. 5c7 holds 114-117 and counters 156-169.

## `_memoized`: its own named step
Decided with the planner (8 Nov ~09:40): lra_live `_memoized` becomes its own named step inside the state step(s), first
when they're split, with the atom's term ids and the query table on the Rust adapter. After this step no Element crosses
on it. What's left is Rust adapter -> Python `_memoized` -> lra_live `memoized` -> `interpret`/`relation(atom)`/`_ids`
(term_live's Python id lookup of a SymPy atom) -> Rust table -> `_pairs`/`_objs` -> back. Moving it needs term_live and
session_live per-query state on Rust, which the state ruling gives to the state step(s). Counts below are unchanged.

**State-rule search (memo tuple identity):** rg over satassume/, tests/ and rust-spike/slice/ found no reader of a memo
result's identity other than `is True/False/None` (singletons; tests/test_lra_adapter.py:213, test_lra_constants.py). So
returning a freshly built tuple per call, in place of Python's stored one, changes nothing Python can read.
