# Values at infinities, nan and poles

The soundness oracles of the test suite evaluate a node at concrete points
and check every template rule and every definite answer there. At finite
numbers they use SymPy's evaluation. Where an infinity, `nan` or a pole is
involved, they take the value from this table, not from what SymPy
evaluates to (#247: SymPy's evaluation is a candidate generator, never the
truth). Each row is justified by a definition, a limit, or a convention
written down in satassume's docs. `tests/_special_values.py` codes the table
(the comments name the rows), and `tests/test_special_values.py` checks the
examples of every row against SymPy.

## How the oracles use it

- A node is evaluated bottom-up. A node whose arguments are finite numbers
  and whose SymPy value is a finite number keeps that value.
- A node with an argument that is no finite number, or whose SymPy value is
  no finite number (a pole: `1/0`, `log(0)`, `gamma(0)`), gets its value
  from a row below.
- A special point that no row covers (`sin(oo)`, `gamma(0)`,
  `oo + oo*I`) keeps SymPy's value as a **candidate**. A rule or answer
  that is false only with a candidate value is reported as a candidate,
  apart from the unsound ones. It still fails the test, as a tripwire, and
  is triaged by an argument: add or fix a row, never by taking SymPy's
  value as right.
- Where a row and SymPy's value differ, `tests/test_special_values.py`
  lists the example with the argument (`DISAGREES`). A new disagreement
  fails there until it is triaged.
- In `tests/test_verify_soundness.py` an atom the oracle cannot decide, or
  decides only from a candidate value, is free. A refutation that holds for
  every value of the free atoms is a verdict; one that needs a particular
  value is reported as a candidate.

## Values

