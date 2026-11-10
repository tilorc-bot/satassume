# Formula step (issue 323): files, inventory, and the boundary conversion

Branch `port/formula`, from rust-slice 59e9d15. Written by sa-port-231, 10 Nov. **Not landed, not barred.** This file is the
step's first deliverable (file list and inventory) and is extended as the step goes.

## What the step is
The Formula classes (`P`, `And`, `Or`, `Not`, `Implies`, `Equivalent`, `Exclusive`, `ITE`) are input and stay Python. A
Formula is converted into Rust's formula nodes once at the boundary; after that no Rust code reads the Python object back
(`.args`, `__eq__`, `__hash__`), and `atoms_of` and the engine's uses of Formula objects as keys run on the Rust nodes.

## Where it stands at 59e9d15
- `compile.rs` reads no Python: it compiles `F` (ids). The read is in `session.rs:942-989` (`SessionCore::to_f`), which
  walks the Python Formula **on every `compile`/`literal` call** (`session.rs:1560`, `:1569`), not once per Formula.
- Every other consumer still gets the Python object and walks it again through Python's `atoms_of`, called back by name
  from Rust (17 sites below), and Formula objects are dict keys in the engine's memos (`Formula.__hash__`/`__eq__`).
- Module-wide probe, base 59e9d15, dev pass 1 (every Python call into the file, `sys.setprofile`): **sat/formula.py 10,977
  calls on converted queries** (`atoms_of` 6,777, `Formula.__hash__` 4,052, `Formula.__init__` 125, `Not.__init__` 21,
  `Formula.__eq__` 2) and 55 on kept queries; knowledge/compile.py 42 on converted queries (`formula_literal` 17,
  `_literal` 23, `_def` 2: the `refuse:object` path). The other workloads are in the table at the end.

