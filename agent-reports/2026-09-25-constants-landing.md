# Agent report: constant queries answered without the assumptions (item 1, landed)

- **Date:** 2026-09-25
- **Status:** landed on `main` (`997e723`, review fix `58b6e39`); semantics
  change listed on issue #12.
- **Scope:** `satassume/sympy_api.py` (`_is_constant_proposition`, `_ask`),
  `tests/test_sympy_api.py`

## What changed

A proposition whose every predicate is built in (`PRED_INDEX` or a
relation) and whose every argument has no free symbols, is a number
(`is_number`) and holds no undefined function (`AppliedUndef`, also inside
`Integral`, `Sum`, `Subs`) is answered by the engine's context-free path;
the assumptions are not read. This is the owner's rule with the engine
version (tip of `constant-queries`, `1279626`); the old-assumption version
(`2a3b38a`, loses 23 gate2 answers) was not taken, and its helpers
(`_old_answer`, `_old_value`, the flag) were dropped.

## Review (Opus, adversarial, two rounds)

Round 1 found no wrong True/False, and two losses the gates do not cover,
both fixed in `58b6e39`:

- custom registered predicates on constants are known only through the
  assumptions: `ask(Q.nice(2), Q.nice(2))` went True -> None;
- `Integral(f(x), (x, 0, 1)).is_number` is True for an undefined `f`.

Accepted (the owner's one-path rule), on the issue:

- a query that assumes a constant fact the engine cannot decide loses it:
  `ask(Q.positive(E**pi - pi**E), Q.positive(E**pi - pi**E))`,
  `ask(Q.zero(Sum(1/n**2, (n, 1, oo)) - pi**2/6), <same>)`: True on `main`
  and in `sympy.ask`, None now;
- the same for values of a user `Function` subclass (`class g(Function)`),
  which is not an `AppliedUndef`: `ask(Q.positive(g(1)), Q.positive(g(1)))`
  True -> None;
- a constant query never raises for inconsistent assumptions:
  `ask(Q.prime(7), Q.composite(7))` is True (`sympy.ask`: False, it trusts
  the assumption); `ask(Q.positive(-2), Q.nice(-2))` with a custom `nice`
  implying positive is False instead of ValueError.

## Gates (local, reviewer's re-run on `58b6e39`)

| gate | result |
|---|---|
| suite | 1758 passed, 1 skipped, 3 xfailed, 1 xpassed, 2 failed (the known `test_shared_facts` pair, failing on `main` too: SymPy at the pin returns None for `(0**n).is_finite`) |
| `ab.py --allow-more-definite` | 428 new more definite (21 distinct propositions such as `Q.zero(pi)`), all agree with `sympy.ask`; 0 less definite; no error change (the stream has no raising query) |
| `gate2.py` | 0 changed |
| real-theory fuzz | 1,000 seeds each lra/euf/both, 0 mismatches |

Not timed on the Pi (a capability change; the reviewer's local ab showed
-1.5%, noise level).
