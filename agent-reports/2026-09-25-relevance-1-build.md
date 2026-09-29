# Agent report: relevance (next-steps item 3), stage 1, build

- **Date:** 2026-09-25
- **Status:** built on branch `relevance` (base `irrational-tune` at
  `064e59e`). **-10.5% / -9.9% on the Pi against `irrational-tune`**
  (two runs of `tools/ab.py`, 3 rounds each, final code `b23bcc1`). That clears the 3%
  line to land. Stream answers are identical to `irrational-tune`, errors
  included. gate2: 0 changed. Suite: only the known failure.
- **Superseded in part:** stage 2 (`2026-09-26-relevance-2-connect.md`)
  no longer splits a set or query with a relation (defect (d) of the
  review). The timing is now -8.1% / -8.4%.
- **Scope:** `satassume/sympy_api.py` (`_ask`, `_relevant`, `_Split`, keys,
  consistency checks), `satassume/engine.py` (option `relevance=True`,
  `Engine.splits`, two stats counters), `tests/test_relevance.py`,
  `tools/relevance_fuzz.py`.
- **Read this if:** you review or land relevance, or change what connects
  terms in the engine (templates, theories, extensions).

## 1. Design

`sympy_api.ask(p, a)` checks the answer memo on `(p, a)` as before. On a
miss, `_ask` does the following:

1. A constant proposition takes the constant route as before (no
   assumptions).
2. Otherwise `_relevant(p, a)` splits `a`'s conjuncts into components by
   shared **keys**, transitively. The split is memoized per assumption
   object in `Engine.splits`, which is cleared together with the answer
   memo when registrations change. The query uses the union of the
   components whose keys meet its own keys.
3. If that union is smaller than `a`, the whole set is checked for
   consistency, once per set (memoized). The query is then answered as
   `ask(p, part)`, with the answer memo keyed by `(p, part)`, and the
   contextual session is the part's own. Every set with the same relevant
   part shares both.
4. If the check does not certify the set as consistent, for whatever
   reason, the query goes the old way under the whole `a`. That covers an
   inconsistent set, a set that is out of scope as a whole, a relation no
   theory reads, and any exception. Whatever the old path did (None,
   ValueError) stays exactly as it was, including which query raises and
   which one returns None first.

**Keys** of an expression:
- its free symbols;
- the classes of its undefined function applications (EUF congruence
  connects `f(x)` and `f(y)`);
- every closed subterm that is not a Rational (`pi`, `sqrt(2)`, `2*pi`,
  Floats, `oo`, `f(1)`);
- a Rational that is itself the argument of a unary predicate
  (`Q.polar(2)`).

A relation's keys are the keys of both sides, so `Q.eq(x, y)`, `x < y` and
`Q.is_true(x < y)` connect x and y.

**No split** in these cases:
- a predicate outside the vocabulary (a custom predicate: its registered
  function may mention any term);
- `Q.is_true` of a non-relational;
- anything that is not a Boolean over applied predicates or relations;
- a query with no key at all;
- any set while a vocabulary predicate is registered for a class
  (`Extensions._vocab`): its function may mention any term.

**Consistency check** (`_consistent`, `_part_consistent`):
- **A set with no relation and no keyless conjunct** is checked component
  by component. The check propagates the component's assumption literals
  in the component's own contextual session (`Engine._context_session`,
  what `Session.query_literal` checks before answering), memoized per
  component. Components are shared across sets, and the session the check
  builds is the one the component's queries use. The whole set's
  `to_formula` must still succeed (a matrix predicate elsewhere keeps the
  old None).
- **Any other set** gets one fresh session for the whole set with
  propagation, as in stage 0's `check` mode, and then a search
  (`Solver.solve`, `CHECK_SEARCH_RELATIONS`). With theories, a conflict
  often surfaces only in search: under `Q.eq(y, u) & Q.negative(u*y)`
  the old path raises for every query that goes to search, and without
  the search a query about another component would have answered None.
- On the stream, the per-component check is about 1% faster than the
  whole-set check everywhere (local, 3 interleaved runs each).
- **Escalation** (`CHECK_ESCALATE`, on). Once propagation passes, a check
  whose session is incomplete escalates once (full discovery of the cone)
  and propagates again, as a query that propagation leaves undecided does.
  For a component, this runs in a fresh session, so the session the
  queries use keeps its state. On the fuzz (section 4) it removed every
  one-sided error that a fresh engine reproduces, for about 0.5-1% of the
  replay: 144 extra fresh sessions and the escalation work.
- `CHECK_SEARCH` adds the search to the relation-free component checks
  too. It was off in the build (the fuzz found nothing it adds); the review
  turned it on: a Boolean conflict propagation does not see,
  `(p | i) & (p | ~i) & (~p | i) & (~p | ~i)` with `p, i` =
  `Q.positive(y), Q.integer(y)`, made the old path raise for `Q.positive(x)`
  under it `& Q.real(x)` while the part answered None (a lost ValueError).
  Not timed on the Pi.

## 2. Soundness

