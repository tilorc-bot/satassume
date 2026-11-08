# Handoff sa-port-182 (step 5c10a, fact caches), 8 Nov ~17:15 UTC

## Done
- port/5c10a from rust-slice 2d12e81. **Tested SHA for the running bar: 64031f6.** WIP 18d2bb6 before it. The handoff commit
  holds only this file and results/port-ownership.md/.tsv (results/, so the landing guard sees no source difference).
- `solver_rs/src/factcache.rs`: `FactCache`, registered as `sa_solver.DictCache` (store, maxsize, `_epoch`, `_settings`,
  sync/facts/get/put/clear, native rollback `_fc_mark`/`_fc_rollback`), `FactView` (the read-only `store` view; `clear` only,
  for the registry and `_settings_changed`), `fc_snapshot` (test-only).
- Counters 260-270 (session.rs NAMES is 271): fc:py_facts, py_get, py_put, py_sync, view, clear, full, key_eq, rollback, new,
  py_key. Plants 200-210 (relations_core.rs; session_live `_MEMO_PLANTS`): fc-shared-sync-is (200, the inventory's planted
  bug: a put lost on a shared DictCache), fc-put-new-drop, fc-new-no-maxsize, fc-sync-no-clear, fc-facts-first,
  fc-get-no-default, fc-no-bound, fc-custom-put-drop, fc-view-drop-last, fc-rollback-skip, fc-clear-skip.
- session_live.py `_install_factcache` / `factcache_native()` (SLICE_FACTCACHE, default rust): binds `sa_solver.DictCache`
  over Python's class in every loaded module, and gives Python's class a `__new__` that returns one. term_live.py: `_Mark.add`
  takes each native cache's mark and `rollback` undoes it; `_journaled_put` is installed only when the caches aren't native.
- test_factcache_core.py: 13 passed on orion. Python == Rust on every case; all 11 plants fire and are caught (200 through
  `shared:hits`, two engines sharing one DictCache); every fc counter fires.
- memo_check.py: fact stores in em_sizes/em_content/em_order, `fc_view_bad`, counts/fired/refused.
  **Switch digest: MATCH on all six workloads** (dev, fuzz, loop, zero, cert, scope) at PYTHONHASHSEED=0, base 2d12e81 (worktree
  ~/sa-rust-ids-work/sa-port-182/base, its own build) against 18d2bb6. Rows are in ~/sa-rust-ids-work/sa-port-182/mc/{base,new}.
  The answers and digests equal 5c9c's table. The fact stores at the end are dev 16, fuzz 7 (+5 custom_cache), loop 12, zero 1,
  cert 26, scope 1.
- Plant table (memo_check, 64031f6 build; `mc/plants-table.txt`, fired then caught by: C cleared, S digest, E stores, V view):
  put-new-drop fires everywhere, caught S E; facts-first is caught S on dev and fuzz; custom-put-drop is caught on fuzz only (the
  only workload with custom predicates); view-drop-last is caught S E V everywhere; clear-skip is caught C everywhere;
  new-no-maxsize fires 2 and is never caught (the default maxsize); 200, 203, 205, 206 and 209 are void on every workload (no
  shared cache, no epoch change, no `get`, no bound, refused 0 everywhere). Each of those is caught by test_factcache_core.py.
- Reached (mc/new2): fc:py_facts dev 435, fuzz 789; py_put 65 and 102; py_key 441 and 838; key_eq 8 and 10. fc:rollback, full
  and py_get are 0 on every workload (the test shows them firing).
- Cache tests on orion (rust): the 9 cache-reading files gave 127 passed and 3 failed, the same 3 as base (provenance x2, `_cowner`).

## Running: the bar on pareto1
`OUT=~/sp19/sa-rust-ids-work/sa-port-182/bar-5c10a` (launcher log ~/sa-rust-ids-work/sa-port-182/bar-launch.out, lease d6f31b78,
launched 16:58). Phases: build, tests (604 passed), direct (exit 0), suite done; live, plants, extra (loop zero cert scope) and
suiteplants (`zero`) were still running at handoff. The end marker is `end.txt`/`done.txt` in OUT.
**Suite: 5,991 passed, 127 failed, 23 skipped, 18 xfailed. Against 5c9c's rows, 1 changed outcome:**
`tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence` passed on base and failed here
(`assert len(run_stream(ops)) == 2`, got 1; the op-4 difference is missing). Unverified hypothesis: the test's planted memo
keys on `(id(self), proposition)` (tests/test_public_incremental.py:189-195), and `run_stream` (:134-141) makes a fresh engine
per op. If op 4's fresh engine reuses op 3's dead engine's address, it gets op 3's memoized None and matches the warm engine's
leaked None. The engine's allocation changed (its caches are now Rust objects). **To do:** check it by printing the fresh
engines' ids under rust on 64031f6 and on base, and run it on the Python backend. If it holds, the cause is the test's id reuse,
not a wrong value. It's still a changed outcome to explain under bar item 1 (and maybe a needs-internals or flaky-test note).

## Left
1. Explain the changed outcome (above). If it is a real Rust difference, fix it and rerun the bar.
2. Read the bar: `sum.txt` (bar_sum.py), plants and extra rows, suite-plants.txt, and the handler multiset against base (39
   rows in 2 tests on 5c9c).
3. `bar.sh land 64031f6` without PUSH, read the incoming diff, then `PUSH=1`. Check `git log origin/rust-slice` first
   (sa-port-175's 6g stack may land first).
4. Write results/port-5c10a.md in port-5c9c.md's form. The TSV/md rows are already done in this commit: DictCache.* landed
   5c10a, state rows `Engine.cache.store` and `Engine.custom_cache.store`, and the wiring row `_journaled_put`. Module count
   from ~/dev/architect/STATUS.md "Counted modules" (14 of 32 before; this step adds no whole module). Then `agent report`.

## FILE:LINE MAP
- rust-spike/slice/solver_rs/src/factcache.rs: doc :1-26, FactCache :50, sync :~190, facts, get, put, `_fc_mark`/`_fc_rollback`,
  FactView, fc_snapshot.
- session.rs: FC_* consts after BUD_QUERY_CONE (:321), NAMES :17, COUNTS size 271.
- relations_core.rs: FC_* plants after EM_SPLITS_PUT_DROP (:263), rel_plant arms.
- session_live.py: `_MEMO_PLANTS` (:790), `_install_memos` (:806), `factcache_native` / `_install_factcache` (:826-).
- term_live.py: `_Mark.__init__`/`add`/`rollback` (:133-170), the `_journaled_put` condition (:~940).
- engine.py, unchanged: DictCache :188-277, is_ :1992-2023, is_many :2050-2090, _put_result :2119, _is_custom :2153-2168,
  _settings_changed store.clear() :1553, _check_version sync :1579.
- tests reading the caches: test_writeback_provenance.py, test_registry_versioning.py, test_engine.py, test_p2_review.py,
  test_lazy_atoms.py, test_shared_facts.py (`type(Engine().cache) is DictCache` passes through the name binding).
- mc scripts: ~/sa-rust-ids-work/sa-port-182/bin/mc_all.sh TREE TAG [PLANT], mc_plants.sh.
