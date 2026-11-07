# Handoff: sa-port-32 to the next session (issue 323), lazy reads

Read the brief first: `~/.local/state/agent/briefs/sa-port-32-20261107T102630Z.txt`. Its terms, rulings and HELD TO list all still apply. `HANDOFF-sa-port-29.md` still holds for traps, survey limits (carry them into the final report) and the map, except where this file corrects it. Clone `~/dev/sa-port-5`, branch `port/lazy`. Nothing is on `rust-slice`. Output: `~/sa-rust-ids-work/sa-port-32/`. Modules of the 32: 0 added.

**State: the design is built and compiles. It has only had the smoke checks listed below. None of HELD TO has been run in full.** No job of mine is running.

## Measured: a key holding a term `.args` doesn't reach

`key_growth.py`, conversion only, run on the eager `convert.py` (`~/sa-rust-ids-work/sa-port-32/growth/`). All three finished with exit 0.

| Workload | Queries | Converted | Terms in keys | Not in the table | Queries |
|---|---|---|---|---|---|
| dev | 1,985 | 1,935 | 6 (`oo`) | 0 | 0 |
| fuzz | 3,000 | 3,000 | 0 | 0 | 0 |
| corpus | 2,863 | 2,673 | 130 (`Float` 44, `oo` 35, `-oo` 51) | **27, all `-oo`** | **27** |

All 27 are `Q.x(nan)`: `NaN.sort_key` holds `S.NegativeInfinity` (`numbers.py:3456`). **Decision, name it in the report:** `term_row` adds `-oo`'s row when it reaches `nan`, where the eager key's walk added it, so the table should be the same as before. Any other miss refuses, reason "read: a value holds a term the table doesn't", counted as `read_term_missing`. The miss path has **not** been exercised: plant a class whose key holds a new term. Other `sort_key` overrides by rg: `Partition` (`combinatorics/partitions.py:94`) and the two polys ring/field ones, not Basic-keyed by my read and not run. `key_growth.py` now raises KeyError on `c.counts['keys']` on this tree, since it needs the eager conversion: rerun it only from cc3055c's `convert.py`, or drop that line.

## Shown so far (smoke only)

- `term_shadow_fresh.py dev --limit 200`, checks on, all reads forced: `bad` empty, read_term_missing 0, read_raised 0. Answers sha 55fe320a718ef763, **not compared with a plain run yet.**
- One-off script, not in the tree, `CRootOf(x**5-x+1,3)`: `Q.positive(y+r)` convert plus `TermTable`: 0 `complex()`. Reading the key of `y+r`: 6. A second read adds 0 and `read:key` stays 1. `row` shows only what's been read. `_Walk` is dead by weakref after table and `c` are dropped. A `BaseException` from `complex` comes through as itself. **This doesn't include the ask itself, the test must.** `counts['opaque']` was 1 at conversion here: untraced, and probably predates this work.

## What's built

**Rust.** `table.rs`: `Read` enum, `Reads` trait, `READ_RAISED`, `V::Text`, `TermTable.reads`/`memo` (a `Mutex<HashMap>`, never locked across Python), `read`, `peek`, `peek_closed`, `peek_power`, `reads_held`, `input_key`, `finite_of`, `complex_of`, `power_of`, `commutative_of`. `TermRow` lost `key`/`closed`/`power` and gained `has_power`. Row tuple is 6 (class, args, content, free, bits, level). `powers` is a flat list of ids; `n_powers` is gone. `algebra.rs`: `operand`, `sort_key`, `add_key` read through those. `py.rs`: `PyReads`, thread-local `RAISED`, `refuse` raises it; `row` forces nothing; new `finite`, `complex`, `power`, `commutative`, `reads_held`.

**`convert.py`:** `READS`, `T_MISS`, `_NotInTable`, `_Walk.read` and `_read_*`, `reading` flag, `tables['reads'] = w.read`. Counts are now `read:key|finite|complex|power|commutative`, `read_term_missing`, `read_raised`, `pow_base_not_input`, `opaque`; `keys`, `decompose_power`, `closed` are gone.

