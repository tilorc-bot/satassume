# Port component 6, rest of atoms: landing report (issue 323)

Tested source 0c0b055, on `rust-slice` dc3f15d with no rebase needed, x86-64 on pareto1, hash seed 0. Commits after 0c0b055 change only docs. Job output: `~/sa-rust-ids-work/sa-port-45/` (orion and pareto1).

**Modules: 1 of the 32 runtime modules now runs whole in the real engine because of this: `templates/atoms.py`.** That takes the planner's count from 3 to 4 of 32; I took the 3 as given and didn't recount it. Partly ported: `_common.py`. It runs under `knowledge_live.install()` only, so Python stays the default.

"Whole" has these limits:

- **`functions._value_units` still evaluates `expr.func(c)` in Python.** So does `special.py` for multigamma. Those lines belong to their modules, not `atoms.py`. The offline table lands with `functions.py`'s unary port (planner's answer to report 9e46d2b).
- **A derived value's facts are read in Python by callback**, and Rust closes them: `value:derived`, `constant:derived`, section 10's "`is_` by callback".
- **Kept on Python with reason:** a template with no query on the stack (`py:no-query`) or on a kept query (`py:kept`).

## The bar

| Check | Result |
|---|---|
| Suite by id against sa-port-44's rows | 6,125 ids on both sides, 0 new, 0 changed |
| Three numbers | 5,961 passed, 77 kept on Python (needs internals), 46 failed on re-entry |
| Fresh dev, fuzz: plain against atoms | Answers and state MATCH: 1,985 and 3,000 queries |
| Fresh `value` workload: plain against atoms | MATCH: 3,742 queries |
| Shadow, field by field | dev 3,050, fuzz 9,822, value 3,699 compared, 0 mismatches. Answers and state also match plain |
| Discard against plain | MATCH on all three. Conversion only, as in `port-6.md` |
| Rust faults, `read_raised`, `read_term_missing` | 0 on the suite. The counters are from the same runs |

S's gate is met except for the 46 named stub failures, one cause. Passed splits as **5,960 with no firing and 1 with a firing on Rust**. This run has no Python handler rows, so "not on Python" isn't tested here. The suite split with Python's counter is on the backend PR list. The `_n_conflicts` view in `rust_plugin.py` isn't a port: it's a test-plugin shim, with the 64 tests it moved.

## Reach: read this before relying on the MATCH

**dev and fuzz never reach `value_units` with a value other than the node.** They hold no call to a function of `VALUE_AT_INTEGER` or to multigamma: 0 of 4,985 queries. **The suite's counters show 0 too**: `value:derived` and `value:input` are 0 in both suite runs. A call with no query on the stack would count under `py:no-query`, which doesn't separate this path, so I can't say none happened there.

So everything shown for the new path comes from the `value` workload I added (`knowledge_value_wl.py`, `knowledge_fresh.py value`): 2,380 `value:derived` and 486 `value:input`. It covers all six functions on both sides of the limit of 200, other constants, multigamma, and a value that is also an input term. It's written for this path, not drawn from real use. The planner has asked that it stays with `functions.py`'s port.

## Plants

Each ran from its own build. Base row: nothing fired.

| Plant | shadow (dev only) | off (dev, fuzz, value) |
|---|---|---|
| `live-value-negated`: facts of `-value` | no | caught on value: 983 lines, 983 answers |
| `live-value-on-value`: facts on the value, not the node | no | caught on value: 2,630 lines, 564 answers |
| `expand-pos-neg-swap` | caught, 1,458 fields | caught on dev: 383 lines, 383 answers |
| `conv-const-reversed` | caught, 1,733 fields | caught on dev: 359 lines, 357 answers |

Both value plants pass dev and fuzz, which confirms the reach gap above. The shadow column runs on dev only, so its "no" there says nothing about the value path. `_compare` also doesn't look at `Compiled.objs`, so `live-value-on-value` would pass the shadow on any workload. Only 4 of the plants were scored.

