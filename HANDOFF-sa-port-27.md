# Handoff: sa-port-27, component 6, atoms (issue 323)

Read the brief first: `~/.local/state/agent/briefs/sa-port-27-20261107T101139Z.txt`. Its terms still apply, with two later rulings below. Clone `~/dev/sa-port-24`, branch `port/6`. Nothing is on `rust-slice`. Earlier map: `HANDOFF-sa-port-24.md`, whose "Gaps" section still stands except where corrected here.

## Rulings that came after the brief

- **Lazy reads:** `~/dev/architect/briefs/addenda/sa-port-lazy-ruling.txt`. Conversion goes lazy, with no refusal rule. sa-port-29 builds it on `port/lazy` and lands it on `rust-slice`. **Atoms can't land before that.** Keep the `complex-unbounded` refusal only until you rebase on that landing, then drop it and rerun what the rebase changes. Don't measure other slow `complex(t)` terms: the brief's "Refusal's reach" item is replaced, and sa-port-29 covers conversion's eager reads.
- **Suite reporting:** `~/dev/architect/briefs/addenda/sa-port-suite-reporting-ruling.txt`. Passed splits into no firing, and a handler firing on Rust that doesn't fire on Python for that test, by id with type and text. No reclassifying by hand. Any firing other than a named needs-internals case is a finding with its smallest case. A large second group goes to the planner. Until the split exists, quoting 5,961 must add that it includes at least `test_ci_stream_reports_only_what_replays`. `suite_split.py` does the split.

## Standing

| What ran | Result |
|---|---|
| fresh2 (fe85470), dev 1,985, fuzz 3,000 | atoms and shadow byte-identical to plain; 0 of 12,872 shadow mismatches; 0 faults; kept 50 dev, out-of-scope; derived 27 dev, 652 fuzz. **Predates the fix below and can't see that bug.** |
| `knowledge_units_cmp.py` after the fix | 304,161 fact lists, no differences; 214,375 conflict path, 263,943 `rest`. Owed item 5 is done, except that it compares `Rules::units` only |
| `quiet_fire.py` under `install()` | counter saw 1 at each of the four calls, 0 unplanted |
| `knowledge_quiet.py rust dev` | `atom_units` at 1107 (1,170 calls): planted raise escapes as KnowledgeFault, counter 0, unplanted rows 0. The other five combinations: **not reached on dev** |
| Forced nest, on a `--limit 6` run only | conversion and `units` raising inside both tries: all four escape, counter 0. Labelled forced, not reached. `quiet-rust-dev.txt` predates this code, so its file has no forced rows |
| Dev recount, run1 | atoms same as plain; handler rows 4 planted, 0 unplanted, in both modes |

**Findings so far:**
1. **Fixed, 0d4620b.** `used` was `(0,)` for a pattern holding only an empty clause; Python says `()`. Smallest real case: `Symbol('x', antihermitian=True, real=True, zero=False)`. No dev or fuzz query holds it, so fresh2 was blind to it.
2. **Pure Python, not changed:** `ask(Q.positive(x))` on that symbol raises IndexError from the empty clause (`sat/solver.py:968` through `engine.py:661`). Rust matches. Named for the planner or Tilo.
3. **Conversion writes to Python (smoke, 40 dev queries):** SymPy `cacheit` (`Basic.has`, `DefinedFunction.__new__`, `sort_key` and others) and satassume's `_NONCOMM`. So "a discarded run leaves nothing" is **false today**. The end state's `_common._CACHE` and `rules._MASKS` also differ, because plain fills them and atoms doesn't. No answer or digest has moved. The lazy ruling should shrink this; rerun after the rebase.
4. **Correction to sa-port-24's gap:** `_SPLIT` isn't unbounded. `engine.py:2334` clears it at 100,000. Atoms still adds more entries than Python's shared `_CACHE` does; that isn't measured.

## Trap in my own tool: fix before believing a zero

`knowledge_leak.py` reads SymPy's `cache_info().currsize`. `cacheit` is an LRU, so **once a function's cache is full, `currsize` stops moving and a write reads as nothing.** On a long run its zeros are false. Switch `snap()` to `misses` (each miss is a write) and rerun. The bug is in run1's `leak-*.txt`, so read those as floors. Show it fires on a planted `cacheit` write. The `_assumptions` count isn't affected.

## Running, detached, not results

All under `~/sa-rust-ids-work/sa-port-27/`. Started about 10:19 UTC on orion.