- **Answers.** Every component is a subset of the conjuncts. Whatever a
  subset entails, the whole set entails too. So a True/False from the part
  is also correct for the whole set, provided the whole set is satisfiable.
  If it is not, SymPy's contract is ValueError, which is the job of the
  check (next point). Keys only matter for *not losing* answers (the part
  must hold everything that bears on the query). For soundness they do
  not matter: connecting more is always safe.
- **Errors.** A set is answered by a part only after a check that finds it
  consistent. Otherwise it takes the old path unchanged. The check sees the
  inconsistencies propagation finds in a session of the whole set (or of
  each component). The old path raises in the same cases, plus some that
  only a query's own nodes, search, or theories engaged by the query
  reveal. Section 4 has the fuzz cases of that kind. The checks escalate
  and, with relations, search, which closes the ones the fuzz found.
- **Why components are independent** (this is what makes the
  per-component check equivalent, and the answers identical):
  - A component's session holds the nodes of its conjuncts and their
    subterms. Templates relate a node only to its own subterms. They never
    create relation atoms.
  - A constant inside a template is resolved on the spot and does not
    become a node. A rule with an undecided literal about a constant
    (`polar(2)`) is dropped (`templates/_common.py`, `_resolve_lit`).
  - So two components without shared keys share no solver variable, apart
    from the node of a Rational that some predicate applies to directly,
    which is a key, and whose facts are all decided except `polar`.
  - Facts declared on a symbol (`Symbol('x', positive=True)`) belong to
    the node x, which lives in one component only.
  - The `DictCache` receives root facts only (the assumptions are guarded
    by a selector literal), so it carries nothing between components.
- **Shared constants do connect.** Since item 2, `pi` is an LRA variable
  bounded by `lo < pi < hi`. Two components that constrain `pi` from
  either side (`x < pi` with x pinned above the true value, `pi < y` with
  y pinned below it) are each consistent but inconsistent together. So
  every closed non-Rational subterm is a key, and `pi`, `sqrt(2)`, `E`,
  Floats (their rationality is open) and `f(1)` (a free EUF term) connect
  the conjuncts that mention them. Rationals do not connect: their facts
  are decided context-free and they are fixed values in LRA and EUF.
- **Relations: where independence is only approximate.** In a session with
  relations, theory combination can connect terms of different components
  when both are pinned to the same value. For example, `x = 2` and `y = 2`
  merge x and y in EUF (directly, or through interface equalities from
  LRA), and congruence can then merge `sin(x)` and `sin(y)`. So the
  per-component check is used only for sets without relations. Sets with
  relations get the whole-set check, which sees these merges as far as
  propagation does.
  - The answers can still differ in principle: the whole set may derive a
    fact about `sin(x)` from a fact about `sin(y)`. Such a difference is
    only ever a None on the part's side (the subset argument above), and
    the fuzz found no case that reproduces in fresh engines.
  - Connecting all of these would mean treating every structural head
    (`Add`, `Mul`, `sin`) as a key, which connects almost everything.
- **The cases the brief asked about:**
  - a query with no free symbols: the constant route runs first,
    unchanged. A non-constant query without keys is not split.
  - custom registered predicates and vocabulary extensions: not split (see
    "No split" in section 1).
  - `f(x)` and `f(y)` with `x = y`: the class `f` is a key, and so is the
    relation.
  - `Q.is_true` of a relational: handled as the relation.
  - matrix and other out-of-scope parts: the whole set fails `to_formula`,
    and the query keeps None.
  - the answer memo: `(p, part)` is exactly what `ask(p, part)` would
    compute, since a part's components all touch `p`. Registrations
    changing clear both memos.

## 3. Gates

