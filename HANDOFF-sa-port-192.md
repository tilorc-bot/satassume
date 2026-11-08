# Handoff sa-port-192: step 5c10d (query entry and counters), WIP on port/5c10d

Base: origin/rust-slice b384ec1. Handed off at the context-budget note, about 75 minutes in. Nothing has been barred yet.

## Done so far (not yet barred)
- **Rust-owned `stats` and `last_budget_limited`.** entry.rs `EngineStats` holds 12 counters in Python's key order plus the
  flag, in the engine's `__dict__['stats']`. `StatsSlot` is a data descriptor that `session_live._install_entry` puts on
  `Engine.stats` and `Engine.last_budget_limited`. `Engine.__init__`'s dict assignment converts (`st:slot_set`) and its flag
  write is `st:flag_set`. The view is read-only: `[k]`, `get`, `in`, `keys`/`values`/`items`, `==`, `dict()`, `repr`, and
  `[k]=v` raises TypeError (`st:py_read` counts reads). The test-only export is `sa_solver.st_snapshot(eng)`.
- **Record methods** (engine.py :1420-1436, Python bodies on the dict; Rust's `ent_record_*`/`ent_*_budget_flag` installed over
  them): `_record_cache_hit`, `_record_relevant`, `_record_consistency_check`, `_record_scope_miss`, `_clear_budget_flag`,
  `_keep_budget_flag(limited)`. Callers changed: sympy_api.py :469 :478 :571 :583 :588-589 :1099 :1114, relations.py :907,
  engine.py Session `_custom` (the old `engine.stats["scope_misses"] += 1`). Rust writers now go native:
  relevance.rs `consistent`, context.rs `build_context` (set_checks; `ctx:py_stats` still ticks but the write is native),
  compile_loop.rs and relations_core.rs scope misses (`entry::scope_miss`).
- **Rows in Rust** (entry.rs): `is_` :567, `is_many` :618, `_decide` :479, `_put_result` :508, `_is_custom` :709, `ask` :743,
  `_ask` :798, `_check_version` :391, `_settings_changed` :436, `_drop_set_memos` :417, `_fresh_session` :452. `_over_budget`
  and `_note_budget` (budget.rs :554/:570, from port/5c7) are now wired and write the Rust state. The SLICE_BUDGET_FLAGS
  switch is gone. Callbacks, counted: `ent:cb_noncomm` (`_noncommutative*`, `noncommutative_false`), `ent:cb_gave_up`,
  `ent:cb_scope` (`theory_scope`), `ent:cb_basis` (`basis_lits`/`basis_formula`). Session methods and `s.truncated` are
  still read through the session (the state step).
- `term_live._Mark` (:155-158, :186-192) snapshots and restores through `_st_mark`/`_st_rollback` (`st:mark`).
- **Counters 301-326** (session.rs NAMES is 327): `ent:*`, `st:*`. **Plants 231-250** (relations_core.rs, `_ENTRY_PLANTS` in
  session_live.py :847). 6g(c6) (sa-port-191, ~/dev/sa-port-5) doesn't touch session.rs or relations_core.rs.
- **test_entry_core.py:** Python vs Rust per query on cert_wl and budget_wl (answer, `list(stats.items())`, flag), plus
  is_many, settings, epoch, a 400-step write sequence through the record methods, and the view forms. Result on orion:
  `same`/`counters` 2 passed. **Plants: 16 of 21 caught.** Not moved by this file: `ent-is-custom-no-hit`,
  `ent-ask-no-gave-up`, `ent-check-version-no-sync`, `ent-ask-no-clear-flag`, `st-consistency-drop`. For each, extend the
  test (a custom predicate, `relevance=True`, a shared DictCache across engines) or put it in `ELSEWHERE` with the
  suite/workload that catches it. The release build on orion compiles with no warnings in entry.rs or budget.rs.

## Left
1. Fix the five plants above (test or `ELSEWHERE`).
2. live.py: add `rec["eng"] = [list(eng.stats.items()), eng.last_budget_limited]` from `sympy_api.default_engine()` after each
   query (live.py :443), and a `stats_diff` in livecmp.py :35. This pins the view on every bar workload, budget included.
3. memo_check.py: add stats and the flag to its digest, then run the switch digest base (b384ec1) vs new on dev, fuzz, loop,
   zero, cert, scope and budget (see port-5c10c.md "The switch digest").
4. Short run of the bar's TESTS list plus test_entry_core.py on orion (`-n 4`), then the full bar on pareto1:
   PLANTS = 5c10d's plants that dev/fuzz reach, WLS="loop zero cert scope budget", SUITE_PLANTS=zero,
   BASE=~/sp19/sa-rust-ids-work/sa-port-189/bar-5c10c/suite, TESTS = 5c10c's list plus test_entry_core.py,
   DIRECT="relations_direct.py 300 0", N=6. Launch it as in port-5c10c.md.
5. Report results/port-5c10d.md, the port-ownership.md/.tsv rows (relabel the DictCache rows 10-15 and the
   `state: Engine.cache.store`/`custom_cache.store` callers from 5c10c to 5c10d), and the count list. engine.py stays out of
   the count: `_put_result` and `_note_budget` read `s.truncated` from Rust (entry.rs :511, budget.rs :573); `_ask` reads
   `s.solver`/`s.n_hold` (entry.rs :801-803) and `_gave_up` reads `s.solver.theories()`; plus the five sites in
   INVENTORY-state.md :302-312 and the Session class itself. Check this against STATUS "Counted modules" (14 of 32).

Rows on orion: ~/sa-rust-ids-work/sa-port-192/ (build.log, entry-test.txt, entry-plants.txt).