| Job | From | End marker | Read |
|---|---|---|---|
| Suites at `-n 3`: Python and atoms together, then Rust alone | `run1/tree` (0d4620b, `.so` `run1/so.sha`) | `run1/suites.done` | `suite_split.py run1/suite-atoms run1/suite-python --base-rust ~/sa-rust-ids-work/port-census/pr328-check/suite-rust --list run1/second-atoms.jsonl`, then again with `run1/suite-rust`, which tells crate firings from atoms firings |
| Recount and leak, dev, fuzz, corpus, then `knowledge_quiet rust` on fuzz and corpus | `run1/tree` | `run1/recount.txt` (`recount.part` until then) | `recount.txt`; `{wl}-{plain,atoms}.handlers.jsonl`; `leak-{wl}.txt`; `quiet-rust-{fuzz,corpus}.txt` |
| 36 planted bugs plus base, 3 jobs | `mut/tree` (commit after 0d4620b) | `mut/done.txt`, `mut/work/results.jsonl.done` | `mut/work/results.jsonl`, one row each |

**Check when reading:**
- **Suite reach:** in the smoke, `knowledge.PID.json` showed only `py:no-query` and no `converted` (2 tests). Sum `converted`, `symbol:input`, `constant:input` across workers. If they're small, the suite hardly exercises atoms, and the report must say so. Each process's `plant_check` adds a few `py:no-query`.
- **Each suite worker's planted rows:** 4 per process, the xdist controller included. A worker with fewer proves nothing.
- **Mutants:** the base row must be `no` in all three columns, and `loaded_here` must be true on every row, or the column is void. They compare with fresh2's plain rows from an earlier commit; the base row is what validates that. Expect `used-*` and other conflict-path mutants to be caught by `direct` only. `live-fault-quiet` should read `no` everywhere: nothing raises a fault in these runs, so nothing catches it unless planted. Name that. A `crash` includes KnowledgeFault.
- `test_performance_smoke_300_vars`: report it either way.

## Still owed, in order

1. Read the jobs above and report the suite split and three numbers, each by id, against 5,961 / 77 / 46. Keep the 46 and the `_n_conflicts` shim as the planner's rulings state them.
2. Fix the leak tool's false zero (above) and rerun.
3. **Planted bugs report:** say which a comparison caught and which only a crash, and name what nothing catches. Re-score the boundary: atom rows from conversion to Rust, patterns from Rust to Python. **No suite column has run for these mutants.** Run it for those no other column catches, or state it wasn't run. Planner's standing ruling: mutants 2, 5, 6, 7, 9 rest on the API fuzzer alone, and they need rerunning on paths where real theories run on Rust; say whether this family's run changes that.
4. **History, not started:** seeds 0, 1, 2 and shuffle on dev, fuzz, corpus, with atoms. `run_history.sh` drives `live.py`, not this family; `knowledge_fresh.py` has no `--shuffle`. Seeds work through `PYTHONHASHSEED`. Add the smallest switch.
5. **Counts, not started:** per query, `default_sort_key` and `decompose_power` constructions beside pure Python's, keys computed against keys used, `complex(t)` with its own counter, conversion's time by site. Callback counts, queries kept on Python by reason, and timing on a quiet pareto1 lease. Since the lazy ruling asks for these numbers to be rerun, do them after that rebase. `term_counts.py` is the place to start.
6. **After sa-port-29 lands:** rebase, drop `complex-unbounded` (`convert.py:43`, the checks in `closed` and `convert`), rerun what the rebase changes (at least fresh, suite with the split, leak, quiet, mutants), push to `rust-slice` without force, and report the SHA, three numbers, what ran and what didn't, and modules of the 32 now running. **0 of the 32 count until then.**

Corpus has never completed a run for this family; the recount above is the first.

## File:line map

| Topic | Where |
|---|---|
| `used` fix | `solver_rs/src/term/py.rs`, end of `pattern` (about :239) |
| Direct compare | `rust-spike/slice/knowledge_units_cmp.py` |
| Handlers | `knowledge_quiet.py`: `plant_check`, `rust`, `forced`; `handler_count.py`, `quiet_fire.py` are byte-identical to port/3 at f189a61; `knowledge_fresh.py --handlers` |
| Suite | `knowledge_suite.py` (`SLICE_KNOWLEDGE=atoms`, plants at session end), `suite_split.py`. `rust_plugin.py` is **unchanged**: a separate plugin replaces the brief's "small switch" |
| Leak | `knowledge_leak.py`: `snap` (the false zero), `cmp` |
| Mutants | `mutate_knowledge.py`: list `M`, columns `direct`, `shadow`, `off` |
| Shared-file change so far | `solver_rs/src/term/py.rs` (the fix). `knowledge_live.py` takes the offline root from the imported tree, so scratch copies load |
| The rest | `HANDOFF-sa-port-24.md`'s map |

Scratchpad script `probe_used.py` is at `~/sa-rust-ids-work/sa-port-27/probe_used.py`: the real-engine probe for finding 1.
