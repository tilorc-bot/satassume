# HANDOFF sa-port-344: (5) and (6) read, written and committed; the bar (7) is RUNNING DETACHED on bfceccc9, unread; NOTHING IS LANDED

Stopped at the context budget, with the bar about 85 minutes from its end. Branch port/witness-reasons (pushed),
worktree ~/sa-rust-ids-work/sa-port-340/wt in clone ~/dev/sa-port-19, from rust-slice 29c5a0db. No source or test
changed in this session: results and tools only.

## Commits of this session (on bfceccc9)

- afda54b4 witness-reasons.md "(5) the gate on dfb544e6 and on 01e8ca74, read": clean. Against base: 47 new ids, the
  state inventory test (fixed by e2088c05: 377 passed on the head, python and rust, off and on, orion) and the known
  planted-history test (also failed on Python in the gate's patch row: tools344/rep344.sh shows the base fails it at
  the same rate, 2 of 12, keep-alive 48 of 48). Certified at cap 32: dev 159 -> 173, fuzz 1060 -> 1284.
- 2c7670c9 witness-reasons.md "(6) S1 ... (a), (b), (c)": the landing rule holds (head against base on: dev +0.7% /
  +0.6% within the spread, fuzz -7.0% / -2.6% faster, budget and wiring within). tools344/.
- this commit: the handoff.

Found: tools343/pc343.py (and cx343.sh) wrap Engine.ask and Engine._within_budget without `witness.accept`, so the
check's P1 guard (witness.py:841) certified nothing in their py rows. tools344/pc344.py registers the wrappers; (a)
and (b) use its rows (~/sa-rust-ids-work/sa-port-344/cx, s1/timing-pc from quiet lease b5a7cd65).

## Running, detached

`tools344/gobar344.sh bfceccc9 cad764d46471b1c6` (orion, setsid), started 17:16Z 19 Nov: pareto0, shared lease
096a1000, job344bar.sh: frozen branch origin/bar/witness-reasons-bfceccc9, clone pareto0 ~/sp19/dev/sa-port-344,
.so cad764d46471b1c6 (checked before the phases: bar/build.txt), BASE ~/sp19/sa-rust-ids-work/sa-port-337/bar/suite,
rows `witness:on witness:pi-sign witness:pi-rational witness:pi-enclosure` as PLANTS and SUITE_PLANTS, phases
`tests suite live plants extra suiteplants fmrows sum`, N=6. tests ended 17:18Z exit 0, suite 17:20Z exit 0
(pareto0 ~/sp19/sa-rust-ids-work/sa-port-344/bar/phases.txt). 337's bar with six rows took 88 minutes.
End marker: orion ~/sa-rust-ids-work/sa-port-344/gobar-end.txt (`END rc <pareto0's bar-end line>`), written after
the bar's small files are copied to orion ~/sa-rust-ids-work/sa-port-344/bar/. pareto0's own marker is
~/sp19/sa-rust-ids-work/sa-port-344/bar-end.txt (`END 0 ... cad764d4 bfceccc9`, then WATCHER-END).

## Not done, in order

1. Read the bar as sa-port-339 read 786410d's (witness-check.md section 12, :569 on): phases.txt all exit 0, the
   sum phase's table, the plain suite against BASE by id (expected new or changed: the ids of 29c5a0db's test-only
   commits and this step's 47 in tests/test_witness.py; the known base rows are in witness-reasons.md section (5)),
   the four step rows on the workloads (witness:on equal to Python under the switch and to Python off;
   pi-sign DIFFER on fuzz only; pi-rational and pi-enclosure MATCH on the workloads, caught by their suite rows:
   test_witness.py 10 and 9 failed), env-summary.txt (each row's SLICE_WITNESS variables), row wall times.
   The planted-history test: a28c548's method each time it shows (section (5) has this SHA's tables).
   Anything that needs a code or test change: Status: question.
2. witness-reasons.md: a section "(7) the bar" with the rows and wall times, and line 1's "IN PROGRESS, NOTHING
   LANDED" and the header paragraph (:3-11) brought up to date. witness-check.md:3 says "NOT LANDED when this was
   written": it landed as 29c5a0db (11:26Z 19 Nov, sa-port-339); fix that header in the same results commit.
3. Land: in the worktree `bash rust-spike/slice/p1/bar.sh land bfceccc9` (rebases on origin/rust-slice, prints the
   guard: files under satassume/ or rust-spike/slice/ outside results/ that differ from bfceccc9 must be none), then
   `PUSH=1`. rust-slice was 29c5a0db at 17:15Z. Report the landed SHA and tell the architect rust-slice moved.

## FILE:LINE MAP (this commit)

- rust-spike/slice/results/witness-reasons.md: line 1 and :3-11 the stale header; sections "(5) the gate ..." and
  "(6) S1 ..." near the end (rg "^## sa-port-34"); "Owed, named here" last.
- rust-spike/slice/results/witness-check.md: :3 the stale "NOT LANDED" header; section 12 :569 (how a bar was read).
- rust-spike/slice/p1/bar.sh: land :50-77 (the push guard :59-70); penv :100 (the witness rows).
- rust-spike/slice/results/tools344: gobar344.sh, job344bar.sh (the bar); pc344.py, pc344.sh, onlease344.sh,
  cx344.sh, go344.sh, pcsum344.py (pc-sum.txt), hv344.py (hv-*.json), rep344.sh (rep-sum-patch-row.txt), cx-counts.md.
- satassume/witness.py: GUARDED :131, accept :137, _patched :148, _pools :714, _holds :763, witnesses :787 (the
  guards asked last :839-842). satassume/sympy_api.py: the check :1136. satassume/engine.py: _within_budget :1814,
  _over_budget :1860, Engine.ask :2203 (the over-budget path :2225-2235).

## Must stay in every report

Tested SHAs and .so: base 29c5a0db; gate and S1 on 01e8ca74 (source c4d6e92c); the bar on bfceccc9 (= 01e8ca74 plus
harness/state.py e2088c05, tools and handoffs); pareto venv .so cad764d46471b1c6, bench .so 0982a28074215658, orion
.so a956b03496066671; no Rust change since 29c5a0db. SLICE_WITNESS off by default and the unchanged path the
default. No SymPy construction or evaluation at query time. "Exact" rests on 325's 14-predicate table plus (2)'s
arguments: (T) pi transcendental, (E) the fixed 50-decimal enclosure (issue 247: SymPy evaluation is not ground
truth). The reasons table before/after at cap 32: dev 159 -> 173, fuzz 1060 -> 1284 (uncapped by 342's rows: 163 ->
177, 1491 -> 1819). Bar row wall times: none yet. Known base rows by id: section (5). S1 wall times from quiet
leases only (pareto1): section (6). The Rust port of the per-call compile and pools follows this step and is not
started. OWED: [150] open; [151] fixed only on this branch until it lands; harness/state.py (shared) changed by
e2088c05; _PiPoly's order comparisons (witness.py:404-414) reached only by a test; new: pc343.py/cx343.sh rows void
for certified calls; the budget test before the check and a bound on points times size ((c)), not started.
