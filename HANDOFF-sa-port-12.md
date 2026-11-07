# Handoff: sa-port-12 to the next session on component 1a (issue 323)

**LRA sessions now run on the Rust core through `ask()`, and dev matches Python on a fresh engine. The step isn't held yet: nothing is on `rust-slice`, and the suite's three numbers aren't in.** The code is on `port/1a`, pushed at the commit carrying this file. I stopped at the context note, about 52 minutes in.

Read first: my brief `~/.local/state/agent/briefs/sa-port-12-20261107T075738Z.txt`, whose terms and planner's rulings still apply, including the state-transfer ruling at its end. **Carry that ruling into any later handoff.** Then `HANDOFF-sa-port-8.md` for what's built. Output is under `~/sa-rust-ids-work/sa-port-12/` (`$B` below).

## Jobs started by this session

The suite was still running when I last looked, and may die with this session. **Check for its end marker, and restart if it's missing and nothing is running.**

| Job | Output | Done when | Restart |
|---|---|---|---|
| Full suite, Rust then Python, shuffled, `-n 3` | `$B/suite1-rust`, `$B/suite1-python` | `$B/suite1.done`, `exit.txt` in each | `bash $B/suite1.sh` |
| Dump-field mutants on dev: **finished 09:09 UTC**, read under "Order from here" | `$B/dm/dev` | `$B/dm/dev/done`, `score.txt` | not needed |

**Which source these ran on:** the suite's Rust workers imported the tree at about 08:42 UTC, at abc8170's source, before `TransferFailed` went in at 496f250 (08:49). That change only touches the path where a dump fails, so I expect it not to matter, but that's a reading. The suite counted for the report has to be on the final source, so rerun it if source changes again. The first few dump mutants also started before 496f250. No dump mutant makes `_state` raise, so they aren't affected, for the same reason.

## What ran, and what it shows

All on this tree. "Fresh" means `live.py --fork`: each query in its own child, forked after import.

