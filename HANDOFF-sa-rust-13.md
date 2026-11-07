# Handoff sa-rust-13: S step 1 done (issue 323, branch rust-slice). Next: step 2, the compare tool (SLICE-PLAN.md section 4).

Base: rust-slice already contained main 9bafaa5 (it is also origin/main), so nothing was merged.

## Setup
`. ~/sa-rust-ids-work/env.sh; export PYTHONPATH`, run from ~/dev/sa-rust on orion. `$PY` is the venv's Python 3.12.
Build: `sh rust-spike/slice/build_solver.sh` (about 5 s; puts sa_solver.so next to backend.py, git-ignored).
Check: `$PY rust-spike/slice/check_step1.py 3000` (a few minutes at most; prints one line of counts, or the first mismatch).

## What's there (rust-spike/slice/)
- `solver_rs/`: the crate. `solver.rs` and `block.rs` copied from replay and edited, `map.rs` as copied, `theory.rs` the `Theory` trait, `lib.rs` the PyO3 class `sa_solver.Solver` and `PyTheory`.
- `backend.py`: `RustSolver`, `make()` (counts `created` and `dropped`), `install()` (patches `engine.Solver` and `ref.Solver`; returns undo). Nothing calls `install()` yet: step 3 does.
- `check_step1.py`: 25 hand scripts plus random API scripts. After every call it compares result or exception, model, conflict, root_trail, nvars, stats. Also a stub theory, hook exceptions, and drop.

## Result at this head
Same on 3025 scripts, 220,653 calls. Reach, summed on the Python side: 2,024 conflicts, 136,267 decisions, 1,782 ring hits, 1,054 blocks, 2,901 raises compared.
Stub theory: 100 hook calls in the same order. 200 sessions with a solver <-> theory cycle: 200 created, 200 dropped after gc.collect(). No `static` or `thread_local` in the crate.
One sanity mutant (VAR_DECAY 0.90) was caught, on php 6 5.
**Thin:** 1 restart and no learnt reduction that I saw (`reduce_db` needs `max_learnts` of at least 1000). `reduce_db`, restarts and `analyze_final` under blocks are weakly tested. The stub theory is one scenario, not a fuzz. Step 2 must drive these.

## Design choices step 2 and 3 inherit
- **Exceptions:** a hook's PyErr, and contract `Fault`s, unwind with `resume_unwind`, caught by `run()` at each entry, so state stands where a Python exception would leave it. Needs `panic = "unwind"`. A real panic still surfaces as PanicException, a BaseException, which `except Exception` doesn't catch: `check_step1.py`'s `call` would crash, which is what we want.
- **Attached token:** `PyTheory` uses `Python::assume_attached()`; the invariant is in `lib.rs`.
- **Lookups:** `assert_lit`, `check`, `push_level`, `pop_level` per call; `propagate`, `decide` once at attach, same as Python. So wrapping a theory method works.
- **Propagate is lazy** (`Theory::Props`), same as `for x, why in prop()`, for generators.
- **Rule tables:** `set_rule_block` calls Python's `_rule_tables` (validation, messages, its existing memo) and copies `.models` into a per-solver `Closure`. So Rust's memos die with the solver. It costs a table copy and a cold memo per session: step 5 will show it. Over 128 models `closure` scans.
- **GC:** `__traverse__` and `__clear__` visit theories, bound hooks and each stored model handle. Each `PyObj` clone is its own strong ref, so each is visited.

## Not ported or different (each is loud, not silent, unless noted)
- `owner` (non-BOTTOM), `provenance`, `root_step` raise NotImplementedError. `track_owners` is stored, unused. The engine sets it False; only tests use provenance.
- No private attributes yet. Tests read these on direct `Solver()`: `_trail_lim` 15, `_held` 12, `_lazy` 9, `_n_conflicts` 6, `_val` 4, `_ok` 4, `_n_ring_hits` 2, `_n_late` 2, `_n_late_written` 2, `_assumptions` 2, and 1 each of `_uowner _trail _ring _restart_first _rbc _rb_base _n_reductions _level _learnt_size_min _cowner _clauses _cante _backtrack`. Two tests subclass Solver (`BlockSolver`, `_CountingSolver`): the class allows it, but overriding a private hook has no effect.
- A solver call from inside a hook raises PyO3's borrow RuntimeError. The plan says adapters don't do this in search; not tested. Test stubs may.
- Literals past i32 raise OverflowError where Python would try to allocate. A hook's out-of-range literal becomes the bad-literal RuntimeError with a clamped number in the message.
- Silent difference: none known. `mention_blocks`' mask past 128 bits raises a TypeError/OverflowError from extraction, not Python's ValueError.

## For step 2
- Fields in `Solver` are private: add a `dump()` (trail, levels, reasons, learnts, watches, activity bits, phases, counters, ring) in `solver.rs` and a Python equivalent. `Reason::Block(m, base)` vs Python's int `(m << 32) | base` needs one encoding.
- `check_step1.py`'s `random_script` is a starting point for the fuzzer, but it has no theory, restart or reduction pressure. Set the tunables by building big instances: `_restart_first` and `_learnt_size_min` are Rust consts.
- Port `mutate.py`'s 10 mutants (paths under replay/ now live in `solver_rs/src`).

## Open for step 4 (not decided here)
`install()` patches the engine and ref.py only, so tests building `Solver()` directly stay on Python and pass trivially. Making them run on Rust needs the private attributes above and provenance. Which of these "backend on" means is a call for step 4 or the planner.
