# HANDOFF sa-port-159: Element._new step, part 1 pushed (port/elemnew dbcda83); not landed (issue 323)

## State (8 Nov, ~08:45 UTC)
- port/elemnew = **dbcda83** on rust-slice **29ee93e** (C2). Pushed to origin. Orion .so built from dbcda83 in the clone.
- No bar run. No job running. Uncommitted: nothing tracked.

## What's done (dbcda83)
- `constfield.rs` end of file: `PyElem`, the Rust `Element` pyclass (`sa_solver.Element`, unsendable, weakref).
  `Num::to_py` (constfield.rs, about :2005) gives it in place of `Element._new`. An Elem that came from a Python Element
  still goes back as that object (`e.py`). `Elem.pyw` is a weak handle, so the same pyclass object comes back while it's alive, with no Rc cycle.
  `==`/`!=`/`bool` (`py_eq`, `nonzero`), `hash` (Python's `hash(("constfield", n, d))` on `poly_to_py`), `repr`
  (`poly_repr`, port of constfield.py:1293) run on Rust. Everything else (order `<`..., arithmetic, `__getattr__`
  e.g. `_n`, `sign`, `to_sympy`) is the named callback `cf:elem_py_read`, which builds the Python Element once per
  Elem (`to_py_element`, the old route). `Num::from_py` and `cf_num` accept the pyclass. `cf_op` returns Python Elements
  (`to_py_element`) so test_cf_diff is unchanged. It has a new op `rust_element` for the test.
- `term/py.rs`: `lra_memo` holds `LraMemo` (Rust values: Constraint / sides / integral, ids), and builds the Python
  result on each call. `TermTable` is now `unsendable`, as LraCore and the adapters already were.
- Counters (session.rs): 156-169 placeholders `rsv:5c7:*` (port/5c7's numbers; on rebase over 5c7, drop them and keep
  5c7's names). 170 `cf:elem_new`, 171 `cf:elem_py_read`, 172 `cf:elem_eq` (also bool), 173 `cf:elem_hash`,
  174 `cf:elem_repr`, 175 `lra:memo_hit`, 176 `lra:memo_miss`.
- Plants (relations_core.rs, `SLICE_SESSION_PLANT` / `rel_plant`; 114-117 left for 5c7): 118 `elem-memo-plus1` (a memo hit gives
  one more: the interpret rhs, the integer_form constant, or the first side's first coefficient, so it's a WRONG VALUE
  and the entry is still there), 119 `elem-eq-flip`, 120 `elem-hash-skew`, 121 `elem-repr-bracket`, 122 `elem-from-neg`.
  Listed in session_live.py `_REL_PLANTS`.
- test_elem_pyclass.py: 26 passed (about 215 Elements in pi, E and sqrt 2 against Python's eq/hash/repr/bool/from_py,
  counters, fallback values, copy). Plants 119-122 are caught there.

## Local check (orion, `~/sa-rust-ids-work/sa-port-159/q1/`, script `../q.sh OUT WLS`)
- dev and cert, Python vs Rust: **MATCH**, answers 31cd0945c07f02a6 (same as C2's) and 6a09c059eb266747; 0 end/stream/lra diffs.
- cf_trace (sa-port-140's `cf_trace.py`), Rust: Element._new **dev 703 -> 100**, all from `constfield.py sign` (Python's
  `(x > 0) - (x < 0)` on the pyclass -> fallback, `cf:elem_py_read` 200). **cert -> 0**. Fuzz not run.
- Session counts dev: elem_new 1380, py_read 200, eq 0, hash 179, repr 2870 (harness state dump), memo hit 2642 /
  miss 2833, **ad:cb_memoized 5508**. cert: elem_new 446, py_read 0, repr 533, memo 1532/738, cb_memoized 2270.
- test_cf_diff.py 7: 0 mismatches. test_cf_laurent.py + test_term_live.py: 22 passed, 1 skipped.

## Next, in order
1. **Remove the 100 left on dev**: find the Python caller of `constfield.sign` that gets a pyclass (likely Constant.enclose's
   `_env` path or lra_adapter; run cf_trace with a frame-2 caller). Either give `__richcmp__` Lt/Le/Gt/Ge on Rust
   (`Num::lt`; `a <= b` as `not b < a` only if the Undecided behaviour is the same, so check `_cmp`), or make the
   reader call Rust. Then cf:elem_py_read should be 0 on dev, fuzz and cert.
2. **`_memoized` crossing** (adapters.rs:91-95 `memoized` -> lra_adapter._memoized -> lra_live.py:178 `memoized` -> read(arg)
   -> lra_live interpret -> table): still 5508 on dev. Get the C2 base count (same counter on 29ee93e's .so) and report
   before/after. Taking it off Python means adapters.rs reads the table directly when a query has one. That needs term ids
   for the atom (term_live.term_id, relation()), so it may be its own step: decide and say so in the report.
3. Show plant 118 caught as a WRONG VALUE on dev or cert: `SLICE_SESSION_PLANT=elem-memo-plus1`, answers or lra state differ,
   and memo_hit > 0 with rel:plant_fired > 0.
4. Fuzz local check, then the full bar (p1/bar.sh, pareto1): PLANTS += elem-memo-plus1 elem-eq-flip elem-hash-skew
   elem-repr-bracket elem-from-neg; WLS must include `cert` (LRA-heavy) as in C2b; TESTS += test_elem_pyclass.py;
   BASE = C2b's rows `~/sp19/sa-rust-ids-work/sa-port-153/bar-C2b/`. Then land per the brief, report results/port-elemnew.md,
   ownership .md/.tsv, `agent report`.
- Identity: pyclass objects are the same while alive. Memo results are new tuples on each call (the old memo returned
  the same Python tuple). Nothing found reading tuple identity, but no whole-tree search has been done: do it for the state rule.
