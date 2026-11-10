# `ad:cbm_noid`: why the suite's count varies (issue 323, OWED [111])

sa-port-235, 10 Nov, on 59e9d15, orion only. Branch `port/cbm-noid`, not landed, not wired. No full suite run.

## Cause

`ad:cbm_noid` ticks when `Reader::id` finds a row for a term by `==` but the row's class is not the same class
object. That is the audit's pointer (b), and the classes are SymPy's undefined functions: every `Function('f')` call
makes a new class object, and two of them are equal (`==`, same hash) to SymPy.

1. An earlier test makes its own `f` and builds `f(1)`. Process-wide memos keyed by `==` keep that object: SymPy's
   `cacheit`, and satassume's `sympy_api._FORMULAS`, `_KEYS`, `_CONST` and `lra_bounds._BOUNDS` (found by walking
   referrers at the first tick).
2. A later test with another `f` builds `f(1)`. Depending on what SymPy's cache still holds, it gets the old object or
   a new one of its own class.
3. When the query's rows hold one class object and the engine's atoms (from a memo) hold the other, `ids` has the term
   but `type(row) is type(e)` is false, so there is no id and Python reads the atom: one tick per read.

In the reproduction every tick had the form "e is `f(1)` of the class made in
`tests/test_verify_soundness.py::test_non_rational_numbers_do_not_crash`, row is `f(1)` of `test_euf_adapter.f`".
Clearing `_FORMULAS` alone takes the small case from 14 ticks to 12, so no single memo is the carrier.

Pointer (a) (the slot memo stores only successes) is not the cause: 30 ticks were 30 first reads on Python's side
(`lra:interpret:no-id` 18, `lra:order_sides:no-id` 12). It was not changed.

Three things move the count: which tests ran earlier in the same xdist worker, which examples Hypothesis draws (the
suite fixes no Hypothesis seed and gives each run a new example database), and when SymPy's cache evicts.

The 19 / 910 / 376 / 208 totals were not decomposed: those runs' rows are on pareto1, off limits during bar-iii-b2.
Locally 18 of about 125 test files were run for the search (2,591 tests); one test showed the count,
`tests/test_euf_adapter.py::test_random_ask_matches_oracle`. Other tests may show it too.

## Reproduction, one order against another

Same source (59e9d15), same 390 tests, one process, `--hypothesis-seed=2`. The order is one xdist worker's from a
three-worker run of 16 files, ending in the test; the other order moves the test first.

| order | `ad:cbm_noid` | refusals in the test | the test's 61 queries and answers |
|---|---|---|---|
| 389 others, then the test | 30 (in 4 queries) | 1 (`scaffold: rebuilt form differs from Rust`) | same |
| the test, then 389 others | 0 | 0 | same |
| the test alone (seeds 1, 2, 3) | 0 | | |
| first order, seed 1 | 0 | | |

Run from `~/sa-rust-ids-work/sa-port-235/` (`probe/` holds the plugin and scripts, outside the clone):

    FILES="tests/test_layering.py tests/test_lazy_templates.py tests/test_lra_constant_coefficients.py tests/test_lra.py tests/test_theory_hooks.py tests/test_history.py tests/test_verify_soundness.py tests/test_euf_adapter.py"
    NOID_ALL=1 NOID_WHY=1 ORDER_FILE=$PWD/order-w3.txt        probe/run.sh ord-w3-all     $FILES --hypothesis-seed=2
    NOID_ALL=1 NOID_WHY=1 ORDER_FILE=$PWD/order-w3-Tfirst.txt probe/run.sh ord-Tfirst-all $FILES --hypothesis-seed=2
    python sum.py ord-w3-all; python sum.py ord-Tfirst-all; python cmp.py ord-w3-all ord-Tfirst-all

Shorter orders gave 0 both ways (the two tests alone; the two files in either order), so the effect needs enough
earlier work to turn SymPy's cache over. The deterministic form needs no order: `test_cbm_noid.py` builds the two
classes with `clear_cache()` between them. On 59e9d15 those queries tick 14 (second class) and 19 (both classes in
one query), and 0 for the first class.

Each run has 1 failure, `test_theory_hooks.py::test_random_forbid_theory_matches_brute_force`, one of the named stub
failures, the same in every order.

## Can the variance reach an answer or state?

Answers: no, as far as checked. On a tick Rust calls Python's own `_memoized` with the same arguments
(adapters.rs `self.callback`), so the value is Python's by construction, and nothing is stored in the slot on that
path. Checks:
- The 61 queries of the test give the same answers in the same sequence with 30 ticks and with 0.
- Six queries with both class objects inside, two of which need them to be one function (`Q.eq(f1(a), f2(a))`, and
  `Q.eq(f1(a), f2(b))` given `Q.eq(a, b)`), give `True, True, False, None, True, False` on Python and on Rust, before
  the fix, after it and under the plant.

