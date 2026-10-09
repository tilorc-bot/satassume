# Performance

Where the engine's time goes, what made it faster, what was measured and
dropped, and what the landed optimizations assume. The engine itself is
described in [design.md](design.md), the theories in
[theories.md](theories.md), the gates and measuring tools in
[testing.md](testing.md).

Unless stated otherwise, a time is one cold pass of the recorded refine
query stream (13,877 `ask` calls, `tools/refine_replay.py`) and a change is
an interleaved A/B of two checkouts (`tools/ab.py`). A later recording of
the stream has 16,232 queries; numbers on it are marked. Every number is
historical: it holds for the commit it was measured at, on the machine
named.

## How the work is done

**Bound before building.** An item gets code only after a measurement
bounds its gain: at least 5% of the pass, or 3% for an item of about ten
lines. The bound is taken on the current tree, usually by wrapping the code
from outside (a per-query log, `tools/refine_replay.py --log`, or a script
that simulates the change and checks every answer), never by argument.

**Keep only what the A/B shows.** An item is kept only if an interleaved
A/B against an untouched checkout shows the same threshold, with every
answer identical on both gates (the refine stream and `tools/gate2.py`) and
the suite unchanged. A change meant to make answers more definite uses
`--allow-more-definite` on both tools and has every new answer checked
against SymPy. One commit per kept item, with the A/B lines in the message,
and a separate review that re-runs the gates.

**Machines.** Most numbers come from a Raspberry Pi 5 container used by one
measurement at a time, some from a shared 2-core (later 4-core) local
machine. The two agree on shares to about 1% but not on small gains: the
rule-block propagator (A2 below) was -8.6% on the Pi and -2.8% to -6.1%
locally. Compare only numbers from one interleaved run. Benchmarks belong
in a container with pinned, exclusively leased cores; see the machine
owner's benchmarking notes. `tools/ab.py`'s noise floor is about 1%.

What the rounds taught about bounds:

- A bound is relative to the pass at its commit. Witness reuse was dropped
  at 4.8% when search was 22% of the pass and kept later at -5% to -8%
  when search had become 38%. Re-measure a dropped item when the profile
  shifts.
- A Python hook replaces work, it does not remove it. The rule block's
  share of watch-list visits (18.9%) was not a cost a propagator removes:
  the fixed cost per processed literal (about 1 µs in CPython) stays.
- Fewer objects pay beyond the timed bound: lazy node atoms were bounded at
  5.2% and measured -7.1% to -8.0%, the difference being collector passes.
- Cuts of about 1% each do not add up exactly when measured one at a time
  on a noisy machine (item C below: two cuts worth about 1% each alone were
  worth 3 to 4 points together).

The measurement scripts of the rounds are in the tag
`agent-reports-2026-09`, under `agent-reports/2026-09-perf-rounds/scripts/`
and `agent-reports/scripts/`. They copy parts of `Engine.ask` and
`Session.node` and need re-copying after those change.

## Stream time by commit

Pi container, cold pass, 13,877 queries. Later commits answer more queries
definitely, so the work is not constant along the table.

| commit | pass | what changed |
|---|---:|---|
| `cbb971f` | about 10.1 s | before the speed work |
| `b3d429b` | 4.2 s | round 1 (answer memo, held levels, cone policy, ...) |
| `895a6c2` | 3.62 s | round 2 (failed-set memo, template and formula memos) |
| `747fb0e` | 3.12 to 3.16 s | lazy node atoms, rule block as a propagator |
| `2069884` | 2.90 to 2.94 s | witness reuse |
| `e2aa724` | 2.75 s | held levels with theories attached |
| `66871eb` | 2.90 s | predicate transfer between equal terms (+5.5% to +6.4%) |
| `ea1cf5e` | 2.76 s | lazy rule-block writes, lazy transfer atoms |
| before `b208af3` | 2.67 s | constant propositions without the assumptions |
| `c8361d7` | 3.47 s | irrational constants as LRA terms (+30%) |
| after `99e8827` | 3.17 to 3.19 s | relevance (-8.3% to -8.8%) |

