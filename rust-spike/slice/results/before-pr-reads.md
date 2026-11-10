# Read-only checks from the before-any-backend-PR list (issue 323, sa-port-250)

Base: rust-slice 0192b35. Branch audit/before-pr-reads. No source change, no plant, no counter: this file is the only
commit. Scratch scripts and run output are in `~/sa-rust-ids-work/sa-port-250/` on orion (not in the repo).

| item | state |
|---|---|
| 1. `_INTERPRETED` first-seen object (Q1 (d)) | done, below |
| 2. Cause of the four slice files that fail on base | done (sa-port-251), below |
| 3. `PROCESS.clear()` and the Rust stores | done (sa-port-252), below |

## Item 1: can `_INTERPRETED`'s first-seen object reach an answer after wiring.py's `==` change?

**Verdict: no path found.** With wiring.py from 17241af on base, 0 of 560 queries change their answer in any of the
orders run; on base without the change 34 of the same 560 do (the control). Every identity, `id()` and ordering site in
`satassume/` is listed below; none besides wiring.py's two can read a memo-held term in a way that differs between equal
objects. One class of equal objects that differ without identity (`Subs` with renamed bound variables) was found and
**not tested**: it is the open point, with a proposed owner at the end.

This is a read plus a measurement on the Python backend. It is not a proof, and the query set is my own.

### What the memo hands out

`lra_adapter.py:433` `_INTERPRETED[GENERIC_CONSTANTS]`, read through `_memoized` (:439) by three methods:

| key | result | what it holds from the first-seen atom |
|---|---|---|
| `atom` (:502) | `interpret(atom)` = `(constraint, terms)` | the term objects in the payload's `(term, coeff)` items and in `terms` |
| `("sides", atom)` (:506) | `order_sides(atom)` | two `{term: coeff}` dicts, in the atom's traversal order |
| `("integer", e)` (:510) | `integer_form(e)` | `Integral(items, const)` and the sorted term list |

The key is matched by hash and `==`, so a later equal atom gets the first atom's term objects. They enter the session
at `relations.py:1016` `_interpret` (`ad.register`, `ad.terms`, `ad.order_sides`), `:1100` `_guard`
(`s.ensure(u, {"real"})`, `s.var("real", u)`), `:1423` `_order_infinite` (`s.ensure(u, ...)`), `:1134` and `:2001`
(`integer_form`), `:1956` (`order_sides`), and the adapter's `_shared` dict (`lra_adapter.py:487`). From `s.ensure` a
term can become a node, and the templates then read its arguments: that is how it reached wiring.py.

### Which equal objects can differ at all (measured, SymPy 1.15.0.dev of `~/sa-rust-ids-work/sympy`, `eqprobe.py`)

| pair | `==` | equal hash | differs in |
|---|---|---|---|
| a symbol, or any term, rebuilt after `clear_cache()` | yes | yes | identity only |
| `Pow(x1, x2)` with two equal symbol objects, against `x**x` | yes | yes | identity of the arguments |
| `Function('f')` twice (after a cache clear), and `f1(x)`, `f2(x)` | yes | yes | identity of the class |
| `Subs(sin(x) + z, x, 0)`, `Subs(sin(y) + z, y, 0)` | **yes** | **yes** | **`.args`** (same `default_sort_key`) |
| `Lambda`, `Integral`, `Sum` with renamed bound variables | no | | |
| unevaluated `Add`/`Mul` in another argument order | no | | |
| `Float(1, 10)` and `Float(1, 20)`; `Float(1.0)` and `Integer(1)` | no | yes | |
| `Function('g', nargs=1)` and `Function('g')` | no | | |

