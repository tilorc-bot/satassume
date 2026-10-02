# History-dependence harness

Checks that `satassume.sympy_api.ask(prop, assumptions, engine)` answers as a
function of the query, the assumptions and the declared configuration only:
never of what was asked before in the same engine or process, of what is
cached or evicted, of which sessions exist, or of `PYTHONHASHSEED`.  Answers
are `True` / `False` / `None` / `ValueError` (inconsistent assumptions); any
disagreement counts, including `None` against a definite answer.

Everything runs from the repository root, with any Python that has SymPy,
pytest and Hypothesis (`pip install sympy mpmath pytest hypothesis`), and
`PYTHONHASHSEED=0` (except the hash-seed mode).  Nothing needs installing:
`python -m harness` and `python -m pytest` find `harness/` and `satassume/`
in the current directory.

## What is checked, and against what

`harness/checker.py` runs a *stream* of queries through one long-lived
engine and compares every answer with a *clean reference* computed right
after it:

| level | reference | resets |
|---|---|---|
| 1 `ENGINE` | a fresh `Engine` of the same configuration, same process | everything the engine owns: fact cache, custom-fact cache, answer memo, splits, contextual sessions (solver, learnt clauses, held levels, witness ring, relation glue, transfer candidacy), failed-set memo, transfer bases |
| 2 `MODULE` | as 1 after `harness.state.reset_module_state()` | also every module-level memo (`to_formula`, relevance keys, template patterns, clause splits, rule tables, LRA bounds and interpretations, EUF class test, `sympy_atom`, extension per-class memo) and SymPy's `cacheit` cache; not the intern table of `constfield`'s constants, which live objects index |
| 3 `PROCESS` | the query in a fresh interpreter (`python -m harness exec`) | the process; used to confirm discrepancies and for `PYTHONHASHSEED` variation |

Level 1 is the default per query; `--ref-check-every k` adds a level-2
reference to every k-th query and reports level-1/level-2 disagreements
separately ("reference instability", a memo dependence).  Discrepancies
are confirmed at level 3 with `--confirm` (several hash seeds).

Registrations (`satassume.register`) are configuration: a stream may carry
`register`/`unregister` events, applied to the global registry as the
stream runs; the reference for a query is computed under the same
registrations.

Each stream runs in several orders (`--orders`): `forward`, `reverse`,
`shuffle`, `grouped` (sorted by assumption set: maximal session reuse),
`interleave` (round robin over sets), `repeat` (memo hits).

Configurations (`harness/state.py`, `--config name,name` or `all`):
`default`, and one preset per mechanism: `tight` (every bounded cache and
threshold small), `whole` (no relevance split), `notransfer`, `norel`,
`free`, `budget` (discovery budget 5), `evict` (fact cache of 16 nodes,
memos of 8 and 2 entries).  Since #97 P1 every contextual query builds the
session of its set, answers and discards it; `reuse`, `cone` and `churn`
set only the session-reuse settings that no longer do anything
(`keep_sessions`, `session_limit`, `cone_search`, `cone_threshold`) and
run as `default` does.

Mismatches are classified (`contradiction`, `none-vs-definite`,
`raise-vs-definite`, `raise-vs-none`, `error`) and grouped by (assumption
set, kind), since one inconsistent session makes every later query under
it disagree.  The first of each group is shrunk by ddmin to a minimal
prefix that still reproduces, and written to `--out DIR` as `NAME.json`
(the stream as srepr strings; an item whose srepr rebuilds into another
tree is marked `"srepr_exact": false`) and `NAME.py` (standalone repro).
`--ignore kind,kind` leaves known kinds out of the report while still
counting them.  Every report line carries `first_hit` (order, index and
the number of queries run when the first mismatch appeared).

