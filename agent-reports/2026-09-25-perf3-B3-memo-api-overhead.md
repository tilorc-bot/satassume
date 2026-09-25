# Agent report: perf round 3, item B3, memo-hit and API overhead (measured, dropped)

- **Date:** 2026-09-25
- **Status:** dropped by the bound rule. Everything `sympy_api.ask` does
  around the engine is at most 1.5% of the cold pass, under the 3% rule for
  ten-line items. No code change. Script
  `agent-reports/scripts/api_overhead.py`, run on the Pi on `main` at
  `9e8c3eb` (satassume code identical to `895a6c2`), cold pass 3.63 s.
- **Scope:** measurement only (`satassume/sympy_api.py`, the answer memo,
  `_registry_state`, `_formula`)
- **Read this if:** you want to speed up the SymPy-facing layer, or wonder
  whether memo hits cost anything

## Measurement

`api_overhead.py` has four modes, one process each, every one on a cold
engine: `plain` (the unwrapped cold pass as the denominator, then passes
over the memo hits and micro-benchmarks of the parts), `wrap` (timers
around `sympy_api.ask`, `_formula` and the engine entry points at depth
1), `wrapnull` (the same wrappers without timers, for their own cost),
`profile` (cProfile).

**Memo hits (5,971 queries).** A pass over exactly the queries that hit
the memo in the cold pass: 11.6 ms, **1.95 us per hit, 0.32% of the
pass** (the wrapped cold pass says 19.1 ms, 0.5%, timers included). Parts
of a hit, summed over the hits:

| part | ms | share of pass |
|---|---:|---:|
| `memo.get((p, a))` (hash is cached; the time is SymPy `__eq__` of the stored key against an equal but distinct query object) | 8.3 | 0.23% |
| `_registry_state()` and the state compare | 1.3 to 1.7 | 0.05% |
| key tuple, `isinstance` checks | 1.3 | 0.03% |
| `hash(p)`, `hash(a)` (cached by SymPy) | 1.5 | 0.04% |

`_registry_state` is already the version counter of round 2's 3.2: no
snapshotting is left (one tuple of three items per call).

**Misses (7,906 queries, 7,746 reach `Engine.ask`/`Engine.is_`).**

| part | ms | share of pass |
|---|---:|---:|
| answer memo work (state, get, put) | 11.3 | 0.31% |
| `_formula` lookups (warm memo, 15,477 calls) | 10.8 | 0.30% |
| `to_formula` itself (2,951 calls on distinct Booleans; profile 0.4% of the profiled pass) | about 15 | about 0.4% |
| first query: `Engine()` and the template registry's warm-up | 15.1 | 0.4% (once per process) |

The wrapped pass bounds the whole API side of a miss from above at
114 ms (miss time minus engine time; timer and wrapper frames included,
`wrap` vs `wrapnull` differ by 50 ms), 3.1%; less the first query and the
timers it is 50 to 60 ms.

`out_of_scope` and `_categories` are not on the path: `ask` never calls
them (0 calls in the profile); scope is decided inside the memoized
`to_formula`.

**Total, removable at best:** hits 0.3% + miss memo 0.3% + formula
lookups 0.3% + `to_formula` 0.4% = about 1.3 to 1.5%, and most of that is
hashing and dict lookups a memo needs anyway.

## Change

None.

## Decision

Dropped: bound about 1.5% (3.1% as a loose upper bound with the
instrumentation included), under the 3% rule, and no single part above
0.4%. The engine (`Engine.ask` 7,520 calls, `Engine.is_` 226) is 97% of
the pass.

## Risks for review

None (no code).
