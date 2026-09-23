# Agent report: satassume, a unified SAT-based assumptions engine, and how it compares to `reasoning`

- **Date:** 2026-09-23
- **Status:** prototype on `main` (`89de1ae`); 302 tests pass; the
  old-handler oracle fallback has been removed at the maintainer's request
- **Scope:** everything in this repository: `satassume/` (rules, formula
  compiler, CDCL solver, engine, templates, SymPy API), `tools/`
  (corpus recorder, replay comparer, benchmark), `tests/`, `PLAN.md`
- **Read this if:** you want to know what was measured about SymPy's two
  assumption systems, what this engine does differently from `reasoning`
  (https://github.com/TiloRC/reasoning), where it stands, and which of the
  two directions to continue
- **Stale after:** changes to `satassume/engine.py`'s query path, the
  template set, the recorded corpus, or a scope change of this repository
- **TL;DR:** one incremental CDCL engine answers both `expr.is_*` and
  `ask(Q.*, assumptions)` from one rule base and one template set, caching
  root-level facts on the expression object. On 9230 queries recorded from
  SymPy's own tests it never contradicts SymPy; it answers 94% of the
  old-system queries and 82% of the new-system ones (the rest is mostly
  matrices, relations and missing templates). Contextual queries run 5 to 8x
  faster than `sympy.ask`; context-free cache misses run 3 to 15x slower
  than the old handlers in pure Python, with the hit path unchanged.
  `reasoning` is SymPy's `satask` extracted and extended (theory protocol,
  LRA, fuzzer, CI parity); it targets only the new system and rebuilds its
  clause database per query. The recommended next step is a narrower scope,
  `ask()` for unary scalar predicates, finished to 100% of the corpus.

## 1. What was measured first

Five core SymPy test files (arithmetic, expr, simplify, complexes, limits),
88 s of tests, instrumented at the property level:

| Measure | Value |
|---|---|
| `is_*` property accesses | 6.07 M |
| ... reaching the compute path `_ask` | 250 k (4 %) |
| `_eval_is_*` handler invocations | 1.44 M |
| Time inside `_ask` | 23.8 s (27 % of wall) |
| Share of that in `FactKB.deduce_all_facts` | ~30 % |
| New-system `ask()` calls | 4 |

Per query: an old cached hit is 0.09 us, an old uncached `_ask` averages
95 us, a new `ask()` with a handler hit is 230 to 380 us, `satask` is 2.2
to 3.2 ms. Of the new `ask()` cost, about 160 us is re-encoding the 105
known-fact clauses on every call.

Conclusions: the hit path is everything; the old system's propositional
part is cheap and its handlers' expression work is what costs; the new
system is slow for accidental reasons (re-encoding, SymPy Boolean CNF).

A second experiment replayed every query in `sympy/assumptions/tests`
through the SAT path with handlers disabled: 81 % agreement, no
contradictions, the gap half "bridge to old assumptions" and half missing
structural rules.

## 2. Design

```
rules.py       one rule base, old string syntax + new-system extras -> clause patterns
formula.py     P(pred, expr) atoms; And/Or/Not/Implies/Equivalent/Exclusive
compile.py     formulas -> integer clauses; VarTable allocates 33 variables per node
solver.py      incremental CDCL: add_clause any time, root propagation, implied(), solve(assumptions), entails()
engine.py      ObjectCache (the node's _assumptions dict), Session, demand-driven discovery, level-0 write-back
templates/     Symbol, numbers, Add, Mul, Pow, functions; pattern-cached; every rule has a soundness test
sympy_api.py   is_(), ask(), install()
```

Query path for `is_(expr, pred)`: cache hit in `expr._assumptions`, else
a fresh session visits the expression's cone (rule base, cached facts as
units, templates), propagates at root, writes every level-0 literal back
to the nodes, searches only if propagation is inconclusive. `ask(prop,
assumptions)` compiles the assumptions under a selector literal and reuses
the session while the assumptions stay the same, so nothing derived under
them reaches the cache.

