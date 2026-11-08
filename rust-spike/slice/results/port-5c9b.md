# Step 5c9b: the process memos Rust works on, Rust-native: `_WANT`, `_SPLIT`, `_NEIGH` (with `neighbourhood`), `_CLOSED`, `_SYMPY_ATOMS` (issue 323)

## What moved
Inventory part 5's 5c9b row (sa-port-147, INVENTORY-state.md :278-280): containers `_WANT`, `_SPLIT`, `_NEIGH` (with
`neighbourhood`), relations `_CLOSED`, `_SYMPY_ATOMS`; row `neighbourhood`. Classified by tracing (`proc_memo_trace.py`,
sa-port-176, rows `~/sa-rust-ids-work/sa-port-176/trace/`), then:
- **Already Rust before this step, the memos still Python dicts:** `want_of`, `_split` (5c2), `closed_units`,
  `with_closed_units`, `sympy_atom` (5c5). On base Rust they made **0 Python calls** on dev, fuzz, loop, scope, zero and
  cert, but each read and wrote its Python dict through the C API. Rust's call counts equal Python's (dev `ses:want_of`
  5,257, `ses:split` 8,127, `rel:sympy_atom` 2,093, `rel:closed_units` 2,704; fuzz 51,089 / 79,164 / 66,365 / 16,727).
- **Moved to Rust-native state** (procmemo.rs): five thread-local maps with Python's dict lookup semantics (`PyKeyMap`: the
  key's hash, then identity or `==`), Python's bounds (`_SPLIT` 100,000, `_CLOSED` 4,096, `_SYMPY_ATOMS` 100,000; `_WANT`
  and `_NEIGH` none, as Python), `_SPLIT` keyed `(id(clauses), want)` with Python's `r[0] is clauses` check. The callers
  read them directly: compile_loop.rs `want_of`/`split`, relations_core.rs `sympy_atom`/`closed_units`.
- **`neighbourhood` ported** (`pm_neighbourhood`), over the Rust-native `_NEIGH`; its reads of `knowledge.rules`
  (`BASIS_OF`, `RULE_CLAUSES`) are a counted callback (`pm:cb_rules`). It runs 0 times per query on every workload, both
  backends: its only caller is tests/test_engine.py:195.
- **Python readers left:** none in engine code or wiring. The registry reads each through a read-only `NativeTable` view
  (memos.rs, `moved`) put where Python's container sat in `memos.PROCESS`, under Python's own name
  (session_live `_install_procmemos`), so `names`, `sizes`, `items`, `get`, `in` and `clear` read Rust's maps. The modules'
  own attributes stay Python's containers, for the pure-Python default and for Python's functions (a kept query).
  `_Mark` skips native views (term_live.py:145), so it no longer snapshots these five tables, as the inventory says.
- **Counters** (session.rs): `pm:neigh` 240, `pm:cb_rules` 241, `pm:full` 242, `pm:key_eq` 243, `pm:key_hash` 244 (236-239
  reserved). **Plants** (relations_core.rs): 180-187, `_MEMO_PLANTS` in session_live.py.
- **New test:** test_procmemo_core.py, Python against Rust in separate processes, for what no workload reaches: `_SPLIT`'s
  100,000 bound (100,001 fresh clause lists) and the registry's clear, and `neighbourhood` over every basis name and index.

## SHAs
BAR_SHAS

## The bar
BAR_ITEMS

## The switch digest (planner's state ruling, item 3)
`memo_check.py WL rust` on base Rust (e0ec542, a worktree with its own build) and on 5c9b Rust (5397118; 73c10d3 adds only
the test file), on orion. The digest covers everything Python can read from the registry: per memo of `memos.PROCESS` and of
the default engine's `Engine.memos`, (owner, name, key, len, stamp). On base the five tables are Python dicts in the registry;
on 5c9b they are the Rust maps' views under the same names, which the digest now counts (`moved`). **Answers and digest equal
on all six workloads, and equal to 5c9a's own digests** (port-5c9a.md):

