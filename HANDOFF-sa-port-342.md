# HANDOFF sa-port-342: (ii) kept tests and the reasons table done; the gate's two jobs (5) are RUNNING DETACHED, unread; S1 (6) and the bar (7) NOT STARTED; NOTHING IS LANDED

Stopped at the context budget. Branch port/witness-reasons (pushed), worktree ~/sa-rust-ids-work/sa-port-340/wt in clone
~/dev/sa-port-19, from rust-slice 29c5a0db. Tested SHA of the gate: dfb544e6 (satassume source a0849b10, tests
ef0b1335). Later commits hold only tools342, results and this file. No Rust change since 29c5a0db.

## Done

- ef0b1335: two kept tests for the planner's (ii) (every raise of witness.py executed and caught; no source change,
  nothing new found). results/witness-reasons.md "sa-port-342" has the argument and the numbers.
- The reasons table before and after, cap 32 and uncapped, and (2b) with and without: witness-reasons.md, same section;
  rows in results/tools342/ana342-dfb544e6.txt (orion output ~/sa-rust-ids-work/sa-port-342/cnt/).
- Staged (tools342/stage342.sh, ~/sa-rust-ids-work/sa-port-342/staged.txt): pareto0 and pareto1
  ~/sp19/sa-rust-ids-work/sa-port-342/s1/bench-{dfb544e6,29c5a0db}/tree with .so cad764d46471b1c6, s1/tools, s1/plug;
  orion ~/sa-rust-ids-work/sa-port-342/tree-SHA and tools/ (flat; time342.sh, onlease342.sh, gos1342.sh, med342.py and
  qt342.py were copied in after staging and are on orion only until gos1342.sh sends them).

## Running, detached (started 14:17Z 19 Nov; nothing of mine waits on them)

- `go342.sh a dfb544e6 29c5a0db`: pareto0 shared lease, job342.sh. End markers: pareto0
  ~/sp19/sa-rust-ids-work/sa-port-342/job-dfb544e6/end.txt; orion ~/sa-rust-ids-work/sa-port-342/go-a-end.txt (after
  the copy back and the comparisons). Read: job-dfb544e6/suite-cmp.txt (suite by id on/off/base, both backends; the two
  new test ids are new against base), iv-cmp.txt (no moved id), pre/dig/dig.jsonl (dev and fuzz digests equal off/on,
  py and rust; DIFFER or MATCH per plant), pre/tw/*.log, pre/rep/rep-sum.txt.
- `go342.sh b dfb544e6 29c5a0db`: pareto1 shared lease, jobb342.sh. End markers: pareto1
  ~/sp19/sa-rust-ids-work/sa-port-342/jobb-dfb544e6/end.txt; orion go-b-end.txt. Read: jobb-dfb544e6/gate-SHA/answers.txt
  (GATE answers equal, 40 rows a tree), xans.txt (80 cells, head against base), fz.txt (last line `FZ rows equal on
  every run`; per SHA and kind the calls and certified counts; any DIFFER on dfb544e6 is Status: question, on 29c5a0db
  it is [151]'s reach). The big rows (*.jsonl, fz/*.json) stay on pareto1.
- Count the quiet catches (engine.py:1906) in the gate rows as earlier gates did, if the planner's list asks for it:
  not done here.

## Not done, in order

1. (5) read the two jobs above and add the rows to witness-reasons.md. A difference on the head: Status: question.
2. (6) S1 and budget/wiring, one quiet lease on pareto1, after job b has ended (a quiet lease waits for the shared one):
   `cd ~/sa-rust-ids-work/sa-port-342 && setsid nohup bash tools/gos1342.sh dfb544e6 29c5a0db > gos1.out 2>&1 < /dev/null &`
   It stages pareto1 ~/sa-rust-ids-work/sa-port-342/s1 (common/, bench-SHA/tree with the bench .so 0982a28074215658),
   compiles bytecode, runs timing-s1 (dev, fuzz) and timing-bw (budget, wiring): 8 arms SHA:MODE-WITNESS, 12 rounds
   each, and writes s1/med-s1.txt and s1/med-bw.txt (end marker gos1-end.txt). NOT YET RUN: time342.sh and
   onlease342.sh are syntax-checked only (arm parsing and med342.py were tried on made-up rows); check
   timing-s1/progress and err.txt after the first round. med342.py prints "BEYOND THE SPREAD" per comparison (rule in
   its docstring). Head against base slower beyond the spread anywhere: Status: question. On against off slower beyond
   the spread on budget or wiring: a finding to report, at 29c5a0db as well (orion sizing says it will show).
3. (7) the bar with this step's rows, then land: as HANDOFF-sa-port-341.md "Not done" item 3 (tools336/gobar336.sh and
   job336bar.sh as the pattern; PLANTS and SUITE_PLANTS witness:on, witness:pi-sign, witness:pi-rational,
   witness:pi-enclosure, plus witness:single). The landing head is the branch head; its source is dfb544e6's.

## FILE:LINE MAP (dfb544e6; satassume/witness.py and sympy_api.py as in HANDOFF-sa-port-341.md, unchanged)

- tests/test_witness.py: _raises :679; test_the_check_raises_only_its_own_undecided :691; _OtherNode :700; _escapes
  (one case per raise) :704; test_every_raise_of_the_check_is_caught_before_the_query_returns :735; the [151] test
  :315 region (+1 line: `import sys` at :4).
- satassume/witness.py try sites the argument names: witnesses :810-823; _roots :697-712; _pools :750-756; _holds
  :781-789. Raise lines: 214, 376, 388, 392, 399, 449, 504, 509, 512, 520, 582, 589, 592, 594, 599, 601, 615, 619, 622,
  624, 640, 646, 670.
- rust-spike/slice/results/tools342: stage342.sh, go342.sh (a|b), job342.sh, jobb342.sh, pre342.sh (pre336.sh plus
  plants 755-757), fz342.py, fzcmp342.py, xans342.py, cnt342.py, ana342.py, qt342.py (qt195.py plus budget and wiring),
  time342.sh, onlease342.sh, gos1342.sh, med342.py.
- harness/campaign.sh :25 QUERIES=300, :75-78 the hash seeds 0,1,2,42 (the planner's "seeds": campaign.sh uses them
  as hash seeds, so (i) runs seeds 0 1 2 42 under each of the four hash seeds).

## Must stay in every report

Tested SHAs and .so hash (base 29c5a0db, tested dfb544e6 = source a0849b10 + tests ef0b1335; pareto venv .so
cad764d46471b1c6, bench .so 0982a28074215658 not yet run on it); SLICE_WITNESS off by default and the unchanged path the
default; no SymPy construction or evaluation at query time; "exact" rests on 325's 14-predicate table plus (2)'s
arguments: (T) pi transcendental, (E) the 50-decimal enclosure, proved again in the tests by Machin's formula (issue 247:
SymPy evaluation is not ground truth); the reasons table before/after (above: certified dev 159 -> 173, fuzz 1060 ->
1283 at cap 32; 163 -> 179 and 1491 -> 1826 uncapped); bar row wall times (no bar yet); known base rows by id; S1 wall
times from quiet-lease runs only (pareto1; none run yet; the orion budget and wiring numbers are sizing). The Rust port
of the per-call compile and pools follows this step and is not started. OWED still open: [150] a fired counter for the
Rust walker's plants 670-674; [151] is fixed only on this branch until it lands.
