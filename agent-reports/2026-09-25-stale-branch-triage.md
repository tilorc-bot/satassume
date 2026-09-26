# Agent report: triage of the stale engine branches (relation-speed, readable-templates, two report branches)

- **Date:** 2026-09-25
- **Status:** `relation-speed`: closed without landing: after two fixes and a port onto
  stage 2 its answers match `main` exactly, but it is only 2.2% faster (below
  the 3% line) for a subtle engagement argument (section 1). `readable-templates`:
  recommendation only (rebase, section 2). `agents-report-cache-ttl` and
  `agents-report-ttl-wording`: deleted from `origin` (both were ancestors
  of `main`: `118a009`, `7ffe4a3`).
- **Scope:** `origin/relation-speed` (`f0334e1`, 2026-09-23),
  `origin/readable-templates` (`a6c254c`, 2026-09-22), against `main` at
  `f01e905` (and, for the port, `66871eb`)
- **Read this if:** you wonder what happened to those branches, or you
  pick up the templates rewrite

## 1. relation-speed

One commit, "Relations: engage EUF on a user equality; zero links
deferred; guard cache" (`relations.py`, `lra_adapter.py`, tests,
`tools/relbench.py`, design note). It is 79 commits behind `main`. It
cherry-picks onto `main` without conflicts.

What it does: an unguarded theory (EUF) takes the internal atoms (link
atoms, interface equalities) only once a user atom engages it. The zero
link is created only at engagement: for LRA it is redundant, since `zero`
gives `real` and neither `0 < e` nor `e < 0`. The guard literal of a term
is cached per session.

Gates, local, quiet machine:

| gate | result |
|---|---|
| `tools/ab.py main cand --rounds 5` (strict) | answers identical on 13,877 queries; best of 5: 2.931 s against 2.754 s, **-6.0%** |
| `tools/gate2.py` | 2,863 records (2,588 in scope), 0 changed |
| suite | 2 known failures, 1,700 passed (3 new tests) |
| Opus review | **do not land as is**: it loses definite answers |

The review found that deferral loses what EUF derives by congruence
through the zero links (`x = 0` gives `f(x) = f(0)`), e.g.
`ask(Q.zero(f(x)), Q.zero(x) & Q.zero(f(0)) & Q.lt(x, 1))`: `main` True,
the commit None; adding any unrelated equality restores it, and answers
became history-dependent. An Opus agent fixed it (`bc52956`): EUF is also
engaged for a linked non-constant term and, before a query is answered,
when the propagated assumptions contain `zero(e)` of a linked term or an
LRA-propagated interface equality (its fuzz found a case with real
symbols only, `nonzero(r) & real(s) & zero(s) & s >= r & s <= r`, which
the reviewer's first suggestion missed). A second Opus review: ready to
land (differential fuzz 0 differences over 40,000+ cases, the rebase onto
`main` clean).

Meanwhile stage 2 of the fact-lattice plan (predicate transfer between
EUF-equal terms) landed in the same code, and the commit no longer
applied. It was ported as `relation-speed-v2` (`c320780`): EUF now also
engages on template and extension equality atoms (which engage transfer),
answers identical to `main` on both gates and in 80,000 differential fuzz
cases. **Pi A/B against `main` `66871eb`, `--rounds 4`: ref 2.903 s, cand
2.838 s, -2.2%**, answers match. Stage 2 already engages EUF for every
session with an equality, which took part of the gain.

**Outcome: not landed.** 2.2% is under the 3% line the rounds use, and
the change carries a correctness argument (when EUF may stay detached)
that needed two review rounds and a port to stay exact. Branches kept
locally (`relation-speed-rebased`, `relation-speed-v2`) with their
reports; `origin/relation-speed` is left in place with this section as
its note, for the owner to delete. If relation-heavy workloads outside
the stream matter (the commit measured cold relation queries 25 to 45%
faster on `tools/relbench.py`), `relation-speed-v2` is the version to
revisit.

## 2. readable-templates: recommendation, rebase

One commit, "Templates: readable rule notation, and a tool to print
compiled rules". Structural templates become generators of rules in a
small notation (`(b.positive & e.real) >> y.positive`) instead of
index-based tuple specs. They lower to the same specs, so compilation,
pattern caching and the engine are unchanged. `tools/dump_rules.py`
prints what an expression gets. The branch's own check: identical clauses
on 5,936 expression shapes, except that `E**x` now shares `exp(x)`'s
rules. That adds `x infinite & extended_positive -> E**x infinite,
extended_positive`, a new consequence, so answers can become more
definite. Per-node template cost is lower for Add, Mul and functions and
about 0.7 µs higher for Pow.

State against `main` (114 commits behind):

- **One textual conflict** in `templates/core.py`. `main` added the
  half-integer parity rules for sums (`caa813d`: `_half_split`,
  `_half_rules` enumerating 2^k parity cases, `add_templates` returning a
  second pattern) in the old index-based style, next to the Add rules the
  branch rewrote.
- **One hidden break.** `templates/functions.py` merges cleanly, but
  `main`'s re/im-of-floor/ceiling rule (also `caa813d`) uses `Rules()`
  and `lits`, which the branch deletes from `_common.py`. The merged tree
  would fail at import. A textual merge is not enough.
- `41f2b80` (the `clauses_for` memo in `registry.py`) merges cleanly and
  is orthogonal.
- No other live branch touches `satassume/templates/`: `facts-theory`,
  `refine-identities` and `refine-monorepo` all leave it alone. So a
  rebase now conflicts with nobody.

Recommendation: **rebase, do not close.**

- **For.** The rewrite is the readability improvement the rounds kept
  asking for: round 3 reverted hot-loop cuts on readability grounds, and
  the rule tables are the part of the engine people read most. The port
  is small: two rules, the dynamic 2^k parity enumeration and the re/im
  look-through, into the notation. If the notation cannot express the
  former, a documented escape hatch that yields raw specs will do.
  `dump_rules.py` also helps whoever reviews the fact-lattice work read
  what a node gets.
- **Against.** It is a 1,200-line diff with an answer change (`E**x`),
  so it needs the full gates. That is about one agent-day plus review.

How to land it: one agent, rebased as one commit on `main`, with these
gates:
- the branch's clause-identity check, re-run and extended to shapes that
  exercise the two ported rules;
- `tools/ab.py --allow-more-definite` and `tools/gate2.py
  --allow-more-definite`, with every more-definite answer checked against
  SymPy (expect only `E**x` cases);
- the suite, and `tools/bench.py` for the template cost;
- an Opus review.

It can run at any time, since it touches no file the Pi session edits.
If nobody takes it up within about a week, close it with a pointer to this
section, because every further template commit on `main` adds to the port.
