# Handoff: sa-port-49, component 4 slice A (issue 323)

Branch `port/4a`, on `rust-slice` 19ed342. **Not landed. Nothing here has met the bar.** Brief: `~/dev/architect/briefs/NEXT-port-4a.txt`.

## What's written, and how far it's been run
- `TermRefuse` is now a BaseException (`solver_rs/src/term/py.rs:16`). Built on orion only (aarch64): rebuild on pareto1 and copy the x86-64 .so to pareto0.
- `term_live.py`: the `_ask` wrapper, `_Query`, `_Mark` (rollback), `_journaled_put`, the `keys=True` consumer, `from_env`.
- `knowledge_live.py` now reads `term_live`'s table, so there's one `_ask` wrap. `COUNTS` and `RAISED` are the same objects.
- `term_discard.py` and `fresh.py --term/--term-out/--discard/--no-rollback`: the discard comparison.
- `test_knowledge_lazy.py`: the read-raises test now expects a refusal, not `KnowledgeFault`. **Edited, not run.**

**Only run so far:** one smoke script, `~/sa-rust-ids-work/sa-port-49/first/smoke.py`, one query. Planted at `_complete_check`, `_formula`, `relations._key`, `query_literal`: answers same, raised 4, refused 4, state clean 4 of 4. `verdict` wasn't reached there, so it shows nothing.

**Dev, orion, seed 0, under `~/sa-rust-ids-work/sa-port-49/first/`. Fresh-engine comparison only, not the bar's full set:**
- `dev-py.txt` against `dev-keys.txt` (table and key consumer on): byte-identical, 1,985 queries. 1,935 converted, 50 kept (`out-of-scope`). Keys asked: 4,048 at `lra_adapter`, 1,919 at `relations._key`. **Real refusals 0**, so the real-refusal path has only run on plants. Handler rows 0.
- `dev-py.txt` against `dev-discard2.txt` (a planted refusal in every query): **0 answers differ, 0 digests differ, session counts equal.** Raised 1,985, refused 1,985, so nothing swallowed one. Handler rows 0. All 12 sites reached (rerun the per-site count from `dev-discard2.json`).
- **Not "leaves nothing" yet:** the state check is clean on 70 and differs on 1,915, always and only in 3 stamps: `sympy_api._FORMULAS` 1,727, `_CONST` 1,682, `_KEYS` 1,682. My guess, not checked: `reset_module_state` leaves the stamp unset, the run restamps it, and it's a stamp only, with no entries left. Check that, then either restore stamps in `_Mark` or explain them.
- **Void, don't use:** `dev-discard.txt`. `_complete_check` is a staticmethod and my plant bound it as a method, so every call raised TypeError and `engine.py:1906` hid 6,616 of them, adding sessions. Answers still matched, which is the danger this slice is about. Fixed in `term_discard.install`. The handler counter showed it.
- **Not run:** the `--no-rollback` plant, so the zero differences above aren't yet shown to catch anything. Fuzz. Any suite. All tests.

## The finding to carry into the report
Section 9 and `PORT-INVENTORY.md:373` name 2 handlers. The engine's path has 7 that catch `Exception`: `engine.py:1906`, `sympy_api.py:1107`, `relations.py:1989`, `:2011`, `:2018`, `lra.py:461`, `lra_bounds.py:249` (`ref.py:605` is the reference path). That's why the base class changed instead of each site being wrapped. Update section 9's wording.

## What's left, in order
1. Settle the 3 stamps above. Any other name in `left` is a channel: fix it in `_Mark` or bring it to the planner. `rollback:cleared` is 0 on dev: report it per workload.
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
- `Engine.is_` and `Engine.ask` called directly have no table (`current()` is None), so they can't refuse.

## Map
- Refusal path: `term_live.py` `_install._ask`. Rollback: `_Mark`. Consumer: `_key_consumer`.
- Handlers: list above. Counter: `handler_count.py:20-45`, covers only the 2 named; bar item 4 is those two.
- Fresh: `fresh.py` loop near its end; sites and state: `term_discard.py` `SITES`, `state`, `check`.
- Suite: `run_suite.sh`, `suite_report.py`, base rows `~/sa-rust-ids-work/port-census/pr328-check/suite-rust`, last bar table `results/port-lazy.md:9-17`.
- Remote: `~/sp19/p1_job.sh` on pareto1 points at sa-port-19's clone, so set T and S for this one.

Report at landing: SHA, three numbers, what ran and what didn't, modules whole (expected 0), the 7 handlers, real refusals by reason per workload, `read_raised`, `read_term_missing`, exp-factor product refusals (the planner's follow-up), the recount at 1906.
