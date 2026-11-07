# Port component 6, `_common.py` first part: landing report (issue 323)

Tested source ed6da92, on `rust-slice` 19ed342 (component 3 included), x86-64 on pareto1, hash seed 0, `.so` sha256 starts 48da6cc9c425. The only commit after ed6da92 adds this report. Job output: `~/sa-rust-ids-work/sa-port-48/` on pareto1, `land3` and `land3s`; scripts in `jobs/` there on orion.

**Modules: 0 of the 32 runtime modules newly run whole in the real engine because of this.** Partly ported: `_common.py`. `atoms.py` was already counted by `port-6b.md`, and I didn't recount the total.

**Now from Rust, under `knowledge_live.install()` only:** `resolve`, `_resolve_lit`, `_unsubsumed` and `Pattern.__init__`. `facts` and `units` call them through module globals, so every template goes through them, except on a kept query. Python stays the default.

**Still Python in `_common.py`:** `facts`, `units`' cache and its Python closing path, `_CACHE`, `const_value`, `lits`, `Rules`, `ge2_alternatives`, `instantiate`, `Compiled.formulas`, `consts_of`, `pattern_key`, `const_key`, `TemplateKeyError`.

Limits that stand:

- **`functions._value_units` still evaluates `expr.func(c)` in Python** until `functions.py`'s port, and so does `special.py` for multigamma. The offline table lands with that port (planner's answer to report 9e46d2b).
- **A constant's facts are read by `const_value` in Python, in Python's order,** by callback from Rust's `resolve`.
- **Kept on Python with reason:** Sum, Product, Integral, queries under a non-default registry, and the other `kept:` reasons, for `resolve` and `Pattern` as well (`common:kept`: 107 on the suite). A kept query can still be served a pattern `_CACHE` got from Rust earlier in the process. That's plain Python data and no Rust runs for it.
- **No query on the stack still runs Rust here,** because these functions need no term table. That differs from the atoms path, which goes to Python (`py:no-query`).

## The bar

| Check | Result |
|---|---|
| Suite by id against sa-port-45's rows (`sa-port-45/atoms1/suite/rust`) | 6,125 ids on both sides, 0 new, 0 changed. 23 skipped, 18 xfailed |
| Three numbers | **5,961 passed, 77 kept on Python (needs internals), 46 failed on re-entry** |
| Fresh dev, fuzz: plain against atoms | Answers and state MATCH: 1,985 and 3,000 queries |
| Fresh `value` workload: plain against atoms | MATCH: 3,742 queries |
| Discard against plain | MATCH on all three |
| Planted bugs | 7 in `_common`'s Rust: 5 caught by answers and state, 1 by the suite, 1 by field only. Table below |
| Quiet firings on Rust | 39 rows, 2 tests, all named. **No new finding** |
| Faults, `read_raised`, `read_term_missing` | 0 on the suite and fresh runs |

S's gate is met except for the 46 named stub failures, one cause. Each of the 46 has `Already mutably borrowed` in its failure row, and they're the same ids as the base's: `test_lra_fuzz` 31, `test_theory_hooks` 7, `test_euf` 4, `test_euf_fuzz` 2, `test_transfer` 1, `test_solver_real_theories` 1. The crate is unchanged for them.

Passed splits as **5,960 with no firing and 1 with a firing on Rust** (`test_ci_stream_reports_only_what_replays`). This run has no Python handler rows, so "not on Python" isn't tested here. The suite split with Python's counter is on the backend PR list. The `_n_conflicts` view in `rust_plugin.py` isn't a port: it's a test-plugin shim, with the 64 tests it moved.

**The base predates component 3.** The landing source includes it, and sa-port-45's rows don't. Outcomes still match by id, and `port-3.md` reports the same three numbers.

**A failed test could fail for a new reason, so I compared the failure text too.** 6 of the 123 differ:

- 5 differ only in a `rust_plugin.py` line number, because component 3 added lines there.
- `test_fuzz_entails_and_implied` differs in Hypothesis' example text, with `Already mutably borrowed` on both sides. An earlier run on this branch also showed `test_dpll_t_matches_enumeration` differing this way, so the set moves between runs.

## Field by field: the shadow, on real workloads

The shadow runs Python's `resolve` and `Pattern` beside Rust's on each call. It compares every field, including whether the two print the same, since the engine iterates `child_preds`.