## Files the step will touch
| file | what | waits on |
|---|---|---|
| `solver_rs/src/formula.rs` (new) | the Rust node type, the one-pass conversion, `atoms` on nodes, the step's counters and plants | nothing |
| `solver_rs/src/lib.rs` | registers `formula.rs` (2 lines; shared file) | nothing |
| `test_formula_nodes.py` (new) | conversion against Python's `atoms_of` and classes; plants | nothing |
| `solver_rs/src/term/rows_tpl.rs` | `scaffold:core:kept_product:mismatch` only (architect's note, KEPT_PRODUCT ruling) | nothing |
| `solver_rs/src/session.rs` | `SessionCore`: per-session node cache by object identity; `to_f` reads the node, not the object; atom keys | (iii) landed + rebase |
| `solver_rs/src/session_glue.rs` | `assume_formula`, `_a_raw`, `:184`: atoms from the node | the cache (so (iii)) |
| `solver_rs/src/compile_loop.rs` | `:327`, `:372-376` atoms from the node; `:182`, `:344` compile the node directly | the cache (so (iii)) |
| `solver_rs/src/query.rs` | `:248` literal of the node; `:271`, `:287` atoms from the node | the cache (so (iii)) |
| `solver_rs/src/scope_core.rs` | `:252-261`, `:286-296` atoms from the node (`scope:cb_atoms_of` to 0) | the cache (so (iii)) |
| `solver_rs/src/budget.rs` | `:61`, `:91`, `:115`, `:199`, `:374`, `:465` atoms from the node | the cache (so (iii)) |
| `solver_rs/src/entry.rs` | `:778` (`proposition.args[0]`), `:781` (`basis_formula` built on Python) | the cache; check part 3's diff to entry.rs first |
| `solver_rs/src/relations_core.rs`, RelKeys | atoms as keys (`rk:intern:engine` atoms to 0); `:3210-3217` | (iii) landed + rebase |
| `solver_rs/src/engmemo.rs`, `procmemo.rs` | Formula objects as memo keys (`em:key_eq`, `pm:key_eq`; `procmemo.rs:305-307`) | the cache (so (iii)) |
| `solver_rs/src/term/common.rs`, `fn_tpl.rs`, `rows_tpl.rs`, `dispatch.rs` | template formulas built as nodes, not as Python Formula objects | nothing in the waiting areas, but after the cache |
| `session_live.py` | its `atoms_of` callers (`f`, `_context_session`, `_ses_assumption_lits`, `verdict`), `_formula_literal` | part 3's sub-part 5 |

## Inventory
Owner is the formula step for every row unless stated. "Wait": (iii) = until state part 2 (iii) has landed and this branch
is rebased; p3 = until state part 3's sub-part 5 has landed; "cache" = needs the per-session node cache, which is in
`SessionCore`, so (iii).

### A. Rust reading a Python Formula object
| # | file:line | read | wait |
|---|---|---|---|
| A1 | session.rs:942-989 `to_f` | `isinstance` against the 9 classes, `.args` (:958), `_Lit.lit` (:967), atom `.pred`/`.expr` (:935-939), per `compile`/`literal` call (:1560, :1569) | (iii) |
| A2 | entry.rs:778 | `proposition.args[0]` of a negated proposition | cache; part 3 touches entry.rs |
| A3 | term/dispatch.rs:127-167 `_split` | `isinstance` against `P` and `Formula` on template results | cache |
| A4 | relevance.rs:602-604, :731-732 | `_formula` called back (`rv:cb_formula`, conversion layer); its result is a Python Formula handed on | cache |

### B. Python's `atoms_of` called back from Rust (walks the Formula again: `isinstance`, `.args`, `P` hash and `==`)
| # | file:line | caller | wait |
|---|---|---|---|
| B1 | session_glue.rs:86 | `assume_formula`: `_a_raw` | cache |
| B2 | session_glue.rs:184 | atoms of a proposition | cache |
| B3 | compile_loop.rs:327 | `note_formula(atoms_of(assumption_formula))` | cache |
| B4 | compile_loop.rs:372-376 | atoms of each template or extension formula | cache |
| B5 | query.rs:271, :287 | `note_formula(atoms_of(f))`; query atoms | cache |
| B6 | scope_core.rs:252-261, :286-296 | `theory_scope` (`scope:cb_atoms_of`) | cache |
| B7 | budget.rs:61, :91, :115, :199, :374, :465 | `_kid(a) for a in atoms_of(f)` and the cone | cache |

### C. Compilation re-entered through Python with the Python object
| # | file:line | call | wait |
|---|---|---|---|
| C1 | compile_loop.rs:182, :344; session_glue.rs:119 | `compile_formula` by name, which comes back to `SessionCore.compile` and `to_f` | cache |
| C2 | query.rs:248 | `formula_literal` by name | cache |
| C3 | entry.rs:781 | `basis_formula(a)`: a Formula built on Python, then compiled | cache; part 3 |
| C4 | session.rs:991-1009 `convert` | refusals compile on Python (`refuse:object` 34 on dev, `refuse:depth`, `refuse:convert`): knowledge/compile.py's 42 calls | (iii) |

### D. Formula objects built by the engine in Rust, then read back (A1)
| # | file:line | what | wait |
|---|---|---|---|
| D1 | term/common.rs:452, :499 | `instantiate`: `Compiled.formulas`/`wide_formulas` | cache |
| D2 | term/fn_tpl.rs:375; term/rows_tpl.rs:1761, :706-714 | `P`/`Not` unit-interval facts; `_wide_of` | cache |
| D3 | relations_core.rs:3210-3217 | the `(compiled, formulas)` wrapper | (iii) |

### E. Formula and atom objects as keys (engine-internal)
| # | file:line | key | wait |
|---|---|---|---|
| E1 | engmemo.rs (`em:key_eq`, 5,860 on dev over two passes) | Formula keys and values of the moved engine memos | cache |
| E2 | procmemo.rs:305-307 (`pm:key_eq` 14,356) | atom `.expr` `==`; Formula keys | cache |
| E3 | relations_core.rs: 22 atom reads (`.pred`/`.expr`: :827, :978, :1000, :1162, :1209, :1234, :1370-1380, :1530-1533, :2137-2138, :2242-2243, :2418, :2449, :2852-2859, :2881-2882, :2907, :3067-3077, :3134) and Relations' dicts keyed by atoms | (iii): RelKeys, `rk:intern:engine` for atoms |
| E4 | atom `.pred`/`.expr` reads outside relations_core.rs: session_glue.rs:101, :148, :298-310, :398; scope_core.rs:145, :174-184, :208; budget.rs:97-101, :230, :383-384; compile_loop.rs:169-171, :230-231, :317; query.rs:84-95, :291-293; transfer_py.rs:316-328; term/rows_tpl.rs:1326; session.rs:873, :1516, :1581, :1605 (`atom_fields`) | cache (session.rs: (iii)) |
| E5 | session_live.py: `Formula.__hash__` from `_context_session` (1,161), `f` (960), `verdict` (91) on dev pass 1 | p3 |

`P` itself is already a Rust class (`formula_py.rs`, step 3); its `.pred`/`.expr` are Python objects, and its hash is
`hash((pred, expr))`, a term hash. Those are term-id work once the atom is a node (RelKeys ruling: `rk:intern:input`).

## KEPT_PRODUCT: what `:none` meant, and the new counter
`scaffold:core:kept_product:none` (core 14 in report ce706d3) is **not** a mismatch count. At `rows_tpl.rs:1454-1484` the
scaffold builds the rest with SymPy's `Mul` and `:none` counts the times SymPy's product doesn't keep exactly those
factors, which is Python's own `kept_product` returning None. Rust's `mul` isn't consulted there at all, so before this
branch a Rust-versus-Python disagreement at that site was **unmeasured**, not zero. (The Python shells it replaced did
compare, `knowledge_core_live.py:126-144`.) This branch adds the comparison; see the counter section once it has run.

## Module-wide probe, before (base 59e9d15, pass 1, every function in the file)
Python calls into sat/formula.py and knowledge/compile.py, per workload, on converted queries (`[query]`); kept queries
in brackets. Full rows with the top functions and the Rust counters: `port-formula-probe-base.txt`. Tool:
`~/sa-rust-ids-work/sa-port-231/probe/` (`count_formula.py`, sa-port-201's count7.py with `--trace` taking package paths;
`runall.sh TAG CLONE`; `summ.py DIR [--callers]`). The Rust counters there are totals over the run's two passes.

| workload | sat/formula.py | knowledge/compile.py | `scope:cb_atoms_of` | `rv:cb_formula` | `refuse:object` | `em:key_eq` | `pm:key_eq` |
|---|---|---|---|---|---|---|---|
| dev | 10,977 (kept 55) | 42 | 3,730 | 244 | 34 | 5,860 | 14,356 |
| fuzz | 102,045 | 205 | 17,404 | 630 | 60 | 30,701 | 242,675 |
| f6 | 1,112 (kept 94) | 0 | 24 | 16 | 0 | 222 | 39,054 |
| value | 4,298 | 0 | 1,676 | 8 | 0 | 6,114 | 19,466 |
| rootof | 2,579 | 0 | 1,474 | 4 | 0 | 2,944 | 15,372 |
| core | 3,175 | 0 | 1,216 | 36 | 0 | 3,474 | 20,272 |
| opaque | 216 | 0 | 124 | 4 | 0 | 672 | 4,320 |
| scope | 4,264 | 7 | 2,006 | 0 | 2 | 1,252 | 3,932 |
| loop | 9,570 | 0 | 976 | 0 | 0 | 1,654 | 7,504 |
| zero | 14,604 | 288 | 3,758 | 74 | 188 | 5,646 | 26,594 |
| wiring | 46,187 | 0 | 19,660 | 406 | 0 | 37,874 | 192,292 |
| cert | 2,688 | 0 | 366 | 0 | 0 | 236 | 3,178 |
| budget | 13,505 | 0 | 58 | 0 | 0 | 146 | 8,154 |

dev and fuzz at hash seed 1 give the same sat/formula.py and compile.py numbers (`em:key_eq` differs by 28 and 93).
**After: not run.** The code below isn't wired into the session, so these numbers can't have moved yet.

## Code on this branch so far (unbarred)
- `solver_rs/src/formula.rs` (new, registered in lib.rs): `convert(f, classes)` walks a Python Formula once and returns a
  `FormulaNode`: the tree (`N`), each atom occurrence's own object with its `pred` and `expr`, and `atoms_of`'s result
  (the first-seen objects, deduplicated by one dict lookup per occurrence, which is `P`'s hash and `==` as Python's `seen`
  set runs them; a bare `P` hashes nothing, as in Python). It refuses, counted, where `to_f` refuses or where a `Bad` node
  would change `atoms_of` (depth over 64; a Formula subclass outside the nine classes or a wrong arity; an `Exception`
  from a read). Counters 630-639 (`formula_counts()`), plants 601-606 (`formula_plant(name)`).
- `test_formula_nodes.py` (new, 15 tests, python mode like its neighbours): 410 formulas against Python's reading (atoms by
  value and identity, tree, occurrences); the node unchanged after the object's `args` are emptied; the four refusals and a
  BaseException going up.
