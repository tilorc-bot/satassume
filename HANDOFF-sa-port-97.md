# Handoff: sa-port-97 to the next 6e session (`knowledge/templates/core.py`, issue 323)

**State:** scope item 1 (the trace) is done. Nothing is ported yet: no Rust and no `knowledge_live` change. Branch `port/6e`
in `/home/tilo/dev/sa-port-5`, from rust-slice de8bd3a. I handed off at my context budget, after reading core.py and running the trace.

## The trace (scope 1)

`rust-spike/slice/core_trace.py` (committed). It uses sys.monitoring PY_START: global events while core imports, then local
events on core's own code objects only. Run it as `python core_trace.py dev|fuzz OUT` (default Python engine), or
`pytest -p core_trace` with `CORE_TRACE_OUT=dir`. One gap: the lambdas in `IPI_GUARDS` (core.py:435) sit in a MappingProxy,
not in module functions, so they aren't monitored. Only `ipi_rules` calls them, through `expand`, so its count covers them.

Results: `~/sa-rust-ids-work/sa-port-97/trace/{dev,fuzz}.json` on orion. The suite's are in
`~/sp19/sa-rust-ids-work/sa-port-97/trace/suite/` on pareto1 (9 process files; source 1e81a98, tree that clone's;
`6084 passed, 23 skipped, 18 xfailed`, Python default, `-n 8`).

- **Import time:** only `<module>:1`: the constants `MAX_ONEOUT`, `MAX_HALF_ODD`, `_INT_BOUNDS`, `_RECIP_BOUNDS`, `IPI_GUARDS`
  and `_TABLE_BUILDERS`. These are data and aren't ported. Rust embeds the ones it needs as constants.
- **Correction to the ownership report (core.py:448, :575, :584):** `IPI_TABLE` is **not built at import**. `_table` builds
  it the first time a query reaches `ipi_rules`, once per process. It's a constant table, so it moves as data inside
  `ipi_rules`' Rust version, with the guards as Rust code. `__getattr__` fired twice per process on dev and fuzz and `_table`
  fired zero times, so those were AttributeError probes for other names, not engine work. Count `__getattr__` as not a port
  item; the trace backs that.
- **After import, dev (calls):** `_imag_term` 674, `_pi_split` 574, `ipi_split` 566, `_mul_factor_sets` 556,
  `_quotient_templates` 556, `_coeff_term` 350, `_half_split`/`_bound_split`/`_imag_split` 329, `_exp_arg`/`_unit_angle`/
  `irrational_root`/`_pow_bound_templates` 207, `_bound_templates`/`_bound_rules`/`_recip_templates` 203, `_half_templates`
  126, `_half_rules` 123, `_quotient_rules` 22, `pi_split` 8.
- **Fuzz:** the same Add and Mul set at about 10x (`_imag_term` 12,704, `_half_split` 5,212), with no Pow or exp items.
- **Not reached on dev or fuzz:** `_recip_rules`, `_imag_rules`, `_imag_number_rules`, `_imag_templates`, `_not_unit_premises`,
  `_ipi_table_rows`, `ipi_rules`, `_unit_power_units`, `_table`.
- **Suite, after import (calls summed over workers):** every named item runs. `_imag_term` 18,714, `_exp_arg` 9,139,
  `_bound_split` 8,410, `_pi_split` 7,896, `ipi_split` 7,387, `_half_split`/`_imag_split` 7,328, `_mul_factor_sets` 6,830,
  `_quotient_templates` 6,596, `_coeff_term` 6,584, `_unit_angle` 3,714, `_pow_bound_templates` 3,673,
  `_bound_templates`/`_recip_templates` 3,196, `_half_templates` 1,643, `_not_unit_premises` 690, `irrational_root` 662,
  `pi_split` 509, `_bound_rules` 478, `__getattr__` 362, `_half_rules` 212, `_recip_rules` 127, `_quotient_rules` 83,
  `_imag_templates` 53, `_table` 50, `ipi_rules` 49, `_unit_power_units` 41, `_imag_rules` 20, `_imag_number_rules` 5,
  `_ipi_table_rows` 3 (once per worker that reached it).
- **So:** import time is `<module>` alone. All 29 other items run after import: 28 are runtime port items and `__getattr__`
  isn't one (see above; its 362 suite calls are more than `_table`'s 50, so most are attribute probes for other names; I
  didn't check which tests make them). Core's runtime work isn't small: 28 items, called thousands of times on fuzz.

## Map

