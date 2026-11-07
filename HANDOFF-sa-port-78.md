# Handoff: conversion floor prototype (sa-port-78, 7 Nov)

Branch `prototype/conv-floor`, from d29e94b. Prototype only, nothing lands. Done so far: the split. Not started: both prototypes, the
plant, the history-argument tests, the floor. No prototype source has changed: the only additions are this file and
`rust-spike/slice/conv_floor/` (tools).

## The split, done (d29e94b, quiet pareto1 lease, bench-container CPU 2, 6 rounds, first dropped, medians of 5)

Raw: orion `~/sa-rust-ids-work/sa-port-78/raw/split/` (`split.jsonl`, `analysis.txt`, `env.txt`, `load.txt`, `host-*.txt`). Tools:
`split78.py`, `ana_split.py`, `run_split.sh`, `onlease.sh`. All digests matched (dev 31cd0945c07f02a6, fuzz 173502b6ef285ad6),
refusals 0. Build f746e9cf0b5d, the same .so sa-port-76 timed.

**Method:** exclusive timers, a stack, so a timed region inside another is charged only to itself. Cold process per arm. `plain` is
qt76.py with no timers, in the same rotation. `klass-miss` times only the branch that builds a row. `row:*` is a timed copy of
term_row, a breakdown of `conv:term_row-total`, not added to it.

**Overhead (arm over plain):** coarse 1.072x dev, 1.069x fuzz. Fine 1.097x, 1.090x. term-py wrapped 1.053x, 1.088x. So every ms below is
inflated by something like that, and unevenly: the many-call rows most.

| s | dev | fuzz |
|---|---:|---:|
| plain rust mode, range | 0.713 (0.709 to 0.718) | 6.323 (6.247 to 6.348) |
| plain `SLICE_TERM=py`, range | 0.308 (0.307 to 0.321) | 3.998 (3.994 to 4.057) |
| difference (arithmetic within one rotation) | 0.405 | 2.325 |

