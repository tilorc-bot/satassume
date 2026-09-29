# Agent report: perf round 3, item B5, the profile after A2

- **Date:** 2026-09-25
- **Status:** measured; **no engine-side item clears its line**. The largest
  engine-owned candidate (precompiled template clause emission) is bounded
  at 2.2%, the B1 early cone re-measured at 3.2% (5% rule); everything else
  engine-side is under 2%. My part of the round ends here unless the
  orchestrator reassigns the unowned theory code (section 4).
- **Scope:** measurement only. Pi, `main` at `747fb0e` (A1 + A2), unwrapped
  cold pass **3.12 to 3.16 s** (the denominator below). Scripts:
  `agent-reports/2026-09-perf-rounds/scripts/profile_split.py` (new: sampling split by phase
  and area), `emit_bound.py` (new), `log_census.py` (new),
  `cone_node_split.py` (node copy updated for A2), `gc_alloc.py`.
  Log: `~/.cache/satassume/log-747fb0e.jsonl` (13,877 lines, 6,390,938
  bytes, md5 `23b0311fe59fa84df191228523328aa1`, made on the Pi with
  `--log-models`, md5 checked on both ends).
- **Read this if:** you pick the next item after round 3, or you run item C

## 1. The split by area

`profile_split.py` samples the CPU every 0.5 ms (`ITIMER_PROF`; the kernel
tick makes it about one sample per 4 ms) and labels each sample by the
innermost satassume function (time in SymPy's own code is charged to the
satassume area that called it). Eight cold passes, 6,198 samples, answers
checked in every pass:

| area | share | owner |
|---|---:|---|
| `_propagate`: rule-block hook | 20.0% | solver (C) |
| search internals (`_search`, `_analyze`, heap, `_backtrack`, ...) | 13.7% | solver (C) |
| theories (LRA/EUF, `relations.py`, solver `_theory_*`) incl. SymPy arithmetic under them | 14.8% (8.7% + 5.2% SymPy + 0.9% adapters) | see section 4 |
| `_propagate`: watch lists | 7.5% | solver (C) |
| clause insertion (`add_internal`, `add_clauses`, ...) | 6.5% | solver (C) |
| `_assume`/`implied`/`propagate` bookkeeping | 4.1% | solver (C) |
| variable growth (`_grow`, `ensure_vars`) | 3.2% | solver (C) |
| `_propagate`: loop and setup | 3.1% | solver (C) |
| template clauses: demand filter, slots, bookkeeping | 3.2% | engine |
| template clauses: shift (`_emit_pattern`) | 2.4% | engine |
| caches (`DictCache`, `AnswerMemo`) incl. SymPy hashing | 3.3% | engine |
| API: formula translation and scope, incl. SymPy | 2.7% | engine |
| engine control flow (`query_literal`, `_literal`, `node`, `_discover`, `ensure`, ...) | about 6% | engine |
| templates (memo misses run SymPy templates) | 1.4% | engine |
| rule-block registration | 0.9% | solver |
| writeback, formula compilation, variable blocks (`VarTable`) | 0.5% / 0.4% / 0.3% | engine |
| collector (sampling under-counts it, see below) | 2.6% | |

**The collector** (`gc_alloc.py`, interleaved): default 3.077 / 3.120 s,
`gc.disable()` 2.963 / 2.983 s: **3.7 to 4.4%** (was 9.4 to 10.2% before
A2; 83 gen0 collections instead of 227). What it scans now: empty lists
41.7% of the gen0 scans (the per-variable watch lists `_grow` creates:
most rule-only literals never get a watched clause after A2), tuples
14.7%, watch lists 14.2%, clause lists 13.6%. That is item C's lazy watch
lists (B4), larger now.

## 2. The split by phase

| phase (where in the query) | share |
|---|---:|
| search in the reused session (`entails`, not a cone) | 29.8% |
| first attempt: visiting the proposition's nodes | 17.0% |
| first attempt: propagation (`query_literal` without search) | 16.6% |
| cone: search | 8.5% |
| cone: proposition's nodes | 6.2% |
| API, memo, formula translation | 4.9% |
| contextual session lookup and build | 3.9% |
| first attempt: escalation | 3.2% |
| context-free (`is_`) | 2.9% |
| cone: propagation / assumptions / escalation / session | 2.7% / 2.1% / 1.5% / 0.4% |

Search (both kinds) is 38% of the pass, propagation-only work about 19%,
node visits about 25% (attempts, cones, escalations, session builds).

**Node visits** (`cone_node_split.py b2`, `b2x`; shares of 3.12 s): a new
node visit is now 69 us (was 140 us before A2, 132 us before B2a):
19.8% of the pass for 8,895 new nodes. Template clauses 11.3% of it
(`add_internal` 7.7%, shift 4.2% with timer overhead, demand filter
2.0%), rule-block registration 2.9%, cached facts 2.0%, template memo
misses 1.5% (602 misses), variable blocks 0.4%.

