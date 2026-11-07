# Handoff: sa-port-13 to the next session (issue 323), components D and 0

Read the brief first: `~/.local/state/agent/briefs/sa-port-13-20261107T075844Z.txt`; its terms, rulings and slice order still apply. Branch `port/D0`, clone `~/dev/sa-port-5`. Nothing is on `rust-slice`. Modules of the 32 running in the real engine because of this: **0**. The shadow decides nothing and counts as no ported module. `HANDOFF-sa-port-10.md` still holds for the conversion and the Pow ruling.

Planner, through the architect, on ruling 6: no ruling yet and no lazy path. The question is construction and time, not key calls. Per query on a fresh engine it wants SymPy constructions during conversion, what pure Python constructs on the same query, and conversion's share of query time. Orion time is load-affected, so say so, or take a quiet lease on pareto1 for the share. It stays item 3: don't let it overtake items 1 and 2.

## State

**Built: the algebra, `solver_rs/src/term/algebra.rs`.** `neg`, `add`, `mul`, `sub`, `coeff_add`, `coeff_mul`, `raw_add`, `raw_mul`, `number`, `sort_key` of derived terms, exposed in `py.rs`. Derived rows follow input rows in the one table; `intern` is where a derived term merges with an input term. Refusal reasons are all literal strings in that file.

**Conversion gained:** a commutative fact bit (`F_COMMUTATIVE`, 128) and class flags `PLAIN_OPS` (1<<14), `PLAIN_BASE` (1<<15), which the shadow's fact check covers for the bit but **nothing checks for the two class flags beyond the derived-term comparison**.

**Shadow gained (`term_shadow.py`):** `install_algebra()` wraps every op on `Expr`'s subclass closure, plus `Add`/`Mul` `__new__`, `Session.node`, `Engine._struct`, `_cone_info`. Only frames in `satassume*` are checked. `settle` is the merge check: `ids[real]` must equal Rust's id. Each new derived term also checks key, free symbols, the number bit and compare against the query's first 9 terms.

**Driver:** `term_shadow_fresh.py WL OUT.json [--plain] [--limit N]`: fresh engine, `reset_module_state(sympy_cache=False)` per query. `~/sa-rust-ids-work/sa-port-13/show.py OUT.json [N]` summarises; `sa-port-13/env.sh` sets the environment (it sets PYTHONPATH to this clone); `sa-port-13/smoke.py` is the hand-case test.

## Results so far, none of them the full slice

| Run | Result |
|---|---|
| Hand cases, `sa-port-13/smoke.txt`: not the engine | 3,424 ops, 1,577 derived terms with keys and compares: 0 mismatches, 586 refused by design reasons |
| Dev, first 100 queries, hash seed 0, fresh engine, `lim100.json` | Answers sha 40feb0ad39ac3f6f, same as `--plain`. 2,070 ops, 846 derived, 639 merged with input, 262 cones all fully known, weight 524, 326 new nodes (12 derived): 0 mismatches, 0 refused, 0 unknown |
| Dev, full, `sa-port-13/dev3/{plain,shadow}.json` | **Started in the background at the end of this session. Read it, don't assume it.** Compare `*.answers` with `cmp`. If the files are missing or the logs show a crash, rerun |

Note what 100 queries doesn't exercise: 0 refusals, and only `core.py:173`, `:84`, `:419`, so `relations.py`, `wiring.py` and `functions.py` sites haven't been seen yet.

**What the cone check does and doesn't show:** weights still come from Python's `_struct`, since templates aren't ported. The check shows that cone objects map one to one onto Rust ids, so Rust's node count would equal Python's. Over-budget cones have no object list and only get the per-object weight check in `struct_`.

## Open, in the brief's order