| workload | queries | answers | digest | `_WANT` | `_SPLIT` | `_NEIGH` | `_CLOSED` | `_SYMPY_ATOMS` | views == maps | empty after clear | rerun of 200 the same |
|---|--:|---|---|--:|--:|--:|--:|--:|---|---|---|
| dev | 1,985 | c9cf2db177fb842d | fa58cc766d98d539 | 51 | 783 | 0 | 222 | 214 | yes | yes | yes |
| fuzz | 3,000 | 7b70c27d5415d320 | c322be409740fe5e | 25 | 1,733 | 0 | 190 | 2,908 | yes | yes | yes |
| loop | 420 | 157ced0aa6f9823f | c8fa633c2526d52e | 14 | 278 | 0 | 49 | 0 | yes | yes | yes |
| zero | 854 | 1c3f3090a3f172c6 | f409711365f18111 | 24 | 153 | 0 | 63 | 145 | yes | yes | yes |
| cert | 61 | c8e58c56d2ac2beb | 124879cd9aca401c | 7 | 65 | 0 | 32 | 88 | yes | yes | yes |
| scope | 169 | f2fd056234f29d49 | 170d770cf3b65109 | 20 | 112 | 0 | 28 | 82 | yes | yes | yes |

The five tables' rows are equal base against 5c9b on every workload. (memo_check's answer hash isn't live.py's.) Rows:
`~/sa-rust-ids-work/sa-port-177/mc/`.

**Known read-state difference, pre-existing, Python vs Rust: `_SPLIT`'s len** (dev 743 vs 783, fuzz 1,718 vs 1,733, cert 64
vs 65, loop 267 vs 278, scope 106 vs 112, zero 149 vs 153; the other four sizes are equal). That's why the switch digest
compares base Rust against 5c9b Rust, as 5c9a's did. **Cause** (sa-port-177, cert, `~/sa-rust-ids-work/sa-port-177/split/`):
`_SPLIT` is keyed by `id(clauses)` and keeps each list alive, so its len counts distinct clause-list objects. On Rust,
knowledge_live `rust_compiled` (the symbol and constant templates) wraps Rust's units in a fresh `Pattern` per call (`_wrap`),
outside `_common._CACHE`, while Python's `units` serves one cached `Pattern` per key. So the same pattern brings a new
clauses list to `_split` each time. On cert the one extra entry is the `('symbol', {commutative: True})` pattern (no rules,
clauses `[]`): Python holds 1 such entry for want {6}, from `_CACHE`; Rust holds 2, neither in `_CACHE`. Only the registry's
len reads this; answers aren't affected (the entries' contents are equal per list). It comes from the knowledge port's wiring
(knowledge_live.py), not from this step.

## Plants
Fired = `rel:plant_fired` (memo_check counts copy, `~/sa-rust-ids-work/sa-port-177/memo_check-counts.py`, kept out of the
landing source). Caught by: V = registry view != Rust maps, C = not empty after `clear()`, S = registry digest, A = answers
(memo_check, against the same workload's unplanted 5c9b run), T = test_procmemo_core.py, D = the bar's plants/extra comparison
(live.py, answers and state). Rows: `sa-port-177/pl/`.

PLANT_TABLE

## Reached (counters on the unplanted 5c9b run, memo_check: one full pass plus the 200-query rerun)
| workload | `ses:want_of` | `ses:split` | `rel:sympy_atom` | `rel:closed_units` | `pm:key_eq` | `pm:key_hash` | `pm:neigh` | `pm:cb_rules` | `pm:full` |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| dev | 5,394 | 8,411 | 2,093 | 2,793 | 7,306 | 4,886 | 0 | 0 | 0 |
| fuzz | 54,479 | 84,405 | 71,177 | 17,965 | 129,377 | 89,142 | 0 | 0 | 0 |
| loop | 5,420 | 7,929 | 0 | 3,168 | 5,394 | 3,168 | 0 | 0 | 0 |
| zero | 7,358 | 9,177 | 8,649 | 3,514 | 15,899 | 12,163 | 0 | 0 | 0 |
| cert | 1,462 | 2,674 | 1,906 | 510 | 3,178 | 2,416 | 0 | 0 | 0 |
| scope | 2,310 | 3,652 | 1,788 | 1,036 | 3,932 | 2,824 | 0 | 0 | 0 |

**Which moved items are reached, and by what:** `_WANT`, `_SPLIT` and `_CLOSED` by every workload; `_SYMPY_ATOMS` by every
workload but loop; `_SPLIT`'s bound, `neighbourhood` and `_NEIGH` by no workload, only by test_procmemo_core.py (and
`neighbourhood` by tests/test_engine.py:195, which runs Rust's under rust_plugin but can't see plants 183 or 184).
Counters shown to fire before quoting their zero: `pm:full` 1, `pm:neigh` 142 and `pm:cb_rules` 47 in test_procmemo_core.py's
Rust run; `pm:key_eq` and `pm:key_hash` fire on every workload (above). `memo:native_clear` 7 per memo_check run (5c9a's 2 plus
the five views).