- `term/rows_tpl.rs`: `scaffold:core:kept_product:mismatch` and `:unchecked`. Python's answer is used as before; Rust's
  verdict (its `mul`, as `core_kept_product`) is compared once the split's shared borrow of the table is released
  (`QIds::check_products`; `rest` runs under that borrow and `mul` interns). Side effect to watch in the bar: the
  comparison's `mul` can intern derived rows that weren't interned before.

### Plant table
| plant | id | fires | caught by |
|---|---|---|---|
| `rows-product-verdict-flip` | 600 | core: once per checked product | `scaffold:core:kept_product:mismatch` equals the fired count; answers unchanged |
| `fm-atoms-drop-last` | 601 | yes | atoms comparison |
| `fm-atoms-no-dedupe` | 602 | yes | atoms comparison |
| `fm-args-reverse` | 603 | yes | tree comparison |
| `fm-implies-swap` | 604 | yes | tree comparison |
| `fm-ite-swap` | 605 | yes | tree comparison |
| `fm-not-drop` | 606 | yes | tree comparison |

None is void in test_formula_nodes.py. All of 601-606 are **void on the workloads**: the conversion isn't reached by any
query until it is wired. Plant 600 has run on core only.

### `scaffold:core:kept_product:mismatch`
core: 0, with the scaffold firing (test_formula_nodes.py, one pass). dev, f6, wiring and loop (where the scaffold also
fires: 33, 82, 10, 2 in ce706d3) and `:unchecked` per workload: **not run**.

