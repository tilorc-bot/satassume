# sa-lzp-1: lazy clause generation for escalated work — bound

Status: **question**. On dev, the ceiling is 3.3% of the pass (4.0% of None time) even if
the propagator were free. After subtracting what any exact propagator still has to do, it
is at most about 1.8%. That is under the 5% build threshold, so I recommend **not building
it** (details at the end). Baseline: satassume `9bafaa5`, branch `lazy-prop`; this
branch adds only `bound/` (instrumentation and raw results, no change to the package).

## What was measured

`bound/lzp_bound.py` monkeypatches satassume (it edits no source file) and replays a workload through
`sympy_api.ask`:

- **Escalation, split into units.** It is a copy of `Session.escalate` that runs the same
  steps, with each unit of work timed and its stored clauses tagged. There are three kinds of
  unit: one node's parked pattern clauses (`pending_c`), one node's parked formulas
  (`pending`), and one node visit (frontier or derived). The unit is attributed to the call
  site that escalated it (`_complete_check`, `_ask` or `_decide`). Each query is labelled
  None or definite by its answer.
- **Would the clause be emitted?** A tagged clause counts as emitted if, later in the same
  session, it is the reason of a trail literal (it became unit) or a returned conflict (it
  became false). This is checked after every `_propagate` call, and the trail is scanned
  again after escalation (`_attach_held` and `_add_lits` assign literals directly). So the
  count is the set of clauses a watch-based lazy propagator would have had to emit on the
  trajectory today's search actually takes. Clauses that stored nothing (they became root
  units or were satisfied at root) are counted as emitted, which errs against the idea.
- **Derived nodes, two rules:**
  - *opt* (not exact): the node is needed if a clause from another unit that was emitted
    mentions one of its 14 variables.
  - *exact*: as *opt*, or a model is found in the session afterwards. That is the rule an
    exact scheme needs; see "Derived nodes" below.
- **Time** comes from a pinned run on a quiet lease on pareto1 (`bench-container`,
  `sa-eval-bench:1`, PYTHONHASHSEED=0). `LZP_TIMING=1` times only the units, plus
  `add_internal` and `mention_blocks` inside them, with no tagging. Its result is divided by
  the plain `evalbench.replay dev` time, 3 rounds each. Counts come from orion (they are
  deterministic).

Workloads: the evaluator's dev set (1,985 queries; 892 answered None), and fuzz seed 424242
(3,000 queries; 2,387 answered None). That seed is not held out. Nothing under `secret/`
was read.

## Bound table

Counts are clauses entering the solver during escalation.

| dev | parked clauses | emitted | derived nodes visited | needed (opt / exact) |
|---|---:|---:|---:|---:|
| set check (`_complete_check`), None queries | 3,128 | 1,486 (47.5%) | 0 | – |
| set check, definite | 1,907 | 685 (35.9%) | 0 | – |
| query (`_ask`), None | 10,532 | 3,054 (29.0%) | 93 | 0 / 93 |
| query, definite | 1,828 | 593 (32.4%) | 6 | 0 / 6 |
| context-free (`_decide`) | 217 | 111 (51.2%) | 0 | – |
| **dev total** | **17,612** | **5,929 (33.7%)** | **99** | **0 / 99** |
| **fuzz 424242 total** | **141,889** | **37,036 (26.1%)** | 0 | – |

Parked *formulas* never reach escalation on either workload (0 units): by then, all parked
work is compiled pattern clauses. The derived-node visits on dev emit 3,104 clauses of their
own; 763 of those are hit (24.6%).

| time (pinned pareto1, medians) | dev | fuzz 424242 |
|---|---:|---:|
| plain pass | 0.576 s (None 0.360 s) | 8.34 s (None 6.89 s), timing mode |
| parked-pattern emission (`pc`) | 0.0287 s = 5.0% | 0.213 s = 2.6% |
|   of which `add_internal` / `mention_blocks` | 0.0208 / 0.0051 s | 0.151 / 0.053 s |
| derived-node visits (`dn`) | 0.0044 s = 0.8% | 0 |
| **ceiling A**: free propagator, never-emitted share of `pc` | **3.3%** (None 4.0%, def 2.0%) | **1.9%** (None 2.0%, def 1.5%) |
| ceiling A plus skipping derived nodes under the non-exact *opt* rule | 4.1% | 1.9% |
| **net estimate B**: watch-based propagator | **≤ 1.8%** | **≤ 1.3%** |

