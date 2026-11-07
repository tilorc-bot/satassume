# Handoff: sa-port-10 to the next session (issue 323), components D and 0

Read the brief first: `~/.local/state/agent/briefs/sa-port-10-20261107T074544Z.txt`, its terms still apply. Branch `port/D0`, clone `~/dev/sa-port-5`. Nothing is on `rust-slice`. Modules of the 32 running in the real engine because of this: **0**. The shadow decides nothing and counts as no ported module.

**Carry this ruling:** `~/dev/architect/briefs/addenda/sa-port-0-pow-ruling.txt` (forward-chain-3b, on a Pow whose `decompose_power` base isn't an input term). It's refused at key time as section 9's "Refused during a run"; move that bullet in section 9. Report refusals at key time, queries holding such a Pow that finished without refusing, the same refusal count across hash seeds, and input-layer construction as its own count beside what pure Python constructs per query, plus keys computed against keys used. Don't add a lazy path on your own: bring numbers as a question.

## State

**Built and run on dev: `convert.py`, the table, the shadow.** Not the algebra, not the Rust key for derived terms.
- `rust-spike/slice/convert.py`: `convert(prop, assumptions, eng)` gives `Converted` or `Kept`. Class, term, power, settings and formula rows as int token streams (`T_*`).
- `solver_rs/src/term/table.rs` (`TermTable`, `V`, `compare`, `value_cmp`, `key_cmp`, `find`), `rat.rs` (plain BigInt; lra's `Rat` can't be included, it reaches `crate::lra`), `py.rs`. `Cargo.toml` gained pyo3's `num-bigint` feature.
- `term_shadow.py`: wraps `sympy_api._ask` (depth 1 only), `relations._key`, `lra_adapter.default_sort_key`. Reads every row back from Rust against SymPy; compare and key order over pairs of each query's first 40 terms; rebuilds the formula from Rust's dump with the real constructors and `relation_atom`, against `to_formula`.
- `term_shadow_live.py SHADOW.json dev py OUT.jsonl --check raw`: live.py's run with the shadow on. `~/sa-rust-ids-work/sa-port-10/show.py SHADOW.json` summarises.

**Dev result, `~/sa-rust-ids-work/sa-port-10/dev2/`, hash seed 0, persistent engine as live.py runs it:** answers sha 31cd0945c07f02a6 same as plain (`dev1/plain`); livecmp MATCH, 0 end differences over 918 sessions. 1,221 queries reached `_ask`, 1,197 converted, 24 kept (out-of-scope), 12,423 term rows, 132,606 compares, 20,682 key compares, 1,197 formulas: **0 mismatches**.

**A mistake to keep in mind:** the first version used `sympy_api.out_of_scope`, which is a diagnostic and names a category for relation queries the engine answers. It kept 296 queries and hid every key use. `dev1/shadow.json` is that run: don't quote it. `convert.formula` mirrors `to_formula` now.

## Open, none of it resolved

1. **12 key compares Rust refuses and Python orders on dev** (`refused` in `dev2/shadow.json`; "types Python's < doesn't order"). Cause not looked at. The shadow only counts them and records no terms: add the pair to `BAD`. Smallest case first.
2. **Keys: 4,515 computed by conversion against 2,012 used by the query, of which 401 are derived terms** (so 1,611 are input terms Rust's supplied key could answer). Same run, persistent engine. Ruling 6 wants this as a question to the planner, in the report. Per-query construction, conversion against pure Python, is **not measured**: count `Basic.__new__` in a separate run. Cached SymPy results will hide some.
3. `decompose_power`: 109 calls on dev, 0 bases not an input term. Nothing has exercised the refusal. Corpus should (82 in the synthetic check).
4. `Kept('out-of-scope')` decides on the whole assumptions; `_ask_general` can narrow them first (`_relevant`), so this may keep queries Python would answer. Not measured.
5. Non-default registry check: `eng._templates`, relation spec names, and each template's module. `extensions` and custom handlers aren't checked. Sum/Product/Integral, args-eq-not-is, non-basic and too-deep haven't fired on dev.
6. Generic constants, atomic-number truth rows and symbols' `assumptions0` rows aren't built (section 9). Symbols' assumptions are in the content, which may be enough.

## Next steps

1. Fix item 1. Run the shadow on fuzz and corpus (`live.py` takes `fuzz`; corpus through `evalbench.common.workload`, see `~/sa-rust-ids-work/port-census/derived.py`), and on a fresh engine with memos cleared per query, which the brief requires and dev2 isn't (`seed_state.py`, `harness.state.reset_module_state`).
2. Algebra in `table.rs`: `neg`, `add`, `mul`, `sub`, `coeff_add`, `coeff_mul`, derived keys, per `HANDOFF-sa-port-5.md` "Algebra" (still unbuilt and unrun; those rules are the design to check). Then the shadow's wrappers on `__neg__` etc, and `_struct`/`_cone_info` weights.
3. Held-to list: suite three numbers by id with the plugin, planted bugs, boundary re-score, counts, history independence, D's landing (generator and reader unchanged from dfe6b73, and `tests_offline.py` needs rerunning).
4. Rebase, push to `rust-slice` without force, report.

## File:line map

`HANDOFF-sa-port-5.md` has the design and its map, `HANDOFF-sa-port-1.md` the engine, relations, adapters and templates. Added here:

| Topic | Where |
|---|---|
| Engine's formula and answer path | `sympy_api.py:1111` `_engine_ask`, `:496` `_formula` (memo: don't call it from conversion), `:354` `to_formula`, `:339` `_relation_formula`, `:257` `_applied_category`, `:576` `_ask_general` |
| Key sites | `relations.py:524` (only `_key` caller), `lra_adapter.py:324`, `:348`, `:412`, sort key `sympy/core/expr.py:168` |
| Add, Mul evaluation | `sympy/core/add.py:216` flatten, `:301` Add arg, `:312` Pow arg, `:333` merge, `:359-366` coefficient rebuild, `:404` sort; `add.py:1280` `Add.__neg__` is `Mul(-1, self)`; `mul.py:194` `Mul.__neg__`; `expr.py:238` `Expr.__neg__` |
| Coefficients | `add.py:463`, `mul.py:854` |
| Compare | `sympy/core/basic.py:58` order, `:96` `_cmp_name`, `:372` compare |

**Traps:** SymPy registers `Integer` as `numbers.Integral`, so test `Basic` first in any encoder. `Add.__neg__` here is `Mul(-1, self)`, which differs from `HANDOFF-sa-port-5.md`'s `Add(*[-i])`: read `add.py:1280`, and go by running.

**Environment:** `. ~/sa-rust-ids-work/env.sh; export PYTHONPATH=/home/tilo/dev/sa-port-5:$W/sympy:$W/shim:$PWD/rust-spike/slice` (use the slice dir as cwd for the driver). Build `sh rust-spike/slice/build_solver.sh`. Output under `~/sa-rust-ids-work/sa-port-10/`.
