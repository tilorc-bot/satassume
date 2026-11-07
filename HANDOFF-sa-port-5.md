# Handoff: sa-port-5 to the next session (issue 323), components D and 0

Read the brief first: `~/.local/state/agent/briefs/sa-port-5-20261107T073346Z.txt`. Its terms still apply. Branch `port/D0`, clone `~/dev/sa-port-5`. Nothing is on `rust-slice`. Modules of the 32 running in the real engine because of this: **0**.

## State

**D: generator and loader written and tested alone; not landed.**
- `rust-spike/slice/gen_offline_data.py` writes `offline_data.json` (126,690 bytes, sha 898caac8...). `solver_rs/src/term/offline.rs` reads it. `tests_offline.py` passes: same bytes under 6 hash seeds, Rust writes the 124,821 body bytes back identically, sha256 agrees with hashlib, and it refuses a changed body byte, format, body hash, source list, truncation, empty file, other SymPy and an edited source.
- **Not checked:** only `BASIS` was compared to the live value after reading; the other sections are correct only because they're read from the live objects by the generator. No consumer reads the data yet. The suite wasn't run with these crate changes (`num-bigint` deps, `term::py::register` in `lib.rs`), so no three numbers exist.
- **Limits to report:** the SymPy check is the version string (`1.15.0.dev`), not a commit. `value_units` is keyed by exact class, so a subclass of those six functions must refuse. `IPI_GUARDS` is names only: guards are code, and Rust binds them by name. `_UNDEFINED_KEYS` and `_MATRIX_TO_SCALAR` aren't in the file (I took them as conversion's reads, not checked). `SOURCES` in the generator is a hand list.

**0: only the types exist.** `solver_rs/src/term/mod.rs` has `TermId`, `ClassId`, `PredId`. `TERMS-INTERFACE.md` is the published interface, sent to sa-port-7 at f153b66; **`convert.py` and `TermTable` in it aren't built**. Tell sa-port-7 when they land.

## Next steps