**Attribution.**  After shrinking, `checker.attribute` re-runs the minimal
prefix and clears one engine state before the final query (the fact
caches, the contextual sessions, the answer memo, the splits memo, the
failed-set memo; then pairs; then all): the state whose clearing restores
the fresh answer is the *carrier* of the dependence.  `checker.family_of`
turns carrier, kind, configuration and the shape of the prefix into a
heuristic family tag (`A`, `B`, `C`, `C'`, `D`, `E`, `G`, `G'`, `K`, `L`,
`T`, `R:<carrier>`, or `new:<carrier>-<kind>` for what no known mechanism
explains); the summary line and the JSON carry both.  A pair carrier
`X+answers` whose prefix asks the query itself is tagged by `X`: the
answer memo only holds a copy of the query's earlier answer, which `X`
made history-dependent.  Two tags rest on
extra replays: with the trigger/observer shape (a relation query in the
prefix under the query's set, none in the query) the prefix is replayed
with `transfer=False` (`without_transfer`: the discrepancy vanishes for
`T`, stays for `G`); with a session carrier the prefix is replayed with
each query replaced by `Q.commutative` of the terms it mentions
(`mention_only`: still reproducing means the prefix acts by linking its
terms, `G'`, not by what it learnt, `K`).  The tag is a triage aid, not a
proof: a cache-carried definite answer with a non-commutative symbol in
the prefix is tagged `C` even if a second mechanism were involved.

## Stream profiles

The base generator draws every assumption set and every proposition
independently.  That covers the *input* space and hardly the *state*
space: a history-dependent answer needs two or three coordinated queries
(the same node under two related sets, a conjunct asked back as a
proposition, the same query on both sides of a registration change, a
probe of a subterm after a big parent was visited), which independent
draws reach with vanishing probability.  `harness/profiles.py` builds those
shapes on purpose; `--profile NAME` (or a comma-separated list, or `all`)
selects one in `fuzz`, `hypo`, `audit` and `hashseed`:

| profile | shape | aims at |
|---|---|---|
| `related` | sets are random subsets of one conjunct pool (shared components, nesting, single conjuncts); propositions are the conjuncts, their negations, sibling predicates on their nodes, subterm probes, context-free probes | the relevance layer's cross-set memos and part sessions, cache flows between a set's nodes and subterms |
| `focus` | one or two symbols, a small term pool, most queries under one set, compound propositions | long sessions: model reuse, held levels, learnt clauses, accumulated demand |
| `deep` | sums and products of 6-30 terms, nested; propositions about the big terms and their subterms | the discovery and escalation budgets (400) and `session_limit` in the default configuration |
| `relational` | relation-heavy sets sharing conjuncts (equalities to symbols, terms, numbers; order chains); unary propositions on sides and on `f(side)`; `Implies(eq, unary)`; relation propositions under unary sets | EUF congruence, predicate transfer, links added after the session exists |
| `declared` | symbols declared with every kind of fact (zero, infinite, prime, composite, irrational, `integer=False`, `finite=False`, polar, ...) and same-name variants | declared facts against assumptions and templates |
| `registry` | the same batch of queries about the objects a registration affects before `register`, after it, and after `unregister`; other registrations switched meanwhile (`--custom`) | the fact caches and sessions across registration changes (family R) |
| `links` | unary-only sets of order predicates on linear forms over real symbols (with opaque nonlinear terms and constants with bounds); *triggers*: relation queries under a set; *observers*: order predicates on linear relatives of the set's terms (shifts, scalings, sums, differences, `c*t + k`) under the same set | the relation glue a session is built with when its query's scope has a relation atom (`scope.theory_scope`, #97 P3; family G) |
| `transfer` | sets that put a term into an EUF class through the links (`zero(u)`, `positive_infinite(u)`) and state facts about applications of the class's value (`positive(f(0))`); *triggers*: equality queries under the set; *observers*: the same applications of the term (`positive(f(u))`, `g(f(u)) + 1`) | the predicate transfer a session is built with when its query's scope makes an equality (`scope.transfer_wanted`, #97 P3; family T) |
| `lazy` | both shapes in one stream, over sets of both and mixed shapes, with generic queries between | the same, in a stream that looks like the base one |
| `mixed` | one of the above per seed | |

The base stream takes `--lazy P`: after a query under a set, with
probability `P`, a trigger (a relation query) and one or two observers
(unary queries about linear and congruent relatives of the set's terms)
follow under the same set (`QueryGen.lazy_pair`).

## Lazily switched-on capabilities (`harness/lazy.py`)

Some capabilities of the engine are not there from the start of a
session: they switch on when a kind of input first appears and stay on.
A history-dependent answer of this kind needs a *trigger* (the query that
switches the capability on) and an *observer* (a later query under the
same assumptions that only that capability can answer).  The always-on
parts (rule base, structural templates, search over the set's own atoms)
answer questions about the syntax the set already contains either way, so
observers must be about terms *related in meaning but new in form*.  The
earlier profiles produced triggers (the `relational` profile asks
relations under unary sets) but their follow-ups were sibling predicates
on the set's own subterms, which the templates decide with or without the
capability.  The capabilities, from the code (see the table in
`harness/repros/README.md`, "Third round", for what was checked by
experiment):

| capability | switched on by, where | scope | what only it can prove (the observers) |
|---|---|---|---|
| **relation glue** (`Session.relations`, a `Relations` object) | construction, when the query's theory scope has the glue (`scope.theory_scope`, #97 P3: a relation atom or a sign-on-sum pair in the set or the query): `Session.__init__` creates `Relations`; the set's own terms are linked after the set's complete check (`Session.link_set`) unless the set's own scope has the glue, and every user formula is passed to `Relations.process` (`Session._relations`); `_link` adds `extended_positive(e) <-> gt(e, 0)`, `extended_negative(e) <-> lt(e, 0)`, `zero(e) <-> eq(e, 0)` for every argument `e` of a vocabulary atom of the assumptions and of every later query, and every relation side (relations.py 392-445, 636-655); the LRA and EUF adapters attach at the first interpreted atom (`_adapter`, `_interpret`) | per session, which is built for the query and discarded (#97 P1) | LRA over the links: order facts about **linear relatives** of the set's terms (`positive(x + y)` from `positive(x + y - 1)`, `positive(x - 3)` from `positive(x - pi)` with the constant's bounds, `positive(n - 2)` from `positive(n - 3)`, `zero(x - y)` from `nonnegative(x - y) & nonnegative(y - x)`), and the inconsistency of such sets (`positive(x + y - 1) & negative(x + y)`); the extended-order clauses (`_order_infinite`) for `oo` summands |
| **linked terms** (`Relations.linked`, `top`) | with the glue on, every term a query mentions (relation sides, vocabulary-atom arguments) is linked, for good; a fresh session links only the set's and the query's terms | per session, per term; grows | as above, through terms an *earlier* query mentioned: a relation in the query about `w + 1` decided because an earlier query mentioned `w` (family G') |
| **predicate transfer** (`Relations.xfer`, `TransferTheory`) | construction, when the query's scope makes an equality (`scope.transfer_wanted`: an `eq` atom, or an order atom and its reverse): `Relations.__init__` calls `_engage_transfer`, which attaches EUF and the transfer theory; candidacy (`sync_transfer`, `_congruent`) only grows | per session; never off | unary facts shared across an EUF class: **congruent applications** (`positive(f(u))` from `zero(u) & positive(f(0))`, `positive(f(u) + 1)`, `g(f(u))`), classes made by the links (`zero(e)`: `e ~ 0`; `eq(e, oo) <-> positive_infinite(e)`: `e ~ oo`), and by two zero terms (`f(u)` from `zero(u) & zero(v) & positive(f(v))`) |
| constant bounds (`Relations._bounded`) | the first atom whose linear form has the constant term (`_bound`, relations.py 614-628) | per session, per constant | part of the glue's observers (`x - 3` from `x - pi`); not separately history-dependent: the bounds come with the atom that needs them |
| infinity links (`_eq_infinity`) | each `eq(e, +-oo)` atom | per atom | part of transfer's observers (T3); the atom itself is the trigger |
| escalation (`Session.escalate`) | a query propagation does not decide, in the session built for the query (`Engine._ask`) | per session, which is the query's own | the conflict of an inconsistent set at level 0 (family A); a fresh session for an undecided query escalates as well, so no none-vs-definite observer |
| cone-session replacement and its memo clause (deleted in #97 P1 with the session reuse: a search runs in the query's own session) | was: a search in a polluted reused session | was: per set | was: the answer of the replaced query by propagation (family K) |
| lazy rule-block writes, `Solver.mention` (solver.py 903-950, 1110-1135, 1255) | a variable mentioned by a clause, an assumption, a theory atom or the query literal | per session, grows | nothing at the API level: the query literal is mentioned, and compound queries' atoms by their clauses; read only |
| held levels, the assumption cache, the witness ring (solver.py 1310-1380, 2265-2300, 2380-2440) | a successful `implied` or `solve` | per session | documented as pure functions of the clause set; read only (family K covers what learnt clauses add) |
| the vocabulary registry (`extensions._vocab`, `_node_cache`), `_failed`, `_xbasis` | a registration; an `Uninterpreted` set; a number's basis | per engine | family R (the first); the other two are memos of pure functions, read only |

`links`, `transfer` and `lazy` generate trigger/observer pairs for the
first three rows without reference to any particular defect; the
`relational` profile and the base stream with `--lazy` reach them too.

The base stream with `--custom` now also repeats recent queries right
after each registration event (six events per stream instead of three).

## Cache audit

`python -m harness audit` runs a stream through one engine, then compares
*every fact in its cache* with what a fresh engine derives context-free for
the same node (one fresh engine per node).  Since issue #97 (P2) the
cache is a pure memo of `Engine.is_` (only `is_` writes, True or False,
and no session reads it), so the audit checks exactly the memo property:
a cached fact a fresh engine does not derive is a fact that some other
path wrote, or an `is_` whose session was not the fresh engine's; the
query that first wrote it is found by replay and the finding goes through
the usual shrink, attribution and repro.  Before P2 a cached fact could
also have flowed into the node from outside its own cone (a session's
root facts written back); this mode found the E, L and C' routes below
that way, deterministically instead of waiting for a lucky probe query.

## Modes

```bash
export PYTHONHASHSEED=0

# pytest, fast part (every push, about 10 s): pinned repros, CI-sized
# links/transfer/registry runs, planted defects, the inventory
python -m pytest -q tests/test_history.py
# pytest, slow part (nightly, about 1 minute; HISTORY_SEEDS, HISTORY_EXAMPLES
# raise the effort; HISTORY_IGNORE=raise-vs-definite,raise-vs-none gates the
# other kinds only; HISTORY_STRICT=1 fails on known families too)
HISTORY_SLOW=1 python -m pytest -q -m slow tests/test_history.py

# random streams: seeds x configs x orders
python -m harness fuzz --seeds 0-19 --queries 300 --sets 6 --config default
python -m harness fuzz --seeds 0-5 --config all --queries 250
python -m harness fuzz --seeds 100-109 --custom --config default,tight      # register/unregister events

# Hypothesis (shrinks the stream itself; examples are kept in --out/.hypothesis-db,
# or --derandomize for the same examples every run)
python -m harness hypo --examples 400 --config default,tight --ignore raise-vs-definite,raise-vs-none

# the recorded corpus (tools/record_queries.py run over SymPy's tests), in chunks
python -m harness replay queries.jsonl --kinds ask,rec,old --config default,reuse,tight,cone --chunk 600

# refine-driven streams (queries sympy.refine makes over random expressions)
python -m harness refine --seeds 0-9 --exprs 40 --config default,reuse

# stream profiles (harness/profiles.py); `all` runs every profile
python -m harness fuzz --profile related,declared --seeds 0-9 --queries 300 --sets 5 --config default
python -m harness fuzz --profile registry --custom --seeds 0-9 --queries 200 --sets 4     # family R
python -m harness fuzz --profile deep --seeds 0-5 --queries 120 --sets 3

# lazily switched-on capabilities (harness/lazy.py): families G, G', T
python -m harness fuzz --profile links,transfer,lazy --seeds 0-9 --queries 150 --sets 4 --config default,whole
python -m harness fuzz --seeds 0-9 --lazy 0.2 --config default            # base stream with trigger/observer pairs

# cache audit: every cached fact against a fresh engine, per profile
python -m harness audit --profile base,related,declared --seeds 0-11 --queries 200 --sets 5

# the same stream under several PYTHONHASHSEED values, one interpreter each
python -m harness hashseed --seeds 0-3 --hashseeds 0,1,2,3,42 --config default --queries 300
python -m harness hashseed --profile related --seeds 0-2 --hashseeds 0,1,2,42 --queries 250

# re-run a saved discrepancy, optionally in a fresh interpreter under a seed
python -m harness repro harness/repros/G7-links-zero-scaled-term-order-after-relation.json [--hashseed 7]
python harness/repros/G7-links-zero-scaled-term-order-after-relation.py
python -m harness repro harness-results/fuzz-links-default-s0-0.json     # one a run wrote

# the inventory of module-level state (fails if an unclassified container appears)
python -m harness inventory

# the nightly campaign, one shard (tests, base, profiles, audit) or all
SEEDS=2 harness/campaign.sh profiles
```

Every mode prints one JSON line per (source, config) with `queries`,
`mismatches`, `kinds`, `groups`, the outcome and (engine/reference) pair
counts, and the family tags of what it found; shrunk discrepancies go to
`--out` (default `harness-results/`, not committed).  The exit status is 1
if a discrepancy was reported; with `--fail-on unknown` only if one has a
family tag that `checker.is_known_family` does not accept (`R:...`, `C+...`
and the documented letters are known; `?` and `new:...` are not), with
`--fail-on never` never.  `hashseed` counts only cross-seed disagreements
under `--fail-on unknown`.

## CI

* `.github/workflows/test.yml` (every push) runs the whole suite, which
  includes the fast part of `tests/test_history.py`.
* `.github/workflows/history-fuzz.yml` (nightly and on manual dispatch)
  runs `harness/campaign.sh` in four parallel jobs: `tests` (the slow
  pytest part with 6 seeds and 200 Hypothesis examples), `base` (random
  streams in four configurations, with registrations, with trigger/observer
  pairs), `profiles` (every profile, and the lazy ones in two more
  configurations) and `audit` (cache audit and hash-seed variation).  The
  size is `SEEDS` seeds per cell (default 8, about 20 minutes for the
  longest job, linear in `SEEDS`); a manual dispatch takes `seeds`,
  `seed_offset` and `queries`.  The seeds move every night.  A job fails
  only on an undocumented family; the logs, a summary table and every
  shrunk repro are uploaded as the artifact `history-<shard>`.

## Runtime self-check

`harness/selfcheck.py` wraps `satassume.sympy_api.ask`: every call is
re-answered in a fresh engine of the same configuration and a mismatch
raises `HistoryDependence` (or is logged); the original answer (or
`ValueError`) is still returned.  About one fresh query of extra cost per
call.

It is off unless installed from code, before the queries to check: at
the top of a script, or in a `conftest.py` to check a whole test run (the
repository root must be on `sys.path`, as it is for `pytest` run from the
root):

```python
from harness import selfcheck
selfcheck.install()                     # raise HistoryDependence on a mismatch
selfcheck.install(mode="warn")          # print a warning per mismatch and go on
selfcheck.install(mode="log", log_path="mismatches.jsonl")   # only record them
selfcheck.install(level=2)              # module memos and SymPy's cache cleared too
```

`install` wraps `satassume.sympy_api.ask` only; the engine is not changed
and nothing in `satassume` imports the harness.  Call it once (a second
call does nothing; the lines above are alternatives).  Recorded mismatches are
in `selfcheck.mismatches`.  Level 2 clears process-wide state (the module
memos, SymPy's cache) in the middle of other queries: single-threaded use
only.

## Findings

Found at c26e5e1.  At a186157 every pinned repro still reproduces
except G1-G6, which #51 fixed, and C, C2-C5, C4b, which #54 fixed (#47);
they are in `repros/fixed/` as regression tests.  The mechanism of G
remains (G7, found after #51).  The fast part of
`tests/test_history.py` checks both on every push.  The campaign logs of
the three rounds are not in the repository; the numbers below are from
them, at c26e5e1.  After #51 the `links` profile finds G in 1 seed of 20
and G' in 3 (100 queries, forward order), `transfer` still finds T in 9
of 10.


Families A-D were found by the base streams (first round), each shrunk to
a one- or two-query prefix and confirmed in fresh interpreters under
several hash seeds.  The profiles and the audit (second round) added:

* **R** (R1-R4 in `repros/fixed/`; fixed by #63, which keys every engine
  cache and session on the registry epoch): the answer memo was invalidated
  when the extension registry changed, but the fact cache, the custom-fact cache
  and the contextual sessions are not, and `Engine.is_` also caches
  `None`.  So a context-free answer computed before a registration stays
  None after it (fresh engine: True), a fact derived from a registration
  is still served after it is unregistered (fresh: None), a session built
  under a registration keeps its clauses, and a custom fact cached under
  one meaning of a predicate is served under another.  Found by
  `fuzz --profile registry --custom` in 7 of 10 seeds (first hit after
  27-149 queries) and by the base stream with `--custom` (seed 2 of 20,
  after 162 queries).  Both directions occur; the None-where-definite
  direction is an answer the current registrations contradict.
* **E** (`E1*.py`): the relation layer's root facts are written back.  A
  relation in a query links every vocabulary argument `e`
  (`extended_negative(e) <-> lt(e, 0)`, ...), and the extended-order
  clauses decide `lt(e, 0)` at the root for a sum with an `oo` summand;
  the linked unary fact is cached and a later context-free query answers
  False where a fresh engine answers None.  Sound (a sum with `+oo` is
  `+oo` or `nan`), history-dependent in the more-definite direction.
* **L** (`L1*.py`): a unit clause learnt by a contextual search is a
  root fact and is written back; a later context-free query about that
  node is decided where a fresh cone is not.  Sound.
* **C'** (`C6b*.py`): family C without a non-commutative symbol: the
  `acos` template's derived node `x - 1` receives `~zero` from the parent
  (its argument is not real), cached, so `ask(Q.zero(x - 1), True)` is
  False where a fresh engine answers None.  Sound (checked against SymPy;
  the symbol `w` is declared `nonzero`, hence real).

The audit over 48 streams (base, related, declared, deep; 200 queries
each) found no cached fact that contradicts a fresh engine's *definite*
answer: every flow is a definite fact where the fresh engine has None, and
every one checked by hand is sound.  Hash-seed variation over the profiles
(4 seeds each) and the eviction configurations (`tight`, `evict`, `churn`)
showed nothing beyond A-D.  The recorded corpus (`queries.jsonl`, SymPy's
own tests) showed no discrepancy.

### Third round: the lazily switched-on capabilities

* **G** (`harness/repros/G7*.py`; G1-G6 in `repros/fixed/`): a session's relation glue was created by
  its first relation atom and stayed (since #97 P3 the session is built
  with its query's scope, `scope.theory_scope`, and discarded after the
  query, #97 P1); it links every vocabulary argument of
  the assumptions and of the query to `lt`/`eq` atoms LRA reads.  So
  under `Q.positive(x + y - 1)` (x, y real) the query `Q.positive(x + y)`
  is None in a fresh engine and True after any relation query under the
  set (`Q.lt(x, 5)`, `~Q.eq(u, v)`, `x < y`, `Implies(Q.ge(..), ..)`); the
  raise direction exists too (`Q.positive(x + y - 1) & Q.negative(x + y)`
  is accepted until a relation query under it).  Carrier: the session; the
  answer memo hides a repeat of the same observer but not its negation or
  a compound with it.  Masked by the relevance layer unless the observer's
  component is the whole set (a relation query is always answered under
  the whole set).  The round-2 base stream had hit it (seed 19, tagged
  `new:sessions-none-vs-definite`, unanalysed).
* **G'** (`Gp2*.py`; Gp1 in `repros/fixed/` since R2): the same glue, per term: with the glue already on
  (the set has a relation), a query that merely *mentions* a term links
  it, and a later query about a relative of that term is decided.  The
  round-2 `relational` profile had hit it (seed 9, tagged `K`).
* **T** (all in `repros/fixed/`: T2 since #63 drops a session with a raise, T1, T3-T5 since R2 answers the prefix equality in its own component's session; the mechanism remains within a component): predicate transfer is engaged by the first equality
  atom that is not glue; from then on every node of the session is a
  candidate for sharing its unary facts with its EUF class.  Under
  `Q.zero(u) & Q.positive(f(0))` the query `Q.positive(f(u))` is None
  fresh and True after any equality query under the set (`Q.eq(u, y)`,
  `Ne(u, 1)`, `Q.is_true(Eq(u, y))`, `Implies(Q.eq(..), ..)`): the link
  `zero(u) <-> eq(u, 0)` puts `u` in the class of `0`, congruence puts
  `f(u)` with `f(0)`, transfer copies `positive`.  Also through
  `eq(u, oo) <-> positive_infinite(u)` (T3), two zero terms (T4), `Add`
  congruence (T5); the raise direction (T2).  Answers of G and T are
  sound where definite; the property under test is agreement.

Hit rates (150-query streams, 4 sets, 5 orders, 30 seeds per cell;
"first index" is the position of the
first discrepancy of the family in the forward order, min/median/max over
the seeds that hit):

| profile, config | seeds hitting G | first G index | seeds hitting T | first T index | G' |
|---|---|---|---|---|---|
| `links`, default | 23/30 | 2 / 26 / 77 | 0 | | |
| `links`, whole (no relevance) | 23/30 | 2 / 23 / 77 | 0 | | |
| `links`, reuse (no cone search) | 26/30 | 2 / 18 / 87 | 0 | | 3 |
| `links`, cone | 20/30 | 2 / 32 / 108 | 0 | | |
| `links`, tight (sessions replaced every 6 nodes) | 6/30 | 2 / 59 / 139 | 0 | | |
| `transfer`, default | 8/30 | 1 / 28 / 64 | 25/30 | 2 / 32 / 100 | |
| `transfer`, whole | 9/30 | | 28/30 | 2 / 34 / 118 | |
| `transfer`, reuse | 8/30 | | 27/30 | 2 / 32 / 113 | |
| `transfer`, cone | 4/30 | | 27/30 | 1 / 32 / 94 | |
| `transfer`, tight | 4/30 | | 23/30 | 1 / 38 / 110 | |
| `lazy`, default | 12/30 | 4 / 34 / 116 | 3/30 | 54 / 100 / 122 | 1 |
| `lazy`, whole | 14/30 | 4 / 34 / 109 | 5/30 | 4 / 31 / 122 | 1 |
| base with `--lazy 0.2`, default | 3/30 | 30 / 82 / 126 | 0 | | |
| base (round 1 generator), default | 1/30 | 1 | 0 | | |
| `relational` (round 2), default | 0/30 | | 0 | | |

The other families the campaign met (A, B, C, D, E) are
the known ones.  The `links` profile finds G in three seeds out of four
within the first 30 queries; `transfer` finds T in five out of six; the
round-2 `relational` profile and the plain base stream, whose observers
are sibling predicates on the sets' own subterms, find neither in 30 seeds
(the base stream's single G is a raise after a relation query).  A CI-sized
configuration that finds each reliably: `links` seeds 0-3 and `transfer`
seeds 0-3, 100 queries, forward order, about 3 s per stream (all eight hit
in the campaign at 150 queries; after #51 the `links` seeds that hit G
are rarer, and `tests/test_history.py` pins seed 13 of `links` and seed 2
of `transfer` as strict xfails).  Hash-seed variation
(`hashseed` mode, seeds 0-2 of both profiles under `PYTHONHASHSEED` 0, 1, 2
and 42) found the same discrepancies
under every hash seed and nothing beyond them.

Remaining blind spots: the reference is a fresh `Engine` in the same
process, so a dependence carried by a module-level memo or SymPy's cache
is only sampled (`--ref-check-every`, the `hashseed` mode); the family tag
is heuristic; the audit checks cached facts only, not what a reused
session holds without writing back; theory-internal state (LRA, EUF) is
exercised only through the answers; and only the harness's five
registrations are switched.

## Layout

| file | what |
|---|---|
| `state.py` | inventory of engine- and module-level state, `EngineConfig` presets, `reset_module_state`, `config_of(engine)` |
| `checker.py` | streams, orders, `execute`, references, `Discrepancy`, ddmin `shrink`, repro files, subprocess runs, `Checker` |
| `generators.py` | `random_stream(seed, ..., profile=)` and `stream_strategy(...)` (Hypothesis) over the whole feature surface |
| `profiles.py` | the stream profiles (`related`, `focus`, `deep`, `relational`, `declared`, `registry`, `links`, `transfer`, `lazy`, `mixed`) |
| `lazy.py` | triggers and observers of the lazily switched-on capabilities (linear relatives, congruent applications, relation queries) |
| `registry.py` | the custom-predicate registrations streams can switch on and off |
| `corpus.py` | `load_corpus` / `old_records` for `queries.jsonl`, `refine_stream` |
| `sympy_io.py` | srepr round trips (with a `Q` that resolves custom predicates) |
| `selfcheck.py` | the runtime self-check |
| `__main__.py` | the command line |
| `campaign.sh` | the nightly campaign, one shard per call |
| `repros/` | the pinned minimal repros (`README.md` there: mechanisms) |
| `../tests/test_history.py` | the CI entry point |
