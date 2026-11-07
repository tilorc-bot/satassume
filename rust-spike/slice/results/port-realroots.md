# Component 6: `knowledge/realroots.py` on Rust (issue 323)

**On `rust-slice`, landed ahead of 1b.** The port was tested on `port/realroots` at 5cd0319, on a base of `rust-slice` 4b2f12b. `rust-slice` was still at 4b2f12b at landing, so the branch fast-forwarded: 5cd0319 itself is the landed source, with no rebase and no rerun. These numbers are for 5cd0319.

**The sequencing changed.** The port's brief said 1b lands first, and 1b's landing job was still running at 14:00 UTC on 7 Nov, so sa-port-56 stopped at a handoff, tested and not landed. The architect then replaced that order with landing now, ahead of 1b. The architect's reasons: the tested base is `rust-slice`'s head, so nothing needs rerunning; waiting would mean a 16-minute rerun on top of 1b's much larger change; the diff is additive; and sa-port-51's diff check found `knowledge_live.install` isn't called on 1b's run path. The landing session didn't repeat that diff check. The diff's only removed lines are 2 replaced in `mutate_knowledge.py`, a harness. 1b now lands on top of this one, under the rebase rule.

**Module: whole.** All 16 functions have a Rust counterpart in `solver_rs/src/realroots.rs`. **1 of the 32 runtime modules newly runs whole because of this: `knowledge/realroots.py`,** as the brief expected. I didn't recount the total.

Tested x86-64 on pareto1, hash seed 0, `.so` sha256 starts df615dc50020. Job output: `~/sa-rust-ids-work/sa-port-56/land1/` on pareto1.

## What runs where

- `knowledge_live.install()` swaps the five public names: `gcd`, `squarefree`, `real_root_counts`, `imaginary_root_count`, `root_facts`. The 11 private functions are reached only through those. Python stays the default.
- **Kept on Python with reason:** a kept query calls Python's functions, under the planner's ruling that those queries stay wholly on Python.
- **Python's path runs a private copy of the module** (`knowledge_live.py:142`). The module's functions call each other by global, so with those globals swapped, Python's `root_facts` would call Rust's `squarefree`, and a shadow would partly compare Rust with Rust. My first unit test fell into exactly this and failed on a call count.
- `MAX_DEGREE` and `MAX_BITS` are repeated in Rust, and `install()` refuses to run if they differ from Python's.

## The brief's claims, checked

| Claim | Result |
|---|---|
| Plain Python over `int` and `Fraction` | True. The module imports only `fractions`, `math` and `typing` |
| Callers hand it plain `int` | True. `templates/rootof.py:28` builds a tuple of `int`, and `:47` an `int` index. `tests/test_rootof.py` passes lists of `int`. So no ruling was needed |
| "Polynomial data comes from conversion" | **Not true today.** `rootof.py:22-28` reads `expr.poly.rep` in Python at query time. Those ints reach Rust from the Python template, and that read stays on Python until `rootof.py` is ported |
| Runs in the query phase on the suite (`realroots` 18) | It runs on the suite: 143 Rust calls (below). **I didn't reconcile 143 with the census's 18.** The 143 includes direct calls from `test_rootof.py` |
| Exact, no size limit Python doesn't have | True. Big ints and rationals only. Compared at coefficients up to 2000 bits, past the limit of 512 where `root_facts` itself refuses at `MAX_BITS`, while the other four functions compute |

## Landing bar

| Item | Result on 5cd0319 |
|---|---|
| 1. Suite by id against `sa-port-48/land3/suite/rust` | 6,125 ids on both sides, 0 new, 0 changed. 23 skipped, 18 xfailed |
| Three numbers | **5,961 passed, 77 kept on Python (needs internals), 46 failed on re-entry** |
| 2. Fresh dev, plain against atoms and against shadow | Answers and state MATCH: 1,985 queries |
| 2. Fresh fuzz, same | Answers and state MATCH: 3,000 queries |
| Fresh `rootof` (new workload), same | Answers and state MATCH: 5,187 queries; shadow compared 5,187 with 0 mismatches |
| `value`, atoms against plain (plant base row) | MATCH |
| Direct, `realroots_cmp.py` | 377,988 calls, 0 differences in value, type or repr, or exception type |
| 3. Planted bugs | Caught; see the table below |
| 4. Quiet handler firings | The two named cases only; see below |
| 5. Known differences in answers or read state | None measured. One refused input class; see below |

S's gate is met except for the 46 named stub failures, one cause. All 46 still carry `Already mutably borrowed`. Passed: 5,960 with no firing, and 1 with a firing on Rust. The second group is `test_ci_stream_reports_only_what_replays`. No Python-side counter ran, as the bar allows, so "doesn't fire on Python" for this run rests on the planner's naming of that test.

## Reach: read this before relying on the MATCH

| Rust calls | dev | fuzz | rootof | suite |
|---|---|---|---|---|
| `root_facts` | **0** | **0** | 5,187 | 133 |
| `real_root_counts` | **0** | **0** | 0 | 5 |
| `imaginary_root_count` | **0** | **0** | 0 | 4 |
| `squarefree` | **0** | **0** | 0 | 1 |
| `gcd` | **0** | **0** | 0 | **0** |

