# S step 3: real queries on the Rust solver (issue 323)

**Result: every answer and every session state matches Python on dev and fuzz.** No exemption was added and no Rust changed. But the answer digests catch none of the 10 mutants, and the real workloads never run the 5 paths the replays missed. Those 5 are still seen only by the API fuzzer of step 2.

Run on orion, seed 0, recorded query order, one process per backend, finishing at 02:23:58 UTC, 7 Nov (`run_live.sh`). Tools at cc41b4e; the crate is unchanged since 1b84ef9. Mutant sweeps ended at about 02:41 and 02:45.

## Answers and state

| | dev | fuzz |
|---|---:|---:|
| Queries | 1,985 | 3,000 |
| Answer digest, Python and Rust | `31cd0945c07f02a6` | `173502b6ef285ad6` |
| Same as the pinned digest in `RESULT-ids.md` | yes | yes |
| Answer or message differences | 0 | 0 |
| Sessions (all on Rust; Python solvers made: 0) | 918 | 3,133 |
| Sessions differing: state at query end | 0 | 0 |
| Sessions differing: call stream, with state after each solver call | 0 | 0 |
| Queries that ran on a Rust solver | 867 | 2,937 |
| Queries with theory calls | 198 | 2,860 |
| Sessions with theory calls | 198 | 3,018 |
| Outermost solver calls compared | 46,214 | 687,993 |
| Of those, propagating or searching | 6,857 | 29,263 |
| Theory hook calls compared | 34,788 | 1,241,630 |

The other 1,118 dev and 63 fuzz queries were answered without a solver.

**What a session's stream holds, in order:** every outermost solver call with its arguments, its result and `state.digest` of the whole dump after it, and every hook with its class, name, arguments and result.

**Controls, all matching:**
- Python against Python in a second process: the compare doesn't differ by itself.
- Traced Python against untraced Python, and against untraced Rust (`backend.make`, no subclass, no hook wrappers), on end states and answers. So the tracing changes nothing, and what a user would run gives the same states.
- `addr_masked` is 0 on all runs: no theory payload or result prints an address. This closes the open point from sa-rust-14 about a stable `repr`, on these workloads.
- Hook counts equal `coverage.md`'s independent ones: `assert_lit` 3,884 and 117,944, `check` 417 and 8,292.
- Sessions created and dropped, untraced: 918 of 918, 3,133 of 3,133.

Answer mix: dev None 892, False 557, True 536. Fuzz None 2,387, ValueError 207, False 204, True 202. No solver entry raised on either workload, and no run wrote to stderr.

## The 10 mutants

The "digest" columns are what step 2 couldn't score: real engine answers (`live.py --check plain`). "State" columns are session streams and end states. API columns are `mutate_slice.py` re-run at this head; they match step 2's table except for one time-limited shrink length (mutant 3, 767 calls against 744).

| # | mutant | missed by replays | dev digest | fuzz digest | dev state | fuzz state | API answers | API state |
|---|---|---|---|---|---|---|---|---|
| base | unmutated | | no | no | no | no | no | no |
| 0 | level sort: ties flip | | no | no | 49 streams, first q348 | 1,603 streams, first q0 | caught | caught |
| 1 | explain: last best wins | | no | no | 6 streams, first q364 | 300 streams, first q9 | caught | caught |
| 2 | `_mention` order | yes | no | no | no | no | no | caught |
| 3 | no var_inc decay | | no | no | 133 streams, first q278 | 2,573 streams, first q0 | caught | caught |
| 4 | watch: blocker-style keep | | no | no | 321 streams, first q0 | 2,739 streams, first q0 | caught | caught |
| 5 | ring: None as false | yes | no | no | no | no | caught, `fixed 5` only | caught, `fixed 5` only |
| 6 | `_fill` growth | yes | no | no | no | no | caught | caught |
| 7 | `_learn` bump order | yes | no | no | no | no | no | caught, hand-set `_cla_inc` |
| 8 | decisions not counted on -1 | | no | no | 876 streams, first q0 | 2,913 streams, first q0 | caught | caught |
| 9 | theory unit reason as learnt | yes | no | no | no | no | no | caught |

Each mutant's build is a different file, and each run checks the hash of the file it loaded. None hung or crashed. No cell is argued equivalent.

**Pass rule as written: holds.** Every mutant is caught by some check. It rests on the API fuzzer for 2, 5, 6, 7 and 9, and for 5 and 7 on states the engine doesn't produce.

