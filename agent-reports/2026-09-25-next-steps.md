# Agent report: next steps after the fact-lattice plan (constants, bounded irrationals, relevance)

- **Date:** 2026-09-25
- **Status:** plan for a fresh session. Nothing in it is implemented except
  item 1, which sits unreviewed on local branch `constant-queries`.
- **Scope:** `satassume/sympy_api.py`, `lra_adapter.py`, `relations.py`,
  `engine.py`; tools `ab.py`, `gate2.py`, `refine_replay.py --log`
- **Read this if:** you are the session that finishes this work

## 0. Where things stand

- `main` at `015d544`: the fact-lattice plan is complete (issue #12;
  `2026-09-25-facts-landing.md` has every stage, review and risk). Stage 2
  (facts shared between EUF-equal terms, `satassume/transfer.py`) and the
  lazy rule-block writes are landed; the replay is about 4.7% faster than
  before them.
- Reports to read first: `2026-09-25-facts-0-measurements.md` section 6
  (capability census, free Booleans), `2026-09-25-facts-2-transfer.md`,
  `2026-09-25-facts-3-refine-outcome.md`,
  `2026-09-25-global-solver-0-measurements.md` (search cost against session
  size, assumption-set structure), the explainer
  https://claude.ai/artifact/4qy6ChvwfsdxdURkJ82JY6 (uninterpreted relations
  and free Booleans).