Two things that did not pay off: a single global session (search cost grew
with everything asked before, fixed by cone-sized sessions) and two-phase
demand-driven instantiation (the classification walk cost as much as it
saved once templates were slimmed).

## 3. Results

Replay of 9230 recorded queries (`tools/compare.py`, templates only):

| Kind | Agree | Extra answers | None where SymPy answered | Wrong |
|---|---|---|---|---|
| old `is_*` (6343) | 94 % | 24 | 333 | 0 |
| new `ask` (2870) | 82 % | 16 | 508 | 0 |

Every extra answer was checked by hand. Five records are flagged for a
semantic choice: the engine raises on assumptions contradicting a symbol's
declared facts, SymPy trusts the assumption. Two SymPy findings on the
way: the old system says `(I**(3+I)).is_imaginary` is False (it is
`-I*exp(-pi/2)`), and `lra_satask` returns False for
`Q.positive_infinite(oo)`.

The 508 new-system misses: 152 matrix or custom predicates, about 40
relations, about 310 scalar template gaps (Pow 78, Add 55, Mul 34, exp 22,
log 19, acos 18, cot 12, sin/cos 12, constants' hermitian/antihermitian
units, re/im/Abs complex closure).

Benchmarks (pure Python):

| Query | SymPy | satassume |
|---|---|---|
| `ask(Q.positive(y + 1), Q.positive(y))` | 381 us | 57 us |
| `ask(Q.real(w*y), Q.real(w) & Q.real(y))` | 341 us | 48 us |
| `ask(Q.even(y + 1), Q.odd(y))` | 304 us | 48 us |
| `(p*q).is_positive`, fresh objects | 102 us | 962 us |
| `(u**2 + 1).is_zero`, fresh objects | 499 us | 1377 us |

Instantiating a node (33 variables, 105 rule clauses, 30 to 50 template
clauses) costs about 300 us, which is the whole context-free gap.

## 4. Comparison with `reasoning`

| | reasoning | satassume |
|---|---|---|
| Target | new system only | both systems |
| Per query | rebuild a ClauseDB, discover facts, solve | reuse a session; facts cached on the object |
| Rule base | vendored new-system known facts | one base pinned to the old strings, extended |
| Structural rules | SymPy's sathandlers (six rules for Add) | 35 to 50 clauses per Add, Mul, Pow, soundness-tested |
| Solver | DPLL2-derived, IPASIR interface, theory hook | fresh CDCL with assumptions and `entails` |
| Relations, matrices | LRA theory, matrix facts | none |
| Validation | Hypothesis fuzzer, parity harness, CI against `ask` | corpus recorder and replay, per-template soundness tests |
| Measured | 1.4 to 1.7x over `satask` | 5 to 8x over `ask` (different harness) |

`reasoning` is the safer path into SymPy: it follows the `TheorySolver`
protocol of PR 30537, handles relations, and its fuzzer found real bugs.
satassume contributes three ideas `reasoning` lacks and that an
old-system replacement needs: root-level write-back to the object cache,
session reuse across queries under the same assumptions, and a single
rule base with a much larger, tested template set. The Rust core in
`reasoning` is a branch experiment and not part of the plan.

The two harnesses ask different questions, so the speed numbers are not
comparable; a shared case set would settle that.

## 5. Process notes

The prototype was built with little maintainer interaction. Two choices
made alone turned out wrong for the maintainer's purpose: a fallback to
the old `_eval_is_*` handlers (removed: it defeats the point of the
rewrite) and a scope covering both systems at once (the maintainer wants a
small scope finished well). One push went out with a failing test because
a pipe masked the exit code.

## 6. Recommended next step

Narrow the scope to `ask()` for unary scalar predicates on scalar
expressions, SAT-only. Definition of done: every such query in the corpus
answered identically or better than today, zero contradictions, faster
than `ask` on each, and `Predicate.register` kept as a way to add
clause-generating functions so the extensibility tests pass. Relations
and matrices return None from the engine and stay with the existing
SymPy path; that is scoping, not a fallback. The old-system replacement
remains the long-term goal and needs this slice first.
