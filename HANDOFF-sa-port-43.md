# Handoff: sa-port-43, component 1b (LRA constants), issue 323

Written 2026-11-07 about 12:52 UTC, at the context note. Replaces HANDOFF-sa-port-42.md as the place to start. That file's "Corrections" section and HANDOFF-sa-port-41.md's "What will bite" still apply. **Not landed. None of the bar's 5 items is met.**

## State

**The engine now runs on `solver_rs/src/lra.rs`, constants included, with no Python theory behind a session.** `lib.rs` uses `mod lra;`. `lra_backend.py` is rewritten and `_Move`, `_move`, `TransferFailed`, `_once`, `_Replay`, `moves` and `calls` are gone.

Base of this work: `port/1b` with `origin/rust-slice` at 6827bf7 merged in (a merge, so `port/1b` wasn't force-pushed). **rust-slice has since moved to dc3f15d (atoms, component 6). Not yet merged or rebased here.** `lib.rs` is the likely conflict. The rebase at landing flattens this branch's merges.

## What ran, on this tree before the rebase

| Run | Result |
|---|---|
| dev, fresh, `--check entry --fork`, orion | **MATCH**: 1,985 queries, answer_diff 0, end_diff 0, stream_diff 0, lra_diff 0, 222 LRA sessions all group `rust`, python solvers 0, `answers_sha` 31cd0945c07f02a6 both. `_rows`' outer order is now in the compared text. This is one run, before the rebase, and it isn't the bar's run. |
| fuzz, fresh, 4 shards, orion | **Running, detached, not read.** Result at `~/sa-rust-ids-work/sa-port-43/first/fz/fuzz.cmp`; `done` in that directory is the end marker. Started about 12:50 UTC; duration unknown. Script: `~/sa-rust-ids-work/sa-port-43/fuzz_fresh.sh OUT TREE J`. Its PIDs weren't recorded: stop it by the path `sa-port-43/first/fz` only if you must. **It imports `lra_backend.py`, `state.py`, `live.py` and loads `sa_solver.so` from this clone when the Rust phase starts, after the Python phase. Don't build or edit those until `done` exists, or that result is void.** |
| `test_cf_diff.py 7 1500`, orion | 23,207 compared, 0 mismatches. Small inputs only. |
| `test_lra_raises`, `test_lra_dirty`, `test_lra_identity`, `test_lra_order_guard` | 5 passed. I saw only the count, so read what they cover before quoting them. |

The first dev run had 83 state differences, one cause: `register_inner` and `register_integral` never set `fields` for an Element constant (lra.py:662, :722). With `fields` off the theory branched as if rational (`branched` True on Rust, False on Python, `int_memo` empty), and **all 1,985 answers still matched**. Fixed. So the state comparison caught a real port bug that answers missed. That is an accident and not the bar's planted bug, but it supports the planner's "state is the test".

**Not run:** the suite, any planted bug on this core, shadow, history, seeds. Nothing has run on pareto.

**Handler counter:** `first/dev-rust.jsonl.handlers` and `dev-py.jsonl.handlers` are both 0 lines. **This zero isn't evidence yet.** I didn't show the counter firing on this tree (FALSE ZEROS rule), and those files come from a run before the `handler_count.py` edit below. `test_handler_count.py` and `lazy_fire.py` plant raises: run one first.

## What's left, in order

1. Read `fuzz.cmp` once `done` exists. `lra_textdiff.py WL Q...` prints the first differing state field per query (run it from `rust-spike/slice`). Fix differences in `lra.rs` or `lra_backend.py`. For the failing queries, list them as dev's were: compare `sessions[i].lra` per query across the two jsonl files.
2. **Transfer's remaining users** (they still name it and would fail if run):
   - `identity_rule.py:152-153` (`m._move("forced")`): drop the moved half, keep the fresh comparison, keep the 14,424-sequence result in the report.
   - `dump_mutants.py:18` and `except_probe.py:15` import the deleted `move_every_call`. `except_probe.py` wants `HOOKS` from it, and `:59-62` is transfer use by the old map.
   - `port_mutants.py:30` (`term:forget_skipped` patches `_move`'s text), `:63-68`. Others in that file patch text I rewrote, so **expect stale patches**: they would then void or fail. Rewrite against the new `lra_backend.py`.
   - `p1/p1_landing.sh:31-36`, `p1/p1_fresh.sh:18`, `p1/p1_move.sh` (delete), `p1/p1_ground.sh:8-10`.
   - `test_lra_raises.py` `scenario` still returns a dummy `False` for "moved", and its `assert not moved` at about :158 is now vacuous: remove both.
   - `grep -rn "group" livecmp.py p1/groups.py` for the old three-group logic, not read.
3. **The gcd stall is still open.** `constfield.rs` `rgcd` :836, primitive PRS, stalled over 100 s on 4 vars with degree-3 factors, per sa-port-42. Fix suggested: port `dmp_zz_heu_gcd` with the PRS as fallback; the monic gcd is unique, so show it by `test_cf_diff.py`. Then a large run with multivariate gcd. Dev didn't stall. The suite may, and a stall there would read as a hang, not a wrong answer.
4. **`_sympy_inner_gcd` isn't patched** at install (constfield.py:577). Python's `num` still uses SymPy's gcd. Patch after the fix.
5. **`_from_sympy` is still Python.** `lra_backend._register` calls `num()`, which makes a Python Element, and `Num::from_py` converts it, so `_from_sympy` hasn't moved to term rows. The brief wants term rows from component 0. `lra_adapter.py:213, :243, :262` call `from_sympy` on derived terms, and no per-query table on the engine path was found by sa-port-42. Lazy reads has landed, so read `TERMS-INTERFACE.md` and `results/port-lazy.md`, then decide. **If that needs a table the engine path lacks, ask the planner; don't count `constfield` as wholly ported.** R9 `enclose` stays a callback.
6. **`certified` and `certified_with`: the choice made is to answer both from the Rust port of all of `lra_cert`.** `lra_backend._certificate` and `rational_values` call the core. No test has exercised it through the theory yet, so tests that patch `_certificate` or need a real theory go on the kept-on-Python list once the suite shows them.
7. Plants for bar item 3. `lra.rs`'s `--features mutants` (`LRA_MUT` 1-9) and constfield's 101-110 exist, but **I didn't check that the core's mutants compile or fire on this core**. `mutate_slice`'s copied crate didn't compile on `lib.rs`'s relative `#[path]`; that `#[path]` for lra is gone now, and `rat`'s remains. Check it. Survivors from sa-port-42: 102, 107, 105. New evidence wanted: `order:_rows` now that `lra_text` keeps the order, with a pivot-then-check case. Until a run shows it, it stays not caught.
8. Merge or rebase on `origin/rust-slice`, rebuild, then the bar on pareto0 or pareto1, detached: the suite by id with three numbers and firings (`run_suite.sh`, `p1/p1_suite.sh`, `suite_report.py`, `handler_cmp`), fresh dev and fuzz, plant caught. `p1/p1_land_short.sh` wasn't read and may fit. Push to rust-slice with no force. Write `results/port-1b.md` and update `PORT-INVENTORY.md`.

## Shared files changed (name in the report)

- `state.py`: `lra_text` keeps `_rows`' order (was sorted); `lra_of` lost the moved group; `lra_branching`'s third field is always None; a `SLICE_LRA_TEXT` debug switch.
- `rust_plugin.py`: `moves` removed from rows. Row consumers reading `moves` weren't checked (`suite_report.py`, `p1/groups.py`).
- `handler_count.py`: `install` re-points the output if already installed. `live.py:282` always installs, so `--handlers` raised "tool 4 is already in use". **This is the cause of that gap, not `catch_count`.** The fix wasn't run with `--handlers` or through `mutate_live.py`.
- New: `lra_textdiff.py`.

## Unverified decisions in the code

- `refresh_limits()` runs on every `register_*`, and on the other hooks only when `fields`. That has a cost on rational sessions; timing isn't on the bar.
- `LraCore.register_*` converts the payload before refreshing limits; `Num::from_py` reads no limits by my reading, not shown.
- `Num`'s `==` for map keys is formal (`constfield.rs:1617`), while Python's dict falls to `Element.__eq__` on a hash collision, which can raise. By reading only, unmeasured: name it as a difference.
- `_int_memo` crosses in hash-map order. `lra_text` sorts by repr, so this is safe for the comparison; nothing else reads it.
- In `register_atom`, if a non-Undecided exception leaves new terms with no variable, `_forget` takes them back. Not tested.
- `Theory::certificate`'s memo is a linear list keyed by `values`.

## File map

| What | Where |
|---|---|
| Certificate glue | `solver_rs/src/lra.rs`: `CertMemo` near `Verdict`, `certificate` :~916, `certify`, `rational_values`, `cert_skips`; `slack_forms` |
| `fields` fix | `lra.rs` `register_inner` :~518, `register_integral` :~566 |
| Binding | `solver_rs/src/lra_py.rs`: hooks, `certificate`, `rational_values`, `touch`, `dump` (`row_order`, `slack_forms`, `forms_order`, `int_memo`, `fields`, `gave_up`) |
| Python side | `lra_backend.py`: `_View`, `register_atom`, `_register`, `_pairs`, `_state`, `_view`, `install` |
| Mainly core | `lra.rs`: `Theory` :~255, `lin` :~463, `register_inner` :~510, `int_verdict` ~:770, `branch` :~830, `simplex`, `pivot`, `check` :~1215, `propagate` :~1310 |
| gcd | `constfield.rs` `rgcd` :836; Python `constfield.py` `_inner_gcd` :510, `_sympy_inner_gcd` :577 |
| Python theory | `satassume/theories/lra/lra.py`: certificate :417-473, hooks :545-644, `_register_atom` :646, `_lin` :681, `_branch` :917, `_simplex` :1010, `_pivot` :1110, `_check` :1176 |
| State text | `rust-spike/slice/state.py` `lra_text` :~221 |
| Handlers in live | `live.py:278-284`, `:298-300`; `handler_count.py:30-40` |
| Output | `~/sa-rust-ids-work/sa-port-43/first/` (dev rows, `fz/` fuzz) |
| Inventory | `rust-spike/PORT-INVENTORY.md`: port order :371-396, 1b row :382, registry :172, R9 :143 |

## Must stay in every report

THE DROP, PLANTED PORT BUGS, QUIET COUNTER, `order:_rows` not caught and 1a's not-run list: in the brief under CARRY FROM 1a, unchanged and not rerun here.

The transfer's results, to keep now it's gone: dev 113 Rust / 109 moved, fuzz 2,569 / 623, suite 42,661 / 2,697 moved in 239 tests, all natural moves at level 0; `identity_rule.py` 14,424 sequences, 344,304 answers, 0 differ (hook level, plain Fractions, moves at level 0). The object rule is `port-1a.md:54-61`. Those moved sessions now run on Rust, and on this tree only dev's are covered, by the state comparison. Fuzz is unread and the suite unrun.

Nothing here suggests the transfer has to outlive 1b.
