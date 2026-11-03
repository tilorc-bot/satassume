# REPORT: sharing LRA/EUF sessions too (option (b)), a measurement for Tilo

sa-lrashare-1, 2026-11-03. Branch `lra-share` (tilorc-bot/satassume, no PR), on top of
fbb484f (sa-node-2's shared theory-free sessions, SHARED_MAX 4).

- e5ca30d: `SHARE_THEORY = False` in `satassume/engine.py` (+ `_shareable`, 2 tests).
  When the switch is on, a contextual session that has a theory, relation glue or
  transfer is kept like a theory-free one, unless one of its theories has ever
  exhausted the branch budget or given up (`_gave_up`/`_exhausted`; both flags are
  sticky for the session). The check runs before the shared session answers (after
  escalation) and again after it answers. Either failure drops the shared session
  and answers the query in a fresh per-query session. Off is the same as fbb484f.
- 7205480: the existing "theory sessions are not kept" test pins the switch off.
- 4f9d931: **measurement tree, switch ON** (submitted to sa-eval-2 for timing).

Not exact: the LRA branch-and-bound budget depends on the search path, so a shared
session can in principle answer differently from a fresh one. Everything below is
empirical evidence, not a proof.

## Answers, switch ON, compared with 9bafaa5

Each workload ran in its own cold process on orion (PYTHONHASHSEED=0, sa-eval's
harness and SymPy pin). Answers were compared position by position. For the
shuffled orders, 9bafaa5's stream-unique answer for the same query is the
reference (the gates already check that 9bafaa5 is history independent).

| workload | queries | differ | more definite | less definite | flipped |
|---|---:|---:|---:|---:|---:|
| stream (recorded order) | 16,232 | 0 | 0 | 0 | 0 |
| battery stream | 16,386 | 0 | 0 | 0 | 0 |
| corpus | 2,863 | 0 | 0 | 0 | 0 |
| stream-unique | 8,393 | 0 | 0 | 0 | 0 |
| stream-unique shuffled, seed 20261103 (gates' seed) | 8,393 | 0 | 0 | 0 | 0 |
| stream-unique shuffled, seed 1 | 8,393 | 0 | 0 | 0 | 0 |
| stream-unique shuffled, seed 2 | 8,393 | 0 | 0 | 0 | 0 |
| grouped shuffle, seeds 1, 2, 3 (see below) | 3 x 8,393 | 0 | 0 | 0 | 0 |
| ho-fuzz (sa-eval's held-out seed) | 3,000 | 0 | 0 | 0 | 0 |
| fuzz, seed 424242 | 3,000 | 0 | 0 | 0 | 0 |
| forkq, fresh process per query (gates.py) | 8,393 | 0 | 0 | 0 | 0 |
| gates.py answers: stream, battery, corpus, ho-fuzz, fork-battery (refine), stream-unique, stream-shuffled, forkq | | all PASS | | | |

gates.py on 4f9d931 (orion, its own runs) fails only on 2 counting tests. With the
switch ON these fail by design and no answer is wrong:
`tests/test_set_verdict.py::test_one_set_check_per_query` (6 set checks where 8 are
expected) and 9bafaa5's `tests/test_engine.py::test_contextual_queries_build_and_discard`
(sessions and set checks per query). Both assert that every query builds its own
session, which is exactly what the switch stops doing for theory sessions. With the
switch off, the suite passes (6,096 passed).

**No query differs, so there is no differing-query list to give.** With the switch
off, every workload above also matches 9bafaa5 exactly.

How much each order actually tests the switch:
- A plain shuffle almost never puts two queries with the same (set, expression) key
  next to each other: 14 to 20 shared calls per seed, 2 to 4 of them on theory
  sessions. Such a shuffle tests history independence in general but hardly tests
  the switch.
- I added a **grouped shuffle**, which does test it. Queries are grouped by the
  sharing key, and both the groups and the predicate order inside each group are
  shuffled. This is the order that varies which predicate a shared LRA session
  answers first, and so its branch-and-bound path. It gives 633 to 636
  theory-session hits per seed with 0 differences.
- The fuzz workloads barely exercise sharing: 0 or 1 shared calls, because the fuzz
  queries rarely repeat a set and expression.
- forkq runs one query per process, so it can differ only if one `ask` makes
  several engine queries.

## Counts (whole pass, one cold process; off = 7205480 with the switch off, the same as fbb484f)

| workload | shared hits off (all theory-free) | shared hits on (free + theory) | fallbacks on | set_checks base / off / on | sessions base / off / on | B&B exhaustions base / off / on | LRA checks off / on |
|---|---:|---:|---:|---|---|---|---|
| stream | 1,366 | 1,975 (1,363 + 612) | 2 | 4,450 / 3,084 / 2,475 | 4,908 / 3,542 / 2,933 | 50 / 50 / 49 | 3,618 / 2,546 |
| battery | 1,297 | 1,973 (1,295 + 678) | 2 | 4,593 / 3,296 / 2,620 | 5,065 / 3,768 / 3,092 | 48 / 48 / 47 | 4,283 / 3,125 |
| corpus | 28 | 29 (28 + 1) | 0 | 1,061 / 1,033 / 1,032 | 1,816 / 1,788 / 1,787 | 0 / 0 / 0 | 107 / 105 |
| grouped shuffle s1 | 1,517 | 2,150 (1,517 + 633) | 2 | 4,450 / 2,937 / 2,304 | – / 3,390 / 2,757 | 50 / 50 / 49 | 3,619 / 2,511 |
| grouped shuffle s2 | 1,519 | 2,155 (1,519 + 636) | 2 | 4,450 / 2,942 / 2,306 | – / 3,396 / 2,760 | 50 / 50 / 47 | 3,618 / 2,502 |
| grouped shuffle s3 | 1,501 | 2,134 (1,501 + 633) | 2 | 4,450 / 2,955 / 2,322 | – / 3,404 / 2,771 | 50 / 50 / 50 | 3,620 / 2,519 |
| ho-fuzz | 1 | 1 (0 + 1) | 0 | 2,938 / 2,937 / 2,937 | 3,149 / 3,148 / 3,148 | 221 / 221 / 221 | 8,354 / 8,354 |
| fuzz 424242 | 0 | 0 | 0 | 2,952 / 2,952 / 2,952 | – | 277 / 277 / 277 | 8,292 / 8,292 |

- "Fallbacks" counts shared-session queries handed to a fresh session because a
  theory had exhausted or given up. No theory gave up in any run (`lra_gave_up` = 0).
- "B&B exhaustions" counts `LRATheory.check` calls that ran out of the branch
  budget, summed over every session in the pass.
- On the stream, the switch adds 612 shared hits on top of sa-node's 1,366
  theory-free ones. That removes another 609 set checks and session builds (20%
  of the switch-off count, 14% of 9bafaa5's) and 30% of the LRA checks.
- Exhaustions change by 0 to 3 depending on the order. These are queries whose
  fresh session would run out of budget while the shared session, already
  escalated with clauses it learnt earlier, does not. On these workloads the
  answer came out the same anyway, but nothing guarantees that. It is exactly the
  path dependence the exactness argument cannot cover.

## Timing (sa-eval-2, pinned A/B on pareto1)

pareto1, one pinned bench-container invocation, 3 trees alternating, cold processes,
5 rounds + warm-up, 09:11-09:16Z. Speedup = 9bafaa5 / tree (median of paired rounds;
range = per-round tree/base ratio). sa-eval-2's report:
~/dev/sa-eval/evalbench/results/sa-lrashare-1-4f9d931.md (sa-eval 0399462). The A/A
noise floor (BASELINE.md): medians within about 1%.

| workload | switch OFF (7205480 = fbb484f + switch) | switch ON (4f9d931) | ON over OFF |
|---|---:|---:|---:|
| dev, total | 1.10x (0.900..0.917) | **1.28x** (0.778..0.833) | 1.17x |
| dev, None queries | 1.13x | **1.34x** (0.741..0.767) | 1.19x |
| held-out stream, total | 1.05x (0.946..0.955) | **1.37x** (0.729..0.735) | 1.30x |
| held-out stream, None | 1.06x | **1.42x** (0.706..0.711) | 1.34x |
| held-out battery | 1.03x | 1.12x (0.884..0.895) | 1.10x |
| fork-battery (time in ask) | 1.05x | 1.15x (0.833..0.940) | 1.10x |
| ho-fuzz | 0.99x (1.005..1.013) | 0.97x (1.027..1.035) | 0.98x |
| corpus | 0.97x | 0.97x | 1.00x |

Counters on the held-out stream (9bafaa5 / off / on): context builds 3,885 / 2,704 /
2,161, solver decisions 43,668 / 34,588 / 26,501, conflicts 1,695 / 1,686 / 944.
With the switch on, the conflicts nearly halve: the shared LRA sessions reuse clauses
learnt by earlier queries. That is where the time goes, and it is also the path
dependence (the fresh session re-derives those conflicts).

Fuzz and corpus are about 3% slower in every round, with the switch on or off. Sharing
almost never triggers there (fuzz: 1 shared call in 3,000 queries), so this is the
cost of keeping the sessions and computing the key, plus whatever fbb484f
itself costs on these workloads. The switch on its own adds about 2% on fuzz
(0.99x to 0.97x).

## What Tilo is deciding

Switching it on would buy, on top of sa-node's theory-free sharing: held-out stream
1.05x to 1.37x over 9bafaa5 (None queries 1.06x to 1.42x), dev 1.10x to 1.28x, held-out
battery 1.03x to 1.12x, fork-battery 1.05x to 1.15x. Fuzz gets about 2% slower and the
corpus is unchanged. The cost on these workloads is zero changed
answers out of about 95,000 asked, across 12 orders and processes (about 1,900 shared
LRA/EUF answers), but that is evidence, not a proof. On the stream, the switch moves
0 to 3 B&B exhaustions per pass in or out of a shared session, so an answer could
differ in principle.

The provable alternative is to redesign `lra.py`'s budget so that whether a check
exhausts does not depend on the simplex basis earlier checks left behind. For
example, the budget could be a function of the asserted literals only, or branch
and bound could restart from a canonical basis.

Measurement scripts (orion): `meas_child.py`, `drive.py` and `compare.py` in
/tmp/claude-1000/-home-tilo-dev-satassume/df81d064-7290-4016-accd-c7852b8fee8e/scratchpad/meas/,
with the raw per-query answers and counters in `out/`.
