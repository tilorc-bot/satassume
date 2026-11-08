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