1. **Slice item 1:** read `dev3`. Look especially at unknown operands by site (`show.py`'s "unknown sites"): each is a construction path section 3 missed. Report with `Status: progress` once it's read.
2. **Slice item 2, not started:** the 12 key-order pairs Python orders and Rust refuses. `check_order`'s refused branch only counts: record the pair in `BAD`, smallest case first. My untested guess, to check rather than rely on: a `V::Rat` coefficient slot against a `V::Term` slot (`Float` or `oo`), which `value_cmp` refuses.
3. **Slice item 3, not started:** fuzz, corpus (`derived.py` shows the workloads; `--limit` helps), other hash seeds (the refusal count must not change across them), and the per-query construction count (count `Basic.__new__`, a separate run with `CHECK_ON` off, and with `sympy_cache=True` since cached results hide constructions).
4. **Not run at all:** the suite's three numbers against 5,961 / 77 / 46 by id, including D's crate changes and these; `tests_offline.py`; planted bugs; boundary re-score; history independence; rebase and landing on `rust-slice`. The ruling's Pow counts (refusals at key time, queries holding such a Pow that finished, same across seeds) and the section 9 bullet move. `dev1/shadow.json` is a bad run; don't quote it.
5. **The synthetic loop** in `HANDOFF-sa-port-5.md` (`-t`, `c*t`, `t+c`, `t-u` on the first 9 input terms) isn't in the shadow yet; `smoke.py`'s loop is the shape to reuse, under a flag since it constructs.

## Design choices to check or report

- **Refusals wider than SymPy needs, all counted:** a term holding an infinity, nan or Float anywhere, even deep (`f(oo)`); any class with its own `as_base_exp`, so `exp(x)*y` refuses even with no shared base; a numeric-base power unless it's a base above 1 with exponent in (0,1), alone and with coefficient 1; `0*x`. If a real-workload count is high, read `mul.py:420-720` (I did not read those lines; the shadow is what checks them) before widening.
- `mul`'s two-argument path doesn't intern a stripped body, per the sa-port-5 note. `coeff_add` and `coeff_mul` do, because the caller asked for it.
- Ties in `compare` between different terms refuse, as do two generators with one sort key (`Symbol('x')` and `Symbol('x', real=True)`), where Python's order would come from a set.
- Derived rows don't carry `MAYBE_NAN`, level or `closed`. Nothing reads them yet; a consumer in 2 or 4 must add them or refuse. `free` and the number bit are checked.
- `__truediv__` in the shadow is a Python helper (`_div`), multiplying by the reciprocal; only rational denominators are handled. `Expr.as_coeff_Add(rational=True)` is treated as the default call; a non-rational head refuses either way.
- `Converted` gained `__dict__` in its slots so the shadow can keep per-query state. Shadow-only need: drop it or move the state when the shadow goes.

## File:line map

`HANDOFF-sa-port-10.md`, `-5` and `-1` have the rest. Line numbers here are from this session's reads.

| Topic | Where |
|---|---|
| Algebra | `solver_rs/src/term/algebra.rs`: `operand` (what may enter), `intern`, `neg`, `keep_coeff`, `mul`, `add`, `add_term`, `coeff_add`, `coeff_mul`, `sort_key`, `mul_key`, `add_key`, `rat_f64` |
| Class prefix constants, flags | `solver_rs/src/term/table.rs`, `flag`, `CLASS_*`, `PREFIX_KINDS`; must match `_PREFIX`, `FLAGS` in `convert.py` |
| Shadow algebra | `term_shadow.py`: `check_op`, `settle`, `same_term`, `check_derived`, `_OPS`, `install_algebra`; pairs to record: `check_order` |
| SymPy read | `core/add.py:216` flatten, `:1280` neg; `core/mul.py:194` neg, flatten from `:275`, `:733` distribution, `:854` coeff; `core/operations.py:62` new; `core/expr.py:168` sort key, `:238` neg, `:1179`, `:1226` terms |
| Sites seen so far | `knowledge/templates/core.py:173`, `:84`, `:419` |

**Traps:** `Add.__new__` is on `AssocOp`, so it isn't in `Add.__dict__`. `Symbol` overrides `sort_key`, so it can't be in the plain-operators test. In `convert`, `assumptions` is `True` for none, not `None`: `None` keeps the query as out-of-scope.

**Environment:** `. ~/sa-rust-ids-work/sa-port-13/env.sh` and use `$C/rust-spike/slice` as cwd. Build `sh rust-spike/slice/build_solver.sh`. Output under `~/sa-rust-ids-work/sa-port-13/`. Orion was at load 37 at the start of this session: `-n 4` or less.
