# Handoff: component 4, slice C, first version (sa-port-70, issue 323)

Branch `port/4c`, based on `rust-slice` 089c70d. **Nothing is on `rust-slice`.** Stopped at the 141k context note. **Modules running whole because of this: 0 of 32 so far.**

## Done in the tree, in the commit that adds this file

- **The `mul` line.** `algebra.rs:264`, `:310`, `:325`; `table.rs:109`, `:472`; `convert.py:49`, `:335` (`own_base`, a new lazy read). A rational coefficient on one factor whose class has its own `as_base_exp` no longer refuses. Two factors still refuse with the old reason.
- **The glue's difference on ids.** `term_live.py:424` `_glue_objects`, installed over `relations.glue_objects` and `engine.glue_objects`. `d` joins the cone only as a `scaffold` object, count `scaffold:rebuilt:glue_objects`. `link_objects` and the adapter reads stay Python's.
- **The `termwise-true` and `termwise-false` plants moved** from `_termwise`'s wrapper to `term_live.py:436`, the glue's site. `_eq_links` still reads `eq_diff`.
- **`fresh.py --budget N`:** the engine's discovery budget.
- **`term_ids_direct.py`:** new atoms `exp(y)`, `exp(x + 1)`, `exp(-y)`, and four `evaluate=False` exp forms in `RARE`.

## The `mul` finding: the planner's note is half right

- **Checked in SymPy:** `Expr.__neg__` (`core/expr.py:238`) is a raw `(-1, self)`, and Rust's `neg` already does that. That part of the note holds.
- **Why `mul` still needed a change:** I read `Add.flatten` as rebuilding that term through `Mul(c, s)`, which is the general path in `mul`, from my memory of the source. The repo side is confirmed: `algebra.rs:453` calls `self.mul(vec![n, body[0]])` in `add`. I did not open `core/add.py` in this session, so check it.
- **Why it needs a read:** `Mul.flatten` rebuilds the factor as `Pow(b, e)`, and that evaluates. Run here: `Mul(2, exp(log(x), evaluate=False))` gives `2*x`, `exp(0, evaluate=False)` gives `2`, and `exp(1, evaluate=False)` becomes `E`. Rust can't tell these apart, so `_read_own_base` asks Python whether `Mul(2, t)` keeps `t`. False or a raise refuses, with reason `mul: own as_base_exp, and Mul changes the factor`.
- **Construction:** that read builds in SymPy on an input term. I put it on the input layer's count (ruling 5), not the scaffolding count, and only input terms can reach it (`table.rs:472`). **The planner hasn't seen this, so say it in the report.**

## Run so far, on orion, on this tree

| What | Result |
|---|---|
| `term_ids_direct.py 3000 1` | 2,951 pairs, no `differs:*` line in the 30 lines I read. Refused `sub` on the new reason: 30. The output was cut at 30 lines, so **the old reason's count wasn't read**. File: `~/sa-rust-ids-work/sa-port-70/c1/direct.json` (plain text despite the name) |
| Fresh dev, default budget | Python and Rust rows byte-identical. `glue:termwise` 30, `scaffold:rebuilt:glue_objects` 69, 0 refusals |
| Dev, budgets 5 and 2 | Below |
| Fuzz, budget 5 | 3,000 rows, Rust against Python: 0 answers, 0 digests, 0 faults, 0 refusals, `glue:termwise` 1,576 |
| Fuzz, budget 2 | **Still running when I stopped**, expected in `plantb/` within minutes. Read it |

### The `termwise-true` plant

| | Rust vs Python | `termwise-true` | `termwise-false` |
|---|---|---|---|
| Dev, budget 5 | 0 answers, 0 digests | **0 answers, 0 digests: not caught** | 8 answers, 15 digests |
| Dev, budget 2 | 0 answers, 0 digests | **0 answers, 0 digests: not caught** | 7 answers, 13 digests |
| Fuzz, budget 5 | 0 answers, 0 digests | **Caught: 7 answers, 74 digests** (first: q352, q632, q912, q2211, q2648) | 0 answers, 15 digests |
| Fuzz, budget 2 | Not read | Not read | Not read |

**So the planner's reading holds on fuzz at budget 5, and the plant is caught there through answers. On dev it isn't caught at either budget,** though the plant reaches the site, with `glue:termwise` 30. These runs are on this first version, so rerun them on the landing source for the bar.

**Why dev doesn't catch it, untested:** the plant can only move anything where the real `_termwise` says False, and I never counted those. If dev has none of the 30, the plant is void on dev, and that's the explanation to report. **Count real False at the glue, per workload.**

**Not compared on this tree:** fuzz at the default budget.