State: not compared by a state harness, only by answers. What the variance does decide before the fix is the path:
counters, speed, and one whole-query refusal that reruns on Python.

The fix itself changes one thing Python could read by identity: where a term of an equal class takes the row, the
native result holds the query's own row object, and Python's result holds the atom's object. They are `==` with `==`
classes. Python's own choice there follows its process-wide `_INTERPRETED` memo, so it is history too. No whole-tree
search or guard for "nothing reads the class object by identity" was done; under the state rule that is an unnamed
exception until the planner rules on it.

## Fix (on the branch)

Classes are compared by `==`, not `is`, at the three sites the audit named: adapters.rs `Reader.id`, and
term_live.py `term_id` twice. For an ordinary class `==` is identity, so Float against Integer still has no row.
13 lines added, 6 removed over three files, plus the test (73 lines).

After the fix: 0 ticks in both orders, the 61 answers unchanged, the small case 0 / 0 / 0.

Plant 660 `ad-lra-class-is` puts the identity compare back in `Reader.id`.
`test_cbm_noid.py::test_plant_660_fires_and_is_seen`: fired 154 times, `ad:cbm_noid` 154 where
`test_equal_classes_take_the_row` asserts 0, answers unchanged. No counter id was used (670-679 free).

## Still open

- The same identity compare is unchanged at rows_tpl.rs:757, :1371, :1395, outer_tpl.rs:242, fn_tpl.rs:201,
  term_live.py:244, :356, knowledge_core_live.py:89 and knowledge_live.py:272 (siblings' modules). The refusal
  `scaffold: rebuilt form differs from Rust` still follows order after the fix (1 against 0), probably through :356.
  So history independence (#96) is not met by this fix alone.
- `term_id`'s rule also sent `_is_number`, `link`, `key`, `relation_atom` and `structural` to Python in the small
  case; those have their own counters and were not followed.

## Not run

Full suite, dev and fuzz MATCH, the 13 workloads, `test_lra_slot.py` and the other slice tests on the fixed build,
x86-64 build, anything on pareto1, timing. The fix is tested only by the runs above.

## The fix on port/formula (sa-port-243, 10 Nov): the query's own class table

Ruling: addenda/sa-port-cbm-noid-fix-ruling.txt (one fix, per-query `==` class keys). 6d6102f above is reference only; its
two-site `==` is replaced by this.

- The query's conversion already gives each class one id by the classes' hash and `==`: `convert._Walk.classes`
  (convert.py `klass`), a dict made per query. `_Query` now keeps it (`q.classes`, term_live.py).
- One rule, `same_class(q, a, b)`: the same class object, or two class objects with one id in `q.classes`. A class the
  query's input doesn't hold has no id, so it is one class only with itself. term_live.py has it for the Python sites and
  formula.rs (`formula::same_class`) for Rust's, the same lines. Nothing process-wide is read or written.
- Sites now asking it (11): adapters.rs `Reader.id`; rows_tpl.rs `QIds::ids`, `learned`, `check_products`; outer_tpl.rs
  (multigamma); fn_tpl.rs `slots`; term_live.py `_key_consumer`, `term_id` (input row and derived row), `scaffold`'s
  rebuilt-form check; knowledge_core_live.py `ids_of`; knowledge_live.py's symbol/constant units.
- **Not edited: rows_tpl.rs `same_value`** (:757 in the ruling's list). It compares an argument with a constant written
  in a rule's shape, not a term with a row; the constant's class is a number class, where `==` on classes is identity.
- term_live.py is also edited by state part 3 (import block and `_install` only); the architect was told before the edit.
- Counters 670 `cls:eq`, 671 `cls:differs` (formula.rs, in the session report). Plants 660 `ad-lra-class-is` (identity
  back in `Reader.id` alone; moved from relations_core.rs's list to formula.rs's, so `sa_solver.formula_plant` or
  `SLICE_SESSION_PLANT` sets it) and 661 `class-is` (identity back at every site, Rust's and term_live's, one switch).

### Checked (short checks, **not the bar**; build of the working tree on 3985a76, orion)
- Two-order reproduction, same 390 tests and seed as above (`~/sa-rust-ids-work/sa-port-243/ord-w3-all`, `ord-Tfirst-all`):

  | order | `ad:cbm_noid` | "rebuilt form differs" refusals | `cls:eq` | the test's 61 asks |
  |---|---|---|---|---|
  | 389 others, then the test | 0 (was 30) | 0 (was 1) | 35 | same sequence and answers |
  | the test, then 389 others | 0 | 0 | 0 | same |

  Each run has the 1 named stub failure (`test_theory_hooks.py::test_random_forbid_theory_matches_brute_force`).
- test_cbm_noid.py, 4 tests, under Rust: passed (`ad:cbm_noid` 0 with `cls:eq` 30 and `ad:lra_native` 268; plants 660 and
  661 fire and are seen). On Python: answers checked, counts skipped.
- dev MATCH (1,985) and scope MATCH (169), one Rust run against sa-port-234's Python runs. `cls:eq` and `cls:differs`
  are **0 on dev and scope**: no workload run so far reaches the slow path, so plants 660/661 are void on them and the
  path is reached only by test_cbm_noid.py and the suite. A workload or a footnote is owed (gaps ruling). zero and
  plant 661 on dev were still running at the handoff (`~/sa-rust-ids-work/sa-port-243/c1/live/`, `c1/end.txt` last).

### Not finished: three slice tests that held the old rule now fail (**the item is not done**)
All three were written by state part 2 (iii) for the same case, a second equal `Function('f')` class, when `term_id`
gave it no row:
- test_rs_core.py `test_two_equal_function_classes_key_as_one`, `test_class_split_plant_is_caught`: `rk:twin` is now 0.
  relkeys.rs `twin_row` (:97-120) took the first class's row when `term_of` had none; `term_of` now has it, so
  `twin_row` and plant 409 `rk-class-split` can no longer fire. Proposed, not done: delete `twin_row`, its call in
  `rk_key`, plant 409 (relkeys.rs:83, relations_core.rs:685, session_live.py:1001) and the `rk:twin` counter, and have
  the two tests assert `cls:eq` > 0 and use plant 661. relations_core.rs and session_live.py are also edited by state
  part 3, so tell the architect first.
- test_relations_core.py `test_join_second_object_resolves_on_its_own` (:981): it asserts the other class's object has
  **no** id from `rel_link_probe` (`[want, None, want, want, None]`); it now gets the row's id (`[want] * 5`). Its
  `second`/`none` counts were not read after the change.
- Four more files fail in the same run and were **not checked against the base build**: test_term_live.py (2,
  `'_Mark' object has no attribute 'facts'`), test_handler_count.py (2), test_catch_count.py (3), test_cf_diff.py
  (collection error on `sys.argv`). None is in sa-port-234's list of 17 files, so they may fail on the base too.
  The other 43 files pass (`~/sa-rust-ids-work/sa-port-243/c1/slice/summary.txt`).

### Q1, open with the planner: which object a native result holds
The ruling asks that native results hold exactly the objects Python's hold. Measured on the six mixed-class queries of
test_cbm_noid.py (Rust: `sa_solver.ad_lra_export`; Python: `_memoized`'s results; `~/sa-rust-ids-work/sa-port-243/explore-*`):
- Two of the six are kept queries (`Q.eq(x1, x2)`, `Q.lt(x1, x2)`: `args-eq-not-is`), so Python reads them.
- In the other four every `f(...)` in a native result is the query's own row object (the first equal object the
  input shows). That is a function of the query alone.
- **In two of them Python's result holds another object**: `interpret(Q.lt(f(a), f(a) + 1))` in `Q.gt(x1 + 1, x2)` and
  `interpret(Q.lt(f(a), 2))` in `Q.le(x1, 3)` given `Q.lt(x2, 2) & Q.real(x2)`. Python holds the atom's own `f2` object,
  the native result the row's `f1` object. Before the fix these reads went to Python (`ad:cbm_noid`), so the two agreed.
- Making them agree is not a few lines: the atom's side can differ from the row at any depth (`x2 + 1` against the row
  `x1 + 1`), and Python's own choice follows its process-wide `_INTERPRETED` memo. The same difference already exists
  without mixed classes (two equal objects of one class), since the slot was built; test_lra_slot.py compares results by
  class name and repr, not identity.
- Identity readers in `satassume/` (one read-only search of the package; not `rust-spike/`, `tests/` or SymPy): no
  `id()` on a term, no `.func is`. Two real ones, both the Pow rule "x**x is positive" in
  knowledge/templates/wiring.py (:223 `a is not args[s[1]]`, :323 `b is e`): equal-but-distinct base and exponent drop
  the rule (a weaker answer, not a wrong one); reader terms reach it through `relations.py` :1123/:1448 `s.ensure`.
  engine.py:1722 and relations.py:1657 read by identity but behave as equality. No reader term reaches a value returned
  by `ask`/`is_`; one can become a key in `Engine.cache.store` (relations.py:1116 `engine.is_(u, "real")`, engine.py:2039),
  which a user can inspect.
- test_cbm_noid.py `test_native_results_hold_the_querys_own_rows` pins today's behaviour, including the two differing
  cases. **No plant was built for Q1**: which direction is right is the question.
