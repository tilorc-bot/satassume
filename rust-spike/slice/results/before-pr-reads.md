# Read-only checks from the before-any-backend-PR list (issue 323, sa-port-250)

Base: rust-slice 0192b35. Branch audit/before-pr-reads. No source change, no plant, no counter: this file is the only
commit. Scratch scripts and run output are in `~/sa-rust-ids-work/sa-port-250/` on orion (not in the repo).

| item | state |
|---|---|
| 1. `_INTERPRETED` first-seen object (Q1 (d)) | done, below |
| 2. Cause of the four slice files that fail on base | **not started** (handed off) |
| 3. `PROCESS.clear()` and the Rust stores | **not started** (handed off) |

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
**Owner: before-PR list, unassigned.**

### Proposed owners

| finding | owner |
|---|---|
| wiring.py:223 and :323 by `==` (17241af) is what removes the 34; it must land with formula | formula's step (already theirs) |
| `Subs` alpha-equivalence check | before-PR list, unassigned |
| Two-order harness as a kept test (twin queries; 560 here, 34 caught on the reference with `is`) | before-PR list, unassigned; it would also serve as the plant-catching test for Q1 (b) on the reference |

## Item 2: cause of the four slice files failing on base

Not started.

## Item 3: `PROCESS.clear()` and the Rust stores

Not started.