Output: `~/sa-rust-ids-work/sa-port-70/c1/plantb/` on orion. Read it with `python3 ~/sa-rust-ids-work/sa-port-70/cmpb.py DIR`. Runner: `~/sa-rust-ids-work/sa-port-70/plantb.sh OUT`. It sets `timeout 900` per job. A fuzz job took a few minutes here, so that should be enough, but check `rc.txt` for 124 before trusting anything short. **Don't rebuild or edit the slice while it runs:** later job groups import the current `.so` and `term_live.py`. Its source is this commit. Rerun it on the landing source anyway.

## Not run on this tree

- **No test file and no suite.** I moved plants out of `_termwise`'s wrapper, so `test_term_ids.py` may rely on the old site. Check it first.
- No check mode, no `SLICE_TERM_CHECK`, no live run, no discard run, no handler count.
- Refusal counts before and after for `mul` on the suite and fuzz. Base: slice B's 19 on 6 distinct queries.

## Left for the rest of slice C

Designed but not written. All of it is first-version guesswork until it runs.

1. **`relation_atom`'s lt, gt, le and ge,** `relations.py:511-540`: `order_relation(name, l, r)` returning None for nan under le or ge, otherwise `(swap, negated, ext positions)`. Return positions and not ids, so Python keeps the objects it was given, including the `args-eq-not-is` case.
2. **`_ext_atoms`,** `relations.py:470`: `is_Rational` class flag, `Kind::Infinity`, `Kind::NegativeInfinity`.
3. **`_eq_links`' clauses and `_eq_infinity`,** `relations.py:1325`, `:1127`, `term_live.py` `_eq_links`: Rust returns a plan of ensure and clause ops over `(sign, pred, id)`, and Python runs it left to right, so var numbering and the digests hold. `s.var` holds SymPy objects until component 5, so a derived id goes through `scaffold`. `_eq_infinity`'s `is_` stays a callback.
4. **`scope.py`:** `affine_pair:133`, `linked_terms:150`, plus `zero_args` and `under_of` at `relations.py:595`, `:607`. Check that a table is live there, and count calls. `_UNDER_APPS` and `_ZERO_TWINS` are cross-query memos, so the ruling applies.
5. **`euf_adapter.py`:** `structural:73` as a new class flag beside `_PLAIN_BASE` (`convert.py:69`), `interned:216`, and `relations._structural_subterms:1948`. Keep the stack order exactly. **`_intern:191` reads dicts keyed by SymPy objects that outlive a query, so per-query ids don't fit until component 5.** Expect euf_adapter to be partial, and name that.
6. **The rest of `Relations`,** `relations.py:777-1921`: `_interpret`, `_guard`, `_link`, `_tvar`, `_apply_role`, `_order_sides`, `_order_infinite`, `_trichotomy`, the transfer methods. These are tied to `Session`, which is Python until component 5, so "clauses over ids" means a plan that Python runs. **This is the size question: slice again here if it doesn't fit,** and say so in the report.

Plants to add per item, each through fresh dev and fuzz with reach counts: dropping a clause in a plan, a swapped pred, le's swap, dropped ext atoms, `affine_pair` False, a dropped linked term, `interned` reversed.

## File map

| What | Where |
|---|---|
| Per-query table, wrappers, `scaffold`, plants | `rust-spike/slice/term_live.py`: `term_id:259`, `scaffold:297`, `_guarded:339`, `_ids:351`, `_relation_atom:363`, `_termwise:398`, `_glue_objects:424`, then `_eq_links`, `_install` near the end |
| Rust term work | `solver_rs/src/term/relations.rs` (133 lines), `algebra.rs` `neg:166`, `mul:214`, `add:392`, `sub`; `py.rs` pymethods from `:82`; `table.rs` `Read:101` |
| Conversion, class flags, reads | `rust-spike/slice/convert.py`: `READS:49`, `_PLAIN_BASE:69`, class flags near `:233`, `read:308` |
| Python's own | `satassume/relations.py`: `relation_atom:511`, `_termwise:673`, `Relations:777`, `glue_objects:1994`; `satassume/scope.py`; `satassume/theories/euf/euf_adapter.py`; `satassume/engine.py`: `_struct:1609`, `_cone_info:1676`, `_within_budget:1783` |
| Comparison | `fresh.py` writes `index, answer, digests` rows; `term_ids_direct.py`; `cmpb.py` above |
| Environment | `. ~/sa-rust-ids-work/sa-port-70/env70.sh` on orion sets the tree, `PYTHONPATH` and `PY`, and cds to the slice directory |
| Slice B's report, for the forms | `rust-spike/slice/results/port-4b.md` |