| Run | `_common` comparisons | Atoms comparisons | Mismatches | Order differences |
|---|---|---|---|---|
| dev | 7,751 | 3,050 | 0 | 0 |
| fuzz | 36,367 | 9,822 | 0 | 0 |
| value | 11,967 | 3,699 | 0 | 0 |
| **suite** (`SLICE_KNOWLEDGE=shadow`, new) | 65,523 | 2,576 | 0 | 0 |

The suite with the shadow on has the same outcomes by id as with it off. The three numbers quoted are from the run with it off. Both zero counters are shown to fire: the wide plant below gave 96 mismatches, and a unit test plants an order difference.

## Reach: read this before relying on the MATCH

| Path | dev | fuzz | value | suite |
|---|---|---|---|---|
| `resolve` calls | 2,719 | 14,339 | 4,232 | 41,366 |
| `Pattern` calls | 2,937 | 14,937 | 4,233 | 23,825 |
| Wide rules | **0** | **0** | **0** | 386 |
| Contradiction raised | **0** | **0** | **0** | **0** |

- **Wide rules aren't reached by dev, fuzz or value.** Their only real-engine evidence is the suite, where the shadow compared 383 of them with 0 mismatches. A MATCH on those three workloads says nothing about this path.
- **The contradiction path never ran on a real query.** Only the hand cases in `test_knowledge_common.py` reach it. The counter is shown firing there.
- **`Pattern.rules` and `_common.Compiled` aren't compared beyond the field list,** and `Compiled.objs` isn't compared at all, as in `port-6b.md`.

## Plants

Each ran from its own build, and every row loaded its own. The base row: nothing fired in any column. "Off" is answers and state against plain, as lines changed / answers changed.

| Plant | Shadow, dev: fields | Off: dev | Off: fuzz | Off: value | Unit |
|---|---|---|---|---|---|
| `common-unsubsumed-keeps-subsumed` | 1,880 | 660 / 0 | 2,834 / 0 | 490 / 0 | caught |
| `common-clause-sort-reversed` | 2,442 | 654 / 0 | 2,780 / 0 | 358 / 0 | caught |
| `common-contrapositive-sign` | 1,107 | 465 / 165 | 2,691 / 377 | no | caught |
| `common-undecidable-premise-kept` | 815 | 445 / 0 | 2,560 / 0 | 98 / 64 | caught |
| `common-internal-sign` | 3,903 | 719 / 577 | 2,835 / 2,471 | 1,888 / 1,838 | caught |
| `common-resolve-keeps-subsumed` | 2,043 | no | no | no | caught |
| `common-wide-off-by-one` | no | no | no | no | caught |
| `expand-pos-neg-swap` (older) | 1,458 | 383 / 383 | 981 / 898 | 3,030 / 2,696 | caught |
| `live-value-negated` (older) | no | no | no | 983 / 983 | no |

- **`common-wide-off-by-one` passes all three workloads, as the reach table predicts. The suite catches it.** With that build and the shadow on, the same suite gives 128 failed, 5 ids moving from passed to failed (`test_the_rows_entail_the_baseline` for Add, Max, Min and Piecewise, and `test_wide_nodes_leave_out_the_negations_of_conjunctions`), and 96 mismatched fields. The workers recorded that build's `.so` as loaded.
- **`common-resolve-keeps-subsumed` changes fields and no answer or state on any workload.** I read that as `_unsubsumed` removing the same rules afterwards, for rules that reach clauses. I didn't test that reading separately. The shadow and the unit tests are what catch it.
- **Three plants change state and no answer on dev and fuzz,** so a comparison of answers alone would miss them there.
- **Plants scored: only these 9.** Two older plants, `in-vocab-keeps-commutative` and `const-basis-offset`, no longer apply: their anchor strings aren't in `py.rs`. That predates this work, and I left them as they are. I repaired `unsubsumed-not-stable`'s anchor, which this crate code had made ambiguous, but didn't score it.

Tests on this source on x86-64: 42 passed across `test_knowledge_common.py` (26), `test_knowledge_value_units.py` (9) and `test_knowledge_lazy.py` (7).

## Firings

From the landing suite run. Each of the 9 workers' counters was shown firing: 36 planted rows seen. The suite with the shadow on gave the same rows on its land2 run. I didn't reprint them for its land3s run.

