# Step 5: timing of slice S (issue 323)

**With only the SAT solver in Rust, a pass runs about 1.5 times as fast as pure Python: 1.50 on dev and 1.55 on fuzz with the full API, 1.46 and 1.51 with abi3.** That removes 33-36% of the pass. 2x would need 50%, so this boundary doesn't reach it on these workloads.

This informs the work and stops nothing. The plan called this step a gate on Q or stop. The brief replaces that: Tilo's scope of 7 Nov is to port everything except the offline code and the input, so the result doesn't bear on whether that happens. It only times the solver part.

## Results

Rust is the crate at c230ee0, untuned. Python is the same source, pure. Seed 0, 10 rounds after a warmup. Each speedup is Python over Rust within one round, as a median, with the range over rounds.

| class | Python, s | Rust full API, s | Rust abi3, s | speedup full API | speedup abi3 |
|---|---:|---:|---:|---:|---:|
| dev, whole | 0.528 | 0.352 | 0.361 | **1.501** (1.480 to 1.568) | **1.460** (1.450 to 1.540) |
| dev, None | 0.313 | 0.202 | 0.207 | **1.552** (1.531 to 1.606) | **1.505** (1.499 to 1.577) |
| dev, definite | 0.215 | 0.150 | 0.153 | **1.436** (1.412 to 1.521) | **1.400** (1.386 to 1.493) |
| fuzz, whole | 8.058 | 5.193 | 5.341 | **1.551** (1.531 to 1.562) | **1.508** (1.495 to 1.529) |
| fuzz, None | 6.730 | 4.296 | 4.421 | **1.566** (1.543 to 1.577) | **1.522** (1.508 to 1.542) |
| fuzz, definite | 1.033 | 0.665 | 0.682 | **1.550** (1.533 to 1.562) | **1.507** (1.498 to 1.533) |

- **Query counts:** None is 892 dev and 2,387 fuzz. Definite (True or False) is 1,093 dev and 406 fuzz.
- **In neither class:** 207 fuzz queries raise ValueError, in both backends. They take 0.292 s on Python and 0.228 s on Rust, and they count in the whole-pass row only.
- **The top of the dev ranges** comes from one Python run at 0.561 s, against a median of 0.528 s. The medians don't depend on it.
- **dev None against dev definite** (1.55 and 1.44) is outside the rounds' spread at the median. I didn't look for the cause.

Whole pass by seed, 5 rounds each for seeds 1 and 2:

| wl | seed | Python, s | full API, s | abi3, s | speedup full API | speedup abi3 |
|---|---:|---:|---:|---:|---:|---:|
| dev | 0 | 0.528 | 0.352 | 0.361 | 1.501 | 1.460 |
| dev | 1 | 0.532 | 0.355 | 0.364 | 1.497 | 1.462 |
| dev | 2 | 0.536 | 0.357 | 0.366 | 1.510 | 1.464 |
| fuzz | 0 | 8.058 | 5.193 | 5.341 | 1.551 | 1.508 |
| fuzz | 1 | 8.051 | 5.194 | 5.339 | 1.547 | 1.509 |
| fuzz | 2 | 8.086 | 5.249 | 5.370 | 1.541 | 1.504 |

## Against the plan's table

| | plan, crossings free | plan, with crossing estimate | plan, across the 31-46% SAT share | measured full API | measured abi3 |
|---|---:|---:|---:|---:|---:|
| dev | 1.53 | 1.45 to 1.51 | 1.40 to 1.74 | **1.50** | **1.46** |
| fuzz | 1.53 | 1.40 to 1.51 | 1.41 to 1.75 | **1.55** | **1.51** |

Dev falls inside the estimate. Fuzz on the full API is above both the 1.51 and the 1.53, though inside the share range. The plan's 1.53 rested on one share figure, so it was never a hard limit.

The Python baselines reproduce the plan's: 0.528 s against 0.527 s, and 8.058 s against 8.033 s.

## Crossings: measured counts times measured cost

**Counts:** step 3's, 34,788 hooks and 46,214 outermost solver calls on dev, 1,241,630 and 687,993 on fuzz. These replace the plan's 80k and 2.67M.
**Costs:** `results/tables-cross.md`, same image and CPU. A hook is charged as `o.m(i)` (37.1 ns full API, 80.1 abi3) and a solver call as one int in and one out (27.4, 54.9).

| wl | backend | charge, s | % of that Rust pass | net of the same calls in Python, s | time removed, s | % of Python pass |
|---|---|---:|---:|---:|---:|---:|
| dev | full API | 0.0026 | 0.7 | 0.0015 | 0.176 | 33.3 |
| dev | abi3 | 0.0053 | 1.5 | 0.0043 | 0.167 | 31.6 |
| fuzz | full API | 0.0649 | 1.3 | 0.0389 | 2.865 | 35.6 |
| fuzz | abi3 | 0.1372 | 2.6 | 0.1112 | 2.717 | 33.7 |