**Cone path** (`b1`): the 757 cone queries' cone parts are 23.0% of the
pass (assumptions 2.6%, proposition's nodes 7.3%, escalation 1.4%,
search 11.7%); the wasted first attempts 6.4%; `b1oracle` against `b1`,
one run each: 3.183 → 2.929 s (-8.0%).

## 3. Census from the log of `747fb0e`

`log_census.py`: logged 3,310 ms (was 3,774 ms on `eae6070`); sessions
built 1,597 (unchanged); solves 6,384, decisions 81,293, conflicts 463.

| session_new | queries | ms logged | share | median ms |
|---|---:|---:|---:|---:|
| reused | 5,036 | 1,856 | 56.1% | 0.18 |
| cone | 757 | 979 | 29.6% | 1.04 |
| first sight (builds) | 444 | 243 | 7.3% | 0.32 |
| context-free | 190 | 108 | 3.3% | 0.35 |
| evicted | 143 | 51 | 1.5% | 0.27 |
| first sight, Uninterpreted | 63 | 33 | 1.0% | 0.42 |
| memo | 5,971 | 21 | 0.6% | 0.00 |
| evicted, Uninterpreted (the 2.5 memo) | 1,067 | 16 | 0.5% | 0.01 |

| path | queries | ms | share |
|---|---:|---:|---:|
| propagation>escalation>propagation>search | 1,349 | 1,216 | 36.7% |
| propagation>escalation>propagation>cone>search | 377 | 599 | 18.1% |
| propagation>search | 1,086 | 508 | 15.3% |
| propagation | 3,312 | 499 | 15.1% |
| propagation>cone>search | 380 | 380 | 11.5% |
| (empty: Uninterpreted, out of scope, `is_` cache) | 1,336 | 53 | 1.6% |
| propagation>escalation>propagation | 66 | 35 | 1.1% |
| memo | 5,971 | 21 | 0.6% |

## 4. Engine-side items and their bounds

| candidate | bound | rule | verdict |
|---|---:|---|---|
| precompiled template clause emission: (pattern, want) → (now, later) memo, plus a generated shift function per clause list (`emit_bound.py`, re-timed on the 14,629 filters and 14,352 shifts of the pass) | filter 51 → 2 ms, shift 53 → 33 ms: **2.2%** | 5% | dropped |
| the filter memo alone (the ten-line part) | 1.6% | 3% | dropped |
| B1 early cone (`p3`, re-measured on `747fb0e`, three interleaved pairs) | 3.116 → 3.018 s, **-3.2%**, answers identical | 5% | dropped (as before) |
| cached facts as unit clauses | 2.0% (the whole step) | | nothing to cut below it |
| API, memo, formula translation (B3 measured the removable part at about 1.5%) | 2.7% area | 3% | dropped |
| template memo misses | 1.5% | | dropped |

Nothing engine-side reaches its line. The shift measured in-pass (4.2%)
is inflated by the timers; re-timed on the recorded calls it is 1.7%.

**Outside both agents' lists: the theory code.** LRA/EUF and
`relations.py` take 14.8% of the pass, of which 5.2% is SymPy code called
from them. The largest single part is the solver's `_theory_sync` (2.8%,
solver-owned). The rest is `lra.py` (simplex, bounds, `register_atom`: its
arithmetic runs on SymPy numbers, about 3.4% of the pass in SymPy under
`lra.py` alone), `euf.py` (`pop_level` 0.6%), `theory.py` `update` (0.6%,
SymPy), `relations.py` `_key` (0.5%, SymPy). `lra.py`, `euf.py` and
`theory.py` are not in my file list (my list has "the adapters",
`lra_adapter.py`/`euf_adapter.py`, which are 1% together). If the
orchestrator assigns them: LRA arithmetic on Python `Fraction`/ints
instead of SymPy numbers is the obvious candidate, bound about 3 to 4%.

**For item C (solver agent), from this profile:** the hook 20.0%, search
internals 13.7%, watch lists 7.5%, insertion 6.5%, assume/implied 4.1%,
growth 3.2%, loop 3.1%, together about 58%, plus the collector's 3.7 to
4.4% which is now mostly empty watch lists. Also: round 2's witness reuse
(1.1) was dropped at 4.8% when search was 22% of the pass; search is now
38%, so the same measurement would give a larger bound. It lives in
`Solver.entails`; worth a re-measure on the solver side.

## Decision

Measurement only; no engine-side item reaches 5% (3% for ten-liners). My
part of the round ends unless the theory files are reassigned.

## Risks for review

None (no code). `profile_split.py` attributes by the innermost satassume
function and by line ranges in `_propagate` and `Engine.ask` read from
source markers at start-up; it exits if a marker is missing. Sampling is
at the kernel tick, not every 0.5 ms; eight passes give 6,198 samples, so
shares under 0.5% are noisy.