The None/definite split of ceiling A apportions the time pro rata, using each class's
share of never-emitted clause time from the tagged run.

## Design considered and why the net is small

The propagator sits next to the theories. It holds the parked clauses out of `_clauses`,
emits a clause through `add_internal` when the clause becomes unit or false, and runs a
final check on a total assignment: no held clause may be false.

- **Exact for clauses.** The emitted clauses are a subset of the held ones. So UNSAT over
  the emitted clauses is UNSAT for all of them. A total assignment that falsifies no held
  clause is a model of the emitted ones and the held ones together.
- **Where the cost is.** To see that a clause has become unit, the propagator must watch
  it. Watching an instantiated clause is the same watch-list work it causes in the clause
  database today, and the watched variables must be mentioned anyway (lazy block writes;
  see `docs/performance.md`, "Invariants"). So a watch-based propagator saves only the
  `_clauses` append and the bookkeeping of `add_internal` on never-emitted clauses. Of the
  dev `pc` time, 0.0077 s is instantiation (the list comprehensions in `_emit_pattern`),
  which the propagator still pays, and 0.0051 s is mentions, which it still needs. That
  leaves at most (0.0208 − 0.0051) × 0.663 ≈ 0.010 s, or 1.8% of the pass.
- **The other way to build it.** The propagator could hold clauses in template form, as
  `(clauses, bases)`, and check them per assigned block variable. That avoids
  instantiation, but every assignment to a parked node's variables then crosses a Python
  callback. The same shape was measured before as `FactTheory` (+56%, `performance.md`,
  "What was measured and dropped"). It cannot win back 3.3%.
- **Search does not get cheaper.** The never-emitted clauses are visited in the same watch
  lists either way. Today's decisions cover all non-lazy variables, and a final check over
  the held clauses needs those variables assigned (or the clause satisfied by another
  literal) anyway.

## Derived nodes: the exact rule

A derived node `d` (say `2*e` of a power, or `x - 1` of a log) has its variables allocated
before its own templates and block are added. Suppose a model leaves `d` unvisited. It is a
model of everything only if `d`'s own clauses (its rule block, its templates, and what they
reach) can be extended over `d`'s variables for the values the model gives `d`'s
arguments. That is a totality property of the template cone *in the SAT abstraction*.
Nothing in satassume proves it (cf. #53 group 1, the non-total templates). So an exact rule
must visit `d` before it accepts a model in which `d`'s arguments are assigned. That covers
every SAT search. A `None` answer runs two SAT searches, and a consistent set's check is a
SAT search. On dev, all 99 derived visits come in sessions that later find a model.

Under the non-exact *opt* rule, no derived node would be needed: none of the 99 nodes is
mentioned by another unit's emitted clause. Their whole cost is 0.8% of dev anyway. A
static proof of template totality could make skipping them exact (for example, by
enumerating each compiled pattern's block models with `_block_models`). But it would buy
at most 0.8% on dev and 0 on fuzz.

## Other risk (if built anyway)

The emitted set changes the search trajectory. LRA branch and bound is path-dependent
(sa-bb-1: 596 exhaustions, all LP-unbounded). So for sessions with an integrality atom,
"answers identical" could not be argued in general, only checked on the workloads.

## Recommendation

Don't build it. Even with a free propagator, the exact ceiling is 3.3% on dev and 1.9% on
fuzz. A realistic watch-based propagator nets ≤ 1.8%, with a new solver component and an
exactness argument to maintain. Escalation is only 5.7% of the dev pass, so leaving
escalated work unbuilt cannot be where the None time goes: on dev, the set's session build
is 33% of the pass and search 13% (from the evaluator's phase split). For sa-lzo-1 and
sa-lzr-1: the clauses escalation parks are not the expensive part. The data says the
lever is what the build constructs before escalation (relation links, the set's own
cone), and that is sa-lzr-1's scope.

## Reproduce

```
bound/run.sh-style: PYTHONPATH=<clone>:<sympy pin>:<sa-eval shim> PYTHONHASHSEED=0 python -P bound/lzp_bound.py dev
python bound/show.py out.json            # the tables above
LZP_TIMING=1 ... lzp_bound.py dev        # timing only (bound/inner.sh is the pinned run)
```

Raw data: `bound/dev.json`, `bound/fuzz.json` (counts from orion; their times are
unpinned, use them only for shares) and `bound/pinned-pareto1.jsonl`.
