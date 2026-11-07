# Handoff: sa-port-49, component 4 slice A (issue 323)

Branch `port/4a`, on `rust-slice` 19ed342. **Not landed. Nothing here has met the bar.** Brief: `~/dev/architect/briefs/NEXT-port-4a.txt`.

## What's written, and how far it's been run
- `TermRefuse` is now a BaseException (`solver_rs/src/term/py.rs:16`). Only the x86/aarch64 build on orion has it: rebuild for pareto.
- `term_live.py`: the `_ask` wrapper, `_Query`, `_Mark` (rollback), `_journaled_put`, the `keys=True` consumer, `from_env`.
- `knowledge_live.py` now reads `term_live`'s table, so there's one `_ask` wrap. `COUNTS` and `RAISED` are the same objects.
- `term_discard.py` and `fresh.py --term/--term-out/--discard/--no-rollback`: the discard comparison.
- `test_knowledge_lazy.py`: the read-raises test now expects a refusal, not `KnowledgeFault`. **Edited, not run.**

**Only run so far:** one smoke script, `~/sa-rust-ids-work/sa-port-49/first/smoke.py`, one query. Planted at `_complete_check`, `_formula`, `relations._key`, `query_literal`: answers same, raised 4, refused 4, state clean 4 of 4. `verdict` wasn't reached there, so it shows nothing.

**Started, not read:** `first/dev-{py,keys,discard}.txt`, with `.json`, `.handlers`, `.log`, and `.done` last. Detached on orion, started 13:15:57 UTC. Compare `cmp dev-py.txt dev-keys.txt` and `cmp dev-py.txt dev-discard.txt`. These ran from the tree at this commit.

## The finding to carry into the report
Section 9 and `PORT-INVENTORY.md:373` name 2 handlers. The engine's path has 7 that catch `Exception`: `engine.py:1906`, `sympy_api.py:1107`, `relations.py:1989`, `:2011`, `:2018`, `lra.py:461`, `lra_bounds.py:249` (`ref.py:605` is the reference path). That's why the base class changed instead of each site being wrapped. Update section 9's wording.

## What's left, in order
1. Read the dev runs. `dev-discard.json`: `left` must be empty, `raised` == `term.refused`, every site's `reached` named. A name in `left` is a channel: fix it in `_Mark` or bring it to the planner. `rollback:cleared` must be reported.
2. Plant: `--discard --no-rollback` must differ from plain or show in `left`. If it shows nothing, the check is void. Also the bar's solver mutant 0 through fresh (`results/port-lazy.md` item 3).
3. Fix the tests that moved: `lazy_fire.py` (its rows expect the counter to see TermRefuse), `quiet_fire.py`, `knowledge_quiet.py`, `test_lazy_reads.py`, `test_knowledge_lazy.py`. Check `term_shadow.py`'s `except Exception` sites, e.g. `:660`-`:690`, still do what they did now TermRefuse passes them; run its shadow on dev.
4. Add `test_term_live.py`: refusal past each handler; nested `_ask` refuses to the top only; second run stays on Python; a **Python theory on the Rust solver raising TermRefuse from a hook** (`solver_rs/src/lib.rs:42-50` unwinds it), which `term_discard.SITES` doesn't plant; `read_raised` and `read_term_missing` reach the top.
5. Wire the suite: `rust_plugin.py` calls `term_live.from_env()` after its installs, near `:88` (shared file: name it). Not done, so **no suite has run on this yet**. `SLICE_TERM` defaults to `keys`.
6. Fuzz, then the suite on pareto0 with `handler_count`, then rebase and land per the bar.

## Open points I didn't settle
- `_Mark` snapshots one `len` per table per query, and a `dict(stats)`. Not timed; the bar moved timing.
- Overwrites of an existing memo key, and in-place changes to a value that's not a dict, list or set, aren't rolled back. The state check sees the first kind and copies one level for the second, so a deeper change wouldn't show. Say so.
- `_CONSTANTS` and `_BY_KEY` are truncated from outside, nothing edits `constfield.py`. `harness/state.py:262` says live objects refer to entries by index, so check nothing surviving a discard holds one. The Rust LRA backend is the place to look. 1b is moving that.
- Rollback's limits, in `term_live.py`'s docstring: SymPy's caches and `_assumptions`, and `Dummy._count` (`limits.py:92`). `term_discard` counts `dummy-count-moved`.
- The keys consumer asks for keys Rust may not have read on Python's order: it runs after Python's key at the same call, so a read happens only where Python's key was made. `read_raised` on these is now a finding (planner's nan ruling).
- A nested `_ask` still converts its own table, as `knowledge_live` did. Section 5 says the table belongs to the top-level query.
- Rust's `Engine.is_`/`Engine.ask` called directly have no table (`current()` is None), so they can't refuse.

## Map
- Refusal path: `term_live.py` `_install._ask`. Rollback: `_Mark`. Consumer: `_key_consumer`.
- Handlers: list above. Counter: `handler_count.py:20-45`, covers only the 2 named; bar item 4 is those two.
- Fresh: `fresh.py` loop near its end; sites and state: `term_discard.py` `SITES`, `state`, `check`.
- Suite: `run_suite.sh`, `suite_report.py`, base rows `~/sa-rust-ids-work/port-census/pr328-check/suite-rust`, last bar table `results/port-lazy.md:9-17`.
- Remote: `~/sp19/p1_job.sh` on pareto1 points at sa-port-19's clone, so set T and S for this one.

Report at landing: SHA, three numbers, what ran and what didn't, modules whole (expected 0), the 7 handlers, real refusals by reason per workload, `read_raised`, `read_term_missing`, exp-factor product refusals (the planner's follow-up), the recount at 1906.
