# REPORT: can LRA branch and bound be made path independent? (sa-bb-1, for Tilo)

sa-bb-1, 2026-11-03. Branch `bb-budget` from 9bafaa5. No lra.py change and no PR. Scripts are
in `bb-tools/`. All runs are on orion, in cold processes, with sa-eval's harness and SymPy pin
and PYTHONHASHSEED=0. Every count below is deterministic; there are no timings.

**Question** (from REPORT-lrashare.md): can whether a check exhausts the branch budget be
made a function of the query's problem? That would let #119's exactness argument (database =
F + things entailed by F; a complete search answers F |= p) cover shared LRA sessions.

**Answer: not with a budget, and not cheaply.** Every exhaustion on every workload is a
problem whose LP relaxation is unbounded. Exactly half of the stream's exhaustions hide
integer conflicts that B&B can never find. The other half are feasible problems on which the
DFS descends forever. Sharing becomes provably exact only with a *complete* procedure for
the integer fragment that satassume generates. Two cheap pieces of such a procedure (below)
remove 88-94% of the stream and battery exhaustions with identical answers. They are still
heuristics, though: what is left is not empty, so they do not give a proof.

## 1. The exhaustions

`exh_child.py` hooks `LRATheory._check`. For each check that exhausts, it dumps the asserted
problem (bounds, slack forms, integrality literals, disequalities), probes each integrality
variable's LP range (is `v >= 1e40` or `v <= -1e40` feasible?) and reruns B&B on a deep copy
with a budget of 200, then 2,000, then 20,000 nodes. The hook does not change answers: the
fuzz answers are byte-identical to 9bafaa5's. `truth.py` decides each dump with z3, offline
only, with π boxed to 9 digits. `proto.py` rebuilds each dump as a standalone LRATheory; all
of them exhaust again there.

| workload | exhaustions (queries, distinct problems) | term vars | int atoms / diseqs | LP-unbounded int var | decided with 20,000 nodes | with π | z3: sat / unsat / unknown (20 s) |
|---|---|---|---|---|---|---|---|
| stream | 50 (49, 33) | 1-2 | 2-4 / 2-5 | **50/50** | 1 (int point) | 0 | 23 / 14 / 13 |
| battery | 48 (46, 33) | 1-2 | 2-4 / 2-5 | **48/48** | 1 (int point) | 0 | 24 / 19 / 5 |
| fuzz 424242 | 277 (-, -) | 1-2 | 2-6 / 2-9 | 277/277 | 4 | 46 | (stopped; slow) |
| ho-fuzz | 221 (165, 175) | 1-2 | 2-6 / 2-8 | 219/221 | 3 (2 bounded: conflict) | 28 | – |

The stream and battery exhaustions fall into exactly two classes:

- **A. Lattice-unsat (stream 27, battery 24): exactly the dumps with a negated integrality
  literal.** The negated form lies in the Z-affine span of the asserted positive integrality
  forms, after substituting the pinned terms. Examples:
  - q14241: `n > 0`, `n ∈ Z` and `n ∉ Z`. These are two literals with the same form, and B&B
    climbs `n = 1, 1+δ, 2, ...` forever.
  - q13560: `a = 0`, `b ∈ Z`, `a + b ∉ Z`.

  This test (`proto.py: lattice_conflict`) fires on every z3-unsat dump and on every dump z3
  timed out on, and on no z3-sat dump. These are real integer conflicts that 9bafaa5 cannot
  find at any budget.
- **B. Feasible, with B&B descending (stream 23, battery 24).** For example q13439: `a < 0`,
  `b < 0`, `a - b > 0`, all integral, with disequalities (a=-1, b=-2 is a solution). The
  slack `a - b` sits on its strict bound δ, so each `<= floor` branch on one variable drags
  the other along: a=-δ, then b=-1-δ, a=-2+δ, b=-2-δ, and so on, all the way to the budget.
  The `>=` side would succeed at once.

