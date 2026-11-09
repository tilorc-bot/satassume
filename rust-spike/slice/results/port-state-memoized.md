# State step, part 1: lra_live `_memoized` on the Rust adapter (issue 323)

## What moved
The planner's go (forward-chain-3b, 9 Nov ~03:12): the state step's first part, lra_live `_memoized`, with the atom's term ids
and the query table on the Rust adapter (ruling of 8 Nov ~09:40, item 1: "At 165k crossings on fuzz it's the largest single
crossing left"). Work by sa-port-195 (WIP d1d9728, handoff 2d41d9d); fuzz quick runs read, plant table, group-D AFTER,
readers, bar and report by sa-port-197.
- **adapters.rs `LraAdapter.memoized`** (:105-170) answers `_memoized(key, read, arg)` from the adapter's own per-query slot,
  `LraQuery`: the query's table, ids and objects (from term_live's stack top, `top_query` :258) and the results, keyed by
  kind (interpret / order_sides / integer_form), the argument's identity and `GENERIC_CONSTANTS`. The slot is replaced when
  the stack top changes and dies with the adapter. `Reader` (:300-440) is lra_live's `interpret`/`order_sides`/`integer_form`
  line for line, calling the table's `lra_*` readers natively (term/py.rs `lra_interpret`/`lra_order_sides`/
  `lra_integer_form` made pub(crate), `n_input_rows`).
- **Callbacks into Python left, counted by reason:** `ad:cbm_off` (lra_live not installed: the pure-Python path),
  `ad:cbm_check` (live.py `--check`), `ad:cbm_patched` (a patched `_memoized` or reader is called, not bypassed),
  `ad:cbm_noquery` (no converted query on the stack: kept queries), `ad:cbm_noid` (a side with no input row: Python reads it).
  `ad:cb_memoized` is their sum. **Inside the slot, Python entered directly:** `relation` (`ad:lra_relation`), term_live's
  `term_id` for a term with no input row of its own class (`ad:lra_term_id_py`), `scaffold` for a derived term
  (`ad:lra_scaffold`), `_fault`.
- `sa_solver.ad_lra_live(cfg|None)`: registered by lra_live `_install`, cleared by its undo. **Test-only snapshot export:**
  `sa_solver.ad_lra_export(on)`, every slot entry as stored.
- **Counters** (session.rs): 327-336 (`ad:lra_native`, `ad:lra_hit`, `ad:lra_relation`, `ad:lra_term_id_py`,
  `ad:lra_scaffold`, `ad:cbm_noquery`, `ad:cbm_noid`, `ad:cbm_check`, `ad:cbm_patched`, `ad:cbm_off`); NAMES is 337.
  **Plants** (relations_core.rs): 251-255, `_LRA_SLOT_PLANTS` (session_live.py); the u8 plant space is now full.
- **New test:** test_lra_slot.py: cert_wl's queries plus integer-form and closed-constant cases, Python against Rust, each mode
  in its own process; every exported slot entry against lra_live's own function on the same query; the digest of the slot's
  results against lra_live's (the switch digest); the flag guard and the patch guard directly. 6 passed, 1 skipped
  (`ad-lra-slot-stale`, void by construction, named in `ELSEWHERE`).
- **pycalls.py** takes `PYCALLS_FILE` (any file in the clone) and files each call under the query it ran under, read from
  term_live's stack top as `top_query` reads it (`by_state`, `by_name_state`).
- Python's `_memoized` (lra_adapter.py :439) is unchanged: the pure-Python path and the callback above.

## SHAs
PENDING

## The bar
PENDING

## Plants
| plant | what it breaks | caught by |
|---|---|---|
| ad-lra-kind-key (251) | memo key without the kind | test_lra_slot.py; PENDING bar |
| ad-lra-slot-stale (252) | slot not replaced when the query changes | **void by construction** (below) |
| ad-lra-flag-key (253) | memo key without `GENERIC_CONSTANTS` | test_lra_slot.py (flag case); PENDING bar |
| ad-lra-patch-guard (254) | a patched `_memoized`/reader bypassed | test_lra_slot.py (patch case); PENDING bar |
| ad-lra-pair-swap (255) | coefficients of the first two pairs swapped | fuzz quick run DIFFER (answer_diff 217, lra_diff 2,445); test_lra_slot.py; PENDING bar |

