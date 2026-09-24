# satfix report: satassume must not use SymPy's `_assumptions` (plan step 1.1)

Branch `satassume-shared-facts`, from `origin/main` at `07e0bd5`.

## Defect

Reproduced on `main`: after `(0**n).is_finite` (True, cached by SymPy),
`satassume.sympy_api.ask(Q.positive(0**n), Q.negative(n) & Q.nonnegative(x))`
raised "inconsistent assumptions", and afterwards `Symbol('fresh').is_negative`
was False.

Chain:

1. SymPy: `Pow._eval_is_algebraic` returns True when the base is zero (or
   one) without looking at the exponent; old-system rules give algebraic ->
   complex -> finite, so `(0**n)._assumptions` holds `finite: True`.
2. satassume's default cache `ObjectCache` used `node._assumptions` as its
   store. `Session.node` asserted every non-None entry as a unit clause, so
   SymPy's handler output became an unconditional fact. With the Pow
   template (zero base, negative exponent -> infinite), root propagation
   derived `~negative(n)`, and the assumptions were declared inconsistent.
3. `Session.writeback` stored that root fact through `ObjectCache.put` into
   `n._assumptions`. For a `Symbol` that dict is the `StdFactKB` returned by
   the `@cacheit` `Symbol._canonical_assumptions`, shared by every symbol
   created with the same assumptions. The copy-on-write in `put` only
   covered `default_assumptions`, not this shared dict.

## Fix (design principle)

The engine never reads or writes SymPy's per-object `_assumptions`.

* SymPy objects enter the engine only through the templates: the
  assumptions a `Symbol` was declared with (`assumptions0`) and the
  old-system properties of fixed-value constants (numbers, `pi`, `oo`, ...).
  I checked the templates: SymPy `is_*` properties are read only on
  constants.
* Context-free facts the engine derives (root-level trail, never under a
  query's assumptions) go into an engine-owned `DictCache` keyed by the node.
  Structurally equal nodes share entries. That is sound because a node's
  context-free facts depend only on its structure and declared assumptions.
* `ObjectCache` is now an alias of `DictCache`, so existing imports keep
  working. `Engine()` defaults to `DictCache()`.

The principle is documented in the `DictCache` docstring
(`satassume/engine.py`), in README "How it answers" and in PLAN.md. PLAN.md
also notes that a later per-object cache (for the old-system replacement)
must hold only engine facts and must copy before its first write on every
shared dict.

## Cost

Measured with `~/bin/bench-container`, image `benchmark-sympy:local`, CPU 10.
Both caches ran on the same engine code in one process, in alternating
order, 12 runs each plus warmup, with fresh symbol names per run. Medians:

| workload | old ObjectCache | DictCache |
|---|---|---|
| contextual: 8 `tools/bench.py` cases x 200 | 0.1079 s | 0.1076 s |
| `is_` repeated (cache hits), 10 exprs x 6 preds x 200 | 0.0268 s | 0.0272 s |
| `is_` first answers, 20 fresh engines | 0.4378 s | 0.4333 s |

The min/max ranges of the two caches overlap in every row, so there is no
measurable cost. `tools/bench.py` itself already used `DictCache`.

## Tests

New file `tests/test_shared_facts.py`:

* a cached SymPy fact does not make `Q.negative(n) & Q.nonnegative(x)`
  inconsistent (default engine and `Engine()`); `0**n` is infinite under
  `Q.negative(n)`; context-free `finite(0**n)` is None
* one ask does not change other symbols (`Symbol('fresh').is_negative is
  None`; plain-symbol KB unchanged)
* `is_` and `ask` leave `_assumptions` of compound nodes unchanged
* declared symbol facts are still used
* a subprocess runs 1,500+ asks over 21 expressions (`0**n`, `1**n`,
  `x**n`, `Pow(0, -1, evaluate=False)`, ...) under about 60 contexts, after
  SymPy has cached its own facts on all of them. It then checks 20 fresh
  symbols and the used symbols against a probe
* the SymPy side (`(0**n).is_finite is not True`) as a non-strict xfail

Six of these tests fail on `main` and pass on the branch.

Full satassume suite, one file per process, `--with pytest --with mpmath
--with hypothesis` (hypothesis is needed by five files):

* before (main 07e0bd5): 1594 passed, 4 xfailed, 1 skipped, 0 failed
* after: 1601 passed, 5 xfailed, 1 skipped, 0 failed (the 7 extra passes
  and 1 extra xfail are the new file)
* rough non-container wall time over all files: 96.4 s before, 91.2 s after.
  This includes the new file's 13.7 s; the rest is host noise in the fuzz
  files.

Corpus (`tools/compare.py queries.jsonl`, default engine):

* in scope: unchanged at n=2595, agree 2497, extra 16, none 70, error 5,
  wrong 0
* old-system records (informational) were 6041 agree / 30 extra / 272 none.
  They are now 6033 / 27 / 283, the same numbers as `--fresh-cache` gave on
  main. The difference was SymPy's own cached answers being read back.

`needs/test_checker_ask_poisons_plain_symbols.py` on `refine-identities`:
I applied the patch to an exported copy of that branch. Both satassume
tests pass there, including the refine one (`refine(sqrt(x**2), Q.even(x))`
is `Abs(x)` after the log refine). The remaining failure is the SymPy test,
which is not patched here. Once this is merged, the needs file can be
reduced to the refine check or deleted.

## Upstream SymPy issue (candidate, not filed)

Title: `(0**n).is_finite` is True for a symbol `n` without assumptions (`Pow._eval_is_algebraic` ignores the exponent)

```python
>>> from sympy import Symbol, Pow, oo
>>> n = Symbol('n')
>>> (0**n).is_finite, (0**n).is_algebraic, (0**n).is_complex
(True, True, True)
>>> (0**n).subs(n, -1)
zoo
>>> Pow(0, -1, evaluate=False).is_algebraic   # but .is_finite is False
True
>>> Pow(1, oo, evaluate=False).is_algebraic   # 1**oo is nan
True
>>> z = Symbol('z', zero=True); (z**n).is_finite
True
```

`Pow._eval_is_algebraic` starts with
`if self.base.is_zero or _is_one(self.base): return True` and does not look
at the exponent. `0**e` is `zoo` for negative `e` and nan for some
non-real `e`, and `1**e` is nan for infinite `e`. Through the old-assumption
rules algebraic -> complex -> finite, so `(0**n).is_finite` becomes True for
a plain `n`, although `Pow._eval_is_finite` itself returns None there. The
same unevaluated `Pow(0, -1)` reports `is_algebraic=True` and
`is_finite=False`, which contradict each other under those rules.

Suggested fix: for a zero base, return True only when `self.exp.is_extended_positive`
(then the value is 0), and False when `self.exp.is_extended_negative` (then
it is `zoo`). For a base equal to one, require `self.exp.is_finite`.
Otherwise return None.

## Not done / open

* No SymPy patch (as instructed).
* Merging into `main` and `refine-identities` is for the coordinator (steps
  1.1 merge, 1.2).