| coarse arm, ms (calls) | dev | fuzz |
|---|---:|---:|
| `conv:klass-miss` | 161.2 (18,317) | 431.7 (45,090) |
| `conv:term_row-total` | 71.4 (12,423) | 407.5 (47,513) |
| `conv:other` (convert's own: formula enc, settings enc, loop) | 28.1 | 84.1 |
| `conv:walk` | 20.9 | 78.2 |
| `table:TermTable()` (Rust parse) | 19.7 | 63.0 |
| `conv:formula` | 14.2 | 30.4 |
| `conv:settings` | 9.2 | 28.3 |
| `live:_convert-own` | 4.1 | 11.6 |
| `conv:power_rows` | 2.1 | 7.5 |
| **conversion, sum of the above** | **0.331 s** | **1.142 s** |
| `read` (lazy reads, kept apart) | 11.9 (630) | 255.2 (17,198) |
| `live:mark` (`_Mark`, the rollback journal: not conversion, but SLICE_TERM=py removes it) | 34.2 | 107.6 |
| `live:_note_query`, `journaled_put` | 2.4 | 10.3 |

Top sites, coarse on rust against term-py wrapped, ms (calls; rust's and Python's call counts differ, since Python's includes
nested and cached paths differently): dev `interpret` 16.3 (3,568) against 4.9 (214), `_is_number` 10.1 (7,684) against 7.4 (9,360),
`order_sides` 10.0 against 2.8, `relation_atom` 7.6 against 3.3. Fuzz `interpret` 395.5 (102,762), `order_sides` 275.2 (43,645),
`relation_atom` 238.8 (63,570), `_is_number` 192.6 (152,694) against 164.9 (216,752), `_memoized` 112.8, `integer_form` 106.7, `_eq_links`
99.4. `analysis.txt` has both columns. `ask:outer` (everything untimed, including engine, solver, theories): rust 305.8 dev, 3,477 fuzz;
term-py 278.7 dev, 3,314 fuzz. Don't quote those as engine time: they hold the solver and theories of two different backends' paths.

Fine arm (`row:*`, ms, calls), dev then fuzz: noncomm 11.7, 69.1; atoms-undef 11.4, 68.8; content 9.9, 58.7; args 8.0, 33.8; has-bad 6.2,
33.3; free_symbols 5.3, 39.1; has-nan 5.1, 28.0; free-enc 4.1, 24.5; may_be_nan 3.9, 29.3; has-float 2.2, 11.4; is_number 2.0, 15.9.
Calls 4,515 and 28,853 facts, 12,423 and 47,513 rows.

**Early read, not a result:** `klass-miss` is about half of conversion on dev and over a third on fuzz. It's the one large piece.
The three facts no consumer reads (below) are about 27 ms dev and 167 ms fuzz under the fine timers. So the cache should be most of the floor;
the lazy facts help fuzz more. Nothing here has been measured as a saving yet.

## What to build, as designed (decided by reading, unverified by running)

Switches in `rust-spike/slice/convert.py` read at import, so one .so serves all arms: e.g. `SLICE_CONV_CACHE=1`, `SLICE_CONV_LAZY=1`.
Arms to time, in one rotation: `base` (`$B/base`, untouched d29e94b tree and its .so), prototype with neither switch (control for
the switch's own cost), cache, lazy, both, plus plain `SLICE_TERM=py`. `qt76.py` works unchanged with `SLICE_DIR`/`PYTHONPATH`.

### 1. Class-row cache, Python only (`_Walk.klass`, convert.py:214-260)

- Module-level `{cls: (tokens, [(pos, text), ...])}`: build the row with its own string numbering, store where the strings sit, and on
  use `class_rows += tokens` and patch each string position with `self.s(text)`. No term ids: if `enc(ckey)` would emit T_TERM, don't
  cache that class, and count it. Don't cache a `_Keep`.
- **Epoch:** check `satassume.state.epoch`'s EPOCH once per `convert()`; clear on change. `TemplateRegistry.register`
  (`knowledge/templates/registry.py:161-192`) bumps it. Lazy-module registration deliberately doesn't (registry.py:97-108), and is safe by
  the same argument as `_mro_cache`: `templates_for` loads every declared module covering `cls` before answering.
- **Don't adopt it into MEMOS:** `harness.state.reset_module_state` clears MEMOS per query in `fresh.py`, so an adopted cache would never
  be read across queries and fresh.py would test nothing about it. Keep it out, and say so.
- Size cap with a plain clear, since `Function('f_i')` makes a class per name, and `_mro_cache` holds the same strong references.
- Possible second step if it matters: the `_PREFIX` rows (9 classes, every query) as one fixed block with fixed string ids.

### 2. Facts on demand

**No consumer in plain rust mode reads these three (by rg, confirm by running):** `fact::UNDEF`, `fact::MAYBE_NAN`, `TermRow.level`
(`constructed_noncommutative`). They reach only `py.rs:229-231`'s row dump, for `term_shadow.py:161-167`, and `algebra.rs:79`'s inherit.
Read for: `free`, NUMBER, NAN, BAD, FLOAT.

Rust, `solver_rs/src/term/`:
- `TermRow` (table.rs:134): keep `bits` eager for READ and COMMUTATIVE only (skeleton gate, table.rs:440, algebra.rs:61, 637; lra_read.rs:170,
  390). Add `facts: OnceLock<Facts>`, `Facts { free: Box<[TermId]>, bits: u8 }`, and `TermTable::facts(t) -> Result<&Facts, Refuse>`.
- A derived term's facts become lazy as well, as the union over its args, or `intern` (algebra.rs:79-90) forces every input it touches.
  `number()` (algebra.rs:117) presets them.
- Sites to move: algebra.rs:64, 637-643; lra_read.rs:160 (`free`, callers 197, 213, 393), 174, 327, 393; relations.rs:14 (`is_number_term`,
  callers 62, 101, 128, 180, 214, py.rs:282), 226-230 (`affine_pair`, py.rs:326); table.rs:449, 460. `is_number_term`, `affine_pair` and
  `free` become `Result`.
- `Read` enum (table.rs:112) and `READS` (convert.py:49), same order: add Facts, Undef, MaybeNan, Level. `from_tokens` (table.rs:322-340): when
  the tokens carry facts, preset the OnceLock, so the eager arm is the same code path.
- `py.rs` `row()` (222-236) must force them when asked, or `term_shadow` sees zeros. `term_live.scaffold` only reads `row` for derived ids.

Python, `term_row` (convert.py:264-302): under the switch emit `T_NONE, T_INT, F_READ, T_INT, 0`. `_read_facts(t)` returns (free terms sorted by
id with `key=ids.get(x, -1)`, bits), so `enc` raises `_NotInTable` on a free symbol `.args` doesn't reach, which refuses with
`read_term_missing`. Keep the NaN line. Count: facts reads by kind, `read_term_missing` and `read_raised` (planner's rulings); a raise used to
be a `TermFault` from `_convert`, and is now a refusal, so say that.

**Say which moved and what still forces them:** count per workload how many terms get a Facts read against rows. If most do, the crossing
may cost more than it saves, and that's a result.

## What must be checked

- **Same work:** answer digests in every timed run; state through `fresh.py`, Python against each arm, with `p_install` ahead and `--term terms
  --lra`. `tools/run.sh` lines 42-52 in sa-port-76's copy has the exact call (`~/sa-rust-ids-work/sa-port-76/tools/run.sh`).
- **Plant:** corrupt one cached row field, per field: kind, rank, flags, class_key, templates, structural, custom_content. Show which ones
  fresh.py catches. A field no comparison catches gets named as such; don't claim the comparison sees it. Show the planted row is
  actually served across queries.
- **History argument:** a check mode recomputing each row on every hit and comparing, on dev and fuzz. Also fill the cache in reverse query order and in
  fuzz-then-dev order, and compare the row digests by class.
- **Cases to run, each with a small script:**
  - non-default registry: `eng._templates` differs, so `Kept` before any row (convert.py:396). A template registered from a non-satassume
    module: bump, row rebuilt, `_Keep` (convert.py:251).
  - class registered mid-process, on a base whose subclass row is already cached: bump clears it.
  - `extensions.register`/`unregister`: bumps by `version`; the row reads nothing of it, so conservative.
  - **The case I expect breaks it, not yet run:** monkeypatching a class attribute the row reads mid-process, with no epoch bump: `MyExpr.as_base_exp
    = ...`, `_op_priority`, `__add__`, `atoms`, `class_key`, `_hashable_content`, or `ordering_of_classes`. Python reads these live, so its answer can
    move while the cached flags (`_PLAIN_OPS`, `_PLAIN_BASE`, `_PLAIN_ATOMS`, convert.py:232-244) stay stale. Build the smallest case with a real answer
    difference, or say it doesn't reach one. Compare with `_mro_cache` and `_redefines` (registry.py:209), which have a similar exposure for some fields only.
  - `UndefinedFunction`: distinct classes that compare equal share a dict entry. `_Walk.classes` already conflates them within a query; `_kwargs` is in the
    equality, so check nothing the row reads differs.
  - SymPy handler changes (`Q.x.register`, `_eval_is_*`): the row doesn't read them, except `FLAGS`' `is_*` class attributes (convert.py:229-231).
- **Quiet-handler counts** with a planted raise first (FALSE ZEROS): `--handlers` in fresh.py, `test_handler_count.py`.
- **Tests:** `test_lazy_reads.py` asserts counts on reads and may need the new kinds. Run `test_term_ids.py` and `test_lazy_reads.py` only; no suites, no mutants.

## Bench setup

pareto1 `~/sa-rust-ids-work/sa-port-78/bench/`: `base` (d29e94b with its .so), `sympy`, `data`, `evalbench`, `tools`, `results/split`. A new session
should `cp -a` it to its own directory. Sync the prototype tree as `tree`, build as `tools/prep.sh` does in `sa-cy-build:1` under a `--shared` lease, and
compile bytecode as prep.sh does. `onlease.sh RUNSCRIPT NAME` takes a run script and a results name, and writes to `results/NAME`; fix its `B=`.
The split took 3 minutes for 6 rounds of 5 arms on both workloads. On orion: `. ~/sa-rust-ids-work/env.sh; export PYTHONPATH=$PWD:$W/sympy:$W/shim
SLICE_DIR=$PWD/rust-spike/slice`, `$PY`; the clone's .so is built for d29e94b.

## File map

- `rust-spike/slice/convert.py`: READS 49, `_Walk` 119, `klass` 214-260, `term_row` 264-302, `read` 318-343, `convert` 448-483.
- `rust-spike/slice/term_live.py`: `_Query` 72-90, `_Mark` 125-185, `_convert` 204, `_ask` 919-963, sites 967-992.
- `solver_rs/src/term/table.rs`: Read 112, TermRow 134, TermTable 146, from_tokens 273, row parse 317-340, read 359, finite_of/complex_of 448-468, row 501.
- `solver_rs/src/term/py.rs`: PyReads 36-50, `new` 169, `row` 218-236, `is_number_term` 281, `affine_pair` 325.
- `satassume/state/epoch.py` the epoch's contract; `satassume/knowledge/templates/registry.py` 97-108, 161-214.
- `rust-spike/slice/fresh.py` the state comparison; `rust-spike/slice/term_shadow.py` 129-167 reads the row's facts.