The fuzz sets have the same two classes plus a third: negated integrality on an unbounded
variable (for example `x < -1`, `x ∉ Z`, `2x ∉ Z`, `x - y ∈ Z`), where B&B splits `x < n` /
`x > n` without end.

**Are any genuinely unbounded?** Yes. In the LP relaxation, 594 of the 596 have an unbounded
integrality variable. Most are integer-feasible, and those that are not are refuted by
lattice reasoning, not by bounds.

## 2. The designs

**(a) No budget where termination is guaranteed (bounded problems), a budget elsewhere.**
It covers 2 of 596 exhaustions (2 ho-fuzz problems that a larger budget refutes). The
"elsewhere" set is everything else, and 49 of 50 stream exhaustions still exhaust at
20,000 nodes. **Refuted by the numbers.**

**(b) The budget made a function of the constraint set (deterministic B&B from a canonical
state per check).** This is not enough for path-independent answers. CDCL returns UNSAT iff
every full assignment S of the clause database is refuted, either by T(S) or by a learnt
clause. A learnt lemma C (valid, from another query or another branch) can prune an S whose
own check T(S) exhausts. A fresh session with a different trail can reach that S before the
lemma exists, take the exhausted "sat" and answer None. So outcomes differ even though T is
a function of S. This is exactly the observed effect: the shared session, already holding
earlier lemmas, does not exhaust where the fresh one does.

What is sufficient: an upward-closed family W of "inconsistent" literal sets such that
1. every conflict or explanation the theory produces lies in W, and
2. the check on a full assignment decides membership of W exactly.

Then DPLL(T) computes "F is W-unsat", and that is a function of F. A node budget breaks
condition 2, and budgeted B&B is not monotone, so neither W = "B&B conflict within budget"
nor its upward closure is decided by any cheap check. **Refuted by argument.**

**(c1) Static guard: share an LRA session only if no integrality atom is registered** (and
its constants are `certified`). This is provable, because the check is then a decision
procedure: simplex plus the disequality argument, with no B&B and no give-up. Run with
lrashare's switch-ON tree (`guard_child.py`), it keeps **0 of 612** stream and 0 of 678
battery theory-session hits: every LRA session registers integrality atoms. **Provable but
worthless.**

**(c2) Lattice test + derived-integral slacks branched first.** These are two pieces of a
complete procedure. Prototype: `patch_child.py`, monkeypatched into fresh sessions (9bafaa5
semantics, no sharing), with coarse but sound explanations.
- In `_check`, before B&B: a negated integrality literal whose form lies in the Z-affine span
  of the positive ones (pinned terms substituted) is a conflict. The span test is an integer
  echelon form of 2-6 short vectors.
- Every bounded or disequality slack whose form lies in that span becomes an integrality
  literal, ahead of the asserted ones in B&B.

| workload | exhaustions 9bafaa5 → prototype | lattice conflicts | answers vs 9bafaa5 |
|---|---|---|---|
| stream | 50 → **6** | 27 | identical (16,232) |
| battery | 48 → **3** | 24 | identical (16,386) |
| fuzz 424242 | 277 → 98 | 272 | 1 more definite (3,000) |
| ho-fuzz | 221 → 65 | 284 | identical (3,000) |

On the rebuilt dumps, derived-first decides every class-B problem in 2-4 nodes, and the
lattice test decides every class-A one. Engine runs still leave exhaustions, because the new
paths reach new problems. The 6 stream and 3 battery leftovers are again feasible and
descending, now through a derived slack or a negated split. Examples:
- stream: `a < 0`, `a ∉ Z`, `b ∈ Z`, `b < 0`, `a - b > 0`, `a - b ∉ Z` (b=-1, a=-1/2);
- battery: `n < 0`, `k > 0`, both integral, with disequalities (n=-1, k=1).