After that, on the 16,232-query stream (pinned container): LRA
integrality (#38) cost +8.0% and PR #45 brought it back to +2.4%; the exact
constant field (#48) costs +5% on the whole stream, +13% on the 3,127
queries with constants and nothing on the rest.

## What landed

Gains are against the commit's parent unless noted; "x" is the ratio of
best cold passes.

| item | commit | gain | where |
|---|---|---|---|
| answer memo, `None` answers included | `328bdbb` | 0.70x | `sympy_api.ask`, `Engine.answers` (`AnswerMemo`) |
| LRA linearisation and relation atoms memoized across sessions | `a36d19f` | 0.94x | `lra_adapter._INTERPRETED`, `relations._SYMPY_ATOMS` |
| cone search only above 3 polluting nodes; the cone session replaces the polluted one | `d34da8b`, `35d5358` | 0.95x, 0.93x | `Engine.ask`, `Engine.cone_threshold` (removed, #97 P7) |
| propagation under assumptions cached | `ddb7bfb` | 0.89x (Pi) | `Solver._assume` (`_acache`) |
| cheaper clause insertion (plain lists for problem clauses) | `7197c28`, `c56dda8` | 0.935x; -3.4% to -4.6% | `Solver._add_lits`, `add_internal` |
| held assumption levels between calls | `9e33d28` | 0.94x (Pi) | `Solver._assume`, `_attach_held`, `_solve` |
| decisions in index order until a solve's first conflict | `54f43bf` | 0.915x (Pi) | `Solver._pick_branch` (`_scan`) |
| `Relations.session` a weak proxy (no reference cycle, no full GC per session) | `15c8fbb` | 4.45 s to 4.21 s | `relations.py`, `Relations.__init__` |
| failed-assumption-set memo (`Uninterpreted` remembered) | `63504aa` | -10.2% (Pi) | `Engine._failed`, `Engine._context_session` |
| `clauses_for` per expression, `to_formula` per SymPy Boolean | `41f2b80` | -3.2%, -3.7% (Pi) | `TemplateRegistry.clauses_for`, `sympy_api._formula` |
| version counter on the extension registry | `5903431` | noise (cleanup) | `Extensions.version`, `sympy_api._registry_state` |
| a node block's 33 `P` atoms created lazily (16.9% were ever read) | `5d6ee73` | -7.1% to -8.0% (Pi) | `VarTable.slots`, `VarTable.atom`, `Session.writeback` |
| rule block as a solver propagator instead of 79 clauses per node | `b9f2151`, `747fb0e` | -7.1% to -8.6% (Pi) | `Solver.set_rule_block`, `register_block`, `Session.__init__`, `Session.node` |
| witness reuse: last two models re-checked before a search; model kept as a slice | `2069884` | -5.2% to -5.6% (Pi), -7.8% locally with the slice | `Solver._ring_hit`, `_ring_blocks`, `_solve` |
| held levels with theories attached; new theory atom asked about at root | `e2aa724`, `3fc0244` | -4.2% to -4.7% (Pi); theory tax +14.1% to +4.9% | `Solver._assume`, `_attach_held`, `register_atom` (`_tpending`) |
| predicate transfer, tuned | `1e0bada`..`f26dc20`, `b8b781e` | cost +12.1% cut to +5.5%, +6.4% (Pi) | `transfer.py`, `Relations._engage_transfer`, `Relations.sync_transfer` |
| rule block by exact closure, implications written above root only to mentioned variables; transfer atoms registered lazy, `decide()` hook | `affd45d`, `256a1fb`, `2d2b5af`, `ef0e59b` | -4.7% (Pi, both together); decisions 64,141 to 36,453 | `_BlockClosure`, `Solver._propagate`, `mention`, `mention_blocks`, `engine._split`, `register_atom(..., mention=False)`, `TransferTheory.decide` |
| constant terms: no guard node, no interface equality with a non-rational constant, not counted as pollution | in `b208af3` | the capability's cost +38% to +30% (Pi) | `relations.py` ("Constant terms"), `Session.n_constants` (removed; it served `cone_threshold`, #97 P7) |
| relevance: a relation-free set split into components by shared symbols | `99e8827` | -8.3%, -8.8% (Pi) | `sympy_api._relevant`, `_Split`, `_part_consistent` |
| relation setup: no-op `ensure`, guard and LRA form memos, no redundant link clauses, a term's own `integer` variable as integrality atom | `4fa0153`, `e14aad4`, `67cead8` | #38's +8.0% to +2.4% (16,232 stream) | `Session.ensure`, `Relations._guard`, `Relations._closed_extended_real`, `relations._own_term`, `LRATheory._var_of_form` |

The rule block went through two forms. `b9f2151` propagated the 79
clauses from shared binary and ternary tables; `affd45d` replaced that by
the exact closure of each block from the table of the rule base's 48
models, with the block state undone per level. The exact closure alone is
slower than the tables; the lazy writes it allows are worth about 10%
(control: the same code writing every implied literal, +4.1%).

Transfer made the stream more expensive on purpose (the owner wanted facts
shared between equal terms even at a cost); the lazy transfer atoms
recovered it. Irrational constants (+30%) and the exact field (+5%) are the
price of queries that used to fail early as unreadable: with `pi`
replaced by `355/113` in those queries they cost almost the same, so the
cost is relation reasoning, not the constants.

## What was measured and dropped

| item | bound or A/B | why dropped |
|---|---:|---|
| witness ring (round 2) | 4.8% | ring of 4 hit 22% of solves, the cheap ones; later kept at 2 models when search had grown (above) |
| component-restricted search | 0.9% | the query's component is 0.88 of the session (0.83 in cone sessions): templates link nodes to subterms, nodes share symbols; the walk cost more than the searches |
| phase heuristic | ceiling 4.9%, about 2.7% | median 11 decisions and 0 conflicts per solve |
| base-session clone for cone rebuilds | 1.6% (5.1% with a free clone) | a base session is about 50 variables and 130 clauses; copying it costs nearly as much as building it |
| atomic fast path before any session | 0.9% | the other 5% (from the fact cache) skips the consistency check and changes 399 answers |
| `keep_sessions` 32 or 64 (setting removed, #97 P7) | 0.4%, 0.7% | after the failed-set memo only 143 sessions per pass are LRU rebuilds |
| root units inserted under held levels | 0.6% | the units are node facts emitted when a node is added, not the writeback; nothing to batch |
| first attempt on a polluted session (early cone) | 3.3% (ceiling 6.0%) | wasted and useful attempts look alike beforehand; the naive early cone lost 2 answers (relation atoms of earlier queries decided them) |
| memo and API overhead | 1.5% | 2 µs per memo hit; the engine is 97% of the pass |
| answer-memo subsumption (definite answer under a subset) | about 3% with checks, 7.2% without | without the consistency and scope checks 251 `None` answers become definite and an inconsistent set is masked |
| precompiled template clause emission | 2.2% | the demand-filter half (1.6%) exists now anyway as `engine._split`, for the mention masks |
| engine-side allocation and GC cuts | under 0.5% | 85% of what the collector walked were the solver's clause and watch lists |
| hot-loop bundle (item C) | -6.8% as a bundle, -2.4% to -3.2% after review | the two largest cuts (lazy watch lists, a `_backtrack` rewrite) were reverted as unreadable for about 1% each; only the model slice survived, in witness reuse |
| binary-rule closure per literal | +3.5% | closures are longer than the direct lists and overlap |
| per-node closure memo keyed by asserted set | -3% to +4% (bound) | building the key per literal costs what it saves |
| `FactTheory`: rule block as a DPLL(T) theory | +56% | every predicate literal crosses the Python theory interface (about 660,000 events per pass); 78% of `assert_lit` calls echo the theory's own implications |
| skipping rule-block writes to unmentioned variables | 5x slower | drops implications through the skipped literal; needs the per-block closure (landed form) |
| lazy writes per literal instead of per variable | +9.3% | the search then checks the block before each decision |
| EUF engaged only on a user equality (`relation-speed`, tag `archive/relation-speed`) | -2.2% after porting onto transfer | under 3%, and exactness needed a subtle engagement argument and two review rounds; 25% to 45% on cold relation queries (`tools/relbench.py` on the branch) |
| LRA bound precision for constants | no change | two bound atoms asserted once at root |
| PR #45 extras | none measurable | nudging off integers before branching (28 of 792 branchings), skipping clause 2 for root-real terms (13 of 1,430), deduplicating clauses (161 of 30,832) |
| GC tuning (`gc.freeze()` after import, thresholds) | -4% (freeze, at `6577484`) | a process-wide setting for the embedding application, not for a library |

Two items dropped by these rules later landed in another form: the theory
hold (2.7% in round 2) became `e2aa724` once the theory tax was measured,
and witness reuse as above.

## Invariants the landed optimizations rely on

A change that breaks one of these either costs speed or, worse, returns a
stale answer. The gates catch some of them only on the workloads they
replay.

**Solver (`satassume/sat/solver.py`).**

- The watched-clause scan exists twice: in `_propagate` (after the rule
  block hook) and in `_propagate_clauses` (solvers without a rule block,
  so they pay nothing for the hook). An edit to one must go to both.
- A rule-block reason is an int, `mask << 32 | base`, not a clause. Every
  reader of `_reason` must go through `_rb_reason` (today `_analyze`, its
  minimization, `_analyze_final`); `_reduce_db`'s lock test relies on an int
  never being a learnt clause.
- The block state (`_rb_mask`, `_rb_cl`) is undone per level. Every site
  that opens a level must also push `_rb_ulim` and bump `_uid`; there are
  four (`_assume_propagate` twice, `_search` twice).
- Lazy writes: above root, a block implication is written only to a
  variable something mentions (a clause, an assumption, a theory atom
  registered with `mention=True`, `Solver.mention`). `implied` is therefore
  weaker for unmentioned variables; the engine mentions the query literal
  in `Session.query_literal`, and any new reader of `implied` must mention
  what it reads. Root is always complete, so `root_trail`, `value` and the
  fact cache are unaffected. Stored models hold None for lazy variables;
  every reader of `_mvals`/`_witness` must complete them with `_fill`.
- Witness reuse returns a stored model only if the call's literals, the
  root literals fixed since, the problem clauses added since and the rule
  blocks registered since all hold in it, and the number of theories and
  of `register_atom` calls (`_n_registered`) is unchanged. It relies on the
  formula only growing and on a theory's `check` depending on its atoms and
  their values only (`theory.py` allows the reuse; LRA and EUF qualify). A new kind of state change the
  gate does not see would reuse a stale model. `_mvals`, `_witness` and the
  ring entry are one list that nothing may mutate.
- The propagation cache is keyed on `(assumptions, _stamp, root trail
  length)`: every change that can alter what propagation derives must bump
  `_stamp`. With a history-dependent theory a cached result is sound but
  may differ from a recomputation.
- Held levels: while `_held` is set, the trail is exactly the propagation
  fixpoint (unit and theory) of the held assumptions. Anything that
  changes the root or registers a theory atom backtracks to root first;
  `_attach_held` handles a clause added while held, falling back to root
  in the awkward cases. Theories stay at the held levels between public
  calls, so nothing may read theory state assuming level 0.
- `stats()["clauses"]` does not count the rule block; `rule_blocks` does.

**Engine and API memos.**

- The answer memo (`Engine.answers`) is keyed on the SymPy objects
  `(proposition, assumptions)` and valid within one registry epoch
  (`satassume/state/epoch.py`; `Engine._check_version` drops it): every
  registration, a new `Engine.extensions` or `Engine.relation_specs`. It stores
  `None` too, so the first `None` stands even if later queries would have
  grounded enough to decide it; on gate2 and the stream this changes no
  answer. An adapter spec mutated in place does not invalidate it.
- `Engine.cache` and `Engine.custom_cache` record the epoch and the
  settings fingerprint they were filled under and are emptied when either
  differs (`DictCache.check`); before PR #63 (issue #53) a fact cached
  before a registration was served after it. No contextual session is
  kept between queries (#97).
- The failed-set memo (`Engine._failed`) assumes that whether building a
  session raises `Uninterpreted` depends only on the assumptions' relation
  atoms and the adapters: `LRAAdapter.register` and `EUFAdapter.register`
  decide from the atom alone. An adapter that learns from earlier atoms
  breaks it.
- `TemplateRegistry.clauses_for` assumes templates are pure functions of
  the expression (they read its structure and SymPy's own `is_*` on numeric
  atoms); it is cleared on template registration, and its results are
  never mutated. `sympy_api._formula` is keyed on `(expr, relations)` and
  cleared when the default registry's version changes; an engine with a
  private `Extensions` is not tracked (nor is `to_formula`'s scope).
- `_RULE_TABLES` (solver) and `_split` (engine) are keyed on object ids
  and keep the keyed object alive so an id is not reused.
- `VarTable.slots` tells a node block's variable (a `(node, base)` tuple)
  from a custom atom (a `P`) by `type(x) is tuple`; custom atoms must stay
  `P` objects. `VarTable.atom_of` builds a fresh list per access.
- `Relations.session` is a weak proxy: nothing may call into a
  `Relations` after its `Session` is gone.
- Relevance splits every set by key connectivity, relations included
  (`RELATIONAL = "components"`, #53 R2). A set with a relation or a keyless
  conjunct is certified by the whole set's verdict (answering under a part
  of a set that is not inconsistent is sound by monotonicity); a
  relation-free set by per-component checks, whose soundness rests on "no
  relation, no theory in the session". A feature that brings LRA or EUF
  into a relation-free session must also turn the split off;
  the sign-on-sum glue (`scope.affine_pair`, #51; `Session._affine_links`
  before #97 P3) does not, and loses answers (#15,
  [design.md](design.md), "Relevance"). `Engine.verdict` keeps no session
  (only the verdict memo), so the whole set of a split set costs one
  build and evicts no part session. The key memo `_KEYS` must be cleared
  if `RELATIONAL` changes.
- (historical; the setting was removed in #97 P7, no session is reused)
  `cone_threshold = 3` counted nodes beyond the assumptions', not closed
  irrational constants; it was tuned on the refine stream (2 to 10 within
  noise; 0, 1 and 20 lose; no cone search at all took 10.1 s to 12.9 s at
  the time).

**Answers that depend on history.** Under assumptions that only search
shows inconsistent, whether a query raises depends on whether an earlier
query searched; the exact closure and transfer each moved a few queries
onto the propagation-decided path. An A/B of an internal change can show
such an answer as less definite without any loss of reasoning; re-ask in a
fresh engine before calling it a regression. Tracked in #53 and #42.

## Measured, not started

| idea | bound | state |
|---|---|---|
| one persistent solver per engine: every assumption conjunct under a selector literal, search that stops when every active clause is satisfied | ceiling 45.7% of the logged pass (every query that built a session), 23% certain; active clauses at the median search 0.004 of the union | stage 0 at `6b935d7` did not meet its stop condition. Without scoped termination search costs 0.37 ms plus 1.8 µs per variable (about 18 ms per search at mid-pass against 0.6 ms). Next step would be a solver-only experiment: stop if scoped search is not free when unused or costs over 10% more than today's |
| compiled solver core (C, Cython or Rust, same API) | a 3.0 s pass to 1.4 to 1.6 s (estimate at `747fb0e`, solver about 60% of the pass) | the engine calls the solver about 100,000 times per pass and `implied` returns whole trails, so the boundary limits it; theories stay in Python |
| integrality link only for expressions asked `Q.integer` | part of #48's +13% on queries with constants | #62 |
| combined terms-by-bits budget in `constfield` | an 11x11 system sharing a 4000-bit denominator squared takes 3.1 s | #62; not seen on the workloads |
| fact-cache fast path; answer-memo subsumption without checks | 5%; 7.2% | semantic changes (skip the consistency check), for the owner |
| watch lists allocated on first use | about 2% (-0.9% alone) | reverted for readability in item C |
| a predictor for "propagation in the polluted session will fail" | ceiling 6.0% | none found that costs less than the node visits it saves |

## Current cost profile

No per-area profile of the current tree exists. The latest, at `747fb0e`
(Pi, 3.12 to 3.16 s, sampled), predates lazy writes, transfer, irrational
constants, relevance and integrality:

| area | share |
|---|---:|
| `_propagate`: rule-block hook | 20.0% |
| theories (LRA, EUF, `relations.py`, solver `_theory_*`), SymPy under them | 14.8% |
| search internals (`_search`, `_analyze`, heap, `_backtrack`) | 13.7% |
| `_propagate`: watch lists | 7.5% |
| clause insertion | 6.5% |
| engine control flow | about 6% |
| template clauses (filter, shift) | 5.6% |
| `_assume`, `implied`, `propagate` bookkeeping | 4.1% |
| collector | 3.7% to 4.4% (timed) |

By phase: search 38% (3,130 of 3,192 searches end `None`, both models
found), propagation-only work 19%, node visits 25%. Definite answers come
from propagation almost always. The rule-block hook's 20% has since been
replaced by the exact closure (about 45% fewer processed literals).

Engine counters on `main` at `7399535`, from the 13,877-query stream (PR
#63's gate): 4,570 engine queries, 9,536 cache hits, 1,689 sessions, 483
cone searches. PR #45 measured garbage collection at about 12% of the
16,232-query stream's time, unchanged by the relation work; the per-commit
counters of `benchmarks/counters.py` (see [testing.md](testing.md)) show
what a commit changes in instantiation and search without timing noise.
