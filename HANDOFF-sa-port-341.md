# HANDOFF sa-port-341: witness reasons: (1') read, exact pi (2) and plants 755-757 (4) committed; gate (5), S1 (6) and the bar (7) NOT STARTED; NOTHING IS LANDED

Stopped at the context budget. Branch port/witness-reasons (pushed to origin), worktree ~/sa-rust-ids-work/sa-port-340/wt
in clone ~/dev/sa-port-19, from rust-slice 29c5a0db. Source head a0849b10 (this file and witness-reasons.md come after
it). No Rust change since 29c5a0db: `git diff 29c5a0db a0849b10 -- rust-spike/slice/solver_rs` is empty, and so is the
diff from 786410d. No job is running anywhere; nothing is staged on the paretos for a0849b10.

## Done (checked on orion only, test_witness.py + test_sympy_api.py + test_layering.py: 260 passed, switch off and on, Python backend)

- (1') barchk read: results/witness-reasons.md "(1')". Void bar exit 3, every plant row fired > 0. Nothing to fix.
- ecf2ff12, a bug in the landed check, switch on only: `_pools` called a symbol's own assumptions outside any handler,
  so `ask(Q.gt(p, 10**7), Q.integer(p))` with `p = Symbol('p', prime=True)` raised `_Undecided` out of
  `sympy_api._engine_ask` on 29c5a0db. Now the value is not proposed. One kept test. Not reached by any workload so far.
