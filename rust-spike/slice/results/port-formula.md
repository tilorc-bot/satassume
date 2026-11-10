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
