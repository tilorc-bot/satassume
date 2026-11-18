# None answers by class: counts, time and work (issue 323, read-only)

sa-port-322 and sa-port-323, 18 Nov 2026. Source measured: 5b1d96f, source-equal to rust-slice 5f53735.
**No package code changed.** The count build is a scratch patch (`tools322/count322.patch`, written by
`tools322/mkpatch322.py`) applied to a scratch copy on pareto1, never committed to the package or copied into 317's tree.
**Shares from shared-lease runs are not wall times**: every time below comes from the quiet-lease S1 rounds; the
shared-lease count passes give only counts, events and answers.

## What the numbers say

1. **None costs what its count predicts.** None is 44.9% of dev answers and 51.0% of dev time; 79.6% of fuzz answers and
   80.9% of fuzz time (both switches on; the default arm is within 1 point). A None that reaches the engine costs no more
   than a definite answer that does the same work: on fuzz a contextual None with its two polarity searches takes 2067 us,
   a contextual True or False that needed no entailment search at all takes 2108 to 2177 us.
2. **Nearly every None is class (i)**: the search found a model each way. Dev 679 of 892 (418 that reach the engine plus
   261 exact repeats of them), fuzz 2202 of 2387.
3. **Class (ii) is BRANCH_BUDGET only, and it is not an artefact of the budget's size.** Dev 2, fuzz 168. No answer and no
   event moves at 32, 64, 256 or 4096 (2x to 256x); the same 16 (dev) and 277 (fuzz) checks run out at every budget, and
   at 4096 the fuzz queries holding them take 2.9 times as long. Lower budgets do change events (11 fuzz rows at 4, 1 at
   8), so the comparison can see a difference. The discovery budget never fired.
4. **Class (iii) is routing only.** Dev 40 (32 matrix, 8 relation, repeats included), fuzz 13, all refused by
   `sympy_api` before the engine. No theory gave up, the catch at engine.py:1906 fired 0 times, and no non-commutative
   refusal reached the engine.
5. **The Nones that never reach the engine are cheap but not free.** Dev: 463 queries, 2.9% of time (42 us each; the
   355 exact repeats take 2 us each, the 89 repeats on the relevant part 190 us each). Fuzz: 15 queries, 0.1%.
6. So the planner's reading, "if they're cheap, the None cost is fuzz's polarity solves", does not hold: the polarity
   solves are not where a None's time goes. The 194 fuzz queries that raise at the set's check, before any entailment,
   already take 1630 us against 2067 us for a None. The cost is building the query's session and its one complete check, which
   every answer pays.

## Method

- **Events.** The count build appends one token per event to a thread-local string that the driver (`tools322/nc322.py`)
  takes after every query; the grammar is the docstring of `mkpatch322.py`. One cold pass per workload in recorded order
  (dev 1985 queries, fuzz seed 424242 3000 queries), on pareto1 under a shared lease, .so `7962cec7164e8a6a`.
  Passes: both switches on, both off, and BRANCH_BUDGET 4, 8, 32, 64, 256, 4096 (`lra_backend.py:130` reads the module
  global at every check, so no rebuild; answers recorded, not adopted).
- **Digests** equal 317's in every pass (dev `31cd0945c07f02a6`, fuzz `173502b6ef285ad6`). Events are equal row by row
  between both switches on and both off, so one classification serves both arms.
- **Times.** S1 under one quiet lease on pareto1 (CPU 2, `sa-eval-bench:1`, unprofiled .so `b18cc160be08e45d`), 12 rounds,
  arms `5b1d96f` (default) and `5b1d96f+rust+frames` (both switches on) interleaved and rotated, each run a cold process
  (`tools322/time322.sh`, `onlease322.sh`; end marker `END rc=0 2026-11-18T14:15:26Z`, 48 rows, empty error file). A
  query's time is the median over the 12 rounds of its own seconds; a class's time is the sum over its queries; shares are
  of the arm's summed medians. S1 wall, median (min to max): dev 0.7589 s (0.7497 to 0.7905) default, 0.6680 s (0.6619
  to 0.6992) both on; fuzz 6.3727 s (6.3228 to 6.4319) default, 5.9115 s (5.8363 to 5.9575) both on.