`pm:key_eq` counts the key `==` a lookup runs when identity doesn't settle it; for `_CLOSED` and `_SYMPY_ATOMS` keys (SymPy
and `P` objects) that is a callback into Python, as is `pm:key_hash` (SymPy's or `P`'s `__hash__`). Python's dicts make the
same calls. They go when the keys are Rust's term ids (conversion pass).

## Kept reasons (planner ruling, 03:42 UTC 8 Nov)
KEPT_TABLE

## State: each container 5c9b's rows touch (planner's state ruling, 8 Nov)
| container | decision | readers past 5c9b | inventory row |
|---|---|---|---|
| engine `_WANT` | **moved to Rust-native** (procmemo.rs WANT); read-only view in `memos.PROCESS` under `satassume.engine._WANT` | registry view only (public API names/sizes/clear/items, tests test_memos.py, test_p4_review.py); module attribute Python's for the pure-Python default | INVENTORY-state.md :278-280; tsv "state: _WANT" |
| engine `_SPLIT` | **moved to Rust-native** (SPLIT, bound 100,000); view under `satassume.engine._SPLIT` | registry view; tests/test_p4_review.py:67-73 swaps the registry entry and restores it (works with the view) | :278-280; tsv "state: _SPLIT" |
| engine `_NEIGH` | **moved to Rust-native** (NEIGH) with `neighbourhood` (row moved); view under `satassume.engine._NEIGH` | registry view; tests/test_engine.py:195 calls `neighbourhood` (Rust's under rust_plugin) | :278-280; tsv "state: _NEIGH", "neighbourhood" |
| relations `_CLOSED` | **moved to Rust-native** (CLOSED, bound 4,096); view under `satassume.relations._CLOSED` in `_tables` | registry view; rust-spike/slice/test_relations_core.py:1054-1072 reads the module attribute (Python's, for Python's functions: unaffected) | :278-280; tsv "state: _CLOSED" |
| relations `_SYMPY_ATOMS` | **moved to Rust-native** (ATOMS, bound 100,000); view under `satassume.relations._SYMPY_ATOMS` | as `_CLOSED` | :278-280; tsv "state: _SYMPY_ATOMS" |

**Snapshot digest at the switch: equal on all six workloads** (above). `memo_snapshot` (memos.rs, test-only) reads all seven
native maps; the views equal it on every workload. No test reads these containers' internals in a way the views break, so
none goes on the needs-internals list.

## Registry tests on Rust
`tests/test_memos.py` (all 8, including its three registry ids) and `tests/test_p4_review.py` (both, including
`test_every_adopted_memo_name_resolves`): **10 passed, unedited**, under rust_plugin with handler_count
(`~/sa-rust-ids-work/sa-port-177/regtests`; `caught` empty on every row; tree is the clone's).

## Module count
**14 of 32, unchanged.** engine.py and relations.py don't count whole; this step moves state and one 0-per-query function.

## Owed-list additions
- `pm:key_eq`/`pm:key_hash` are callbacks into SymPy's and `P`'s `__eq__`/`__hash__` from the moved `_CLOSED`/`_SYMPY_ATOMS`
  lookups (fuzz 129,377 / 89,142 a pass, counting `_WANT`/`_SPLIT`'s cheap ones too). They go with the keys becoming Rust term
  ids (conversion pass).
- The `_SPLIT` len difference Python vs Rust (above) comes from knowledge_live's per-call `Pattern`; if the knowledge port makes
  `rust_compiled` go through `_common._CACHE`, the lens should become equal.

## Not run
NOT_RUN
