# Handoff sa-rust-14: S step 2 is built but NOT done: no valid mutant scores yet (issue 323, branch rust-slice)

Stopped at the architect's request at 184k. No job is running. The successor finishes step 2, then stops; step 3 is another session.

## What is left
1. Fix `mutate_slice.py` (below), run it, and get the table.
2. Each mutant not caught: argue it equivalent in writing, one at a time, or state it as not caught. Pass rule, plan section 4: if the 5 missed aren't caught, say so plainly; don't weaken the check.
3. Re-run `check_step1.py` (not re-run since the edits here), push, report head SHA and table.

## Mutant scores: none valid
- **First table (01:22 UTC, all "no"): void.** `fuzz.py` put its own directory ahead of `--so`, so all 10 mutants ran the unmutated build. Fixed, with a check that exits if the wrong `.so` loads. The file `mut/mutants.json` in sa-rust-14's scratchpad is from that run: don't use it.
- **Second run: no result.** Killed by my own 590 s `timeout` (10 mutants x 4 checks, 1500 fuzz + 300 step-1 sessions, 4 jobs). It prints and writes only at the end, so nothing survived. I don't know why it ran long: a mutant may hang or just be slow, since the run had no per-check limit.

## Fix before running `mutate_slice.py`
- Add a `timeout=` per check in `score()` and score a timeout as its own outcome. A hang differs from a caught mismatch; don't count it as caught without saying so.
- Write `mutants.json` as each check ends.
- Run it in the background (`run_in_background`), not under a foreground timeout. An uncaught mutant costs about 70 s per 1500 sessions.
- Run: `. ~/sa-rust-ids-work/env.sh; export PYTHONPATH SA_EVAL_DATA PYTHONHASHSEED; $PY rust-spike/slice/mutate_slice.py WORKDIR --sessions 1500 --step1 300 --jobs 4 [--only 2,5,6,7,9]` from ~/dev/sa-rust on orion. Mutants are indexed from 0; the 5 the replays missed are **2, 5, 6, 7, 9**: `_mention` order, ring None, `_fill` growth, `_learn` bump order, theory unit reason.
- Use `[m]utate_slice` style patterns with pkill: `pkill -f 'fuzz.py --so'` killed my own shell.
- Sanity: 3 (no var_inc decay) must be caught by state compare. If not, the tool is broken again.

## Column meaning (my reading, check it)
`digest` = answers only (result or exception, conflict) on step 1's corpus. `state` = state compare on that corpus. `fuzz-a` = answers only on fuzz sessions. `fuzz` = state compare on fuzz sessions. **These are API answers, not engine dev and fuzz digests**, which need step 3. The plan's "digest" column can only be filled that way once step 3 runs: say so in the report.

## Clean run on the unmutated solver
`$PY rust-spike/slice/fuzz.py --sessions 1500 --seed 1000 --reach 2>/dev/null` (68 s): clean apart from the known differences below. 1483 sessions finished, 181,574 calls.
Reach, Python side (planner asked for the first three):
- `analyze_final` under blocks: 658 calls with blocks registered, 82 hits on a block reason (1103 calls in all)
- restarts: 1667; `reduce_db`: 126 (48 with blocks, 62 with theories)
- `_fill`: 265, 15 past the model's end, **1 leaving None** (only the fixed session in `fixed_sessions`); ring reads with a None stored: 1039; ring hits on a model with None: 136
- clause rescale 100, theory conflicts 1334, theory unit reason above root 86, theory decisions 303, mention with 2+ blocks pending 250, late mentions 6, late written 9, raises compared 1547
- solver.py lines: 1744 of 2017. The list includes def and module lines, because monitoring starts after import. Larger real gaps: 1147-1151 (mention masks overlapping a new block), 1168-1171 (block with no models), provenance 2765-2824.

**Thin or unverified:** nearly all reductions use lowered tunables (`_restart_first`, `_learnt_size_min`, set per session). `fixed_sessions` has 3 at real tunables, and I did not measure whether they reach `reduce_db` at 1000 learnts. `_cla_inc` and `_var_inc` are set near the rescale limit by hand. Only one session leaves None after `_fill`, and whether it catches mutant 5 is untested. No state compare runs inside a hook, because of difference 1.

