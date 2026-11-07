# Handoff sa-rust-15: S step 2 is done (issue 323, branch rust-slice)

No job is running. Next is step 3, in another session: live theory callbacks into the Python theories.

## Read first
`rust-spike/slice/results/step2-mutants.md`: mutant table, known differences A to E with smallest scripts, limits.

## For step 3 and 4
- The plan's "digest" column is still open: step 2's digest column is API answers. Step 3's dev and fuzz digests fill it, so re-score the 10 then.
- Difference A (solver call inside a hook, 42 of 42) is step 4's to trace. The planner's ruling: a gate failure unless only test stubs do it, and any adapter that can reach it gets fixed.
- B to E are unfixed and need `solver.rs`, not the wrapper. Decide whether they matter once real adapters run. Check whether a real theory can raise from `pop_level` (B).
- Mutant 5 is caught only by `fixed 5`. Mutant 7 needs `_cla_inc` set by hand.
- From sa-rust-14, still open: `fixed_sessions` has 3 sessions at real tunables, and whether they reach `reduce_db` at 1000 learnts isn't measured. Theory models are compared by `repr`, so real theories need a stable one, which isn't checked.

## Running the tools
From ~/dev/sa-rust on orion: `. ~/sa-rust-ids-work/env.sh; export PYTHONPATH SA_EVAL_DATA PYTHONHASHSEED`. `env.sh` sets `W`, so don't use that name for your own paths.
- Sweep, 3 minutes, in the background: `$PY rust-spike/slice/mutate_slice.py WORK --sessions 1500 --step1 300 --seed 1 --jobs 4`. Writes `results.jsonl`, `mutants.json`, `table.md`, `logs/` in WORK as each check ends. Unmutated row must read "no"; mutant 3 must be caught by state compare.
- `$PY rust-spike/slice/fuzz.py --known 2>/dev/null`: known differences and the exemption self-test.
- `fuzz.py --sessions 1500 --seed 1000 --reach 2>/dev/null`: clean run with reach and uncovered lines. `--no-fixed`: random sessions only. `--label "fixed 5"`: one session.
- Panics print to stderr, so keep it out of your context.

## File:line map for step 3 (lines at this head)
- `rust-spike/slice/backend.py:34` `install()`, `:40` patches `engine.Solver` and `ref.Solver`; `satassume/engine.py:92,311` and `satassume/ref.py:80,217` import and build them.
- `lib.rs:37` `run` (exceptions at entry), `:89` `PyProps`, `:138` `impl Theory for PyTheory`, `:221` `__traverse__`, `:371` `register_atom`, `:452` `dump`.
- `solver.rs`: `:581` `clear_hooks`, `:1180` `new_level`, `:1328` `backtrack`, `:1369` `attach_theory`, `:1386` `register_atom`, `:1427` `tprop`, `:1441` `theory_sync`, `:1528` `theory_imply`, `:1570` `theory_decide`, `:1601` `theory_check`, `:1858` `search`, `:1926` `solve_int`, `:2318` `dump`.
- Hook-using adapters: `satassume/theories/euf/euf_adapter.py:149-165` and `theories/lra/lra_adapter.py:468-496` (solver binding), `euf_adapter.py:153`, `lra_adapter.py:486,518,543` and `satassume/relations.py:1685,1834,1842,1853` (`register_atom`), `satassume/theories/transfer.py` (lazy atoms), `satassume/engine.py:895,924` (`solver.value`).
- `satassume/sat/solver.py`: `:2348` `_search` (hook order 2376-2412), `:1851` `attach_theory`, `:1876` `register_atom`, `:1953` `_theory_sync`, `:2025` `_theory_imply`, `:2063` `_theory_decide`, `:2091` `_theory_check`, `:2432` `_solve`, `:2516` `_fill`, `:2553` `_ring_hit`.
- Per-session state in step 3: `state.dump_py(s)` and `s.dump()` give the same dict; `state.digest(d)` hashes it for two-process runs; `state.diff(a, b)` names the first difference.
- `fuzz.py`: `:64` `Probe`, `:138` `Stub`, `:255` `after_pop_raised`, `:268` `KNOWN_SITES`, `:275` `known_difference`, `:296` `run_session`, `:335` `shrink`, `:403` `gen_session`, `:640` `fixed_sessions`, `:684` `reentry`, `:775` `known_scripts`, `:792` `selftest_known`, `:840` `known`, `:869` `main`.
- `mutate_slice.py`: `:28` `M`, `:86` `triage`, `:103` `score`, `:166` `main`.