| gate | result |
|---|---|
| stream answers, `irrational-tune` vs `relevance` (all 13,877, exact, errors included; local, every version up to `b23bcc1`) | **identical** |
| `tools/ab.py tune relevance --rounds 1 --allow-more-definite` (local) | both sides 24 errors (item 2's), 549 more definite, same lists |
| stage 0's three queries 5718/5720/5768 | now definite on both sides (item 2 reads `pi`); no set on the stream fails the check as uninterpreted |
| sets not certified by the check on the stream | 4 whole-set checks, all out of scope (`Q.zero(Y)`, a matrix): old path |
| gate2 `--allow-more-definite`, both sides (`relevance` at `b23bcc1`) | 0 changed, the same 1 more definite (#2860, out:relation) on both |
| suite, per file, at `b23bcc1` | all pass except the known `test_shared_facts.py::test_cached_sympy_fact_does_not_make_assumptions_inconsistent` (2 params) |
| `tests/test_relevance.py` | 17 passed |

Engine counters on one stream pass (tune → relevance):

| counter | tune | relevance |
|---|---:|---:|
| engine queries | 6,311 | 4,472 |
| searches | 3,750 | 2,731 |
| cone searches | 753 | 509 |
| sessions | 1,664 | 1,540 |
| queries answered by a smaller part | | 3,244 |
| consistency checks | | 179 |

## 4. Differential fuzz (`tools/relevance_fuzz.py`)

**Setup.**
- Five symbols: `x`; `y` real; `z`; `u` integer; `v` positive.
- Each seed takes a random subset of them, so that sets split often.
- Terms: `s`, `s + 1`, `2*s`, `s*t`, `s + t`, `f(s)`.
- Conjuncts: unary facts; the relations lt, le, gt, ge, eq and ne between
  terms, or against 0, 1, 1/2, -2, `pi`, `pi/2`, `sqrt(2)` or a Float;
  negations; disjunctions.
- Per seed, two fresh engines (relevance on and off) get the same 4 sets ×
  6 queries in the same order.

Run in 6 chunks of 700 seeds (1000-5199) on the final code:

| | |
|---|---:|
| queries | 100,800 |
| same answer | 100,786 (of them 15,807 `error` on both sides) |
| answered by a smaller part | 30,094 |
| contradiction (True against False) | **0** |
| error on one side, a definite answer on the other | **0** |
| definite from the part, None from the whole set | 2 |
| None from the part, definite or error from the whole set | 12 |

12 of these 14 were re-run in fresh engines, one query per engine
(seeds 1206, 1731 ×2, 1890, 2250, 2445, 2916, 3196, 4393, 4901 ×3; the
other 2 were not listed by the run). All 12 give the same answer on both
sides, None in each case. So these differences come from each engine's
history: its fact cache and LRU sessions after the earlier sets of the
seed. The old path depends on that history in the same way. Seed 3196 is
not even split (its set is a single component) and still differs.

**How the checks got here.** Before escalation and relational search
were added, the same kind of run had one-sided errors that do reproduce
in fresh engines:
- seed 2336: `Q.negative(v + 1)` with `v` positive. The old path raises
  for queries that go to escalation.
- seed 1084: `Q.even(x) & ~Q.nonzero(x + 1)`.
- seed 4203: `Q.eq(y, u) & Q.negative(u*y)`, found only by search.

With the final checks these give the old answers. The earlier fuzz logs
are not kept in the repository.

**What remains.** Under a semantically inconsistent set whose
inconsistency no check finds, the old path already raises for some
queries and answers others. For example,
`Q.finite(x) & Q.irrational(x + 1) & Q.prime(2*x) & ...` answers
`Q.real(x)` True and raises for `Q.positive(y)`. With relevance, a query
whose part avoids the inconsistent component can answer where the old
path would have raised through search in the whole session. The fuzz
did not produce such a case once the checks escalate and search.

## 5. Pi timing (exclusive, `tools/ab.py`, 3 rounds, best-of, twice)

Final code, `b23bcc1`:

| pair | run 1 | run 2 |
|---|---|---|
| `irrational-tune` → `relevance` | 3.462 → 3.100 s, **-10.5%** | 3.446 → 3.103 s, **-9.9%** |
| `main` → `relevance` | 2.665 → 3.117 s, +17.0% | 2.668 → 3.104 s, +16.3% |

Earlier versions, same pairs:

| version | vs `irrational-tune` (two runs) | vs `main` (two runs) |
|---|---|---|
| `3aa5bfd`: propagation-only checks | -10.2%, -10.2% | +16.0%, +16.0% |
| `f374158`: + escalation | -9.5%, -9.4% | +15.8%, +17.0% |

The three versions are within noise of each other (about 1%).

- Relevance recovers about 0.35 s of the 0.78 s that item 2 added over
  `main` on these runs.
- `ab.py` prints "ANSWER MISMATCH" for every side except `main`, because
  of the 24 errors item 2 introduced against the recording (made on
  `main`). Both item-2 sides show the same 24 errors and 549 more definite
  answers.
- Pi hygiene: bundle `/tmp/rel-all.bundle`, refs
  `refs/remotes/land/rel-{main,tune,cand}` in `/work/src/perf-work`,
  worktrees `/work/src/wt-rel-{main,tune,cand}`, logs
  `/tmp/rel-ab-*.log`. All removed afterwards. The two idle `claude`
  processes were not touched.

## 6. Risks

- **Error set:** the error set is not identical in principle for
  semantically inconsistent sets that no check finds but some query's own
  nodes or theories would (section 4). It was already query- and
  history-dependent before. The fuzz found no case that reproduces in a
  fresh engine, and the streams have none.
- **Memory:** `Engine.splits` holds up to 20,000 `_Split` entries plus the
  per-component check results. `_KEYS` is a global memo of up to 100,000
  entries.
- **LRU:** the per-component check builds the component's contextual
  session through the LRU (16 sessions). For a query whose part is empty,
  this builds sessions for components that may never be queried. On the
  stream the net effect is fewer sessions built (1,540 against 1,664).
- **Completeness:** in sets with relations, congruence through pinned
  values across components is not a key (section 2), so a None where the
  whole set would answer is possible. The fuzz and the stream found none.
- **Extensions:** any registered vocabulary extension disables relevance.
  A registry with only custom predicates disables it only for sets and
  queries that use them.
