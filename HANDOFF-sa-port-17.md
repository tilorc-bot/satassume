# Handoff: sa-port-17, component 3 (transfer core), issue 323

**Not done, and not on `rust-slice`.** Handed off at the context note after the first slice. Everything is on `port/3`. Brief: `~/.local/state/agent/briefs/sa-port-17-20261107T093036Z.txt`; its terms still apply.

## What runs

`TransferTheory`, `EqualitySharing` and `transfer_wanted` are in Rust and run through the real engine via `backend.install()`. **`P` is not ported.** Python stays the default; `SLICE_TRANSFER=py|rust|shadow` selects (default `rust` once `install()` is called).

Results are under `~/sa-rust-ids-work/sa-port-17/s1/`. All on orion at hash seed 0, load about 35, no timing.

| Check | Result | Limit |
|---|---|---|
| Shadow, dev (`transfer_fresh.py dev shadow`): result and full state per hook | 6,013 calls, 52 theories, 0 differences | Never shown to catch anything: no mutants run. Rust `EqualitySharing` isn't in this mode (it uses Python's); Rust `transfer_wanted` is, uncompared |
| Fresh engine, `py` against `rust`, dev: answer, solver and transfer digest per session | 1,985 queries, 3,332 sessions, `cmp` identical | **Only 52 of 3,332 sessions have a transfer theory.** `explain` crossed 13 times, so lemma paths are thinly covered |
| API fuzz (`transfer_fuzz.py --seed 1 --rounds 400`) | exit 0: pyset 2,000, sharing 400, wanted 2,000, theory 400 sequences, 15,568 ops | One seed, no mutants. Its EUF merges are positive equalities only |
| Quiet handlers, `engine.py:1906` and `sympy_api.py:1107` | 0 catches on the dev runs | Dev only. Counted by `sys.monitoring`, and that counter has never fired, so it isn't shown to work |
| EUF crossings, dev, `rust` | rep 2,079, members 1,397, explain 13 | |

## Not run

In order. None of the "held to" items below has a result yet:

1. **Plant mutants first.** Every 0 above is unproven until then. Say which were caught by a comparison and which only by a crash. Force a catch to prove the quiet counter works.
2. `transfer_fresh.py fuzz` in `py`, `rust`, `shadow`; hash seeds 0 and 1 on `py` and `rust`.
3. Wire `live.py` (non-`plain` checks don't call `install_transfer`; see `:276`) and `rust_plugin.py` (`:45`; must install before collection, as port/2's lines 67-75 do). **Until this, `run_live.sh` and `run_suite.sh` don't test component 3 at all**, apart from `--check plain`.
4. Suite's three numbers by test id against 5,961 / 77 / 46, on `mbp2015`, detached. Brief conflict: its task paragraph says pareto0 or mbp2015, its addendum says keep pareto0 free. mbp2015 satisfies both.
5. History (`run_history.sh`), boundary re-score, rerun of mutants 2, 5, 6, 7, 9 now a real theory runs on Rust. The planner's standing text on 10 of 25 boundary mutants still applies.
6. **`P`** (below). Then landing: rebase on `origin/rust-slice`, rerun, push without force.

Also unmeasured: SymPy-construction counts (the core handles only ints, by reading, not by a count), speed, and how many of the 32 runtime modules this adds. Queries kept on Python by this component: none known, not counted.

## Things to know

- **Order in `decide`.** `for p in preds` iterates a Python set of small ints, and the first match picks the decided variable, so order reaches the search. `pyset.rs` reproduces CPython 3.12's table (the crate's own copy, wider than `lra.rs`'s because `|` needs `set_merge`). It's not hash-seed dependent, but it is hash order in the sense of the brief's "no hash order": **report it as a named fact, don't call it clean.** Tied to 3.12; env's Python is 3.12.14.
- **Known divergence, not yet tested:** Rust `transfer_wanted` raises `ValueError` on any `lt` atom without exactly two sides, while Python raises only on reaching it in the loop and could return True first. Real `lt` atoms have two. Python's `TypeError` on an unhashable or non-iterable `expr` may also differ in type or order. The fuzzer doesn't cover these.
- **Handle:** `handle.rs`, `TermId(u32)`, same shape as TERMS-INTERFACE.md's. A one-line `pub use` swaps it, but `git show origin/port/D0:rust-spike/slice/solver_rs/src/term.rs` printed nothing when I looked, so the path is unconfirmed. Today's ids are EUF's term numbers (transfer) and a per-instance dict's (sharing), not `TermTable`'s. Both die with the session.
- **`P` plan, untried:** `satassume/__init__` imports everything, so patching after import misses module-level `P` instances and `from ... import P` names. Likely a `sys.meta_path` hook replacing `P` right after `satassume.sat.formula` executes, installed before `import satassume`, with no source change. Must keep `hash((pred, expr))` (real-hash set order can reach state), the dataclass `__eq__` class check, `repr`, and the four operators. No pickle or `dataclasses.` use in `satassume` by rg.
- **`&mut self` across EUF calls:** safe on reading Python's EUF. port/2's module note says its listener reads classes inside a merge; transfer's `_merged` doesn't. Recheck when running on port/2's EUF, which hasn't been tried.
- `_attach` is why `backend.TransferTheory` exists: a bare `sa_solver.TransferTheory` refuses `register_atom` until attached.

## File:line map

| Topic | Where |
|---|---|
| Rust core, pyo3-free; `Classes` is the EUF seam for component 2 | `rust-spike/slice/solver_rs/src/transfer.rs` |
| Python layer, `PyClasses` adapter, crossing counts, `transfer_wanted`, `_pyset_replay` | `solver_rs/src/transfer_py.rs` |
| Set order; handle | `solver_rs/src/pyset.rs`; `solver_rs/src/handle.rs` |
| Shared file changes, both small | `solver_rs/src/lib.rs` (mods, `register`); `slice/backend.py` (`TransferTheory`, `install_transfer`, `install`) |
| Shadow, `dump_py`, quiet counter | `slice/transfer_shadow.py` |
| Fresh-engine runner; API fuzzer | `slice/transfer_fresh.py`; `slice/transfer_fuzz.py` |
| Python reference | `satassume/theories/transfer.py` (`_scan` :296, `_spread` :357, `decide` :471); `sat/theory.py:185`; `sat/formula.py:13` |
| Glue | `relations.py:1675` engage, `:1587` sharing, `:1716` `set_fixed`, `:1852` `switch`; `scope.py:111`, `:174` |
| Quiet handlers | `engine.py:1906`; `sympy_api.py:1107` |
| port/2's EUF views and wiring | `origin/port/2`: `solver_rs/src/euf_py.rs:165-172`, `backend.py:34-47`, `rust_plugin.py:67-82`, `fresh.py` |

**Env:** `. ~/sa-rust-ids-work/env.sh; export PYTHONPATH=$PWD:$W/sympy:$W/shim` from the clone, then `cd rust-spike/slice`. Build: `sh rust-spike/slice/build_solver.sh`, about 1 minute.