- **Classification** (`tools322/sum322.py`, whose docstring is the rule). The event string is parsed with a stack. The
  deciding frame is the query's last top-level frame when that is `Engine.ask` or `Engine.is_`; the deciding entailment is
  the last `Solver.entails` or `entails_all` directly under it. Every None with a deciding frame has result N in it
  (0 exceptions in 420 dev and 2368 fuzz queries).
- Full output: `tools322/sum322.out.txt`. Rows: orion `~/sa-rust-ids-work/sa-port-322/run-count/`,
  `~/sa-rust-ids-work/sa-port-323/run-bb/`, `run-plant/` and `timing-r1/`.

### Planted cases (each token shown to fire before its zero is read)

`tools322/plant322.py`, run on the count build with and without `SLICE_SESSION_PLANT=ctx-check-raise`.

| token | meaning | fires on | dev / fuzz |
|---|---|---|---|
| `B` | discovery budget (`Engine._over_budget`) | an engine with `discovery_budget = 1` | 0 / 0 |
| `N` | non-commutative refusal in the engine | `Engine().ask(P("commutative", A))`, `Engine().is_(A*B, "positive")` | 0 / 0 |
| `K` | the `_constructing` None of `Engine.is_` | a node put in `Engine._constructing` | 0 / 0 |
| `C`, `F` | the catch at engine.py:1906 and the fallback session | the planted check raise | 0 / 0 |
| `g` | LRA gave up | the set of tests/test_lra_constant_coefficients.py:398 | 0 / 0 |
| `xb` | a check ran out of BRANCH_BUDGET | BRANCH_BUDGET 0 and 1 | 16 / 277 |
| `T01` | the session's exhausted flag at the query's end | BRANCH_BUDGET 0 | 15 / 196 |
| `xs` | a split skipped beyond the certificate's bound | **not shown to fire** | 0 / 0 |

`xs` did not fire on seven attempts (integer-valued offsets of pi, sqrt(2) and pi/7, and bounds of 10^3 to 10^3000 plus
pi); Python's own test reaches it only by replacing `_certificate` (tests/test_lra_exhaustion.py:276). Its zero is
covered another way: the skip sets the same `exhausted` flag as the budget, and every query whose flag is set at a frame
end (15 dev, 196 fuzz) also holds an `xb` token, so no exhaustion in either workload comes from the skip alone.

`sympy_api` routes every non-commutative query away before the engine ("matrix"), which is why `N` reads 0 on these
workloads and fires only for a caller of the engine. `F` also fires without `C` when the set's check makes a theory give
up (the `g` plant), as design.md :663 describes. The existing counters `ctx:caught` and `ctx:fallback` are absent (0) in
both workloads.

## (a) Time by answer

| workload | answer | queries | share of answers | default: ms, share | both on: ms, share | us per query (both on) |
|---|---|---|---|---|---|---|
| dev | None | 892 | 44.9% | 377.9, 50.0% | 339.4, 51.0% | 381 |
| dev | False | 557 | 28.1% | 231.3, 30.6% | 201.4, 30.2% | 362 |
| dev | True | 536 | 27.0% | 146.1, 19.3% | 125.2, 18.8% | 234 |
| fuzz | None | 2387 | 79.6% | 5133.4, 80.7% | 4764.9, 80.9% | 1996 |
| fuzz | ValueError | 207 | 6.9% | 359.0, 5.6% | 324.0, 5.5% | 1565 |
| fuzz | False | 204 | 6.8% | 448.0, 7.0% | 415.2, 7.0% | 2035 |
| fuzz | True | 202 | 6.7% | 418.9, 6.6% | 387.8, 6.6% | 1920 |