**The digest column catches 0 of 10.** On these workloads, answers alone say nothing about whether the solver is the same one. State compare is what catches anything here (5 of 10).

## Why the real workloads miss 5 mutants

They never run those paths. A scratch build counted the exact condition under which each mutant behaves differently:

| # | Condition | dev | fuzz | API fuzzer, 1,500 sessions (positive control) |
|---|---|---:|---:|---:|
| 2 | a mention with 2 or more pending blocks | 0 | 0 | 245 |
| 5 | a ring clause literal still None after `_fill` | 0 | 0 | 1 |
| 6 | `_fill` grows past the model's end | 0 | 0 | 15 |
| 7 | a rescale during `_learn` | 0 | 0 | 39 |
| 9 | a theory unit reason above root | 0 | 0 | 91 |

So the compare isn't blind on them: there is nothing to see. Mutant 7 needs tens of thousands of conflicts in one session at decay 0.999, and fuzz has 7,797 in all. These are unreached paths, not equivalent code, and a query that did reach them would be unchecked by these runs.

## What the workloads reach

| | dev | fuzz |
|---|---:|---:|
| Propagations | 53,418 | 800,527 |
| Decisions | 7,738 | 105,266 |
| Conflicts | 257 | 7,797 |
| **Restarts** | **0** | **0** |
| **`reduce_db` runs** | **0** | **0** |
| Ring hits | 135 | 26 |
| Theory decisions | 1 | 34 |
| Late mentions that dropped held levels | 7 | 7 |
| Most learnts in a session at its end | 18 | 57 |

**Restarts and `reduce_db` are never reached by the real engine here.** The API fuzzer reaches them (1,513 restarts and 72 `reduce_db` runs, 30 with theories), with its own tunables and stub theories. This answers sa-rust-14's open point for these workloads; step 4's suite may reach them.

## Re-entry (difference A)

**No real adapter reached it, so nothing was fixed.** Every solver call from inside a hook is counted with its caller, on both backends:

| | Hook calls | Solver calls from inside a hook |
|---|---:|---:|
| dev | 34,788 | 0 |
| fuzz | 1,241,630 | 0 |

- **Did not reach it, by trace:** `LRATheory`, `EUFTheory`, `TransferTheory`, the only theory classes attached, and so `LRAAdapter`, `EUFAdapter` and `relations.py`, whose solver calls all came from outside hooks.
- **Static, weaker:** an AST walk finds no name containing "solver" in those three classes. It sees direct references only, not a call through a helper.
- **Not run:** the theories in `tests/` (`test_solver.py`, `test_verify_integration.py`, `theory_harness.py`). Step 4's suite will show those.

## Known differences B to E

None occurred: no entry raised and stderr is empty on every run, and a PanicException would have ended the process. No new exemption, and `live.py` has none.

- **B:** the three real `pop_level`s have no `raise` of their own; only an unbalanced `_lims.pop()` or an asynchronous exception could do it. From reading them, not from a test.
- **C, D:** `mention_blocks` is called within `satassume` only by the solver itself (`solver.py:928`), with the engine's `add_internal` mentions.
- **E:** `add_pattern` has no caller in `satassume`.
- `tests/test_solver.py` and `tests/test_solver_incremental.py` call both directly, on the Python solver, unless step 4 changes that.

## A correction to the plan

Section 2's "80k callbacks on dev, 2.67M on fuzz" counted every method of the theory classes, internal calls included (`cover.py`'s `wrap_all`). Real crossings are **34,788 and 1,241,630**, 44% and 46% of those. The callback part of the crossing estimate is about 2.2 times too high. Step 5 should use the measured counts.

## Limits

- One hash seed and one query order. Seeds, shuffles and fork runs are step 4's.
- None of the 10 mutants touches the callback layer in `lib.rs`, so nothing yet shows this compare catches a callback bug. The new boundary mutants are step 4's.
- State is compared after outermost solver calls, not inside a hook.
- The step's estimate of about 300 new callback lines didn't apply: step 1's `lib.rs` already had the callbacks, and they needed no change.
- Probe counts come from a scratch build that isn't in the tree. It is `solver_rs` plus `eprintln!` at the 5 sites; its answer digests match on both workloads.
- No timing was taken. Run times here include tracing and shared load and mean nothing.