Rounding the strict bounds of integral and derived-integral variables before branching
("tighten" in `proto.py`) decides 22 of 23 class-B dumps at 0 nodes, so a third tweak would
probably reach 0 on the stream. A fourth would then be needed on fuzz. That is heuristic
chasing, and it can never close the argument: B&B on an unbounded problem is not a decision
procedure. Cost: the prototype is about 50 lines plus about 35 for the span test, above the
60-line bar. The span test runs on every check that has integrality literals: 908 of 3,645
stream checks reach it. Timing was not measured; a pinned A/B is not worth it for a design
that does not deliver the proof.

**(c3) A complete procedure for the fragment.** The fragment is: real terms; linear bounds
(strict and non-strict); disequalities; `m*form + k ∈ Z` and its negation. The problems are
tiny (1-2 term variables here). Mixed real/integer linear arithmetic with these atoms is
decidable. The known complete methods are:
- Bromberger's reduction of unbounded mixed problems to bounded ones ("A Reduction from
  Unbounded Linear Mixed Arithmetic Problems into Bounded Problems", IJCAR 2018), after which
  B&B terminates;
- an Omega-test-style elimination with lattice (Hermite) handling of the integrality atoms
  and a real shadow for the real parts.

With such a procedure, W is the integer theory itself: checks are exact, so the answer is a
function of F, and #119's argument covers shared LRA sessions. Cost: several hundred lines
and a new decision procedure in lra.py. Its answers would also differ from 9bafaa5's
wherever a class-A conflict is reachable: they become more definite (1 in 6,000 fuzz queries
with the c2 prototype, 0 on the stream and battery). That needs forward-chain-3b's OK, and
the readability cost is Tilo's call.

**(c4) A small-model box instead of a node budget** (B&B confined to |x| ≤ M, with M a
function of the atoms). This would be sound and complete, but M would be a
Papadimitriou-type bound, (m·a)^(2m+1), and the class-B descent walks the whole box. Bounded
in theory, a hang in practice. Rejected.

## 3. Recommendation

1. **Do not claim exactness for shared LRA sessions.** Ship the theory-free half (provable)
   as planned. If Tilo wants the extra 1.37x→1.42x on None queries, the LRA half can only be
   taken as an empirical result. Its hazard is now precisely characterised: with lrashare's
   drop-on-exhaustion rule, a shared answer can differ from a fresh one only when the fresh
   session exhausts and the query is entailed (shared definite, fresh None). It can never
   flip, because every conflict is sound and a non-exhausted sat is a real integer model.
2. If a provable path is wanted, the only one is (c3): a complete integer procedure for this
   fragment. It is a project of its own, not a budget tweak. (c2) is a natural first slice of
   it (lattice conflicts are its equality and congruence step). Even on its own, (c2) cuts
   stream exhaustions 50→6 with identical answers, which shrinks the empirical hazard in
   point 1 by about 8x. It needs a pinned A/B and a cleaner implementation (incremental span,
   tight explanations) before it is worth a PR.
3. Side observation, not investigated: 5 fuzz and 2 ho-fuzz dumps conflict already at
   assert time when rebuilt standalone. That is probably my rebuild registering scaled
   Integral forms differently, but it could also be an order dependence of the rounded-bounds
   check.

Data: per-exhaustion dumps and ground truth are in
/tmp/claude-1000/-home-tilo-dev-satassume/f1d7341c-bd17-441e-9a56-dcc729cb3820/scratchpad/bb/out-base/
(`*.jsonl`, `*.truth.jsonl`, `*.proto.jsonl`). The prototype's answers and leftover dumps are
in `out-patch2/` and `out-patch3/` there. To reproduce:
`CHILD=patch_child.py MODE=latds bb-tools/drive.sh ~/dev/sa-bb OUT stream battery fuzz:424242 ho-fuzz`.
`proto.py` and `patch_child.py` import each other's helpers, so run them from one directory.
