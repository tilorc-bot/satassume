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