- Why these items: queries whose assumptions hold a comparison against an
  irrational constant (`x <= pi/2`, from refine's inverse-trig handlers) are
  answered None today, because no theory reads the comparison. Of the 498
  stream answers free Booleans would add, 404 are questions about constants
  only (item 1), 90 involve the comparison's variables (item 2), 4 are
  unrelated to it (item 3).

## 1. Constant queries without the assumptions (branch `constant-queries`, unreviewed)

Two commits on `015d544`. Rule (the owner's): if every expression in the
proposition has no free symbols and is a number (`expr.is_number`, which
excludes undefined functions such as `f(1)`), the query ignores the
assumptions; one path, no fallback.

- `2a3b38a`: answered by SymPy's old assumption system (`expr.is_<pred>`).
- `1279626` (tip): answered by the engine's context-free path instead
  (`_engine_ask(proposition, True, eng)`); `_old_answer` kept unused.

| version | stream | gate2 |
|---|---|---|
| old system | 428 more definite, all agree with SymPy | **23 answers lost** (e.g. `Q.algebraic(asin(7))`, `Q.imaginary(exp(pi*I/2))`) |
| engine without assumptions (tip) | the same 428 | 0 changed |

Semantics change in both: a constant query no longer raises for
inconsistent assumptions. **The owner has not yet chosen between the two
versions** (they first asked for the old system; the engine version was
recommended because it loses nothing). Then: suite, an Opus review,
land, a comment on issue #12 listing the semantics change. If the owner
keeps the tip, delete `_old_answer` and its helpers, or keep them only if a
test uses them.

## 2. Irrational constants as bounded variables in LRA (high priority)

The arithmetic theory reads only linear relations with rational
coefficients, so `x <= pi/2` is uninterpreted and sinks the query. Treat
each maximal closed numeric subexpression that is not rational (`pi`, `E`,
`sqrt(2)`, `pi**2`, `log(2)`, `sin(1)`, Floats as they are) as a fresh LRA
variable per session (the same constant, the same variable) with rational
bounds `lo < c < hi` from a rigorous interval (mpmath interval arithmetic,
or `evalf` with an error bound, widened by a margin), asserted as root
facts. `pi/2` and `x - 2*pi` stay linear; `x*pi` stays uninterpreted.

- Sound: anything proved for every value in the interval holds for the
  constant. Comparisons closer than the bounds' width stay undecided (fixed
  precision first, e.g. 30 digits; refine on demand only if measured
  necessary).
- Catches what free Booleans cannot: `x > 3 & x <= pi/2` is inconsistent.
- Where: `lra_adapter.py` (`terms`/linear forms and registration) and
  `relations.py` (guards: LRA sees relations through a `real`-guarded twin;
  a constant is real iff SymPy says so, `is_extended_real`).
- Stage 0 first (an hour): from the stream, count sessions that fail with
  `Uninterpreted` and how many of their relations would become linear
  (`agent-reports/2026-09-perf-rounds/scripts/` has the round-2 failing-set
  census to copy from).
- Acceptance: answers may become more definite (verify every one against
  SymPy's `ask`, by hand where SymPy says None); new InconsistentAssumptions
  only where the assumptions are really inconsistent, each listed (expect
  the 3 sets of section 4 of the explainer, 36 stream queries); nothing less
  definite. Fuzz: an LRA fuzz with constants (`tests/test_lra_fuzz.py`
  style) against a checker that evaluates with the true values; the solver
  and real-theory fuzz; suite; `tools/ab.py` and `tools/gate2.py` with
  `--allow-more-definite`; refine scoreboard (expect the 6 relation losses
  to go; recipe in `2026-09-25-refine-capability-baseline.md`, with the
  plugin's `REFINE_BASELINE_ENGINE_KW`).
- After it lands, re-measure the free-Boolean option
  (`Engine(uninterpreted="free")`): it becomes a fallback for what is still
  unreadable (nonlinear), and its default is the owner's call again with
  new numbers.

## 3. Relevance: use only the assumptions connected to the query

Assumption conjuncts that share no symbol (transitively) with the query
cannot change its answer, only the consistency check. Stage 0 first:

- From the per-query log (`tools/refine_replay.py --log`, format in
  `tools/query_log.py`): time in queries that end None, and, for each
  query, whether its assumption set splits into components by shared free
  symbols (transitively; `eq(x, y)` and `x < y` connect) and how many
  nodes and clauses the query's own component has against the whole set.
  Also count sessions that would be shared if keyed by the component.
- Design if it pays (the rounds' lines: 5% to start, 3% to land): key the
  session and the answer memo by the query's component instead of the
  whole set; keep the error set identical by checking the whole set's
  consistency once per set (memoized) before answering, or ask the owner
  to drop that check.
- Relation to other work: it is a cheap cousin of the persistent-solver
  plan's scoped search (`2026-09-25-global-solver-0-measurements.md`: a
  median search needs 50 clauses; search cost grows about 1.8 ms per 1,000
  variables). Do it before that plan's stage 1.

## 4. Smaller open items

- `readable-templates`: rebase recommended (`2026-09-25-stale-branch-triage.md`
  section 2: two rules on `main` use helpers the rewrite deletes).
- `origin/relation-speed`: closed at -2.2%; the owner may delete it.
- Persistent solver stage 1: fund as a bounded experiment, after item 3.
- Update the memory notes (`next-engine-plans`, `perf-round-2-outcome`) at
  the end.

## 5. How to work (the owner's rules)

- Every subagent is Opus (`model: "opus"`), including reviewers; ordinary
  subagents, no Claude sessions on the Pi.
- Every command under 270 s (`timeout 260`; chunk fuzz seeds; the suite
  takes about 150 s, split by file if needed).
- Stage work on a branch; an Opus reviewer reads the diff for the case that
  breaks it and re-runs fuzz and gates; land on `main` by fast-forward or
  cherry-pick; never stage unreviewed commits on local `main`; risks in an
  issue, no PR.
- One measuring workload per machine. Clean timings on the Pi: give one
  subagent exclusive use, sync by git bundle (recipe in the memory note
  `pi5-benchmark-container`).
- Environment: `PYTHONHASHSEED=0 PYTHONPATH=.:/home/tilo/sympy
  .venv/bin/python` (memory note `satassume-test-environment`; the refine
  tests need SymPy `6379c4da69`, extracted with `git archive`).
- Reports in `agent-reports/`, written as the work happens.

## 6. Finish (after each item and at the end)

- Record each landing on an issue (a new one per item, or #12 for item 1)
  with the answers that changed and the risks; update this file's status.
- Clean up everything the session made, and say what was kept and why:
  temporary git worktrees and `tmp-*`/landing branches here
  (`git worktree list`), files under `/tmp/claude-1000` that are not
  another session's, the session scratchpad; on the Pi, bundles in `/tmp`,
  worktrees under `/work/src/wt-*`, landed branches and `refs/remotes/land/*`
  in `/work/src/perf-work`, any SymPy copy shipped there. Leave other
  sessions' directories alone.
- Update the memory notes (`next-engine-plans`, `perf-round-2-outcome`,
  `pi5-benchmark-container` if the Pi layout changed).
- Final message: what landed (commits, Pi numbers), what was dropped and
  why, open decisions for the owner.
