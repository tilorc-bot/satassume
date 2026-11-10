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
