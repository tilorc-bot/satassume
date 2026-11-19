# HANDOFF sa-port-340: witness reasons: (0), (1), (2a) and the (3) simulation done; exact pi (2) not started in code; NOTHING IS LANDED

Stopped at the context budget. Branch port/witness-reasons (upstream origin/port/witness-reasons), worktree
~/sa-rust-ids-work/sa-port-340/wt in clone ~/dev/sa-port-19, from rust-slice 29c5a0db. Results so far:
rust-spike/slice/results/witness-reasons.md. Orion .so in the worktree: a956b034 (built here, no Rust change).

## Done

- (0) count probe and [138b] diagnostic: witness-reasons.md "(0)".
- (1) 1f6ddb5b: bar.sh [148], plant_count.py + bar_sum.py [146], witness.py FIRED + session report [147]. Checked on
  orion (table in witness-reasons.md).
- (2a): bound 19 of 82 dev (23.2%), 372 of 372 fuzz: (2) is NOT skipped. (2b): 0 of the no-rational-pair rows hold a
  pi. (3): best order +0.7% of the class on fuzz, -0.8% on dev: NOT implemented.

## Running detached at the handoff

tools340/barchk340.sh on pareto1 (shared lease, launched from orion under setsid). End markers:
orion ~/sa-rust-ids-work/sa-port-340/barchk-end.txt; pareto1 ~/sp19/sa-rust-ids-work/sa-port-340/barchk-end.txt
("END void V fired F": V must be 3, F 0). Read pareto1 ~/sp19/sa-rust-ids-work/sa-port-340-fired/sum.txt: the lines
"plant fired in the suite" (witness:single, witness:integer-half, term:mark-wrong-pattern, dispatch-nan-arg-on must
be > 0; convert:enc-int-no-sign "no counter"; witness:on "no plant"), "sa_solver loaded", and the plants table's
fired column for witness:single and witness:skip-own (> 0) and witness:on (0). Its BASE directory does not exist on
pareto1, so "against base" lines there mean nothing. Seen so far: the void bar's done.txt starts with VOID.
If a line is wrong, fix it in a new commit before anything else: the step lands under this bar.sh.

## Not done, in order

1. Read the barchk job (above); add its lines to witness-reasons.md "(1)".
2. (2) exact pi in satassume/witness.py, one commit. Design worked out, nothing written:
   - `bind` takes a seventh class, pi's (`type(S.Pi)`, by type only), from sympy_api.py:137.
   - `_PiPoly`: a tuple of rational coefficients, degree >= 1, never 0; a constant result goes back to a Fraction.
     Operators + - * with int/Fraction/_PiPoly, / by a non-zero rational, ** by an int >= 0 (a negative power of
     p(pi) is not in Q[pi]: undecided), ==, hash, < > through `_sign`; guards on degree and _MAX_BITS.
   - `_sign`: sum the bounds of c*pi**k over a rational enclosure LO < pi < HI (50 decimals truncated, and that plus
     1e-50; source in the code); L > 0 or U < 0 decides, else _Undecided.
   - `PI_TABLE`, 16 entries with one-line arguments: at a non-constant p(pi), algebraic False, rational, integer,
     even, composite, prime False, zero False, complex/extended_real/finite True, imaginary False, polar None,
     extended_negative/positive by `_sign`, eq by equal polynomials, lt by `_sign(b - a)`. ONE_WAY stays True (real).
   - Two-pass compile so a query without pi runs today's closures unchanged: `_term` raises a `_NeedPi`
     (_Undecided subclass) at a pi leaf when `q.pi` is False; `witnesses` then recompiles with `q.pi = True`, where
     `_pred` dispatches on `type(v) is _PiPoly`, `_term` uses a pi-aware power closure, and `_own` is pi-aware.
   - (2b) falls out of `_roots`: with Q[pi] values the secant root of x - pi/2 is pi/2. `_roots` must skip a
     denominator that is a _PiPoly; `_pools` must survive an undecided comparison in `sorted`.
3. (4) plants 755 pi-sign (in `_sign`), 756 pi-rational (PI_TABLE), 757 pi-enclosure (wrong bounds); kept tests in
   tests/test_witness.py that check returned witness points with the test's own exact enclosure (Machin's formula
   with alternating-series bounds), no SymPy evaluation. bar.sh: add 755-757 to the plant list in its header comment.
4. (5) gate, (6) S1, (7) bar and land, as the brief says. Rerun cnt340.py/ana340.py for the reasons table after.

## FILE:LINE MAP (1f6ddb5b)

- satassume/witness.py: bind :78; FIRED and _Plant :96-118; _Undecided :194; _integer :212; TABLE :220-252;
  TWO_WAY :261, ONE_WAY :283; _pred :294; _Query :324; _term :334 (the undecided leaf :378); _formula :381;
  _own :425; _HEAD/_TAIL :433; _roots :438; _pools :463; _holds :508; witnesses :532 (compile try block :540-545).
- satassume/sympy_api.py: bind call :137; the check's call :1136.
- rust-spike/slice/p1/bar.sh: socheck and the phase loop, just above `for ph in $PHASES`; penv :~95; fired().
- rust-spike/slice/p1/bar_sum.py: void lines after `build:`; the plants table; "plant fired in the suite".
- rust-spike/slice/plant_count.py: `_read` (one entry per plant kind).
- rust-spike/slice/session_live.py: `_write_report` (witness_plant_fired).
- results/tools340/: stage340.sh, go340.sh (staging and shared-lease launch), pc340.sh, s7n0-340.sh, barchk340.sh,
  cnt340.py (per-call rows: pi leaves, other undecided leaves, the search under five pool orders), ana340.py
  (inputs: sa-port-340/cnt sa-port-329/cnt sa-port-325/run3 sa-port-322/run-count
  sa-port-325/wt/rust-spike/slice/results/tools322, all under ~/sa-rust-ids-work), ana340-29c5a0db.txt.
- Staged tree of 29c5a0db with .so cad764d4 on both paretos: ~/sp19/sa-rust-ids-work/sa-port-340/tree-29c5a0db.
- Outputs on orion: ~/sa-rust-ids-work/sa-port-340/{pc340-29c5a0db,s7n0-340-29c5a0db,chk1,cnt}.

## Must stay in every report

Tested SHAs and .so hash (29c5a0db base, head 1f6ddb5b; pareto .so cad764d46471b1c6, orion a956b03496066671);
SLICE_WITNESS off by default and the unchanged path the default; no SymPy construction or evaluation at query time;
"exact" rests on 325's 14-predicate table plus (2)'s arguments (issue 247); the reasons table before/after; bar row
wall times; known base rows by id; S1 wall times from quiet-lease runs only (pareto1). The Rust port of the
per-call compile and pools follows this step and is not started.