**`ad-lra-slot-stale` is void by construction.** It fired 59,037 times on fuzz with answers and state MATCH
(`~/sa-rust-ids-work/sa-port-195/q2-stale`, d1d9728). Python's own memo (`_INTERPRETED`, lra_adapter.py :425-450) is shared
across queries and keyed by the atom and `GENERIC_CONSTANTS` only ("equal atoms linearise identically"), so the results are a
function of (atom, flag). A stale slot serves those same results, and a miss against the old table goes through `term_id` /
`ad:cbm_noid` to Python. The per-query slot is the state rule's scoping (cross-query memos under per-query ids), not an answer
path.

## Crossings and the group-D samples, before and after
`ad:cb_memoized` per pass: **dev 5,508 -> 33, fuzz 164,954 -> 0** (quick runs on orion, d1d9728; PENDING the bar's rows).
**5,508 to 33 is the first real drop in a crossing count in the state work** (planner, 9 Nov ~03:30).

Group-D C API samples on the LRA path, sa-port-146's method (sa-port-195's tools, `~/sa-rust-ids-work/sa-port-195/gd/`):
BEFORE rust-slice 9529850 (`run-9529850/SUMMARY.md`), AFTER f7ea3d3 (`run-f7ea3d3/SUMMARY.md`), both on pareto1 under a shared
lease with `--cpus 1`, dev x10 and fuzz x3. Sample totals differ between the runs (dev 10,364 / 23,460, fuzz 27,744 / 46,467:
the shared lease's load), so shares compare, not counts. **Counts and shares only, no timing.** Answer digests equal on every
row of both runs (dev 31cd0945c07f02a6, fuzz 173502b6ef285ad6).

| | dev before | dev after | fuzz before | fuzz after |
|---|--:|--:|--:|--:|
| (a) C API from LRA Rust modules (adapters, term::py, term::lra_read) | 256 (2.5%) | 618 (2.6%) | 782 (2.8%) | 2,186 (4.7%) |
| ... of which with a `memoized` frame in the stack | 36 (0.3%) | 0 | 221 (0.8%) | 0 |
| (b) callbacks entered at `memoized` | 290 (2.8%) | 6 (0.0%) | 2,479 (8.9%) | 0 |
| (b') slot callbacks entered from adapters (`relation`, `term_id`, `scaffold`) | in (b) | 94 (0.4%) | in (b) | 495 (1.1%) |
| (c) SymPy called from Rust under `memoized` | 30 (0.3%) | 0 | 328 (1.2%) | 0 |
| (c') SymPy called from an LRA Rust module | 7 (0.1%) | 35 (0.1%) | 87 (0.3%) | 207 (0.4%) |
| **LRA path, (a)+(b)+(b')** | **5.3%** | **3.0%** | **11.7%** | **5.8%** |

The callbacks are gone; part of their cost came back as C API in adapters, mostly on fuzz (adapters 1.7% -> 3.7%: "other C"
331, unicode 228, attribute lookup 205, allocation 186, dict 179). Every slot call still does `getattr`s on the module
(`_memoized`, the reader by name, `GENERIC_CONSTANTS`) and on term_live's `_local.stack` and the query's `kept`, the guards
that keep a patch or a flag flip correct. A speed item for later (cache them per query), not a bar item.

## Readers: lra_adapter.py per query, by workload (the lra_adapter count ruling)
`pycalls.py` with `PYCALLS_FILE=satassume/theories/lra/lra_adapter.py`, Rust, f7ea3d3, orion
(`~/sa-rust-ids-work/sa-port-197/pyc/`). Calls filed by the query they ran under.

| workload | queries | converted: `relation` | converted: other | kept:out-of-scope | no query (import) |
|---|--:|--:|--:|--:|--:|
| dev | 1,985 | 3,212 | 0 | 141 | 3 |
| fuzz | 3,000 | 100,449 | 0 | 0 | 3 |
| zero | 854 | 10,868 | 0 | 0 | 3 |
| loop | 420 | 0 | 0 | 0 | 3 |
| scope | 169 | 1,530 | `integer_form` 4 | 0 | 3 |
| budget | 28 | 60 | 0 | 0 | 3 |
| cert | 61 | 1,154 | 0 | 0 | 3 |

dev's 141 kept calls, by name: `_memoized` 33, `_lin` 24, `relation` 22, `_constraint` 22, `_closed` 10, `_side` 8,
`interpret` 7, `_linear` 7, `integer_form` 4, `order_sides` 4. The import-time three are `<module>`, `_Unhandled` and
`LRAAdapter` (class bodies).

Checked and reported as the ruling asks; **nothing claimed for the count before the planner applies the count rule:**
- **Per-query reach:** outside kept paths, two lra_adapter.py functions still run per query on Rust: `relation` (every
  workload but loop) and `integer_form`, 4 on scope. Those 4 are the slot's `ad:cbm_noid` fallback: term_live.py :717 sends a
  non-eq atom to relations.py `glue_objects`, whose `link_objects` (Rust) asks the adapter's `integer_form` for a side that
  has no input row in the query's table, so `_memoized` goes back to Python and lra_live's `integer_form` runs Python's
  (`on_python`, lra_live.py :169). Every other function is at 0 per query outside kept paths on all seven workloads.
- **`relation` as conversion:** it reads only the input relation's SymPy parts: `atom.function`, `atom.arguments` (and for
  `Q.is_true` its one argument) for an `AppliedPredicate`, otherwise `type(atom)`, `atom.lhs`, `atom.rhs`. It returns
  `(name, lhs, rhs)`. Rust (`Reader.rel`, adapters.rs) takes `name` as a string and uses `lhs`/`rhs` only to look up their
  ids in the query's `ids` dict. The results are built from the table's output and the query's `objects`, so nothing
  `relation` builds is kept or later read as engine state.
- **The 33 remaining `_memoized` calls (dev):** all 33 are kept, reason **out-of-scope** (convert.py's scope check: the query
  runs on Python, so `top_query` sees `kept` set and the slot counts them `ad:cbm_noquery`). No-query in the strict sense (no
  query on the stack at all): 0. fuzz, zero, loop, scope, budget, cert: 0 `_memoized` calls into lra_adapter.py.

## Which moved items are reached, and by what
PENDING (bar counters per workload)

## Kept reasons
PENDING

## State: each container this step touches (planner's state ruling, 8 Nov)
| container | decision | Python readers past this step | inventory row |
|---|---|---|---|
| the adapter's per-query slot (adapters.rs `LraQuery`: table, ids, objects, results) | **new, Rust-native from the start**; replaces lra_live's per-call reads through Python; dropped when the query changes | none in engine or wiring; test-only export `ad_lra_export` | tsv "state: LraAdapter slot" (new) |
| lra_live's per-table memo (term/lra_read.rs, inside the table) | unchanged (Rust-native, per query) | none | as 6-series rows |
| `lra_adapter._INTERPRETED` (Python, cross-query) | **unchanged**: since lra_live a converted query neither reads nor writes it (lra_live.py :192-196); kept queries and the pure-Python path keep it | `_memoized` (kept and pure-Python paths), tests/test_invariant_repros.py :80, test_term_live.py :141, satassume/state/memos.py :201 | tsv row 768 notes |

**Switch digest:** test_lra_slot.py's export at f7ea3d3: 1,484 entries, each equal to lra_live's own function on the same
query; slot digest a2fa4c14a0805a07 equal to lra_live's (also at d1d9728). PENDING the bar's live state comparison.

## Not run
PENDING