So apart from `Subs`, equal atoms have equal arguments position by position, and the only thing a reader can tell
apart is identity (of an object, or of an undefined function's class).

### Every identity, `id()` and ordering site in `satassume/`

Found with an AST scan of the 0192b35 tree (`scan_identity.py`): 68 `is`/`is not` comparisons where neither side is a
constant, a singleton or `type(...)`; 4 comparisons of two objects' classes; 17 `id()` calls; 88 `sorted`/`sort`/`min`/
`max` calls. Those that can see a term, each with its mark:

| site | what it compares | mark |
|---|---|---|
| `knowledge/templates/wiring.py:223` `a is not args[s[1]]` | two arguments of one term (`'same'` shape) | **flagged on base**; `!=` in 17241af |
| `knowledge/templates/wiring.py:323` `b is e` | base and exponent in the Pow key | **flagged on base**; `==` in 17241af |
| `engine.py:1722` `o is not d` | a popped node against the traversal's root | safe: a term does not contain itself, so identity means "the root" (footnoted by Q1 (c)) |
| `relations.py:1657` `o is node or o == node` | two nodes of one head | safe: equality, identity is a shortcut (footnoted by Q1 (c)) |
| `relations.py:1193` `lk.get(atom) is lk.get(rev)` | the link terms of `0 < e` and `e < 0` | safe: both entries are written in one statement with one object (`:1505`), and equal keys are overwritten together |
| `relations.py:1289` `lst[-1] is g` | a role's guard list against the last one stored | safe: `g` is a per-role list, not a memo result; a miss only stores the guard twice (a repeated clause) |
| `relations.py:1153`, `:1155` `b is inf` | a side against `S.Infinity`, `S.NegativeInfinity` | safe: singletons |
| `knowledge/templates/__init__.py:159` `b is c for c in _SPECIAL` | an argument against `nan`, `oo`, `-oo`, `zoo` (`:139`) | safe: singletons |
| `knowledge/templates/_rows.py:550` `s is not node` | the other argument of one atom | safe: a position inside one object |
| `knowledge/templates/_rows.py:758` `s is a` | whether `s` was derived from `a` or is `a` | safe: both come from the same loop step |
| `theories/lra/lra_adapter.py:240` `rest is not e` | `as_coeff_Mul`'s rest against its input | safe: guarded by `c != 1` beside it |
| `sympy_api.py:580`, `:966`; `engine.py:1217`, `:1448`, `:1545`, `:2342`; `rules.py:336`; `solver.py` (12); `constfield.py` (5); `_compat.py` (3); adapters' `self._solver is solver`, `t is self.theory` | formulas, containers, clause lists, theories, field elements | safe: no term |
| `theories/transfer.py:348`, `:398` `val.get(v) is wb` | two stored truth values | safe: bools (read from `:341`, `:361` only) |
| `lra_bounds.py:220-236` `head is exp` ... | a constant's head against a SymPy class | safe: fixed classes |
| class identity: `wiring.py:220`, `:463` (`type(a) is type(number)`), `lra_bounds.py:251` (mpmath types), `sat/formula.py:45` | types of numbers, intervals, formula nodes | safe: no undefined-function class reaches them |
| `id()`: `engine.py:2340`, `rules.py:334`, `compile.py:313/341/342/360`, `solver.py` (10), `memos.py:261` | clause lists, blocks, formula parts, a label | safe: none takes a term |
| ordering: `lra_adapter.py:323/348/412`, `relations.py:539` (`_key`, `:465`) | terms by `default_sort_key` | safe: the key is equal for equal objects (measured for the pairs above, `Subs` included); these run inside the readers or on the query's own sides |
| ordering: `relations.py:1435` `for u, c in form.items()` | `order_sides` dicts in the first atom's traversal order | safe: equal atoms traverse in the same order (other argument orders are not `==`); it sets clause order only |
| containers keyed by a term: `_shared`, `_guards`, `_bounded`, `_tsrc`, session tables | hash and `==` | equality; which key object is kept is rulings 4 and 5, not an answer |

`.func is`, `id()` of a term and `isinstance(x, type(term))` do not occur in `satassume/`. This agrees with sa-port-243's
search (cbm-noid-cause.md, "Q1"), which named the same two wiring.py sites.

### Two-order runs

`twoorder.py` (and `twoorder3.py`, a new `Engine` per ask): 35 terms x 16 query forms = 560 queries, most with a
relation atom over the term (`x**x`, `f(x)**f(x)`, `(x*y)**(x*y)`, `Abs(x)**Abs(x)`, `Subs(...)`, `Piecewise`, ...).
The *twin* of a query is an equal query in which every node, symbol and function class is a new object per occurrence
(built with `clear_cache()` before each node; asserted `==` with equal hash). Each order ran in its own process, on the
base tree and on a copy of it with only wiring.py replaced by 17241af's (`tree-eq/`; the diff is 10 lines). Python
backend, orion, two processes at a time.

| comparison | base | base + `==` |
|---|---|---|
| A. original: asked alone vs right after its twin (default engine) | **34** | 0 |
| A2. as A, `_INTERPRETED.clear()` between twin and original | **34** | 0 |
| B. twin: asked alone vs right after its original | **34** | 0 |
| A with a new `Engine` per ask (process memos kept) | **34** | 0 |
| A2 with a new `Engine` per ask | **34** | 0 |
| B with a new `Engine` per ask | **34** | 0 |
| original (one process) vs twin (another process), new `Engine` per ask | **34** | 0 |
| original vs its twin, per query, process memos emptied between (default engine kept) | 0 | 0 |
| base against base + `==`, original and twin, process memos emptied per query | 0 changed | |

All counts are of 560. The 34 are 25 `True -> None` and 9 `False -> None`, all on terms with two equal arguments
(`x**x`, `(x*y)**(x*y)`, `Abs(x)**Abs(x)`, `(x + 1)**(x + 1)`, `exp(x)**exp(x)`, ...). Answers of the set: 131 True,
31 False, 398 None.

Minimal two-order reproduction on base (`carrier.py`; one process, new `Engine` per ask, `PROCESS.clear()` and
`clear_cache()` between): `ask(Q.gt(x**x + 1, 0), Q.ge(x, 0))` is `True` for `x**x` with one `x` object and `None` for
`Pow(x1, x2)` with two equal ones. In one process without the clears, whichever was asked first decides both
(`t0f5`: `True, True` or `None, None`).

That the counter can fire: the wrapper around `_memoized` counts hits where the memo answers an atom that is not the
object it first stored. 113 per run with process memos emptied per query, 1,593 in the twin-first run, 6,002 with a new
`Engine` per ask. So the first-seen path ran in every order, and on base the runs do show changed answers.

What these runs do not show:
- On base, clearing `_INTERPRETED` alone does not stop the flips (A2 = A). Other holders keyed by `==` carry the first
  object too (the engine's own tables with the default engine; with a new engine per ask, the other process-wide
  memos). Whether `_INTERPRETED` alone carries one was not isolated. After the `==` change no holder matters for these
  answers, since the reader no longer tells the objects apart.
- The rows called "process memos emptied" kept the default engine, so they do not isolate a query. (A first version
  of the harness meant to give each its own engine and did not; `run2/` is void for that reason and is not used here.)
- Rust was not run: the question was about the Python reference.
- The workloads and the suite were not rerun in two orders; sa-port-244 measured 0 changed answers there for the `==`
  change itself.

### Open: `Subs` with renamed bound variables

`Subs(sin(x) + z, x, 0) == Subs(sin(y) + z, y, 0)`, with equal hash and equal sort key, and different `.args`. `_lin`
takes a `Subs` as an opaque term, so a memo-held `Subs` of an earlier query can stand in for a later query's equal one
whose bound variable has another name. No identity is involved, so the list above does not cover it. A reader that
follows a `Subs` term's arguments (to make nodes, or to match assumptions on a symbol of that name) would see the first
query's bound variable. Not checked: whether any reader does. The 560 queries hold two `Subs` terms, but a twin keeps
the bound variable's name, so they do not test this.

Proposed check: two orders of one query over `Subs(g(x), x, 0)` and `Subs(g(y), y, 0)` with an assumption on `x`.
**Done by sa-port-251: see "The `Subs` two-order check" below (0 of 392).**

### Proposed owners

| finding | owner |
|---|---|
| wiring.py:223 and :323 by `==` (17241af) is what removes the 34; it must land with formula | formula's step (already theirs) |
| `Subs` alpha-equivalence check | done by sa-port-251 (0 of 392), section below |
| Two-order harness as a kept test (twin queries; 560 here, 34 caught on the reference with `is`) | before-PR list, unassigned; it would also serve as the plant-catching test for Q1 (b) on the reference |

## Item 0 (sa-port-251): the two-order harness on satassume main

**Verdict: main (9bafaa5, the shipped Python package) has the same flips as the base: 34 of 560 answers change with
query order, and 0 of 560 with only wiring.py's `==` hunk from 17241af applied. For all 34 the order-independent answer
is the definite one (25 `True`, 9 `False`); the other answer is `None`. No wrong answer in either order: the bug loses
answers, it does not invert them.** Python only; nothing was opened against main.

### What was run

- Tree: `git worktree add --detach ~/sa-rust-ids-work/sa-port-251/main origin/main` (9bafaa5, an ancestor of 0192b35,
  499 commits behind it). The fixed tree is a copy of that worktree's `satassume/` with
  `git show 17241af -- satassume/knowledge/templates/wiring.py` applied by `patch -p1` (3 hunks, offset -13 lines, no
  fuzz); the applied diff is `item0/applied.diff` in the work dir (10 changed lines, wiring.py only: `a is not args[s[1]]`
  to `a != args[s[1]]` at :210, `b is e` to `b == e` at :310, two docstring lines).
- Harness: sa-port-250's `twoorder3.py`, unchanged. Nothing had to be adapted: main has `satassume.Engine`,
  `sympy_api.ask(proposition, assumptions, engine)`, `lra_adapter._INTERPRETED` / `_memoized` and `memos.PROCESS` as the
  base does. Each run's log names the tree it imported (`main/satassume` or `main-eq/satassume`).
- 13 orders per tree, each in its own process (`item0/run.sh`): the 8 of item 1 with the default engine, and 5 with a
  new `Engine` per ask. Env: sa-port-250's `py.sh` with `TREE` set (Python reference, `PYTHONHASHSEED=0`), orion, four
  processes at a time. 0 exceptions in any row.

### Counts (of 560; `cmp0.py item0 0 main main-eq`)

| comparison | main | main + `==` |
|---|---|---|
| A. original: asked alone vs right after its twin (default engine) | **34** | 0 |
| A2. as A, `_INTERPRETED.clear()` between twin and original | **34** | 0 |
| B. twin: asked alone vs right after its original | **34** | 0 |
| A, A2, B with a new `Engine` per ask (process memos kept) | **34** each | 0 |
| original (one process) vs twin (another process), default engine or a new `Engine` per ask | **34** | 0 |
| original from emptied process memos vs right after its twin, per query | **34** | 0 |
| twin from emptied process memos vs right after its original, per query | 0 | 0 |
| original vs twin, process memos emptied between (default engine kept) | 0 | 0 |

The last two rows are 0 on main because the default engine is kept across the asks and the original is asked first:
the twin then gets the original's answer. They are not isolation (same limit as item 1).

The 34 are the same query ids as on the base (item 1), 25 `True`/`None` and 9 `False`/`None`. In every one the term
holds a power whose base equals its exponent: `x**x` (4 queries), `(x*y)**(x*y)` (2), `Abs(x)**Abs(x)` (4),
`x**x + 1` (3), `x*x**x` (3), `(x + 1)**(x + 1)` (4), `x**x*y**y` (5), `exp(x)**exp(x)` (4), `(2*x)**(2*x)` (4),
`x**x - y**y` (1). By form: `Q.gt(t + 1, 0)` given `x >= 0, y >= 0` (8), `Q.gt(t, 0)` given `x = y, x > 0` (10),
`Q.le(t, 0)` given `x > 0, y > 0, real(f(x))` (8), `Q.extended_positive(t)` given both extended nonnegative (7) or
`x` extended nonnegative and `x < y` (1). The full list with all four answers per query is printed by `cmp0b.py`.

### Which answer is the order-independent one

With the `==` hunk, every one of the 12,320 answers (13 orders, original and twin) equals main's answer for the
original asked alone in a new process. So for each of the 34:

- the answer for the term built from one object (`b is e`) is unchanged by the fix: `True` (25) or `False` (9);
- the answer for the equal term built from two objects, and any answer asked after such a term, goes from `None` to
  that same `True`/`False`.

The other 526 queries give one answer in every order on main, and the fix changes none of them.

By hand, the definite answers are right: `b**b > 0` for real `b >= 0` (`0**0 = 1`), so the 25 `True` hold and the 8
`Q.le(t, 0)` are `False`; `x**x - y**y > 0` given `x = y` is `False`. This is my reading of 10 term shapes and 5 forms,
not a check against an oracle (SymPy's evaluation is not ground truth, issue 247).

### Three minimal reproductions on main (`item0/repro.py CASE ORDER`, one process each; output in `item0/repro.out`)

`same` builds the query with `Pow(x, x)` from one `x` object. `distinct` builds an equal query (`==`, asserted) whose
power is `Pow(x, Symbol('x'))` made after `clear_cache()`, so base and exponent are equal and not one object.

| case | query | engine | `same` alone | `distinct` alone | `same, distinct` | `distinct, same` | with `==`, all four |
|---|---|---|---|---|---|---|---|
| r1 | `ask(Q.gt(x**x + 1, 0), Q.ge(x, 0))` | default | True | None | True, True | None, None | True |
| r2 | `ask(Q.le(x**x, 0), Q.gt(x, 0))` | a new `Engine` per ask | False | None | False, False | None, None | False |
| r3 | `ask(Q.gt(x**x - y**y, 0), Q.eq(x, y) & Q.gt(x, 0))` | default | False | None | False, False | None, None | False |

So in one process the first of two equal queries decides both answers, with the default engine (r1, r3) and with a new
engine per ask (r2: the carrier is process-wide, not the engine).

A fourth, with no twin and no `clear_cache()` (`item0/repro_nocache.py`): `t = (x + 1)**(x + 1)` written once, as a
user would. With SymPy's cache on, `t.base is t.exp` and main answers `ask(Q.gt(t, 0), Q.gt(x, 0))` True and
`ask(Q.le(t, 0), Q.gt(x, 0))` False. With `SYMPY_USE_CACHE=no`, the two `x + 1` are two objects and main answers
`None` to both. With the `==` hunk: True and False either way. So on main an answer depends on SymPy's cache setting
(and, by the same route, on its evictions), not only on query order.

A trap met while writing these, for whoever makes the kept test: without `clear_cache()` before each construction,
SymPy's cache returns the first object (`Pow(x, x2)` gives back the cached `Pow(x, x)`, and `distinct + 1` gives back
the `Add` holding it), and the two queries are one object. The first version of r1 and r3 showed no flip for that
reason. `repro.py` asserts `base is not exp` on the query it asks.

### Limits

- Same 560 queries as item 1 (mine, chosen around this rule), so 34 of 560 is not a rate for real workloads. Main's
  suite and workloads were not run in two orders.
- The fix was measured as wiring.py's hunk alone on main. 17241af's other changes (Rust `same_term`, tests, plants) are
  not on main and were not needed for these answers.
- Not isolated here either: which process-wide holder carries the first object on main when `_INTERPRETED` is cleared
  (A2 = A).

**Owner: the planner (it goes to Tilo with the held Python PR); the kept test is the formula step's.** The worktree
was removed after the runs; the outputs are in `~/sa-rust-ids-work/sa-port-251/item0/`.

## Item 2: cause of the four slice files failing on base

**Verdict: (iii) caused none of them. The four files give the same results, test id for test id, on 9e10f0d (the
commit before (iii)'s first, 0fa9532) as on base 0192b35. One file holds a real stale test (test_term_live.py, 2
tests, since 18d2bb6 of 8 Nov). The other three are not failures of the code: two need the suite's plugins and pass
with them, and one is a script that pytest collects by its name.**

| file | plain pytest, base 0192b35 | plain pytest, 9e10f0d (before (iii)) | cause | run as its docstring says, base | caused by (iii) | proposed owner |
|---|---|---|---|---|---|---|
| test_term_live.py | 2 failed, 18 passed, 1 skipped (2 failed, 19 passed with `SLICE_TERM_TEST_RUST=1`) | the same 2 | the tests build `_Mark` by `__new__` and set `tables, engines, cache` only (:339-340, :354-355); `_Mark.rollback` reads `self.facts` (term_live.py:171), which 18d2bb6 added to `__init__` (:141) | the same 2 fail under the plugins too | no | formula's step |
| test_handler_count.py | 2 failed | the same 2 | `handler_count._out` is `None` until the `handler_count` plugin installs the counter (test_handler_count.py:54) | 2 passed with `-p rust_plugin -p handler_count`; script form exits 0 | no | before-PR list, unassigned |
| test_catch_count.py | 3 failed | the same 3 | `catch_count.sink` stays empty: nothing installs the counter without `-p rust_plugin` | 3 passed with the plugins; script form exits 0 | no | before-PR list, unassigned |
| test_cf_diff.py | collection error | the same | a script: `seed = int(sys.argv[1])` at module level (:10) reads pytest's `-q` | `test_cf_diff.py 1 20000`: MISMATCHES 0 | no | before-PR list, unassigned |

### Evidence

- Runs (`~/sa-rust-ids-work/sa-port-251/item2/run4.sh TREE OUT [pytest args]`: one pytest per file from
  `rust-spike/slice`, as sa-port-243's `check1.sh` does it; Python env of `py.sh` plus the slice dir; orion):
  `base-plain/`, `base-plain-rust/` (`SLICE_TERM_TEST_RUST=1`), `base-plugin/` (`-p rust_plugin -p handler_count`, as
  run_suite.sh:17), `pre-plain/`, `pre-plugin/`. Each has `tree.txt` naming the `satassume` and `sa_solver.so` that
  imported. Script forms: `hc-script.log`, `cc-script.log`, `cf-script.log`.
- Failing ids, the same in base-plain and pre-plain:
  `test_term_live.py::test_a_table_emptied_and_regrown_past_the_mark_keeps_nothing_of_the_run`,
  `::test_what_was_there_before_the_run_stays` (`'_Mark' object has no attribute 'facts'`);
  `test_handler_count.py::test_each_route_is_seen`, `::test_uninterpreted_is_not_counted`
  (`'NoneType' object has no attribute 'flush'`);
  `test_catch_count.py::test_formula_route_into_1107`, `::test_verdict_route_into_1107`,
  `::test_complete_check_route_into_1906` (`assert [] == ['formula<_consistent']` and the like);
  `test_cf_diff.py` (`ValueError: invalid literal for int() with base 10: '-q'`).
- Which build: the clone's `sa_solver.so` was built at 12:02Z on 10 Nov from the tree of ba1ca22, and
  `git diff ba1ca22 0192b35 -- rust-spike/slice/solver_rs satassume rust-spike/slice/*.py` is empty (the later commits
  are documents). `sh rust-spike/slice/build_solver.sh` in the clone was a no-op and the copied `.so` has the same
  bytes as before, so the base runs are on the base's source. The 9e10f0d runs use a worktree with its own build
  (`build-pre-iii.log`); the worktree is removed, the logs stay.
- History: `git log 9e10f0d..0192b35` touches none of the four test files, nor handler_count.py, catch_count.py or
  rust_plugin.py. It touches term_live.py twice (7282317, f5dfa60), with no line about `facts`:
  `git diff 9e10f0d 0192b35 -- rust-spike/slice/term_live.py` has no such line. `self.facts` came with 18d2bb6
  (8 Nov 16:55Z, "WIP 5c10a: fact caches Rust-native"), an ancestor of 9e10f0d; the two tests date from before it and
  were not updated. results/HANDOFF-sa-port-197.md:16 and port-state-memoized.md:249 already report the same 2 on
  their base 9529850.
- The docstrings say how each is meant to run: test_handler_count.py:3 ("By pytest with `-p rust_plugin -p
  handler_count` ... or as a script"), test_catch_count.py:2 ("By pytest with `-p rust_plugin` ... or as a script"),
  test_cf_diff.py:1 (`test_cf_diff.py [SEED] [OPS]`). `check1.sh` runs every `test_*.py` plain, which is where the
  three come from.

### Proposed fixes (none made here)

- test_term_live.py: set `m.facts = {}` next to `m.tables, m.engines, m.cache = {}, {}, []` at :340 and :355 (test
  only; `_Mark.rollback` is right to read it). **Owner: formula's step**, whose open list already names term_live;
  if that item means something else, before-PR list, unassigned. Until then the 2 ids are known base failures and no
  bar that lists test_term_live.py can be clean.
- test_handler_count.py, test_catch_count.py: nothing to fix in the code under test. Either short checks run slice
  tests with `-p rust_plugin -p handler_count` (as run_suite.sh does), or the two files get a fixture that installs
  the counter when no plugin did, as their script forms do. **Owner: before-PR list, unassigned.**
- test_cf_diff.py: keep it out of `test_*.py` globs, or put the module-level run under `if __name__ == "__main__"`
  with a small pytest entry. **Owner: before-PR list, unassigned.**

Not checked: whether any landing bar lists these four in TESTS or DIRECT (bar.sh's TESTS default is
test_session_limits.py; each bar passes its own list); Rust backend through the plugin (`SLICE_SUITE_BACKEND=rust`).

## The `Subs` two-order check (item 1's open point; sa-port-251)

**Verdict: no flip found. 0 of 392 query pairs that differ only in the bound variable's name (`Subs(g(x), x, p)`
against `Subs(g(y), y, p)`) change any answer with order, on base 0192b35 and on base + wiring.py's `==`. A measurement
on my own queries plus a short read, not a proof. One other finding, not an order flip: two `Subs` whose *point* symbols
differ only in assumptions are `==` in SymPy although the symbols are not, and the reference then treats two different
terms as one.**

### Runs (`~/sa-rust-ids-work/sa-port-251/subs/subs2.py`, `cmp.py`; Python backend, orion)

- 14 term shapes x 28 forms = 392 pairs. Shapes: `Subs(f(a), a, 0)`, `Subs(sin(a) + z, a, 0)`, `Subs(a**a, a, z)`,
  `Subs(a**2, a, z)`, `Subs(f(a) + a, a, z)`, `Subs(Abs(a), a, z)`, `Subs(exp(a), a, z)`, `Subs(a**2 + 1, a, 0)`,
  `Subs(f(a, z), a, 1)`, `Subs(a*z, a, 2)`, `Subs(Derivative(f(a), a), a, 0)`, `Subs(a, a, z)`, `Subs(f(a), a, z) + 1`,
  `Subs(a**2, a, z)**Subs(a**2, a, z)`. The bound `a` is the free symbol `x` in one query and `y` in the other, and
  the forms put assumptions on `x`, on `y`, on `z`, and on the term itself (23 forms), or hold both namings in one
  query (5 forms, such as `ask(Q.positive(S_x), Q.positive(S_y))`).
- Each pair is asserted `==` with equal hash and different `srepr`. Each query is built after `clear_cache()`: without
  it SymPy's cache hands back the first-built term whatever its bound name (so in ordinary use SymPy itself already
  merges the two).
- Per pair, 10 answers: each query alone from emptied state (`PROCESS.clear()`, `clear_cache()`, a new default engine,
  a new `Engine` for the ask); then x-named first and y-named first, once on a new default engine and once with a new
  `Engine` per ask (process memos kept inside the pair).

| | base | base + `==` |
|---|---|---|
| x-named alone vs y-named alone | 0 of 392 | 0 of 392 |
| any of the 10 answers differ | 0 of 392 | 0 of 392 |
| base against base + `==`, any answer | 0 | |

Answers of the set: 96 True, 11 False, 285 None; 0 exceptions. That the stand-in happens: `_INTERPRETED` answered a
key whose first stored object had another `srepr` 984 times per run, so a memo-held `Subs` of one name did stand in for
the other. That the harness can show a flip is item 0's and item 1's 34 (the same comparison, on `x**x`).

### Read: who follows a `Subs` term's arguments

`rg '\bSubs\b|free_symbols|atoms\(Symbol|bound_symbols' satassume/`:

- euf_adapter.py:29-31: binders (`Sum`, `Integral`, `Lambda`, `Derivative`, `Subs`) are one opaque constant keyed by
  the expression; no congruence over their arguments. The run agrees: assumptions on `x` or `y` alone give `None` for
  every shape (for example `ask(Q.zero(Subs(x**2, x, z)), Q.zero(x))` is `None` for both namings).
- sympy_api.py:192, the `strict=True` check, reads `e.atoms(Symbol, ...)`, "bound ones included". It reads the
  query's own objects before anything is keyed: `subs/probe.py` asks `Subs(f(y), y, 0)` and the equal
  `Subs(f(xp), xp, 0)` (`xp` positive) in both orders with `strict=True`, and the second raises
  `AssumptionSymbolError` in either order while the first answers. Safe.
- templates/__init__.py:147 (`_may_be_nan`) and domain.py:408 (`_holds_matrix`) look inside a `Subs` for `nan`,
  infinities or a matrix. Renaming the bound variable does not change which of those a term holds. Safe by that
  reason, not run.
- `free_symbols` readers (scope.py:141, ref.py:151, lra_adapter.py:185/:197/:535, relations.py:579, engine.py:1774)
  get the same set for both namings: the bound variable is not free. Not each read line by line.

### Other finding: `Subs` with point symbols that differ only in assumptions (`subs/probe.py`, `probe-base.out`)

With `z = Symbol('z')` and `zp = Symbol('z', positive=True)`: `z != zp`, yet
`Subs(f(x), x, z) == Subs(f(x), x, zp)` with equal hash (SymPy compares a `Subs` through a renamed copy whose
placeholder carries the point's printed name). The reference keys by `==`, so:

| query (same answer alone and in every order tried; same on base + `==`) | answer | the same with `f(zp)`, `f(z)` written directly |
|---|---|---|
| `ask(Q.positive(Subs(f(x), x, zp)), Q.positive(Subs(f(x), x, z)))` | True | None |
| `ask(Q.gt(Subs(f(x), x, zp), Subs(f(x), x, z)))` | False | None |
| `ask(Q.eq(Subs(f(x), x, zp), Subs(f(x), x, z)))` | True | not run |

This is not history dependence (no order changes it), and with `strict=True` the `zp` query raises. Whether the
definite answers are wrong depends on whether `z` and `zp` are meant as two symbols; SymPy says they are (`z != zp`)
and its `Subs.__eq__` says the terms are one. It is a property of keying terms by SymPy's `==`, so Rust keying "as the
replaced Python containers did" (RULINGS 4) inherits it. **Owner: before-PR list, unassigned; a question for the
planner, not a fix proposed here.**

### Limits

- 392 pairs of mine; one-variable `Subs` only; no nested `Subs`, no `Subs` whose point holds the other bound name.
  Other binders (`Lambda`, `Integral`, `Sum`) were not tried; item 1's `eqprobe.py` is the list of which equal objects
  can differ at all.
- Rust was not run. Main was not run for this check (base and base + `==` only).
- The point-assumption finding was run alone and in two orders for the strict pair only.

## Item 3: `PROCESS.clear()` and the Rust stores (sa-port-252)

**Verdict: on base, `memos.PROCESS.clear()` empties the Rust stores that are in the registry (6 of the 7 measured
going to 0; the seventh, `_NEIGH`, was empty), and leaves two that stand in for adopted Python memos and are not in it: the dispatch's memo, class cache and entries
(for `registry._clauses_cache` and `_mro_cache`; 50 of 50 lookups still hit after a clear) and `RULE_MASKS` (for
`rules._MASKS`; one slot). Formula's pending c170496 covers the first, by its diff. Nothing covers the second, which
cannot change an answer.**

Base 0192b35, Rust backend installed as `memo_check.py` does, `sa_solver.so` sha256 `bfc06f0cd68a252a` from the
clone (the base's build), orion. No source change.

### Every Python process memo and what Rust has in its place

The 25 names are `memos.PROCESS.names()` after `load_owners()` under Rust: Python's 9 tables and 14 adopted
containers, plus Rust's 2 own. "py / rust" is the size after 600 dev queries on each backend, before the clear.

| Python memo | py / rust | Rust store | in the registry | emptied by `PROCESS.clear()` |
|---|---|---|---|---|
| `engine._SPLIT` | 317 / 322 | `procmemo.rs:110` `SPLIT` (thread-local) | yes, view put in `_adopted` (session_live.py:1151) | yes, 322 -> 0 |
| `engine._WANT` | 37 / 37 | `procmemo.rs:109` `WANT` | yes, view | yes, 37 -> 0 |
| `engine._NEIGH` | 0 / 0 | `procmemo.rs:111` `NEIGH` | yes, view | not shown: empty in every run (no engine code calls `neighbourhood`) |
| `relations._CLOSED` | 74 / 74 | `procmemo.rs:112` `CLOSED` | yes, view put in `_tables` | yes, 74 -> 0 |
| `relations._SYMPY_ATOMS` | 66 / 66 | `procmemo.rs:113` `ATOMS` | yes, view | yes, 66 -> 0 |
| `registry._clauses_cache` | 74 / 0 | `term/dispatch.rs:52` `Dispatch.memo`, held by `knowledge_live.DISPATCH` (:201) | **no** | **no**: 50 of 50 hits after the clear |
| `registry._mro_cache` | 21 / 0 | `term/dispatch.rs:55-56` `Dispatch.classes`, `entries` | **no** | **no** (same object; emptied only by an epoch change, `sync_epoch` :173) |
| `rules._MASKS` | 1 / 0 | `relations_core.rs:2730` `RULE_MASKS`, one slot (clause tuple, masks) | **no** | **no**: the tuple's refcount stays 4 -> 4 (fuzz); Python's goes 4 -> 3 |
| `_common._CACHE` | 59 / 48 | none: `term/common.rs:45` holds Python's dict itself | Python's | yes, 48 -> 0 |
| `sympy_api._KEYS`, `_CONST` | 104, 9 / 104, 9 | none: Python's tables, restamped from Rust (`memos.rs` `restamp`) | Python's | yes, 104 -> 0 and 9 -> 0 |
| `sympy_api._FORMULAS` | 142 / 142 | none on this branch | Python's | yes, 142 -> 0 |
| `domain._NONCOMM` | 55 / 55 | none: read by callback (`entry.rs:528`) | Python's | yes, 55 -> 0 |
| `relations._UNDER_APPS` | 39 / 0 | none: `relations._under_apps` by callback (`relations_core.rs:2940`) | Python's | Python's own clear; empty under Rust here |
| `relations._ZERO_TWINS` | 0 / 0 | no Rust store by that name (rg; `zero_twins` is `relations_core.rs:2961`) | Python's | empty on both backends in every run |
| `lra_adapter._INTERPRETED` | 1 / 0 | `term/py.rs:248`, a memo inside each query's term table, and `adapters.rs:283` `LraQuery.memo`, per query | no, not process-wide | not needed if the table dies with its query (read, not measured) |
| `solver._RULE_TABLES` | 1 / 0 | `rule_tables_gen.rs` (generated constants) and `block.rs:182`, per solver | no, not a memo | not needed |
| `euf_adapter._class_ok` | 9 / 0 | none found (rg: no memo or cache in `euf_py.rs`) | Python's | empty under Rust here |
| `lra_bounds._BOUNDS`, `_IV`, `_ENCLOSURES` | 0 / 0 | none: `lra_bounds.constant_bounds` by callback (`term/lra_read.rs:336`) | Python's | empty in every run |
| `rules._DEF_IMPL`, `extensions._node_cache` | 0 / 0 | none | Python's | empty in every run |
| (Rust only) `relations_core.SPEC_ROWS` | - / 2 | `relations_core.rs:2669` | yes, attached (`memo_install`) | yes, 2 -> 0 |
| (Rust only) `constfield.ENCLOSURES` | - / 1 | `constfield.rs:185` | yes, attached | yes, 1 -> 0 |

The other process-lifetime Rust state is not a memo: one-time reads of fixed Python objects (`PyOnceLock`s in
memos.rs:211, relevance.rs:46, relkeys.rs:25 and :51, adapters.rs:211, constfield.rs:154, :155, :2055;
transfer_py.rs:86), install-time settings (`HOOKS` in scope_core.rs:32 and relations_core.rs:40, `LIVE` in
adapters.rs:216, `JOIN_HOOK` session.rs:1927, `LIMITS` constfield.rs:183, `NPRED` session.rs:627), counters and
plants. The list is every `static` and `thread_local!` in `solver_rs/src` (rg) and every module-level container in
`backend.py`, `lra_backend.py`, `*_live.py`, `convert.py`.

### Evidence

- `~/sa-rust-ids-work/sa-port-252/item3/run.sh MODE N` (`clearprobe.py`, summary by `show.py *.json`): the first N
  queries of a workload, then every registry size, each module's own container, `sa_solver.memo_snapshot()` (the
  maps, not the views) and the refcount of `rules.RULE_INSTANTIATED`, before and after one `PROCESS.clear()`.
  Runs: dev 600 on Rust and on Python (same answers hash `46e32c7746b52a80`), fuzz 300 on Rust, dev 60 on Rust.
- Registered stores: every non-empty one goes to 0, in the views and in the maps. After the clear and a new default
  `Engine`, rerunning the same queries gives the same answers in all four runs.
- The dispatch: `Dispatch.clauses_for` on 50 expression objects taken from the queries: 50 hits (`registry:memo`)
  before the clear, 50 again, and 50 after `PROCESS.clear()`; `registry:epoch-clear` 0. Python's `_clauses_cache`,
  `_mro_cache` and `_CACHE` are 0, 0, 0 at that point. The memo is keyed by `==` like `_clauses_cache`, so it is
  one of the holders that keeps a first-seen object, and on base it outlives a clear.
- `RULE_MASKS` is reached on fuzz, not on dev (refcount 3 -> 3 on dev Rust, 4 -> 4 on fuzz Rust, 4 -> 3 on dev
  Python). A hit needs the stored tuple to be the very object (`relations_core.rs:2742`, `is`) and the slot keeps it
  alive, so it cannot return another tuple's masks. It is missing from `names()`, `sizes()` and the inventory.
- The five moved memos: the modules' own containers (`engine._SPLIT` and the rest) leave the registry at install.
  They stayed empty under Rust in all runs, so the clear left nothing behind here.
- c170496 (origin/port/formula, read as a diff, not built or run here): `Dispatch.clear_memos` empties `memo`,
  `classes` and `entries`, called from a `dict` subclass that replaces `registry._clauses_cache`, so the clear of
  that adopted name reaches it. Its own evidence is plant 665 and `test_cache_fix.py`.

### Proposed owners (no change made here)

| finding | proposed fix | owner |
|---|---|---|
| Dispatch memo, class cache and entries outlive `PROCESS.clear()` on base | c170496 as written; until it lands, a Rust two-order harness cannot isolate asks with `PROCESS.clear()` | formula's step |
| `RULE_MASKS` is outside the registry | list it in `memos.rs` `TABLES` under `rules._MASKS`' name, as 5c9b did for the five | before-PR list, unassigned (formula's step holds relations_core.rs) |
| Python's own containers of the five moved memos are outside the registry while Rust is installed | check the suite's 42 Python fallbacks (tests/test_transfer.py) leave them empty; if not, clear both | before-PR list, unassigned |
| `_SPLIT` 322 against Python's 317 and `_CACHE` 48 against 59 after the same 600 queries | already c170496's subject (one pattern per key) | formula's step |

### Limits

- dev 600 and fuzz 300 only; the suite was not run. Stores empty before the clear show nothing about their clear.
- No answer was shown to change because of the surviving dispatch memo; only that it survives.
- `Engine.memos` (per engine: engmemo.rs, factcache.rs) is not `PROCESS`'s and was not checked.
- That a term table and its memo die with the query is read from py.rs:248 and adapters.rs:277, not measured.