1. Write `rust-spike/slice/convert.py` and `solver_rs/src/term/{table,algebra,key}.rs`, as designed below. A first version that runs and fails against SymPy beats more reading (architect's note: read by rg only).
2. `term_shadow.py`, its workload driver and a pytest plugin, then dev, fuzz, corpus. Fix or refuse by what mismatches.
3. The held-to list: suite three numbers by id (`PYTEST_ADDOPTS="-p term_shadow_plugin"` with `run_suite.sh`, `PYTEST_N="-n 4"`, needs `rust-spike/slice` on the path), planted bugs, boundary re-score, counts, history independence, answers sha unchanged with the shadow on (dev 31cd0945c07f02a6).
4. Rebase, push to `rust-slice` without force, report SHA and that the shadow counts as no ported module.

## Design decided, none of it built or run

**Conversion (`convert.convert(prop, assumptions, engine)`), hooked at `sympy_api._ask`** (the module global `ask` calls, `sympy_api.py:480`, so a memo hit never converts; depth counter for top level).
- Walk every `Basic` node, proposition then assumptions, preorder over `.args`; dict by SymPy hash and `==` gives ids. `assumptions=True` is not walked.
- Kept reasons: non-basic value, class with no row, non-default registry, Sum/Product/Integral anywhere, args `==` not `is` (same id, different object, within a term), out-of-scope formula (`to_formula` raising `Unsupported`, `sympy_api.py:354`).
- **Proposed deviation from section 9, tell the planner:** a `Pow` whose `decompose_power` base isn't an input term refuses at run time when a key needs it, not at conversion. `x**(3/2)` has such a base, and refusing up front would keep queries that never reach a derived key.
- Classes: a fixed prefix always sent (Add, Mul, Pow, Integer, Rational, Zero, One, NegativeOne, Half), since Rust can build these with none in the input. Row: name, kind, rank (index in `ordering_of_classes`, else unknown), flags, class_key, `registry.templates_for(cls)` names (`registry.py:194`), `structural` (`euf_adapter.py:85`).
- Facts: `has_bad` is `.has(*_BAD)` (`lra_adapter.py:293`, `:376`, `:406`), `has_nan` (`relations.py:1801`), `may_be_nan` (`templates/__init__.py`, `_may_be_nan`), level from `domain.constructed_noncommutative`, `free_symbols`, `is_finite`, `complex()`. Reading `is_finite` and `complex()` can write SymPy's caches, which is why the answers-and-state check with the shadow on matters.
- Keys and `_hashable_content` as a flat token stream of ints: tuple(n), int, string index, bool, none, rational, term id, opaque. Conversion's `default_sort_key` and `decompose_power` construct inside SymPy: measure and report that count, it isn't zero.
- Formula: own walk mirroring `to_formula`, relation atoms kept as (name, lhs, rhs) because `relation_atom` is component 4. Check: rebuild from Rust's dump with the real constructors and `relation_atom`, compare to the real `to_formula`.
- Generic constants table (`_IV_PREC`, `lra_bounds.py:26`, `:150`): undecided, its consumer is 1b. Build it if cheap, else name it as not built. Same for atomic-number truth rows if nothing reads them.

**Rust table:** hash-cons on (class, args, payload), input rows inserted first, so a derived term equal to an input term gets its id. `Rat` from `lra/port/src/rat.rs` has parse, add, mul, neg, cmp; sa-port-6 may bring it into this crate, so check before copying.

**`compare` (`Basic.compare`):** class by (rank, name) with unknown ranks by name, then content length, then elementwise; int against str is an error, so refuse.

**Algebra, each from SymPy's code; refuse anything else with a reason:**
- `Mul.__neg__` `sympy/core/mul.py:194`: raw `_from_args`, coefficient merged into a numeric head, or `-1` prepended. `Add.__neg__`: `Add(*[-i])`. `Expr.__neg__`: raw `(-1, self)` with no evaluation, so `-sqrt(2)` doesn't merge.
- `Add`: as `algebra_check.py` (`~/sa-rust-ids-work/port-census/`), `form`, `merge`, `term`, `build`: rational constant first, the rest sorted by `compare`. Refuse infinities, nan, Float, Order, non-commutative, a numeric-base power, and a coefficient on a sum (it builds `Mul(c, s, evaluate=False)`). Don't intern the stripped body of a Mul as a term: it would take an id Rust's result never holds.
- `Mul.flatten`, `mul.py:290-312` two-argument path: rational `a` times `r*b`, with `b` an Add: `r != 1` gives `Mul(a*r, b, evaluate=False)` unless `a*r` is 1; `r == 1` distributes, `Add(*[_keep_coeff(a, bi)])`. `mul.py:733`: distributes when exactly two commutative parts are a finite Number and an Add. Otherwise sort by `compare`, coefficient first. Refuse two factors sharing an `as_base_exp` base (`exp(x)*exp(y)` merges), a numeric base, and more than one `I`.
- `coeff_add`, `coeff_mul`: `relations.py:496-502`; the rest is `_new_rawargs`, order kept. A Float head refuses.
- `sort_key`: `algebra_check.py` `key_of` and `term_data`, the only version that has shown 0 mismatches, and that was in Python. `complex()` of a rational must round correctly: `p/q` in f64 if both are under 2**53, else refuse. Python's complex multiply is the plain formula.

**Shadow (`term_shadow.py`), monkeypatch only, no satassume source change:**
- Wrap `__neg__`, `__add__`, `__radd__`, `__sub__`, `__rsub__`, `__mul__`, `__rmul__`, `__truediv__`, `as_coeff_Add`, `as_coeff_Mul`, `Add.__new__`, `Mul.__new__`, on every class of `Expr`'s subclass closure that defines them in `__dict__` (Add, Mul, Number, Rational, Integer override them). Check only when the immediate caller's `__name__` starts with `satassume`, so each row has a real file:line and sites need no list.
- On each: map operands to ids, ask Rust, compare the recipe against the real term recursively, class and arg order included; then `ids[real]` must be absent or equal to Rust's id (the merge check). Count unknown operands per site: they show what section 3 missed.
- Wrap `Session.node` (`engine.py:545`), `relations._key` (`:466`), the sort calls in `lra_adapter.py` (`:324`, `:348`, `:412`), comparing keys.
- Wrap `Engine._cone_info` (`engine.py:1676`) and `_struct` (`:1609`): distinct objects under Rust ids and their weight sum must equal Python's. This is the exactness the brief asks for.
- Also the synthetic loop of `algebra_check.py` (`-t`, `c*t`, `t+c`, `t-u` on the first 9 input terms) against Rust, on dev, fuzz, corpus. `derived.py` beside it shows how workloads are driven.

## File:line map

`HANDOFF-sa-port-1.md` has the engine, relations, adapter and template map. Added here:

| Topic | Where |
|---|---|
| Spec | `PORT-INVENTORY.md` section 3 (`:57`), 4 (`:129`), 9 (`:311`), 10 (`:369`), held-to (`:393`) |
| Query hook, formula | `sympy_api.py:480` `_ask` call, `:354` `to_formula`, `:316` `relation_parts`, `:300` `out_of_scope` |
| Termwise, strip, atom | `relations.py:672`, `:496`, `:523`; eq links `:1366`, glue `:2008` |
| Level, registry | `domain.py:58`, `:388`; `templates/registry.py:67`, `:194`; `templates/__init__.py` `_may_be_nan` |
| Python prediction | `~/sa-rust-ids-work/port-census/algebra_check.py`, `derived.py` |
| Pymodule | `solver_rs/src/lib.rs` (`mod term`, `term::py::register`), `solver_rs/src/term/py.rs` |
| Suite | `run_suite.sh`, `suite_report.py`, `rust_plugin.py`; base numbers `results/pr328-check.md` |
| Boundary mutants, format | `mutate_boundary.py`, `mutate_slice.py` |

**Environment:** `. ~/sa-rust-ids-work/env.sh; export PYTHONPATH=$PWD:$W/sympy:$W/shim:$PWD/rust-spike/slice`. Build `sh rust-spike/slice/build_solver.sh` (about 70 s). Output under `~/sa-rust-ids-work/sa-port-5/`. Run `tests_offline.py` to recheck D; rerun the generator if any `SOURCES` file changes.