### Not run
The suite (so no three numbers and no handler multiset), fresh dev and fuzz answers and state, kept shares per reason,
the after-probe, `rk:intern:engine`/`rk:intern:input` (RelKeys isn't on rust-slice at 59e9d15), the mismatch counter off
core, and everything on the "before any backend PR" list.

## sa-port-234, 10 Nov: the node cache and the `atoms_of` callbacks (B1-B7). Unbarred, unlanded.
Rebased onto rust-slice 3203cb4 ((iii) landed, tested ba1ca22). rust-slice has since moved to 0192b35 (docs only): **not
rebased onto it yet.** Commits: 7874c7d (cache, `to_f` on the node), a9b4073 (B1-B7).

### What changed
- `SessionCore.fnodes` (session.rs:643): each Formula object's node, by identity, the node holding the object. `convert`
  (:1114) walks the node (`to_f` :1075), calling `pred_id`, `nid_in_formula`, `custom_in_formula` per atom occurrence in the
  walk's order. A refused conversion (depth, class, read) returns None and Python compiles the formula.
- B1-B5 (session_glue.rs:87, :185; compile_loop.rs:327, :376; query.rs:271, :287): `SessionCore::atoms_of` (:1062), the
  cached node's atoms.
- B6, B7 (scope_core.rs:259, :291; budget.rs:61, :373, :465-466): **no session exists there** (`theory_scope` runs before
  the session is made, the cones are engine memos), which the inventory's "wait: cache" missed. They call
  `formula::atoms_nosession` (formula.rs:420): one walk of the object in Rust, node dropped, counted `fm:nosession`. So no
  Python `atoms_of` runs, but a formula the session also converts is **read more than once**, which the formula ruling's
  "no Rust code reads a Python Formula object back" doesn't allow yet. Open, owner this step: the entry converts and hands
  nodes down (or a per-query cache; the query's `_Query` is Python, term_live.py:72, so reaching it costs a Python call).
- Counters 640-644: `fm:cache_hit`, `fm:to_f`, `fm:atoms_py`, `fm:atoms_node`, `fm:nosession`. All `fm:*` are in the session
  report's `counts`. Plants 601-606 take the bar's channel (`SLICE_SESSION_PLANT`, counted in `rel:plant_fired`).
- `scope:cb_atoms_of` reads 0 by construction (the tick is removed); test_scope_core.py:151-152 now says so.

### Behaviour differences to name (none seen on a workload)
- A Formula class outside the nine, or a wrong arity: before, Rust compiled it as `Bad` (TypeError from compile.rs) or
  panicked on the arity; now Python compiles it (`refuse:convert`, `fm:refuse:class`).
- A read error or depth refusal part-way: before, `to_f` had already taken node ids for the atoms before it; now nothing
  is taken before Python's compiler runs.
- A Formula whose `args` are reassigned after its first use in a session keeps its first reading under Rust (identity
  cache; by the formula ruling's "converted once"). For the backend PR list as a contract difference.

### Checked (short checks, **not the bar**)
- test_formula_nodes.py 15 passed (python mode). Slice tests under Rust, all passed: test_scope_core 7, test_query_core 14,
  test_compile_loop_core 13, test_cones_core 10, test_context_core 12 (3 skipped), test_entry_core 23,
  test_relations_core 88, test_engmemo_core 11, test_procmemo_core 6, test_rs_core 15, test_rd_core 17, test_rl_core 6,
  test_glue_plain 4, test_session_limits 242, test_relevance_core 34, test_discovery_core 10.
- One Python and one Rust run, answers and state: dev MATCH (1,985), scope MATCH (169), budget MATCH (28), zero MATCH (854)
  (`~/sa-rust-ids-work/sa-port-234/live-b/summary.txt`, on the build before the counter routing; no engine change after).
- dev, one pass, from a plant run's report: `fm:convert` 3,413, `fm:cache_hit` 2,203, `fm:nosession` 2,383, `fm:atoms_py` 0;
  `refuse:object` 17, `refuse:depth` 0, `refuse:convert` 0.

### Plants on the workloads (dev so far)
| plant | id | dev fired | dev verdict |
|---|---|---|---|
| `fm-atoms-drop-last` | 601 | 3,413 | caught: DIFFER (49 answers, 617 end states) |
| `fm-atoms-no-dedupe` | 602 | 4,089 | **not caught**: MATCH. Caught only in test_formula_nodes.py |
| `fm-args-reverse`, `fm-implies-swap`, `fm-ite-swap`, `fm-not-drop` | 603-606 | running when handed off | read `~/sa-rust-ids-work/sa-port-234/plants/*.cmp` |
Plant 600 is unchanged from sa-port-231 (core only).

### Not run
The suite (no three numbers, no handler multiset), fuzz and the other nine workloads' answers and state, seed 1, kept
shares, fallback rows (dispatch.rs:242, rows_tpl.rs:413, `ad:cbm_noid`), `rk:intern:engine`/`rk:intern:input`,
`scaffold:core:kept_product:mismatch` off core, the digest extension, and the "before any backend PR" list. The
**after-probe was started** (detached, all 13 workloads plus dev and fuzz at seed 1) and not read:
`~/sa-rust-ids-work/sa-port-234/probe/probe-after/` (`end.txt` when done; `summ.py` beside it). Until it is read the
"after" column of the table above is unfilled.

### Inventory changes
- B1-B5: done (unbarred). B6, B7: Python callback gone, repeat conversion open (above).
- C1, C2: wait changed to **p3**. The by-name calls go through session_live.py's `_compile_formula`/`_formula_literal`
  (:1264-1277), whose `_rust_call` decides the `emit` Rust calls back; part 3's branch has the helper for calling past a
  session_live frame (session.rs `named`, ebdf52e).
- New rows, owner this step: the `ad:cbm_noid` fix (per-query `==` class keys), the `_common._CACHE` fix, and (planner
  ~15:23 10 Nov) the term_live wrappers falling back in tests/test_transfer.py::test_inequalities_restate_an_equality (42
  calls into relations.py; cause **not read**; port-state-relations.md:627-629 on 0192b35). None started.

## sa-port-243, 10 Nov: the after-probe and the plants on dev and zero, read. Unbarred, unlanded.
Rebased onto rust-slice 0192b35 (docs only; no rerun). Read from `~/sa-rust-ids-work/sa-port-234/probe/probe-after/` (15 runs,
all exit 0, empty stderr; the build is a9b4073's) and `plants/`.

### Module-wide probe, after (a9b4073, pass 1, every function in the file)
Same tool and columns as the before table. Python calls on converted queries, kept in brackets; the Rust counters are
totals over the run's two passes. `scope:cb_atoms_of` is 0 by construction (the tick is removed), so it has no column.

| workload | sat/formula.py | of which `atoms_of` (all from engine.py) | knowledge/compile.py | `rv:cb_formula` | `refuse:object` | `em:key_eq` | `pm:key_eq` | `fm:convert` | `fm:cache_hit` | `fm:nosession` | `rk:intern:engine` | `rk:intern:input` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev | 5,810 (kept 24) | 1,616 | 42 | 244 | 34 | 5,860 | 14,356 | 7,856 | 4,294 | 5,796 | 8,134 | 1,022 |
| fuzz | 68,474 | 5,899 | 205 | 630 | 60 | 30,701 | 242,675 | 46,196 | 30,764 | 35,030 | 186,572 | 19,078 |
| f6 | 38 (kept 14) | 12 | 0 | 16 | 0 | 222 | 39,054 | 2,296 | 1,190 | 268 | 0 | 0 |
| value | 1,274 | 1,274 | 0 | 8 | 0 | 6,114 | 19,466 | 4,622 | 2,458 | 3,590 | 2,366 | 788 |
| rootof | 737 | 737 | 0 | 4 | 0 | 2,944 | 15,372 | 2,948 | 1,472 | 2,212 | 0 | 0 |
| core | 809 | 607 | 0 | 36 | 0 | 3,474 | 20,272 | 4,132 | 1,928 | 2,182 | 0 | 0 |
| opaque | 61 | 61 | 0 | 4 | 0 | 672 | 4,320 | 248 | 124 | 186 | 0 | 0 |
| scope | 2,306 | 332 | 7 | 0 | 2 | 1,252 | 3,932 | 3,526 | 1,404 | 2,340 | 3,906 | 606 |
| loop | 6,247 | 488 | 0 | 0 | 0 | 1,654 | 7,504 | 6,158 | 4,686 | 1,818 | 0 | 0 |
| zero | 8,045 | 1,423 | 288 | 74 | 188 | 5,646 | 26,594 | 8,994 | 6,098 | 6,536 | 36,676 | 2,054 |
| wiring | 22,299 | 9,819 | 0 | 406 | 0 | 37,874 | 192,292 | 37,768 | 21,662 | 25,604 | 0 | 0 |
| cert | 1,954 | 122 | 0 | 0 | 0 | 236 | 3,178 | 982 | 728 | 738 | 1,804 | 384 |
| budget | 12,744 | 49 | 0 | 0 | 0 | 146 | 8,154 | 1,490 | 1,072 | 450 | 0 | 0 |
| dev-seed1 | 5,810 (kept 24) | 1,616 | 42 | 244 | 34 | 5,888 | 14,356 | 7,856 | 4,294 | 5,796 | 8,134 | 1,022 |
| fuzz-seed1 | 68,474 | 5,899 | 205 | 630 | 60 | 30,608 | 242,675 | 46,196 | 30,764 | 35,030 | 186,572 | 19,078 |

- sat/formula.py, before to after: dev 10,977 to 5,810; fuzz 102,045 to 68,474; f6 1,112 to 38; value 4,298 to 1,274;
  rootof 2,579 to 737; core 3,175 to 809; opaque 216 to 61; scope 4,264 to 2,306; loop 9,570 to 6,247; zero 14,604 to
  8,045; wiring 46,187 to 22,299; cert 2,688 to 1,954; budget 13,505 to 12,744. knowledge/compile.py, `rv:cb_formula`,
  `refuse:object`, `em:key_eq` and `pm:key_eq` are unchanged on every workload (groups C and E aren't started).
- **Not zero, so the module does not count.** What is left in sat/formula.py: `atoms_of`, every call from
  satassume/engine.py (the column above; the entry's own reading of the input, item "the entry converts once");
  `Formula.__hash__` from session_live.py (`f`, `_context_session`, `verdict`) and from formula.py itself (group E, and
  session_live rows that wait for state part 3); `Formula.__init__`/`Not.__init__` (group D).
- `fm:nosession` is nonzero on all 13 workloads (B6/B7 convert on the spot), and `fm:convert` exceeds one per input
  formula by at least that much. Owner: this step, the entry-converts-once item.
- Seed 1 on dev and fuzz gives the same numbers except `em:key_eq` (5,888 and 30,608).
- `rk:intern:*` read 0 on f6, rootof, core, opaque, loop, wiring and budget in this probe's reports; whether RelKeys is
  unreached there or the report dropped the keys is **not checked**.

### Plants 601-606 on dev and zero (one Rust run each against one Python run)
| plant | id | dev fired | dev verdict | zero fired | zero verdict |
|---|---|---|---|---|---|
| `fm-atoms-drop-last` | 601 | 3,413 | caught: 49 answers, 617 end states | 3,590 | caught: 163 answers, 614 end states |
| `fm-atoms-no-dedupe` | 602 | 4,089 | **not caught** (MATCH) | 9,568 | **not caught** (MATCH) |
| `fm-args-reverse` | 603 | 1,818 | caught: 0 answers, 412 end states, 113 LRA | 3,812 | caught: 0 answers, 561 end states, 99 LRA |
| `fm-implies-swap` | 604 | 0 | **void** | 0 | **void** |
| `fm-ite-swap` | 605 | 0 | **void** | 0 | **void** |
| `fm-not-drop` | 606 | 263 | caught: 157 answers | 908 | caught: 123 answers |

604 and 605 are void on both workloads: no `Implies` or `Ite` node reaches the conversion there. They are caught only in
test_formula_nodes.py; they need a workload with such formulas, or a footnote. 602 fires and is not caught on either;
its classification is still owed. The other 11 workloads were not run with plants.

## sa-port-246, 10 Nov: gate item 1, the `_common._CACHE` fix (c170496). Unbarred, unlanded.
On 9a7d47f (rust-slice 0192b35). Ruling: the planner's `_CACHE` fix ruling of 10 Nov ~12:53. One commit, c170496.

### What changed
- **common.rs `atom_pattern` (:636).** knowledge_live's symbol and constant templates (`rust_compiled`,
  knowledge_live.py:288) now build Python's key in Rust (`('symbol', frozenset(assumptions0.items()))`,
  `('const', const_key(value))`), read `_common._CACHE` and fill it on a miss, as `units` does (`room`, MAX_CACHE). For an
  input term the key comes from the term table's read, so no Python runs for it; for a node read here the reads are the
  ones Python's template makes (`assumptions0`; `const_value` only on a miss, where before it ran on every call).
- **A second cause, found by the new test: dispatch.rs `clear_memos` (:316).** `memos.PROCESS.clear()`
  (`reset_module_state`) emptied `_CACHE` and Python's `registry._clauses_cache`, but Rust's memo of compiled nodes
  (`Dispatch.memo`, which stands in for `_clauses_cache`) was registered nowhere and survived. After a clear Rust served
  nodes from it and never refilled `_CACHE`: 0 keys where Python held 3 on the test's queries. The memo and the class
  cache are now emptied with Python's two (knowledge_live.py:246, a dict subclass on `registry._clauses_cache` whose
  `clear` also calls `clear_memos`). Workloads don't clear mid-run, so 239's twin and transfer numbers did not show it;
  the suite clears between tests.
- knowledge_live's shadow compares this call's uncached build (`_fresh`, :127) with what Python's key holds. Comparing
  the cached pattern would compare it with itself, since Python's template now answers from the same entry.
- The two plants in `rust_compiled` (`knowledge-no-query-drop`, `knowledge-value-multigamma-drop`) cut a copy, so they
  don't shorten the cached pattern for later queries.

### The key determines the value
1. By reading. A symbol's pattern is built from its `assumptions0` items (filtered by VOCAB, not None, not
   `commutative`), closed under the rule base and sorted, and the key is the set of exactly those items. A constant's is
   built from `const_value(value, pred)` over `_CONST_BASIS`, and the key is `(type(value), value)`. What the key leaves
   out is the order of `assumptions0`, which matters only if the closure is contradictory (`units` then keeps the
   generator's order); SymPy refuses such a Symbol.
2. By running: cache_det.py. On every `_CACHE` hit the pattern is built again from the hitting call's own arguments,
   outside the cache, and compared field by field. It covers `_common.facts`/`units` under their Python names on both
   backends, and the atom templates on Rust (`RECHECK`, knowledge_live.py:124). It does not cover templates Rust calls
   natively (rows_tpl.rs, outer_tpl.rs, fn_tpl.rs); for those the evidence is the digest's `_CACHE` row against Python's,
   with values (below).
3. Plant 664 `atom-symbol-key-names` (a symbol's key without its values: `Symbol(prime=True)` then
   `Symbol(composite=True)` share an entry): caught three ways by test_cache_fix.py:139 (the probe's mismatch, the table
   against Python's, and the answer `ask(Q.prime(b))` True where Python says False).
   Plant 665 `dispatch-keeps-memo`: caught by :171 (`_CACHE` short of Python's keys after a clear).

### Checked so far (short checks, **not the bar**)
- test_cache_fix.py 7 passed. Also passed on the final build: test_knowledge_common 26, test_knowledge_value_units 10,
  test_knowledge_core 7, test_knowledge_lazy 7, test_formula_nodes 15, test_knowledge_f6_fallback 6,
  test_knowledge_fn_direct 14; on the build before `clear_memos`: test_knowledge_rows 51, test_knowledge_wire 6,
  test_cbm_noid 2 (6 skipped outside the backend plugin).
- Digest, in a scratch tree (c170496's first build + e82147a cherry-picked + `_CACHE`'s row extended to values + **no
  known rows**), Python against Rust, `--check entry`: twin MATCH (`_SPLIT` 2/2, `_CACHE` 2/2; before 2/4, 2/0),
  transfer:7:60 MATCH (174/174, 277/277, 332/332; `_CACHE` 19/19, 23/23, 24/24; before 174/182 ..., 19/14 ...), dev MATCH
  (first point 35/35, 12/12), cls MATCH (25/25, 11/11). These four ran before `clear_memos` was added.
- **Running detached, not read here**: `~/sa-rust-ids-work/sa-port-246/j1` (job1.sh, end marker `j1/end.txt`): the same
  digest on 20 workloads at c170496 (`j1/dg/verdicts.txt`; ground and port MATCH when this was written), cache_det on
  both backends on the 20 (`j1/det/*.json`), pycalls for knowledge_live.py before (17241af) and after on six workloads
  (`j1/pc`), then the suite on Python and on Rust with `-p cache_det` (`j1/suite-python`, `j1/suite-rust`).

### Not done in item 1
- The digest change itself: e82147a arrives with the rebase onto state part 3. Then apply
  `~/sa-rust-ids-work/sa-port-246/cache-values.diff` (moved_digest.py: `_CACHE`'s row by keys and values), regenerate
  known_moved.json with known_moved.py from clean runs (expected: no rows left), and switch `_SPLIT` to exact in
  livecmp.py. Plants 450-453 (test_split_order.py) come with e82147a: 451 `atoms-uncached` makes Python do what Rust
  did before the fix, so its test's expected Rust row counts change (twin 4 to 2).
- Python calls for knowledge_live.py module-wide, before and after: in the job (`j1/pc`), not read.
- Layer (b) of 239's report (Rust calling an atom template again where Python's `_clauses_cache` serves): not looked
  for. With the fix a second call is a `_CACHE` hit and adds no row; `common:atom:hit` counts them.
- test_knowledge_value_units.py::test_with_no_query_rust_answers now compares a pattern with itself (Python's template
  hits the entry Rust filled). test_cache_fix.py:109 is the test that fills in both orders.

## sa-port-248, 10 Nov: gate item 1 read; the detached job was not as expected; a third cause fixed. Unbarred, unlanded.
On 32eb7e1 (rust-slice 0192b35). The job: `~/sa-rust-ids-work/sa-port-246/j1` (ended 20:18Z), scratch tree c170496 +
e82147a + `_CACHE` values in its row + no known rows.

### The job, read
| part | expected | got |
| --- | --- | --- |
| digest, 20 workloads (`j1/dg/verdicts.txt`) | MATCH on all, no known rows | **16 MATCH, 4 DIFFER: f6, wiring, lra, scope** |
| cache_det, 20 workloads, both backends (`j1/det`) | 0 mismatches | 0 mismatches on both. Hits Python / Rust: budget 477/449, cert 47/25, cls 26/1, core 1016/33, dev 211/20, f6 615/45, fuzz 241/1, ground 13/1, loop 31/3, lra 10859/4683, opaque 60/9, port 10/2, rootof 367/0, scope 25/2, transfer2:3:40 156/3, transfer:7:60 170/3, twin 0/2, value 554/214, wiring 59/40, zero 32/3. Rust's are fewer because the probe does not cover the templates Rust calls natively; a 0 proves nothing (rootof on Rust, twin on Python). Answers: 19 MATCH, lra DIFFER by `stats_diff` only (below) |
| pycalls for knowledge_live.py, before 17241af / after (`j1/pc`, Rust) | `rust_compiled` equal, `_wrap` and `_derived_facts` 0 after | as expected. Module total before -> after: core 94 -> 88, dev 184 -> 160, fuzz 53 -> 46, transfer:7:60 76 -> 65, value 1818 -> 952, wiring 164 -> 125. `_wrap` 7, 25, 8, 10, 397, 40 -> 0; `_derived_facts` 1 (transfer), 234 (value) -> 0; `rust_compiled` 401 -> 401 (value); `rust_value_units` 250 -> 250; `rust_units` 151 -> 151. The one new call is `_WithRusts` (the class body, once per process). No per-query Python added |
| suite with `-p cache_det` (`j1/suite-python`, `j1/suite-rust`) | Rust's failed ids = 244's 127 | Rust 129 failed + 5 errors, Python 8 failed. **The 127 are the same ids** (0 differences against `sa-port-244/q1/suite-rust`). The rest are test_cache_fix.py (7) and test_cbm_noid.py (6 on Python) run under the suite's plugin together with the probe plugin, where they are not meant to run: an invocation artifact, not failures of the fix. Both pass plain (9 passed with the new test file below). cache_det over the suite: 0 mismatches on both backends (Python 85 key families hit, Rust 84) |

### f6, wiring, lra: `_CACHE` short on Rust. Third cause: the discarded run. Fixed
`_CACHE` rows, Python / Rust: f6 93/90 from engine point 40, then 2 short to the end (208/206 keys), and `_SPLIT`
716/720 then 16 over; wiring 61/57 from point 170 (99/95); lra 167/164 at point 0 (2130/2037, 93 keys). None is an
atom key: `('mul', ...)`, `('pow', ...)`, `('cosh', ...)`, `('add_half', ...)`, one `('const', GoldenRatio)`.
- First query: f6 1008, `Q.real(cosh(y + 1*I*pi))`, alone: Python 6 keys, Rust 1. Rust builds the five patterns
  (`common:facts` 5), is then refused (`lra: a callback on a derived term`), and term_live's rollback (`_Mark`, term_live.py:133)
  cuts `_CACHE` back to the mark. Rust's memo of compiled nodes (`Dispatch.memo`) is not rolled back, so the second run is
  served the nodes and never asks for their patterns: the keys stay missing. Only the symbol's units are asked again
  (a new pattern, and new `_SPLIT` rows beside the discarded run's: f6's 4 and 16 extra).
- **Fix (term_live.py `_Mark.__init__`): the pattern cache is not rolled back.** The key determines the value (above), so
  the entry a discarded run left is the one the next run builds; Rust's node memo and the native `_SPLIT` already keep
  what the discarded run wrote and hold those patterns. The other way (roll back `Dispatch.memo` too) would rebuild every
  pattern in the second run and leave the discarded run's rows in the native `_SPLIT`, which is not rolled back either:
  more `_SPLIT` copies, not fewer. **This is a choice the planner may overrule.**
- Plant 666 `mark-cuts-patterns` (term_live `PLANT`): rolls `_CACHE` back as before. Caught by
  test_cache_rollback.py (2 tests, each run its own process through cache_rollback.py: f6 1008 and wiring 4264; with the
  fix 9 keys = Python's 9 in order and `_SPLIT` 16 = 16; with the plant 4 keys).
- After the fix, per query (`_CACHE` keys added by each query, Python against Rust, `--check plain`): f6 0 of 2900 differ,
  wiring 0 of 6512, lra 0 of 1416. Digest: **f6 MATCH, wiring MATCH** (`~/sa-rust-ids-work/sa-port-248/dg1`).
- **Not checked: term_discard.py** (`fresh.py --discard`) compares all of Python's state after the rollback with a copy
  taken at the start; it will now list `_CACHE` as left. It needs the same exemption, or the other fix.

### scope and lra: differences that are on base 0192b35
- **scope**: `engine:splits` differs (3 rows each, other hashes), `moved_diff` 8. The same row with the same hashes on
  0192b35 + e82147a (`sa-port-248/dgbase`): the digest extension shows a base difference. State part 3's 4d14638 is
  their scope fix; expected to MATCH after the rebase. Not from this step.
- **lra** (a workload no bar has run): besides `_CACHE`, `end_diff` 2, `stream_diff` 2, `lra_diff` 2 (first at query
  204), `stats_diff` 1427 (first at query 73: Rust one `sessions`, `consistency_checks` and `set_checks` short; 25 such
  steps over the run, some with `cache_hits` short too). **Both reproduce on the base tree 0192b35**: `live.py lra
  --only 204,585,6 --check entry` gives end 2, stream 2, lra 2; `--only 73 --check plain` gives the stats row. Query 73
  (`Q.eq(u, -4/3*sqrt(3)*0*u*n/pi)` given `Q.nonnegative(exp(2))`) is a refused query (`scaffold: rebuilt form differs
  from Rust`): after the rollback the second run does one session and no consistency check where Python does one. My
  reading, not shown: something the discarded run wrote outside Python's tables serves the second run. Answers are equal
  on all 1500. **No owner yet.**

### Running detached
`~/sa-rust-ids-work/sa-port-248/j2` (job2.sh, started 20:42Z, end marker `j2/end.txt`): the digest on the 20 workloads in
the scratch tree `sa-port-248/dg` (32eb7e1 + e82147a + cache-values.diff + no known rows + this fix), then plant 666 on
f6 against Python (`j2/p666/verdict.txt`, expected DIFFER). Expected: 18 MATCH; scope and lra DIFFER as on base, with
`_CACHE` equal at every point.

### Not run
Items 2 to 5 of the gate; the bar; the two-order reproductions; h2.py; the clear() test; D and E.