**Changes to name in the report:** `is_finite` and `decompose_power` were unguarded; a raise now gives None (finite reads as unknown, power refuses). `Kept('too-deep')` can shift, since a `RecursionError` in a read is now a refusal: count it against the eager tree. A raising `is_commutative` reads as not True, so it refuses.

**Tools.** `term_shadow.py`: explicit reads in `check_table`, `check_order`, `_has_key`; counts added at query end; new `DRIVE` flag (algebra and used keys only, no checks, no printing) **written, never run**. `term_history.py`: excludes `reads` from the digest and forces every read; not run. `mutate_term.py`: anchors moved for `closed-value-abs`, `conv-key-dropped`; new `read-memo-off`, `read-text-swapped`; not run.

## What's left, in order

1. **Fix `term_counts.py`**: `:103-105` read `counts['keys']`, `['decompose_power']` and will KeyError. Add a `complex(t)` counter by wrapping `Expr.__complex__`.
2. **Count test** `rust-spike/slice/test_lazy_reads.py`: `Q.positive(y+r)` zero `complex()`, by count, for convert, `TermTable` and the whole ask, with the shadow's checks off (`str` evaluates). Include cheap evaluations (`f(r)`'s 3). Rerun `lazy_probe.terms(d)`'s 60 hand-built terms through conversion with complex, evalf and root-refinement counters (`lazy_probe.py:99` `_count`; its main is guarded), per the ruling's item 1. Plant per kind: wrap `_Walk.term_row` to do the eager read again; each must fail. Also plant: the miss path, `read_raised`, and memo death with a second `TermTable` re-reading.
3. **`lazy_reads.py WL OUT.jsonl`**, the ruling's item 3. Two passes per query, each `reset_module_state(sympy_cache=True)` on a fresh engine, because a shared cache hides inner reads. Pass 1, pure Python: record (kind, term) by wrapping every class with `sort_key` in `__dict__` (walk `Basic` subclasses: outer wrapper, outside `cacheit`), every `__complex__`, and `sympy.core.exprtools.decompose_power` (check `as_terms` looks it up at call time). Pass 2: `term_shadow.install()`, `install_algebra()`, `DRIVE[0] = True`, wrap `_Walk.read` to record (kind, term) with recording of Python's reads off inside it. Row: reads by kind, reads not in pass 1, answers equal. Report a difference with its smallest case. `is_commutative` can't be compared: it's an instance slot or class constant on stock classes. Say that, and don't reclassify.
4. HELD TO: plain against shadow answers and state on dev and fuzz; D and 0's shadow on dev, fuzz, corpus (D0 report's numbers are the base: dev a5349612416b55ef, fuzz d4006a14c365ecdf, corpus 544a8c885fcd4911); `term_history.py` across seeds; handlers with `handler_count.py` and `quiet_fire.py` from `~/dev/sa-port-17/rust-spike/slice/` (copy them; the plant raises from `table.sort_key` inside each `try`); suite by id with `suite_report.py` and the passed split from the reporting ruling; ruling 6 on a quiet pareto1 lease (`~/sa-rust-ids-work/sa-port-18/p1-site-time.py`, `timing_summary.py`, `~/sp19/p1_job.sh`, x86-64 `.so` rebuilt), with `klass`'s share.
5. Section 9 (`enclose` no longer "the one permanent callback": read-only callbacks on input terms; Closed terms, Power factors and Term facts rows are now reads; `:634`'s note), `convert.py`'s header at lines 6-7, `TERMS-INTERFACE.md` (`reads`, `row` shows what's read so far, new methods, a lazy key can't add a term, `-oo`). Rebase, push to `rust-slice` with no force, tell the architect the SHA first, report.

## Map (line numbers as of this commit; use rg)

| Topic | Where |
|---|---|
| Rust read and memo | `table.rs` `fn read`, `input_key`, `*_of`, `peek*` |
| Rust callers | `algebra.rs` `operand`, `sort_key`, `add_key` |
| Python face | `py.rs` `PyReads`, `refuse`, `row`, `finite`... |
| Conversion | `convert.py` `term_row`, `power_rows`, `read`, `_read_*` |
| Shadow | `term_shadow.py` `DRIVE`, `check_table`, `check_order`, `top_level`, `install` |