| Test | Site | Type and text | Rows | Outcome |
|---|---|---|---|---|
| `test_ci_stream_reports_only_what_replays` | `_consistent` | AttributeError, `'Solver' object has no attribute '_ok'` | 34 | passed |
| same | `_consistent` | AttributeError, `... '_rb_clauses'` | 4 | passed |
| `test_protocol_on_fuzz` | `Engine._build_context` | RuntimeError, `Already mutably borrowed` | 1 | failed, in the 46 |

Both are named cases. Fresh runs had 0 unplanted firings on dev, fuzz and value.

**Catches at `engine.py:1906` and `sympy_api.py:1107`:** the `knowledge_quiet.py` recount ran on dev and fuzz, not on `value`. A forced fault in conversion or an atom template reaches both handlers and comes out as `KnowledgeFault`, with the counter seeing 0. That recount forces those two paths, not `resolve` or `Pattern`. Their fault path is the same `KnowledgeFault`, shown only by direct calls in the unit tests.

**What stays quiet, as on Python:** an exception raised by `const_value` passes through `resolve` as itself, the same object, and a unit test holds that. If it happens under one of those handlers, it becomes a quiet result on both backends.

## What changed

- `knowledge_live.py`: `install()` swaps `_common.resolve` and `_common.Pattern`, and `undo` restores both. A kept query calls Python's. `MAX_EXPAND` is read at call time. The shadow gains `ORDER_DIFFS` and `shadow:order`.
- Crate: `term/knowledge.rs` and `term/py.rs` gain `resolve`, `unsubsumed_clauses`, `expand_clause` and `build_pattern`, written by sa-port-45.
- New: `test_knowledge_common.py`. Seeded random rules against Python by field and by the order of reads, plus the hand cases.
- `mutate_knowledge.py`: 7 `common-` plants, a `unit` column, and each workload scored on its own, so `off` no longer stops at the first catch. `knowledge_fresh.py` keeps order differences. `knowledge_suite.py` gains a shadow mode and records which build loaded.
- No change to `satassume/`. No heuristic added or changed.

**One departure from the handoff, by the planner's ruling.** The handoff sent every template through Rust. The planner's ruling keeps those queries wholly on Python, so a kept query now calls Python's `resolve` and `Pattern`. The first runs had Rust there, with no answer moved. The numbers above are all from after this change.

## Known differences

1. **Reads:** none in `resolve`'s order. The random tests hold the read log equal to Python's, call by call, including stopping at a contradiction.
2. **Object identity:** Rust returns new literal tuples, equal to Python's, where Python passes the template's own objects along. No state or answer difference showed. I didn't audit every reader for `is` on a literal.
3. **The suite's counters move between runs on the same source,** as `port-6b.md` reports. `common:resolve` was 41,464 on land1, 41,366 on land3 and 41,376 with the shadow on. Outcomes were identical by id. Don't compare these as exact.
4. **Non-list rules:** the shadow materializes a non-list `gen()` before Python's run. Without the shadow, Rust iterates it directly.

## Not run

Moved to before any backend PR: the mutant 2, 5, 6, 7, 9 rerun and mutlive's control, the boundary rescore and suite column, the final drop score and its lost rows, the suite split with Python's counter, `order:_rows`' evidence (not caught meanwhile), the `_forms` guard test, history and seed reruns, forced moves, the native path, and timing.

Also not run: corpus fresh and leak, shuffled orders, the other plants, the quiet recount on `value`, a suite run on the base with this source's component 3 beside it, and a public-API `test_incremental_matches_fresh`, which is due during the engine port.

10 of the 25 boundary mutants have no real-engine catch, and the boundary suite column wasn't run. Mutants 2, 5, 6, 7, 9 still rest on the API fuzzer alone. Section 8's limits still stand on the base: PR 328's fuzz history and censuses aren't read, and suite2 is a floor.

History note: the rebased commit "WIP component 6, _common" still says "not wired or tested, not for landing". Later commits on this landing wire and test it. I didn't rewrite it, so the tested SHA stays valid.

## What's left of `_common.py`

`lits`, `Rules`, `ge2_alternatives`, `consts_of`, `pattern_key` and `const_key` feed Python templates and move with them. `instantiate` and `Compiled.formulas` build SymPy formulas and move with the engine. Don't count `_common` until these are done or ruled out. The `value` workload stays with `functions.py`'s unary port.
