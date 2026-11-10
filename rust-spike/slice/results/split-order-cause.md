# `_SPLIT` rows and the order of `_SPLIT`, `_WANT`, `_CLOSED`, `_SYMPY_ATOMS`: cause read (issue 323)

sa-port-239, 10 Nov, branch digest/split-order on c931c16 (238's draft digest on ba1ca22). Read-only for engine, relkeys,
session and crate code: nothing there changed. Runs on orion, `.so` sha256 bfc06f0cd68a (238's build of this tree), output
in ~/sa-rust-ids-work/sa-port-239/. Workloads: twin and transfer:7:60, `--check entry`, PYTHONHASHSEED=0.

## What could change a verdict

1. **The direction in the brief is reversed.** Rust has more `_SPLIT` rows than Python, not fewer: twin Python 2, Rust 4;
   transfer:7:60 Python 174, Rust 182 (238's own .cmp files list Python first). Nothing is dropped on Rust.
2. **No answer changes through these four containers.** Every Rust-only row is a second copy, equal by content to a row
   Python has. No reader iterates any of the four.
3. **The cause sits outside the four containers and is a state difference in landed code**: Rust's atom templates do not
   use the pattern cache `_common._CACHE`, so `_CACHE` lacks keys on Rust (twin 0 against 2; transfer 14 against 19, 16
   against 23, 17 against 24). `_CACHE` is not in any digest (moved_digest.py:173 skips memos the port did not move). One
   route from this to an answer exists on paper and was not run: see "Not established".

## 1. What differs in `_SPLIT`

Rows read by split_probe.py at each engine point, each as (clause list by content, want, len(now), len(later)):

| workload, point | Python rows | Rust rows | distinct rows, both | Python-only | Rust-only copies |
|---|---|---|---|---|---|
| twin, after query 2 | 2 | 4 | 2, same set | 0 | 2 |
| transfer:7:60, query 24 | 174 | 182 | 153, same set | 0 | 8 |
| transfer:7:60, query 49 | 277 | 289 | 223, same set | 0 | 12 |
| transfer:7:60, query 59 | 332 | 347 | 261, same set | 0 | 15 |

Cause, two layers, both needed:

- **Rust's atom templates build a pattern per call.** Python's `symbol_units` and `value_units` (atoms.py:37, :64) go
  through `units(key, ...)`, which keeps one `Pattern` per key in `_common._CACHE` (_common.py:345). Rust's versions
  (knowledge_live.py `rust_compiled`, :258-295, pattern made by `_wrap` at :281) never read or write `_CACHE`. A new
  pattern has a new `clauses` list, and `_SPLIT` is keyed on `id(clauses)` (engine.py:2340), so it gets a new row. Shown
  by a trace on twin (spy2.py): Python makes 2 patterns over both queries, from _common.py:386; Rust makes 4, all from
  knowledge_live.py:281, and `_CACHE` stays empty. On transfer every Rust-only row's list belongs to a pattern outside
  `_CACHE` (22, 42, 47 such rows at the three points; Python has none).
- **Rust calls the atom template again where Python does not.** On twin Python calls each atom template once across both
  queries (the per-node result is kept in `registry._clauses_cache`, registry.py:238, :281); Rust calls it in each query.
  Which Rust-side store differs was not read (dispatch.rs:285-297 holds an `epoch`; start there).

Confirmation: plant 451 makes Python do both things (pattern rebuilt on every `atoms.units` call, per-node results
emptied before each ask). Python's `_SPLIT` on twin then has Rust's 4 rows and the comparison finds 0 Rust-only copies.

Effects of the same cause, none on answers: `_SPLIT` on Rust grows by one row per (atom template call, want), so it
reaches its 100,000 bound sooner and empties at a different time; Python's `_CACHE` gains a key per distinct constant, so
it reaches MAX_CACHE (4,096) sooner. Both only cause recomputation.

## 2. Readers, and whether order matters

Whole-tree search (`rg` over the clone, results and docs left out). No reader iterates any of the four.

| container | reader | use | order-sensitive |
|---|---|---|---|
| `_WANT` | engine.py:2368, :2370 | `get(key)`, `[key] =` | no |
| `_WANT` | procmemo.rs:191, :195 (`want_get_or_put`) | find, set | no |
| `_SPLIT` | engine.py:2341, :2356-2358 | `get(key)`, `len`, `clear`, `[key] =` | no |
| `_SPLIT` | procmemo.rs:200 (`split_get`), :229 (`split_put`) | find, len, clear, set | no |
| `_CLOSED` | relations.py:403, :417-419 | `[node]`, `len`, `clear`, `[node] =` | no |
| `_CLOSED` | procmemo.rs:279, :289 | find, len, clear, set | no |
| `_SYMPY_ATOMS` | relations.py:568, :572-574 | `get(atom)`, `len`, `.size`, `clear`, `[atom] =` | no |
| `_SYMPY_ATOMS` | procmemo.rs:299, :315 | find, len, clear, set | no |
| all four | memos.py:134 `items`, :150 `sizes`, :153 `clear` | yields the container, `len`, `clear` | no |
| all four | memos.rs NativeTable :105-141 (`__len__`, `get`, `items`, `keys`, `__iter__`) | the registry view | only its caller |
| plants only | procmemo.rs:180 (PM_WANT_KEY_LEN), :306 (PM_ATOMS_KEY_EXPR) | iterate `items` | first match wins; armed only |

Callers of the views' `items`/`keys`/`__iter__`: only the slice harness and tests (moved_digest.py:171, memo_check.py,
term_live.py:142 and term_discard.py:85, which note or copy the containers, test_procmemo_core.py:43 `len`,
test_relations_core.py:1058-1060 keyed reads). Nothing in satassume/ calls them.

**Why the order differs:** Python's dicts list rows as inserted. Rust's maps are `std::collections::HashMap` and the
views list them in the map's own order (procmemo.rs:96-98 for `_WANT`, `_CLOSED`, `_SYMPY_ATOMS`; :152-159 for
`_SPLIT`). That order is not Python's and is not stable: two Rust runs of twin under the same hash seed listed `_CLOSED`
and `_SYMPY_ATOMS` in different orders (same rows).

**Proposed, for the planner:** compare `_WANT`, `_CLOSED`, `_SYMPY_ATOMS` as multisets, and `_SPLIT` as in
split_order.py (same distinct rows, no Python-only row, each Rust-only copy accounted for by a pattern outside
`_CACHE`). The state rule's three conditions: (1) the search above; (2) `split_order.guard`, an AST check that the four
names are used in satassume/ only for keyed reads and writes, `len`, `clear` and `.size` (test_split_order.py
`test_guard`); (3) this report names the exception. The guard covers Python source only; the Rust sites are the table's.

## 3. Plants (test-only, Python harness; no crate change; no counters taken)

| plant | what it does | shown on twin (test_split_order.py, 2 passed) |
|---|---|---|
| 450 `split-row-drop` | Rust's read leaves out every `_SPLIT` row of one (clauses, want) | fired; comparison DIFFER, `_SPLIT` |
| 451 `atoms-uncached` | Python's atom templates rebuild their pattern per call and per ask, as Rust's do | fired; Python has Rust's 4 rows, 0 Rust-only copies |
| 452 `order-reader` | a source text with `for k in _CLOSED` | the guard reports it; satassume/ is clean |
| 453 `closed-row-drop` | Rust's read leaves out one `_CLOSED` row | fired; comparison DIFFER, `_CLOSED`, though order is ignored |

450 and 453 change what the probe reads, not the engine: they show the comparison catches a lost row although counts and
order already differ on the clean build. They do not show an engine bug being caught. Clean runs: twin MATCH with 2
copies; transfer:7:60 MATCH at all three points with 8, 12, 15.

Files: split_probe.py (rows by content, plants), split_order.py (comparison, guard), test_split_order.py, and 9 lines in
moved_digest.py (SPLIT_PROBE and SPLIT_PLANT hooks, off by default). `SPLIT_PROBE=PATH` on a live.py run writes the rows;
`python split_order.py cmp PY.probe RUST.probe` compares them.

## Known-difference rows for sa-port-230's verdict

- `_SPLIT` twin: Python 2, Rust 4. transfer:7:60: Python 174, 277, 332 against Rust 182, 289, 347 (queries 24, 49, 59).
  Cause: this report, section 1. Rust-only copies 2; 8, 12, 15.
- Order of `_SPLIT`, `_WANT`, `_CLOSED`, `_SYMPY_ATOMS`: differs on both workloads, and between two Rust runs. Rows equal
  as multisets (`_SPLIT` as above).
- New row, not in ruling (A): `_common._CACHE` holds fewer keys on Rust (twin 0 against 2; transfer 14/19, 16/23, 17/24).
  The missing keys are all `('symbol', ...)` and `('const', ...)`.

## Not established

- Which Rust store makes the atom template run again per query (section 1, second layer).
- Whether the missing `_CACHE` use can move an answer. On paper: a registered template that calls `units` with a key equal
  to an atoms key but other facts gets, on Python, whichever pattern was cached first, for both; on Rust the atoms side
  never shares. That breaks the key contract (_common.py:311-318), and no run was made.
- dev, fuzz, the suite, any bar, pareto0/pareto1: not run. Quiet handler firings were not counted in these runs.
- `_NEIGH` and the other moved containers: not looked at.

## Fix, if the planner wants one (not made here)

- `rust_compiled` (knowledge_live.py:258-295) reads and fills `_common._CACHE` under Python's keys, as common.rs's `units`
  does (common.rs:404-444). That removes the Rust-only `_SPLIT` copies and the `_CACHE` difference. Owner: the formula
  step lists knowledge_live.py among its identity sites, so sa-port-234 or whoever the planner names.
- Listing the views in insertion order (procmemo.rs:96, :152) is needed only if order is to be compared; no reader needs it.