**This charge is too low.** It is a micro-benchmark product, not a live measurement, and the one piece that can be checked live disagrees. abi3 minus full API, paired per round:

| wl | live, s (range) | table predicts, s | live over predicted | per crossing, ns |
|---|---:|---:|---:|---:|
| dev | 0.0097 (0.0056 to 0.0115) | 0.0028 | 3.5 | 119 |
| fuzz | 0.1462 (0.0728 to 0.1999) | 0.0723 | 2.0 | 76 |

The charge leaves out lists read back and clause literals, which may be part of the gap, but I didn't separate them. Live crossing cost on the full API has no direct measurement here. Even at 2 to 3.5 times the charge it stays under 3% of the Rust pass, but that scaling is an extrapolation.

**abi3's price, measured:** 2.6% on dev and 2.8% on fuzz, relative to the full API pass.

## What this does and doesn't measure

It measures the whole `ask` pass and its None and definite classes, on dev and fuzz in recorded order, in a cold process, for each of the three backends.

It doesn't measure:

- **The binary step 4 tested.** Sha 44577e02 is an aarch64 build (orion) and can't load on pareto1, which is x86-64. These numbers are from x86-64 builds of the same source: full API `43379978`, abi3 `a7e54049`, in `sa-cy-build:1` with rustc 1.98.1. A rebuild on orion from c230ee0 reproduces 44577e02 exactly, so the source is the one step 4 tested.
  - Checked on x86-64: end state of all 918 dev and 3,133 fuzz sessions equal to Python's on both modules (`check-s5.sh`, `live.py --check raw`, seed 0), and answer digests on all timed runs.
  - Not run on x86-64: the entry-by-entry compare, the suite, the history runs and the mutants.
  - The hook and call counts are from aarch64 and weren't recounted. Equal end states suggest they carry over.
- **Live k or the real SAT share.** The plan expected a timed pass to settle both, but nothing here times inside the Rust call. The nearest figure is a floor: Python's solver work is at least about 33% of dev and 36% of fuzz, if all the removed time came from the solver. Fewer Python allocations could also mean fewer GC passes, which would lower that floor. The run doesn't separate them. `qtime.py`'s sampler wasn't used, because a signal handler can't run inside a Rust call.
- **A tuned build.** Default release profile, no LTO, `fxhash` off.
- **Anything past the solver.** Session, Relations, knowledge and adapters stay in Python, so this says nothing about what porting them gains or what a fuller port's crossings cost.
- **Other inputs or conditions.** Only these two workloads, on one CPU, Python 3.12.15 and hash seeds 0 to 2. Not memory, load time of the module (imports come before the timer), other Python versions, or shuffled query order.
- **A real install path.** The backend is `backend.install()`'s monkeypatch, including its `weakref.finalize` per solver.

**Step 4's gate stays unmet.** Its 46 failures come from one test stub re-entering the solver (`tests/theory_harness.py:242`). These workloads don't run that stub, and step 3's traced runs counted 0 solver calls from inside a hook on both (aarch64; `--check raw` has no hook wrappers, so `check-s5.sh` can't count this). So the timing doesn't exercise that path or say anything about it.

## Method

- **Machine:** pareto1, quiet lease, `bench-container`, image `sa-eval-bench:1`, `BENCH_CPU=2`, all inside one invocation.
- **Schedule (`run-slice.sh`):** Python, full API and abi3 in a cold process each, rotating one place per round. Seed 0 has 11 rounds, seeds 1 and 2 have 6 each, and the first round of each seed is a dropped warmup. 138 runs, all with digests `31cd0945c07f02a6` (dev) and `173502b6ef285ad6` (fuzz).
- **Source:** `satassume` at c230ee0, which `diff -r` finds identical to `base-9bafaa5`. SymPy, evalbench and data are checked equal to what steps 3 and 4 used on orion (file hashes). Bytecode is compiled with the image's Python.
- **Times:** 05:59:07 to 06:07:55 UTC, 7 Nov 2026. Tables come from `step5_report.py`.
- **Raw:** `step5-timing.raw.jsonl` holds per-pass seconds and digests. Per-query files stay on orion at `~/sa-rust-ids-work/slice/step5/out/`.

**One run was thrown out, and it's kept.** The first timed run (05:49:06 to 05:57:46 UTC, `step5-timing-nopyc.raw.jsonl`) gave dev 1.44 and 1.41 and fuzz 1.54 and 1.51. Its source copy had no bytecode and the mount is read-only, so query 0 compiled lazy imports inside the timer on every backend, at about 57 ms against about 10 ms. That fixed cost pulled dev down by 0.06. I found it because Python's dev pass was 0.579 s on source identical to the plan's 0.527 s. No install runs like that, so the rerun with bytecode is the result.