The same split by the work a query did (both switches on, us per query; queries in brackets):

| work | dev None | dev False | dev True | fuzz None | fuzz False | fuzz True |
|---|---|---|---|---|---|---|
| contextual, entailment with searches | 799 (380) | 1069 (41) | 1232 (12) | 2067 (2257) | 2262 (130) | 2439 (98) |
| contextual, answered without an entailment search | - | 594 (200) | 539 (144) | - | 2177 (51) | 2108 (64) |
| context-free, entailment with searches | 311 (40) | - | - | 838 (111) | 1056 (3) | - |
| context-free, no entailment search | - | 242 (119) | 245 (115) | - | 347 (20) | 346 (40) |
| the set's check, then the memo | 447 (9) | 412 (5) | - | 843 (4) | - | - |
| contextual, raised at the set's check (ValueError) | - | - | - | 1630 (194) | | |
| no event (memo or routing) | 42 (463) | 42 (192) | 17 (265) | 255 (15) | - | - |

## (b) Why None

Counts are of queries. "With repeats" adds the exact repeats of an earlier equal (p, A), which the answer memo serves in
2 us each (dev) and which carry the class of the first occurrence. Times are for the class's own rows, both switches on;
the default arm's shares are within 1.3 points.

| class | cause | dev: own, with repeats | dev: ms, share, us each | fuzz: own, with repeats | fuzz: ms, share, us each |
|---|---|---|---|---|---|
| (i) | a model each way | 418, 679 | 312.7, 47.0%, 748 | 2200, 2202 | 4386.6, 74.5%, 1994 |
| (ii) | BRANCH_BUDGET ran out inside a polarity solve | 0, 0 | - | 165, 165 | 364.2, 6.2%, 2207 |
| (ii) | BRANCH_BUDGET ran out elsewhere in the session (the set's check) | 2, 2 | 3.2, 0.5%, 1592 | 3, 3 | 6.9, 0.1%, 2285 |
| (ii) | discovery budget, any other cap | 0, 0 | - | 0, 0 | - |
| (iii) | routed away before the engine: matrix | 17, 32 | 1.7, 0.3%, 102 | 0, 0 | - |
| (iii) | routed away before the engine: relation | 2, 8 | 0.2, 0.0%, 98 | 13, 13 | 3.8, 0.1%, 294 |
| (iii) | theory gave up, catch, non-commutative in the engine | 0, 0 | - | 0, 0 | - |
| (iv) | repeat on the relevant part: memo under (p, part), no engine work | 89, 156 | 16.9, 2.5%, 190 | 0, 0 | - |
| (iv) | the same after the set's check ran | 9, 15 | 4.0, 0.6%, 447 | 4, 4 | 3.4, 0.1%, 843 |
| - | exact repeats of (p, A), counted above | 355 | 0.7, 0.1%, 2 | 2 | 0.0, 0.0%, 6 |

The two (ii) rows are kept apart because a ring hit can reuse a model from an exhausted check: "inside" means an `xb`
token within the deciding entailment, "elsewhere" means only the session's exhausted flag is set when the query ends.
On dev both such queries have the set's verdict UNKNOWN (`V>u`).

Class (iv) holds no unexplained row. The 89 dev queries with no event that are first occurrences and in scope all ask a
proposition that already answered None under another set, so they are the memo under (p, relevant part) of spec.md s1
step 3; the part itself was not recorded, so their class is not resolved to the earlier row's.

Grouped as the planner asked: Nones with no engine work are dev 463 queries, 19.5 ms, 2.9%; fuzz 15 queries, 3.8 ms,
0.1%. The set's check alone: dev 9, 0.6%; fuzz 4, 0.1%.

## (c) Work per query

### Class (i)

A contextual class (i) query makes three `solve_int` calls: the set's complete check, then the two polarity solves of
`Solver.entails` (solver.rs :2214-2226: `L & ~q`, then `L & q`). Dev: 364 of 378 make 3, 8 make 4, 6 make 5. Fuzz: 1933
of 2089 make 3, 139 make 4, 17 make 5. A context-free one makes 2 (dev 40, fuzz 111).

| | dev | fuzz |
|---|---|---|
| contextual class (i) queries | 378 | 2089 |
| ring already holds a model when the entailment starts | 377 | 2054 |
| both polarity solves are searches | 255 | 2005 |
| one polarity is a ring hit (no search) | 113 | 23 |
| `entails_all` with three or four solves | 10 | 61 |
| `solve_int` calls: searches, ring hits | 1039, 115 | 6417, 23 |
| `witness_satisfies` calls | 0 | 0 |

- **Does the first model settle the other polarity?** The first polarity's model cannot: it has `~q` true. The model that
  could is the set check's, which the ring holds in all but 1 (dev) and 35 (fuzz) queries. It settles a polarity in 30%
  of dev queries and 1.1% of fuzz queries. `ring_hit` (solver.rs :2048) skips a record when a theory atom was registered
  after it (`rec.na != n_registered`) or a later clause is not satisfied by it; on fuzz the proposition is nearly always a
  relation, which registers a new atom after the check. The reason for each miss was not counted.
- **`witness_satisfies`** never runs for a None: `entails` calls it only when propagation already decided the literal
  (solver.rs :2208). Over the whole workload it ran 344 times on dev (210 true) and 115 on fuzz (4 true).
- 10 dev and 61 fuzz class (i) queries have an unsatisfiable solve inside the deciding `entails_all`: one literal of a
  derived predicate was decided and another was not.

### Class (ii)

| BRANCH_BUDGET | dev: answers moved, event rows differing, queries with `xb` | fuzz: the same |
|---|---|---|
| 4 | 0, 1, 16 | 0, 11, 206 |
| 8 | 0, 0, 15 | 0, 1, 197 |
| 16 (default) | -, -, 15 | -, -, 196 |
| 32 | 0, 0, 15 | 0, 0, 196 |
| 64 | 0, 0, 15 | 0, 0, 196 |
| 256 | 0, 0, 15 | 0, 0, 196 |
| 4096 | 0, 0, 15 | 0, 0, 196 |

- No class (ii) None reaches a definite answer at any larger budget, and nothing else moves either.
- The budget is spent at the larger sizes: the 196 fuzz queries with `xb` take 0.437 s at 16, 0.484 s at 256 and 1.264 s
  at 4096 (count build, shared lease: a ratio, not a wall time). The branch and bound in those checks does not converge.
- Budget 16 sits in a gap: from 8 upward one fuzz query's events differ from those at 16, and from 16 to 4096 none do.
- An exhausted check does not make a None by itself: of the queries with `xb`, 13 of 15 on dev and 28 of 196 on fuzz
  answer True or False.
- Whether a complete procedure would decide these 170 queries was not measured. I read 12 of them (both dev ones and 10
  of fuzz's, picked by position): in each the proposition is independent of the set, often because a bound such as
  `y <= 2` admits an infinite value. That is my reading of 12 queries, not a proof about the rest.

## (d) What None means in the documents

- spec.md :22-45 (s1, routing): the answer memo, the constant route, the relevance split with its memo under (p, part),
  and `_engine_ask`, where `Unsupported` and `Uninterpreted` give None. These are the no-engine rows of (b).
- spec.md :322-357 (s8): with `C & L` satisfiable, True if `C & L |= q`, False if `C & L |= ~q`, else None; "None
  meaning not entailed". Every query gets a session built for it alone and discarded (issue 97 P1), so what could depend
  on a path is the path of the query's own session.
- spec.md :386-409 (s10): a query over the discovery budget (400) is None without session work; a query within it is
  never truncated. design.md :411-424 says the largest cone on the corpus and the stream weighs 16; `B` is 0 here.
- design.md :658-672: the set's verdict is three-valued; UNKNOWN (a theory gave up, the cone is over the budget, or the
  check failed) never raises, and a plain session replaces one whose check made a theory give up.
- lra.py :84-116: at most BRANCH_BUDGET branch nodes per check; when it runs out the check reports no conflict and sets
  `exhausted`. Integrality is sound but incomplete: a conflict is always valid, a satisfiable check may be integrally
  infeasible, and "satassume reads a definite answer only from an unsatisfiable search". Whether the budget runs out
  depends on the search path. lra.py :349-356: the `exhausted` flag, cleared only by the caller.
- The set-order issue draft (forward-chain-3b): clause order follows the hash seed, order decides which checks run and
  which way they split, so at budget 16 another path can run out where this one finds a conflict. By the docstring the
  worst case is a definite answer becoming None, never the opposite answer. Not reproduced there. This run adds one fact:
  on these two workloads at `PYTHONHASHSEED=0` no check sits near the budget's edge (nothing moves from 8 to 4096 except
  one event row at 8).