- 49e30f57, (2) exact pi, as HANDOFF-sa-port-340.md "Not done" item 2 designed it. Differences from that design:
  `_PiPoly` degree cap 16 (`_MAX_DEG`); roots are ordered by `_near` (the value at pi's lower bound) instead of
  catching an undecided comparison; `1/pi` and `sqrt(pi)` (pi to a negative or non-integer rational literal) are
  undecided at compile time, so no point is tried for them.
- a0849b10, (4) plants 755 pi-sign, 756 pi-rational, 757 pi-enclosure (`SLICE_WITNESS_PLANT`; bar rows
  `witness:pi-sign` and so on need no bar.sh change, only its comment was updated). test_witness.py under each, orion,
  one process: 11, 12 and 8 failed of 148; without a plant 148 passed.

## Not done, in order

1. (5) gate on a0849b10 against base 29c5a0db. The tools take a staging root, so stage and reuse them:
   - Stage as tools336/stage336.sh does, but under sa-port-341 and with no build: both SHAs take the venv .so
     cad764d46471b1c6 (orion copy ~/sa-rust-ids-work/sa-port-340/so/sa_solver-29c5a0db.so) on pareto0
     ~/sp19/sa-rust-ids-work/sa-port-341/s1/bench-SHA/tree, with `SHA` files, tools (tools328, tools336, tools340 flat
     in s1/tools) and s1/plug from orion ~/sa-rust-ids-work/sa-port-336/plug.
   - tools336/job336.sh ROOT NEW BASE (suite by id on/off/base via tools328/suite331.sh, pre336.sh, iv336.sh), then
     tools336/go336.sh's two comparisons (cmp329.py, ivcmp329.py). pre336.sh's plant list (two `for pl in` lines)
     needs `pi-sign pi-rational pi-enclosure` added: copy it to tools341/pre341.sh.
   - tools328/gate330.sh TREE OUT for the 20 workloads (ans328.py: answer_diff 0 in 40 rows).
   - The reasons table: tools328/cnt329.py and tools340/cnt340.py wrap `_pred(name)` and `_own(sym)` with one
     argument and copy `_pools`; with a0849b10 they must pass `*args` through (`_pred(name, table)`, `_own(sym, pi)`),
     and cnt340.py's pool simulation and self-checks no longer match (`sorted(..., key=_near)`). Write tools341/cnt341.py:
     wrap `witnesses` only plus the reasons wrappers with `*args`; record per call `q.pi`, certified, points tried.
     For "(2b) with and without": patch `witness._roots` in the tool to drop `_PiPoly` roots. Run at cap 32 and with
     SLICE_WITNESS_CAP=0, dev and fuzz, on orion (short). Before: 29c5a0db certifies 159 dev / 1060 fuzz at cap 32
     and 163 / 1491 uncapped; pi-class bound 19 dev, 372 fuzz (witness-reasons.md "(2a)").
2. (6) S1 on pareto1, one quiet lease: tools336/gos1336.sh, onlease336.sh, time336.sh take ONE SHA (B=/work/bench-$SHA).
   Write time341.sh with arms SHA:MODE-WITNESS (29c5a0db and a0849b10; py and rust; on32 at both, off at both), dev and
   fuzz, 12 rounds; and, per the planner, budget and wiring off against on at both SHAs, 12 rounds (qt195.py takes any
   workload name). Bench staging on pareto1 ~/sa-rust-ids-work/sa-port-341/s1/bench-SHA: copy sympy, evalbench, data
   and the bench .so 0982a28074215658 from ~/sa-rust-ids-work/sa-port-336/s1/bench-786410d (source-equal crate), tree =
   git archive, then the compileall step of tools336/build336.sh for BOTH trees (arms run with
   PYTHONDONTWRITEBYTECODE=1). dev and fuzz runs take about 4 s each there.
3. (7) bar with this step's rows (tools336/gobar336.sh, job336bar.sh as the pattern): PLANTS and SUITE_PLANTS with
   witness:on, witness:pi-sign, witness:pi-rational, witness:pi-enclosure (plus witness:single as the known-good
   row). Expect the three pi plants caught by their suite rows (kept tests) with fired > 0; on the dev and fuzz
   workload rows a MATCH is possible (the engine answers None where a wrong pair is made), so the suite row is the
   catch. Then land (bar.sh land, then PUSH=1) and fix witness-check.md's stale "pending" header in a results commit.

## FILE:LINE MAP (a0849b10)

- satassume/witness.py: bind :87 (seventh class pi); plants' comment :98-106; _Plant :111; _MAX_DEG :204;
  _Undecided :207; TABLE :233; the pi section from :305: (T) and (E) in the comment, _PI_N/_PI_D :321, _LO/_HI :323,
  _BAD_LO/_BAD_HI (plant 757) :326, _PiPoly :330, _poly :418, _sign :426 (plants 757 and 755 inside), _pi_rational
  (plant 756) :452, PI_TABLE :458; _pred(name, table) :497; _pi_pred :527; _NeedPi :533; _Query(pi) :537; _term :548
  (pi power branch :579, pi leaf :597); _PI :605; _pi_power :608; _formula :629 (rel :643, pred :647);
  _own(sym, pi) :673; _roots :687; _near :716; _pools :726 (sorted by _near :739, the own try/except below it);
  _holds :778; witnesses :802 (second compile at `except _NeedPi` :814).
- satassume/sympy_api.py: Pi import :126, bind call :137, the check's call :1136.
- tests/test_witness.py: escape test :315; _machin :335, enc :345; test_the_enclosure_holds_pi :356; PI_ROWS :366;
  table :380; ring :396; sign :418; own-enclosure points :434; (2b) :451; the three answer tests for plants 755-757
  :469, :475, :481; the 21 pi queries at the end of QUERIES.
- rust-spike/slice/p1/bar.sh: plant comment :35-36 and :99; penv :100 (witness:NAME is generic).
- Tools: results/tools336 (stage336.sh, job336.sh, go336.sh, pre336.sh, iv336.sh, gos1336.sh, onlease336.sh,
  time336.sh, build336.sh, gobar336.sh, job336bar.sh), tools328 (gate330.sh, suite331.sh, ans328.py, cmp329.py,
  ivcmp329.py, med329.py, qt195.py, wit328.py, cnt329.py), tools340 (cnt340.py, ana340.py).
- 340's barchk rows: pareto1 ~/sp19/sa-rust-ids-work/sa-port-340-fired/sum.txt and sa-port-340-void/.

## Must stay in every report

Tested SHAs and .so hash (base 29c5a0db, source head a0849b10, orion .so a956b03496066671; pareto venv .so
cad764d46471b1c6 and bench .so 0982a28074215658 are builds of the same crate source, not yet run on a0849b10);
SLICE_WITNESS off by default and the unchanged path the default; no SymPy construction or evaluation at query time;
"exact" rests on 325's 14-predicate table plus (2)'s arguments: (T) pi transcendental, (E) the 50-decimal enclosure,
proved again in the tests by Machin's formula (issue 247: SymPy evaluation is not ground truth); the reasons table
before/after (after: not measured yet); bar row wall times; known base rows by id; S1 wall times from quiet-lease
runs only (pareto1; none run yet). The Rust port of the per-call compile and pools follows this step and is not
started. OWED still open: a fired counter for the Rust walker's plants 670-674 ([150]).