## Real differences found (not fixed)
1. **A solver call from inside a hook: 42 of 42 hook x method pairs differ.** Python runs it; Rust raises RuntimeError "Already borrowed" or "Already mutably borrowed". `--reach` prints the table (`fuzz.py:635`). Smallest: a theory whose `assert_lit` calls `solver.nvars()`, then `solve([1])` on a registered atom. A grep of satassume/theories found adapters holding `_solver` only around registration; I did not trace hooks at runtime, and tests' stubs may do it. Step 3 or 4 should confirm.
2. **After `pop_level` raises inside a backtrack, the next call:** Python IndexError, Rust PanicException (a BaseException), same state. Smallest (`fuzz.py` spec form): `{'raise_at': {'pop': 29}, 'decide': [31], 'conflicts': [(-31,), (-31, 31)], 'finals': [(-31, 31)], 'model': True}` with `attach_theory T0; register_atom T0 31 'a31' False; entails 24 [] 0; add_clause [-13, -18]`. Counted as "known difference" (23 in the clean run): state is compared there, then the session ends. **That exemption is a choice of mine to review:** `known_difference` (`fuzz.py:236`) accepts any IndexError vs out-of-bounds panic, not just this cause.
3. **`add_pattern` with a one-literal clause:** `add_pattern([[1], [0, 2]], 29, 2)`. Python appends the clause, then raises IndexError at `out[1]`; Rust panics before storing it, so the state differs. Input breaks the contract, and nothing outside solver.py calls `add_pattern`. I removed unit patterns from the generator, so the fuzzer no longer shows this.

Also a Python oddity (same on both): after a raising `push_level` a variable can leave the heap for good, and a later model holds None for it; the ring then counts a clause as satisfied by that None. Only for a caller who keeps a solver after a hook raised.

## Changed in this session
- `solver_rs/src/solver.rs`: `dump()` at the end; `restart_first` and `learnt_size_min` are now fields; `var_inc` and `cla_inc` public.
- `solver_rs/src/lib.rs`: `dump`, getters and setters `_restart_first`, `_learnt_size_min`, `_var_inc`, `_cla_inc`.
- `state.py` (Python dump, `diff`, `digest`), `fuzz.py`, `mutate_slice.py`; `check_step1.py` now has a main guard.
- `dump()` skips Python's `_cowner`, `_uowner`, `_cante`, and closure memos. `model()` is never called by the tool except where a script says, because it completes stored models; step 1's check called it every time, hiding the None paths.

## File:line map for step 3 (lines at this head)
- `rust-spike/slice/backend.py:34` `install()`, `:40` patches `engine.Solver` and `ref.Solver`; `satassume/engine.py:92,311` and `satassume/ref.py:80,217` import and build them.
- `lib.rs:37` `run` (exceptions at entry), `:89` `PyProps`, `:138` `impl Theory for PyTheory`, `:221` `__traverse__`, `:371` `register_atom`, `:452` `dump`.
- `solver.rs`: `:581` `clear_hooks`, `:1180` `new_level`, `:1328` `backtrack`, `:1369` `attach_theory`, `:1386` `register_atom`, `:1427` `tprop`, `:1441` `theory_sync`, `:1528` `theory_imply`, `:1570` `theory_decide`, `:1601` `theory_check`, `:1858` `search`, `:1926` `solve_int`, `:2318` `dump`.
- Hook-using adapters: `satassume/theories/euf/euf_adapter.py:149-165` and `theories/lra/lra_adapter.py:468-496` (solver binding), `euf_adapter.py:153`, `lra_adapter.py:486,518,543` and `satassume/relations.py:1685,1834,1842,1853` (`register_atom`), `satassume/theories/transfer.py` (lazy atoms), `satassume/engine.py:895,924` (`solver.value`).
- `satassume/sat/solver.py`: `:2348` `_search` (hook order 2376-2412), `:1851` `attach_theory`, `:1876` `register_atom`, `:1953` `_theory_sync`, `:2025` `_theory_imply`, `:2063` `_theory_decide`, `:2091` `_theory_check`, `:2432` `_solve`, `:2516` `_fill`, `:2553` `_ring_hit`.
- For per-session state in step 3: `state.dump_py(s)` and `s.dump()` give the same dict; `state.digest(d)` hashes it for two-process runs; `state.diff(a, b)` names the first difference. Theory models are compared by `repr`, so real theories need a stable one, which isn't checked.
- `fuzz.py`: `:52` `Probe`, `:126` `Stub`, `:246` `run_session`, `:354` `gen_session`, `:591` `fixed_sessions`, `:635` `reentry`.