**The dev and fuzz MATCH says nothing about this module's arithmetic, because neither calls it.** That's why `knowledge_rootof_wl.py` exists. Those calls count entry points only: `real_root_counts` and the others also run inside Rust's `root_facts`. Public `gcd` has no caller outside the module, so only the direct comparison and the unit tests reach that entry point.

## Planted bugs

Each ran from its own build, and every row loaded its own. The base row: nothing fired in any column. Fresh columns are answers and state against plain, as lines changed / answers changed.

| Plant | dev | fuzz | value | rootof | Direct | Unit |
|---|---|---|---|---|---|---|
| `realroots-chain-no-negate` | no | no | no | 1,870 / 886 | caught | caught |
| `realroots-sign-boundary` | no | no | no | 206 / 102 | caught | caught |
| `realroots-squarefree-skipped` | no | no | no | 145 / 114 | caught | caught |
| `realroots-imaginary-sign` | no | no | no | 4 / 2 | caught | caught |
| `realroots-bits-off-by-one` | no | no | no | **no** | caught | caught |
| `common-contrapositive-sign` (control) | 465 / 165 | 2,691 / 377 | no | no | no | caught |

- **The control shows the dev and fuzz comparison still fires on this source.** The bar's "at least one planted bug" is met by that row. Its dev shadow also gave 1,107 mismatches.
- **`realroots-bits-off-by-one` is caught only off the engine.** No engine workload has a polynomial with a coefficient of exactly `MAX_BITS` bits. The suite column wasn't run for any of these plants.
- `realroots-imaginary-sign` moves only 2 answers on `rootof`, so that workload is thin on this path. The direct comparison is the stronger check there.

## Quiet handlers

From the landing suite run. Each of the 9 workers' counters was shown firing: 36 planted rows seen.

| Test | Handler | Type, text | Rows | Outcome |
|---|---|---|---|---|
| `test_ci_stream_reports_only_what_replays` | `_consistent` | AttributeError, `'Solver' object has no attribute '_ok'` | 34 | passed |
| `test_ci_stream_reports_only_what_replays` | `_consistent` | AttributeError, `'Solver' object has no attribute '_rb_clauses'` | 4 | passed |
| `test_protocol_on_fuzz` | `Engine._build_context` | RuntimeError, `Already mutably borrowed` | 1 | failed, in the 46 |

Both are named cases, and neither touches this module. Fresh runs on dev, fuzz and `rootof` had 0 unplanted firings in all three modes.

**Catches at `engine.py:1906` and `sympy_api.py:1107`:** the `knowledge_quiet.py` recount on dev and fuzz gave 0 unplanted rows, and `quiet fire` shows the counter seeing each of its 4 plants. Its output on dev and fuzz is identical to `sa-port-48/land3`'s in the first 400 characters of every line. That output prints `fault: 719` on dev. It's the same number on the base, and the ordinary dev runs have no `fault` count, so I read it as coming from the recount's own plants; I didn't trace each of the 719. The recount wasn't run on `rootof`, and its plants don't target `root_facts`. The `fault` counter on this path is shown firing by a unit test, and the suite and fresh runs show none.

## Known difference

Rust takes `int` and `Fraction` only. Python's `_strip` accepts anything `Fraction()` does, such as a float, a string or a SymPy number, and `root_facts` accepts a float index. Rust refuses these with a TypeError, which `knowledge_live` raises as `KnowledgeFault`, a BaseException, so it's loud and can't become a quiet "unknown". No caller passes them, and the suite shows no fault. This is the brief's limit, not a widening. A plain zero polynomial raises IndexError from `real_root_counts` on both sides.

## Not run

- Moved to the backend PR list by the landing bar: the mutant 2, 5, 6, 7, 9 rerun and mutlive's control, the boundary rescore and suite column, the final drop score and its lost rows, the suite split with Python's counter, `order:_rows`' evidence (not caught meanwhile), the `_forms` guard test, history and seed reruns, forced moves, the native path, and timing.
- Also not run: the suite with the shadow on, a suite column for the plants, the other `common-` plants, corpus fresh and leak, shuffled orders, the quiet recount on `rootof` and `value`, and fresh `value` in shadow mode.
- aarch64 got only short runs on orion: 38,914 direct calls with 0 differences, `test_rootof.py` 5 passed, and the 13 unit tests.

## Standing limits, unchanged

- The `_n_conflicts` view in `rust_plugin.py` isn't a port. It's a test-plugin shim, with the 64 tests it moved.
- 10 of the 25 boundary mutants have no real-engine catch, and the boundary suite column wasn't run. Mutants 2, 5, 6, 7, 9 still rest on the API fuzzer alone.
- Section 8's limits still stand on the base: PR 328's fuzz history and censuses aren't read, and suite2 is a floor.
- `test_performance_smoke_300_vars` didn't change outcome by id on this run. I didn't look further.

## Changes outside the module

No sibling's module changed, and `lra_backend.py` and constfield are untouched.

- `solver_rs/src/realroots.rs`: new. `lib.rs`: its `mod` and `register` lines (shared file).
- `knowledge_live.py`: the swap, the private copy, `undo`, the limits check and the shadow.
- `knowledge_fresh.py`: a `rootof` workload. `knowledge_rootof_wl.py`: that workload.
- `realroots_cmp.py`: the direct comparison. `test_knowledge_realroots.py`: 13 unit tests.
- `mutate_knowledge.py`: 5 plants, a `realroots` column, the unit column running both test files, and a `rootof` workload when its plain rows are there.