`test_knowledge_value_units.py`, 9 passed on orion (aarch64), not run on x86-64: the counters fire, a wrong value shows in `_compare`, nothing is read above the limit, `install` doesn't import `special`, and `undo` restores the bindings.

## Firings

From suite run 1. Run 2 gave the same tests and counts. Each worker's counter was shown firing: 36 planted rows seen.

| Test | Site | Type and text | Rows | Outcome |
|---|---|---|---|---|
| `test_ci_stream_reports_only_what_replays` | `_consistent` | AttributeError, `'Solver' object has no attribute '_ok'` | 34 | passed |
| same | `_consistent` | AttributeError, `... '_rb_clauses'` | 4 | passed |
| `test_protocol_on_fuzz` | `Engine._build_context` | RuntimeError, `Already mutably borrowed` | 1 | failed, in the 46 |

Both are named cases. **No new finding.** Fresh runs had 0 unplanted firings on dev, fuzz and value: only the 12 planted rows. The `knowledge_quiet.py` recount at `engine.py:1906` and `sympy_api.py:1107` ran on dev and fuzz, not on `value`.

## What changed

- `knowledge_live.py`: `rust_compiled` now serves `symbol_units`, `constant_units` and `value_units`. `_bind_value_units` rebinds `atoms` and any caller already loaded. It doesn't import `functions` or `special`, because that would skip the registry's lazy load, and a test holds that.
- `knowledge_fresh.py` gains the `value` workload. `mutate_knowledge.py` adds it to `off`, gains the 2 value plants, and 2 existing plant strings follow the renamed variable.
- No change to `satassume/` or the crate on this landing.

## Known differences

1. **Reads, for `value_units`.** Differences 1 and 2 of `port-6.md` carry over. Also, a derived value's facts are read on every call, where Python reads only on a miss in `_CACHE`. Nothing is memoized for them, and this path leaves `_CACHE` unfilled. From reading the code, not measured: fresh runs clear memos per query. History runs would be the place to measure it. No answer or state difference showed.
2. **The suite's read counters move between runs, on the same source.** Run 1 and run 2 of 0c0b055:

   | Counter | Run 1 | Run 2 | sa-port-44 (`port-6.md`) |
   |---|---|---|---|
   | converted | 34,735 | 34,731 | 34,736 |
   | symbol reads | 2,798 | 2,925 | 2,504 |
   | constant reads | 210 | 199 | 194 |

   So the gap from `port-6.md` isn't evidence about this change, and those counts shouldn't be compared between runs as if exact. Outcomes were identical by id across the runs. xdist scheduling against per-worker memos is the likely cause, but I didn't isolate it.

## `_common.py`: not landed

**Written, builds, has never run, not wired:** `resolve`, `_resolve_lit`, `_unsubsumed` and `Pattern.__init__` in Rust, on `origin/port/6b-common` (e330f28). Nothing on `rust-slice` includes it. `HANDOFF-sa-port-45.md` has the wiring plan.

**Runs from Rust on `rust-slice`:** the closing part of `units` and the reads behind `const_value`, for atoms only.

**Still Python:** `facts`, `units`' cache, `_CACHE`, `lits`, `Rules`, `ge2_alternatives`, `instantiate`, `Compiled.formulas`, `consts_of`, `pattern_key`, `const_key`, `TemplateKeyError`.

## Not run

Moved to before any backend PR: the mutant 2, 5, 6, 7, 9 rerun and mutlive's control, the boundary rescore and suite column, the final drop score and its lost rows, the suite split with Python's counter, `order:_rows`' evidence (not caught meanwhile), the `_forms` guard test, history and seed reruns, forced moves, the native path, and timing.

Also not run: corpus fresh and leak, shuffled orders, the other plants, `test_knowledge_lazy.py` on this exact source on x86-64 (7 passed on orion), and a public-API `test_incremental_matches_fresh`, which is due during the engine port.

10 of the 25 boundary mutants have no real-engine catch, and the boundary suite column wasn't run. Mutants 2, 5, 6, 7, 9 still rest on the API fuzzer alone. Section 8's limits still stand on the base: PR 328's fuzz history and censuses aren't read, and suite2 is a floor.