| Run | Result | Where |
|---|---|---|
| One session, q1914, `Q.nonzero(i - j)` given `Q.ne(j, i)` | Same answer and same LRA state digest as Python; 0 Python LRA hook bodies run, 261 core calls | `$B/one/one_session.py` |
| dev, **fresh**, Python against Rust, entry check | 1,985 queries, 3,332 solvers, 0 differences in answer, end state, stream or LRA state | `$B/fresh/dev.cmp` |
| dev and fuzz, shared memos (sa-port-8's `live1`) | 0 differences on all four comparisons, both workloads; no `.err` output | `~/sa-rust-ids-work/sa-port-8/live1/summary.txt` |
| Move at every call index, dev, fresh | 8,406 moves over 222 queries, 6,855 at level > 0 (levels up to 27), **0 differences** | `$B/mv/dev.cmp` |
| `test_lra_dirty.py` | Passes; fails on `LRA_MUT` 6 and 7 | direct calls to the theory |
| `LRA_MUT` 6, 7 through `ask()`, q1887 only | Both caught, by solver end state and stream. Answer and LRA state unchanged. Unmutated row on the same build is clean | `$B/dirtymut2` |
| `test_lra_raises.py` | 27 bad and 17 odd inputs: same exception type and text, same state after, none moved. Two planted faults caught (23 and 5 differences) | direct calls; **run as a script, not yet under pytest** |
| Failed transfer through `ask()` | Raises out, on a natural move and forced at each of G=0..39 of one query | `test_lra_raises.py` |

### The group counts

| Run | Rust throughout | Moved | Python from the start |
|---|---|---|---|
| dev, fresh | 113 | 109: 95 `constant` at call 0; 6 and 4 `constant coefficient` at calls 31, 32; 2 at call 60; 2 `constant offset` at call 31 | 0 |
| dev, shared memos | 90 | 108 | 0 |
| fuzz, shared memos | 2,422 | 596: 474 `constant` at call 0, 122 at call 1 | 0 |

**Use the fresh row:** shared memos hide sessions, so these differ (q1914 has 2 sessions fresh, 1 shared). Fresh fuzz hasn't run. Every natural move is at level 0 on these runs, and the dev queries I sampled are all `pi` constants, which is 1b. Queries kept wholly on Python (Sum, Product, Integral, non-default registries) aren't counted here.

### `lra_cert`'s reach, by running

`lra_cert_reach.py`, shared memos: `certify` runs 53 times on dev and 228 on fuzz, `within` 65 and 1,140, all under `ask()`, with identical counts on both backends. **So the engine does reach it, through Python.** It only runs on moved sessions: a live core has no `lra_cert` path, which is by reading, not by per-session attribution. Not ported and doesn't count. The suite's reach (`-p lra_cert_reach`, `LRA_CERT_OUT` set) wasn't run. Files: `$B/cert/`.

## Findings to carry into the report

1. **A failed transfer was being swallowed (condition 4), now fixed.** `engine.py:1906` wraps the complete check in `except Exception`, treats any failure as "not evidence" and starts a fresh session. Forced at G=10 of q1914's query, a failed dump came back as answer `None` with no error. `TransferFailed` is now a `BaseException`, so it goes through, and the engine is unchanged.
2. **This affects siblings, so say so.** Any exception from a ported theory or from Rust during the complete check becomes a quiet "unknown" at that handler, on both backends, unless it's a `BaseException`. A Rust bug there looks like a lost answer rather than a crash. `sympy_api.py:1107` is a second `except Exception` I didn't read.
3. **sa-port-8's dev and fuzz numbers aren't fresh-engine numbers.** They're real comparisons, but the step is held to fresh, so dev is now redone and fuzz isn't.
4. **`_dirty` order rarely shows on real sessions.** Propagate calls whose output order depends on it: 1 of 4,057 on dev, 11 of 73,631 in fuzz's first 1,500 queries. An answers-only check can't catch `LRA_MUT` 6 or 7 on q1887.
5. **Still name:** `live.py`'s hook filter (Python digests not comparable with older recordings), the `_view` and `certified` test shims, the `_n_conflicts` shim with its 64 tests, and sa-port-8's list of shared files touched.

## Traps I hit

- **`SLICE_SO` does nothing under `live.py`,** because `backend.py` imports `sa_solver` first. Use `--so DIR`, and check `so_sha` in the `.tot`. My first `LRA_MUT` dev run loaded the plain build and looked like "no catch"; it's in `$B/plainbuild-invalid/`. Don't use it. `test_lra_dirty.py` does honour `SLICE_SO` and asserts which build loaded.
- **The reference has to be fresh too.** Forced runs against shared-memo Python rows differ on session count and stream for no real reason. Use `$B/fresh/dev-py.jsonl`.
- `run_suite.sh` isn't executable: call it with `bash`. Mutant build: `$B/somut/sa_solver.so`, built from 04559e1's source with `--features mutants`; rebuild it if the crate changes.

## Order from here

1. Read the suite: `suite_report.py $B/suite1-rust $B/suite1-python`, compared by id with 5,961 / 77 / 46. Check the `test_lra*` failures **id by id** against `port-census/pr328-check/suite-lists.md`, not by family. Sum `lra` over the rows for the groups.
2. Dump mutants on dev finished (`$B/dm/dev/score.json`), 83 in all. Close the five idle ones below; the rest are ready to report as written there:
   - **49 caught by a comparison:** 43 by the LRA state digest alone, 6 by end state and stream as well (4 of those also raised, one changed the session count). `identity:_ints` and `identity:_int_lits` are among the 43. `order:_ints_on_inner` was effective in only 4 of its 25 runs.
   - **27 caught only by the state read (all the `drop:` mutants):** the child dies with `KeyError` at `state.py`'s `get = lambda n: d[n]`, or `AttributeError` at `lra_backend.py`'s `__getattr__` for the `_py_` fields, after the session. The row is lost, so **these say nothing about whether the answer or stream changed.** Say so; don't list them with the 49.
   - **2 not caught, name them:** `order:_forms` (effective in 25 of 25 runs) and `order:_rows` (5 of 25). `lra_text` sorts both, and neither changed end state or stream in those runs. That supports the claim at `lra.rs:4-8` that order there has no effect, on these runs only.
   - **5 never effective:** `order:`, `lose:` for `_ground` and `_pending_ground`, and `value:_ground`. Neither field was non-empty at a move on dev, so these need a query or a direct session that has them. `drop:_ground` and `drop:_pending_ground` had 1 run each and are in the 27.
3. Fresh fuzz: `live.py fuzz py|rust --fork`. Then move at every call on fuzz, with `--stride`, **stating that it's sampled** (dev is every index). The branch budget is the point of condition 2, so confirm the moved sessions include some with branches, and with `exhausted`.
4. `LRA_MUT` 6, 7 on full dev and fuzz with `--so` (only q1887 so far). Run `test_lra_dirty.py` and `test_lra_raises.py` under pytest.
5. `real_theory_fuzz`, `test_solver_real_theories`, `run_history.sh`, `historycmp.py`, hash seeds.
6. Solver mutants 2, 5, 6, 7, 9 via `mutate_live.py`; boundary mutants via `mutate_boundary.py`, including `--suite`, and the 10 with no real-engine catch (11, 26, 33, 34; 27, 29, 31; 17, 18, 32). New mutants in payload conversion, term ids and model rendering. The solver's 6 and 7 aren't `LRA_MUT` 6 and 7.
7. Native path, then timing on a quiet pareto1 lease, with the moved count beside the numbers. Nothing can be said yet about the boundary's cost or shape for siblings: each hook is still a Python method calling Rust.
8. The planner's question, what would keep the transfer alive past 1b: on dev and fuzz so far, natural moves are all reasons in the constants family. The raising cases stay in Rust. Answer it once fresh fuzz and the suite's reasons are in.
9. Rebase on `origin/rust-slice`, push without force, report.

**Not run at all:** the suite's result, fresh fuzz, transfer on fuzz, history and hash seeds, solver and boundary mutants, timing. **Modules now running in the real engine because of this:** `lra.py`'s rational core runs on Rust for the sessions above; `lra_cert` doesn't. Don't claim a count against the 32 until the step is held.

## File:line map (at 496f250)

| Topic | Where |
|---|---|
| `TransferFailed`, `_move` | `slice/lra_backend.py:33`, `:307` |
| Payload conversion, state, view, install | `lra_backend.py:181` `_register`, `:225` `_pairs`, `:259` `_state`, `:299` `_view`, `:322` install |
| The handler | `satassume/engine.py:1906`, in `_build_context`; called through `_complete_check` |
| Forced move | `slice/move_every_call.py:31` `forced_class`, `:47` `drive`, `:89` `cmp` |
| Dump mutants | `slice/dump_mutants.py:108` table, `:146` where applied, `:193` score |
| Raising cases, failed transfer | `slice/test_lra_raises.py:139`, `:163`, `:190` |
| `_dirty` | `slice/test_lra_dirty.py`; `lra/port/src/lra.rs:134`, `:1042` |
| Reach | `slice/lra_cert_reach.py` |
| Core, binding, state code, earlier maps | `HANDOFF-sa-port-8.md`'s map (`lra_backend.py` lines there have moved) |
