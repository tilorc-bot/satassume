# HANDOFF sa-port-333: witness check, steps (1) and (2) done, (2b)-(4) and the landing left

Branch port/witness-check, head da6eb2ee (before this file's commit), pushed to origin. Worktree
~/sa-rust-ids-work/sa-port-328/wt in clone ~/dev/sa-port-19. Rebased onto origin/rust-slice 32ba9a3 (sa-port-335's
F_MAYBE_NAN removal, landed 06:38Z 19 Nov). Nothing is landed. No bar, no S1, no digests, no iv were run by 333.
Stopped at the context budget, between items.

## Done

(1) d52129da: the check falls through on knowledge a user registered. Entry points found (rg over `def register`,
`def lazy`, `_handlers|_vocab`, `_bump(`, `relation_specs`, `templates` in satassume/, and `def register|def lazy|
\.lazy\(` in rust-spike/slice/*.py): eng.extensions is NOT the only one.
- Extensions.register / unregister on the engine's registry (the old guard (f), unchanged, asked first) and on the
  default registry while the engine uses another (state/epoch.py: it still decides sympy_api's scope).
- TemplateRegistry.register (templates/registry.py:161), and TemplateRegistry.lazy (:98), which registers a user's
  module like a built-in one with no epoch bump.
- Engine(templates=...) and the Engine.templates setter (engine.py:~1550): clause_templates is then None.
- Engine(relations=...) and Engine.relation_specs (engine.py:~1465).
- The slice adds none: session_live.register_instrument (:948) registers our instruments only.
Whose a template or adapter is, is read off `__module__` (satassume.knowledge.templates. / satassume.theories.).
Checked on Rust after the dev workload: 34 templates, none outside the package (knowledge_live's replacements keep
the module). `_users_knowledge` is asked last, next to the P1 guard, and writes nothing.
Kept test, 5 cases (one per entry point); plant 754 `SLICE_WITNESS_PLANT=skip-users`: all 5 fail, `template` and
`templates-function` on the answer (None, not True), python and rust.

(2) da6eb2ee: Engine._record_certified (queries +1, witness_certified +1), called by sympy_api._engine_ask. The key
is always in Engine.stats (0 with the switch off): THE DEFAULT PATH NOW HAS A 13TH STATS KEY. This needed the first
Rust change of the witness check: entry.rs EngineStats is a view of exactly Python's keys, so KEYS is 13 and
ent_record_certified is new (no tick, no plant). The stats test is unchanged and passes off and on.

Checked on orion only (aarch64 .so a956b03496066671 on da6eb2ee, not the bar's x86-64 build):
- tests/test_witness.py + test_sympy_api.py + test_layering.py: 214 passed in each of python/rust x off/on.
- 14 rust-spike/slice test files that touch stats (p1/one_test.sh, before the rebase): all exit 0.
- 8 tests/ files that read stats, switch on: python 212 passed; rust 3 failed, all in test_writeback_provenance.py,
  the same 3 ids that fail on the rust base e5db633 (sa-port-331/job-c5239b9/suite-base-rust).

## Not done, in order

- The FULL SUITE has not run on da6eb2ee. Unknown: whether harness/state.py or tests/test_memos.py need a row for
  witness.py's two new module constants `_TEMPLATES`, `_THEORIES` (strings) or for the 13th stats key.
- results/witness-check.md is not updated: section 3 (f), section 4 (plant 754), section 8 (the stats test now
  passes), section 10, and "There is no Rust change" in section 3, which is no longer true.
- bar.sh has no route for SLICE_WITNESS_PLANT rows or a SLICE_WITNESS=1 no-plant row; (4) needs both.
- (2b) freeze, digests on/off, test_witness.py, iv with the switch on: tools328/pre330.sh, gate330.sh, iv329.sh.
- (3) S1, 12 rounds on a pareto1 quiet lease: tools328/time328.sh / time329.sh. `_users_knowledge` scans every
  loaded template per certified query, uncached: 76 us on loaded orion with all 107 loaded, 34 are loaded in dev.
  If dev Python loses beyond the spread, the alternative is a memo keyed on the epoch, which is a query-time write
  and needs a state row; that is a design change to put to the architect, not to make silently.
- (4) the bar with rows no-plant SLICE_WITNESS=1 and plants 749-752, 754, wall time per row, quiet handler firings.
- OWED to name: Engine.stats has a 13th key on the default path; ent_record_certified has no tick.

## FILE:LINE MAP (da6eb2ee)

- satassume/witness.py: assumption 5 :34-40; PLANT names :88-93; _users_knowledge :134; witnesses :508, the two
  last guards :551-556; "what still differs" :56-60.
- satassume/sympy_api.py:1136-1141 the switch, _record_certified, return None.
- satassume/engine.py: stats dict :1402-1409; _record_certified :1429.
- rust-spike/slice/solver_rs/src/entry.rs: KEYS :47, WITNESS_CERTIFIED :64, ent_record_certified :343, :903.
- rust-spike/slice/session_live.py:1067 _ENTRY_METHODS.
- tests/test_witness.py: users_knowledge fixture :294, the kept test :310, the counts test :396.
- tests/test_sympy_api.py:206 the stats test (unchanged).
- rust-spike/slice/p1/bar.sh: PLANTS routing (`term:NAME`) for the witness rows to add.
- Outputs: ~/sa-rust-ids-work/sa-port-333/ (build logs, t2/ slice test logs).