- Issue 96 (open): randomised tests for invariants (test order, redundant assumptions, irrelevant rules). Issue 97
  (closed): one session per query, pure memos, a reference implementation.

One consequence for reading class (i): "a model each way" is what the solver reports. Because the theories are sound but
incomplete, it means "not entailed by the clause set under these theories". It does not prove that a real counter-model
exists, and this run has no reference answer to say how many class (i) Nones a stronger theory would decide.

## (e) Proposals

No None-to-definite change is proposed: nothing measured supports one. No budget changes an answer, and the run cannot
tell a true independence from a gap in the rules.

1. **Count the class with the answer (answers identical).** At the points where the engine already returns None, bump one
   counter per cause: models both ways, exhausted flag set, gave up, over the discovery budget. `Engine._ask` already
   reads `_gave_up` there for `stats["theory_gave_up"]`; the exhausted flag is read today only for the set's verdict
   (engine.py :2003), so 168 fuzz Nones are budget-limited with nothing in `stats` saying so. This is a read of existing
   flags and no branch on them, so no answer can change. It makes the table in (b) available on every run without a
   scratch build.
2. **Certify class (i) by its witnesses, as a scratch measurement first (answers identical).** For a relation-only
   query, take the LRA point of each polarity's model, substitute it into the set and the proposition with exact
   arithmetic, and check that the set holds with the proposition false in one and true in the other. A None certified
   both ways is a real independence that no algorithm can turn definite; the uncertified remainder is the whole room a
   stronger theory or a new rule has. That number is what the "none problem" turns on, and it is missing. Limits: it
   covers relations (most of fuzz, part of dev), not predicates whose models are only truth values; a model satisfies
   bounds and disequalities but not necessarily integrality (lra.py :92-97), so some witnesses will fail for that reason
   and need a second look. Any rule that later comes out of the uncertified set needs its own soundness proof for Tilo.

Looked at and not proposed:

- A larger BRANCH_BUDGET: no answer moves up to 256x, and the cost of the exhausted checks grows with it.
- Letting the set check's model settle one polarity more often: the polarity solves are not where the time is (finding
  6 above), and a model recorded before the proposition's atom was registered says nothing about that atom.
- The parked speed-only items (module handles read once, direct add_internal/add_clause calls, borrow-once).

## Limits

- Two workloads, one hash seed (0), one cold pass per count configuration.
- Per-query times are medians of 12 rounds of sub-millisecond intervals on one pinned CPU; class sums are stable to
  about a point of share between arms, single queries are not.
- The count build's own time is not used anywhere except the ratio in (c).
- `xs` was not shown to fire (see the plants).
- The reason a ring record misses, and the relevant part of the 89 dev memo repeats, were not recorded.