core.py (587 lines). Callers: `wiring.py:44-47` imports 16 names by value, and `functions.py:34` imports `ipi_rules`,
`ipi_split` and `pi_split`. A swap has to patch those module globals **and** core's own globals, because core calls itself
(`_pow_bound_templates`→`_bound_split`/`_not_unit_premises`, `_mul_factor_sets`→`ipi_split`, `_half_split`/`_bound_split`→
`_coeff_term`). Call sites: `wiring.py:666-677` (Add: `_half_split`, `_half_templates`, `_bound_split`, `_bound_templates`,
`_recip_templates`, `_imag_split`, `_imag_templates`), `:634-635` (Mul: `_mul_factor_sets`, `_quotient_templates`), `:213`,
`:285-335` (Pow and exp: `_exp_arg`, `ipi_split`, `_unit_angle`, `ipi_rules`, `irrational_root`, `_unit_power_units`,
`_pow_bound_templates`), `:133`, and `functions.py:114`, `:129`, `:214`, `:311`.

The items fall into three kinds:
1. **Splits that read SymPy structure:** `_half_split:58`, `_coeff_term:88`, `_bound_split:150`, `_imag_term:235`,
   `_imag_split:252`, `_mul_factor_sets:325`, `_pi_split:406` (`ipi_split:392`, `pi_split:400`), `_unit_angle:380`,
   `_exp_arg:524`, `irrational_root:485`, and the shape tests in `_recip_templates:225`, `_quotient_templates:360` and
   `_pow_bound_templates:533`. Port over session-local ids: read `TermRow.args`, `ClassRow.kind` and a Rational's p/q from
   `content` (`solver_rs/src/term/table.rs:96-146`). `is S.ImaginaryUnit`/`S.Pi`/`S.NegativeOne` become Kind tests. A
   non-input expr goes to Python with a `core:derived` count, as atoms' `derived` path does (`knowledge_live.py:170-190`).
2. **Rule builders, pure over small ints and rationals:** `_half_rules:100`, `_bound_rules:166`, `_recip_rules:203`,
   `_imag_rules:259`, `_imag_number_rules:280`, `_not_unit_premises:309`, `_quotient_rules:353`, `ipi_rules:476` (with
   `IPI_TABLE`'s rows and `IPI_GUARDS` as data). Output format: `Rules.rules` (`_common.py:59-75`), a list of
   `(premises list of (slot, pred, bool), conclusion list)`, **in Python's order** (`resolve` reads in order). These only run
   on a `_CACHE` miss inside `facts`. Test them directly by enumeration against Python, as `test_knowledge_common.py` does.
   Rational arithmetic (`c0 + c1*b`, comparisons) uses `term/rat.rs`.
3. **Templates calling `facts`:** `_half_templates:120`, `_bound_templates:183`, `_recip_templates`, `_imag_templates:288`,
   `_quotient_templates`, `_pow_bound_templates`. `facts`, `_CACHE` and the keys stay Python (6d). Keys hold SymPy Rationals
   (`c0`, `c1`, `const_key`), so Rust returns ids (or p/q for a computed Rational) and Python builds the key from
   `q.objects[id]`, or from `Rational(p, q)` for a computed one. That counts as conversion, not a callback.

**SymPy construction inside core, which needs a decision:**
- `kept_product` (`domain.py:474`) at core.py:97, :346, :430 builds `Mul(*rest)` and checks that it kept its factors. The
  product is usually not an input term. Under the scaffolding ruling, "a template callback on a derived term may rebuild it in
  SymPy": count it per step and check it against Rust's form. `PyTermTable.raw_mul`/`mul` (`py.rs:472-486`) can build Rust's form.
- `_imag_templates:295` builds `Add(*[c*x ...])` (number terms only).
- `_unit_power_units:498` calls `e.as_real_imag()` (marked sympy-boundary) and returns Formula `P`/`Not`. By the Formula ruling
  the output Formula is engine data. Keep it on Python with a reason if the suite shows few calls, or port the Rational branch.

Plan: wrappers in `knowledge_live.install()` like `template()` (`knowledge_live.py:191-202`), with `kept()` respected and a
`shadow` compare of the split and the rules against Python's. New Rust in `term/knowledge.rs` (or a new `term/core.rs`) and
`py.rs` methods on `Knowledge` taking `(table, id)`. Then plants (`mutate_knowledge.py`/`knowledge_plants.py`, one per moved
function; a plant that never fires is void, with a direct test standing in), then the five-item bar through `bar.sh` (on
origin/port/5c 1b97a5a until 5c1 lands; read it with `git show`).

## Rebase and wiring watch

5c1 (sa-port-96, `~/dev/sa-port-7`, port/5c) and the wiring step both touch `knowledge_live.py`. Check `git log origin/rust-slice`
before landing, and apply the ruling's rebase rule and `rows_kept` rule (whoever lands first carries the `rows_kept` guard
with a plant).