| row | value | facts |
|---|---|---|
| V1 | `nan`: no value (`oo - oo`, `0*oo`, `1**oo`) | every predicate False, but `finite`, `infinite` and `commutative` unknown (design.md, "Extended reals and `nan` in templates"; #189) |
| V2 | `oo`, `-oo` and the directed infinities `oo*u` (`u` a non-real unit, `oo*I`): the value of `t*d` as real `t -> +oo`, for a nonzero number `d` (`u = d/|d|`) | `infinite`; no complex number, so every predicate implying `complex` is False; `oo` and `-oo` are extended reals of their sign (`positive_infinite`, `extended_positive`, `noninteger`, ...), `oo*u` is no extended real |
| V3 | `zoo`: the one infinity of the Riemann sphere, no direction | `infinite`; every other predicate False (it is no extended real) |

`commutative` is True of every infinity (design.md, "Non-commutative
symbols"). `polar` is not stated. Two directed infinities are equal when
their directions are; `zoo` is unequal to `oo` and `-oo`, and is not
compared with a directed infinity off the real line.

## Rows

Every row holds for any order of the arguments of `Add` and `Mul`.

| row | node | value | why |
|---|---|---|---|
| N1 | any function, `Add`, `Mul`, `Pow` with a `nan` argument | `nan` | nan is no number, so a function of it has no value (design.md; #189) |
| A1 | an infinity of direction `d` plus finite numbers | the same infinity | `t*d + c` has direction `d` as `t -> oo`: a finite summand does not move an infinity (`oo + I` is `oo`) |
| A2 | infinities of directions `d1`, `d2`, ... | `nan` if two of them are opposite (`oo - oo`); else the same infinity if all directions are equal; no row otherwise | the limit of `t*d + s*d`; `t - s` has no limit as `t, s -> oo` independently |
| A3 | `zoo` plus finite numbers; `zoo` plus another infinity | `zoo`; `nan` | on the Riemann sphere `oo + c = oo` for finite `c`, `oo + oo` is undefined |
| M1 | `0` times an infinity | `nan` | the indeterminate form `0*oo` |
| M2 | nonzero finite numbers (product `c`) times directed infinities `oo*d1`, ... | the directed infinity of direction `c*d1*...` (`-2*oo = -oo`, `I*oo = oo*I`) | `|t*s*c*d1*d2|` grows without bound with a fixed direction |
| M3 | `zoo` times nonzero numbers or infinities | `zoo` | its modulus grows without bound, no direction |
| P1 | `0**e`, `e` real negative | `zoo` | the pole of `x**e` at 0; `1/0 = zoo` (design.md) |
| P2 | `b**0`, `b` any value but `nan` (`oo**0`, `zoo**0`, `zoo**0.0`) | `1` | the empty product; `0**0 = 1` (design.md); `0.0` is the number 0 |
| P3 | an infinity `b` to a real finite nonzero `e` | `0` for `e < 0`; for `e > 0`: `zoo` for `b = zoo`, else the directed infinity of direction `d**e` (`(-oo)**2 = oo`, `(-oo)**3 = -oo`, `sqrt(-oo) = oo*I`) | `(t*d)**e = t**e * d**e` for real `t > 0` and real `e`, principal branch |
| P4 | a finite `b` to `oo` or `-oo`, `|b| != 1` | the limit of `b**t` as real `t -> +oo` (or `-oo`): `0` where `|b**t| -> 0`; where it grows, `oo` for `b > 0` and `zoo` otherwise (`(-2)**oo = zoo`, `(-3/2)**(-oo) = 0`, `(-1/2)**(-oo) = zoo`); `0**oo = 0`, `0**(-oo) = zoo` | `|b**t| = |b|**t`; for `b` not positive the argument `t*arg(b)` turns, so the only limit of a growing modulus is `zoo`; `0**t = zoo` for every `t < 0` (P1) |
| P5 | `b**oo`, `b**(-oo)` with `|b| = 1` (also `1.0`) | `nan` | `b != 1`: `b**t` turns on the unit circle, no limit. `b = 1`: a convention, not a limit (`1**t = 1` for every `t`): the indeterminate form `1**oo`, as SymPy and the templates' comments write it (`templates/core.py`: "`1**oo` is nan"); see "Choices" |
| P6 | an infinity `b` to `oo` or `-oo` | `0` for `-oo`; for `oo`: `oo` if `b = oo`, else `zoo` | `|b**t| = |b|**t`; the argument of `(-s)**t` turns |
| F1 | `exp` of an infinity | `oo -> oo`, `-oo -> 0`; `oo*d -> zoo` for `re(d) > 0`, `0` for `re(d) < 0`, `nan` for `re(d) = 0`; `zoo -> nan` | `|exp(t*d)| = exp(t*re(d))`, its argument `t*im(d)` turns; `exp` has an essential singularity at infinity |
| F2 | `log` of a directed infinity; `log(0)`, `log(zoo)` | `oo` (`log(-oo) = oo`); `zoo`, `zoo` | directed: `log|z|` grows without bound and `arg(z)` stays bounded, so the direction is 1 (A1). `log(0)` and `log(zoo)`: satassume's documented convention (`templates/exp_log.py`: "`log(0) == zoo`", "`log(zoo) == zoo`"), not a limit; see "Choices" |
| F3 | `Abs` of an infinity | `oo` | `|z|` grows without bound |

A node at a special point that no row covers has no table value: its SymPy
value is a candidate (see above).

## Where SymPy differs

`tests/test_special_values.py::DISAGREES` lists the examples with their
arguments. At SymPy 1.14:

- `oo + I` (A1): SymPy keeps `oo + I` and calls it no extended real.
- `zoo**0.0` (P2): SymPy gives `nan`, but `zoo**0 = 1`.
- `(-3/2)**(-oo)` (P4): SymPy gives `nan`, but `(-2)**(-oo) = 0` (#240).
- `(-1/2)**(-oo)` (P4): SymPy gives `nan`, but `(-2)**oo = zoo` (#97 P6).
- `(2*I)**oo` (P4) and `I**oo` (P5): SymPy leaves them unevaluated.
- `(-oo)**oo` (P6): SymPy gives `nan`, but `(-2)**oo = zoo`.
- `zoo**oo` (P6): SymPy gives `0`, but `zoo**2 = zoo` and `2**oo = oo`.

## Choices

A1 (with F2) is a convention between two consistent ones. Directed
infinities, as here: a finite summand does not move an infinity, so
`oo + I = oo` and `log(-oo) = oo` (`log(-t) = log(t) + I*pi`, direction 1).
SymPy's `oo + I` instead keeps the imaginary part, so `oo + I` is no
extended real; then `log(-oo)` would be no extended real either, and the
`log` rule "an infinite extended real argument makes `log` extended
positive" (`templates/exp_log.py`, which writes `log(-oo) == oo` after
SymPy) would be unsound at `-oo`. SymPy itself mixes the two (`oo + I` no
extended real, `log(-oo) = oo`).

Two rows follow satassume's documented conventions rather than a limit:

- P5 at `b = 1`: `1**oo` has no value, although `1**t = 1` for every `t`.
- F2 at 0 and at `zoo`: `log(0) = log(zoo) = zoo`. By the limit with the
  directions of A1, `log(0)` would be `-oo` (`log|z| -> -oo`, `arg(z)`
  bounded) and `log(zoo)` would be `oo`. With `log(0) = -oo` the `log` rule
  `zero(x) -> ~extended_real(log(x))` (`templates/exp_log.py`) fails at
  `x = 0` (3 failures in `test_templates.py`).
