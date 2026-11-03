# Handoff: sa-rust-3, Rust spike (issue 323)

Stopped at the architect's request after the recording step. **Nothing is measured yet:** no k, no search-order
result, no crossing cost, no report, no comment on issue 323. No Rust has been written.

## What exists

| what | where | state |
|---|---|---|
| `rust-spike/record.py`, `common_trace.py`, `rec.sh` | branch `rust-spike` (from `rust-ceiling`) | run on both workloads; the `--timers` mode has never been run |
| traces: `{dev,fuzz}.trace`, `.res`, `.meta.json` | **pareto1 only**, `~/sa-rust-spike/traces/` (32 MB, not committed) | written, but nothing has read them back |
| copies of the tools | pareto1 `~/sa-rust-spike/tools/` | same as the branch; `rec.sh` there lacks the harmless `REC_DEBUG` prefix |

Checked on the recordings: the answers reproduce 9bafaa5's digests while recording (dev `31cd0945c07f02a6`, fuzz
`173502b6ef285ad6`), no theory calls back into the solver (`nested` 0), and no call uses owners or provenance
(`owners` 0), so the port can leave provenance out.

**Not checked:** the trace format has no reader yet, so a format bug would first show up in the replay. Two
recordings have not been compared for repeatability.

Re-record (not timed):

    machine run pareto1 --shared -r "rust spike: record" -- 'docker run --rm --user $(id -u):$(id -g) -v $HOME/sa-rust-bench:/work:ro -v $HOME/sa-rust-spike:/spike sa-eval-bench:1 sh /spike/tools/rec.sh dev'

`machine` exists on orion only, so run it from there, not over ssh. Don't filter its output with `grep -v lease`:
the summary JSON contains `release`, and the filter removes it.

## Counts from the recordings

| | dev | fuzz 424242 |
|---|---:|---:|
| queries | 1,985 | 3,000 |
| solvers / theories | 918 / 431 | 3,133 / 6,940 |
| public solver calls | 46,214 | 687,993 |
| decisions | 7,738 | 105,266 |
| conflicts | 257 | 7,797 |
| propagations | 53,418 | 800,527 |
| ring hits | 135 | 26 |
| restarts / DB reductions | 0 / 0 | 0 / 0 |
| theory `propagate` / `push_level` / `pop_level` | 9,060 / 7,514 / 6,643 | 347,151 / 281,262 / 261,111 |
| theory `assert_lit` / `check` / `decide` | 6,039 / 908 / 81 | 215,720 / 18,900 / 2,724 |

Two things to read before trusting a k:

- **Restarts and `_reduce_db` never fire**, so the replay can't test the port of those paths.
- **Search is small.** Most calls are bookkeeping: on fuzz, `add_clause` is 316,135 and `ensure_vars` 128,990 of
  687,993, and the theory hooks run about as often as propagations. So k may be set by call overhead and the
  theory hooks, not by watch loops. This is an observation, not a measurement.

The trace uses only these public calls: `attach_theory`, `register_atom`, `ensure_vars`, `add_internal`,
`add_clause`, `propagate`, `implied`, `solve`, `theories`, `release`, `mention`, `entails`, `consistent`, `value`,
`entails_all`, `set_inert`, `set_rule_block`, `register_block`. One block table (op 40). `add_clauses`,
`add_pattern`, `mention_blocks` (called only from inside `add_internal`), `model`, `conflict`, `new_var`,
`root_trail` and `stats` are not called from outside, so the spike can skip their public forms.

## Trace format

`.trace` is little-endian u32 words: `MAGIC, n_api, n_theories`, then the `n_api` API words, then per theory
`n_words, words`. Read words as i32, except mask parts, which are u32. Opcodes are in `common_trace.py`.
Argument layouts are the `ENC` table in `record.py`; each record is the opcode, then the `ENC` output, and `sid`
comes first. A mask is 4 words, low first. `hold` None is -1.

- Tape records, chronological per theory: `1 x n lits` (`assert_lit`, n=-1 for no conflict), `2 npairs (x n lits)*`
  (`propagate`), `3 status n lits` (`check`: 0 None, 1 model, 2 conflict), `4 x` (`decide`, 0 for None). `push_level`
  and `pop_level` are not on the tape, only counted.
- `.res`: one u32 per public call, the CRC32 of the normalized result (`norm` in `common_trace.py`: the i32 words of
  the list, `[-2]` None, `[1]` True, `[0]` False, `[-3]` ValueError).
- `.meta.json`: `answers`, and `perq`, the cumulative counters after each query (`counters` + pushes, pops, calls).

A DROP event can land just before the record of a call that was in progress when the finalizer ran. It only ever
names a solver no longer in use.

## Next: the replay and port step

1. Write `replay_py.py`: load the trace, `gc.collect(); gc.freeze()`, then loop over `(op, sid, args)`. Use a tape
   theory that checks `x` against the tape and raises on a mismatch, so any search divergence fails at once. Two
   modes: check (CRC per call, per-query counters against `perq`) and timed (no CRCs; a timestamp per query, for
   the None / definite split). Run it first: it validates the trace against the real solver before any Rust exists.
   Set `track_owners = False` on each solver.
2. Port `satassume/sat/solver.py` to `rust-spike/replay/` as a binary reading the same files, with the same two
   modes. Read the solver once, whole (about 35k tokens): lines 200-360 and 390-2750 matter; provenance doesn't.
3. Pinned on pareto1, in one invocation, alternating: `tools-rust/rc.py base`, Python replay, Rust replay. Report k
   and the solver's share of `base`; `record.py --timers` is a second estimate of the share.

Calibrate and report separately: an empty dispatch loop, and the Python tape-call cost beyond a plain method call.
A tape body in Python would otherwise inflate k. Report k with and without them.

### Build

orion is **aarch64**; pareto1 is x86-64 (i5-13600T), with no cargo installed yet. Check and test on orion, but the
timed binary must come from pareto1: install rustup there under `~/`, and build under `--shared`. For glibc,
`sa-cy-build:1` has gcc and Python 3.12 with glibc 2.41, the same as the bench image `sa-eval-bench:1`; the pareto1
host is 2.44, so a host-built binary may not run in the container. Build in that image with the toolchain mounted.
Run pinned as before: `machine run pareto1 --quiet`, `bench-container`, `BENCH_CPU=2`.

### Where a port can silently change search order

I worked these out reading the solver; none is tested yet.

- **`_fill`:** `mv[lo:lo+n] = values` can **grow** `mv` when the block runs past its end, and the later
  `pad`/`v <= n` logic sees the new length. `_mvals`, `_witness` and ring entries share one list (use `Rc<RefCell>`),
  except that the pad case makes a copy.
- **Tri-state tests:** `_ring_hit` tests `x is not (l & 1 == 1)`, where None counts as "not equal" and so as literal
  true, and `x is not (not l & 1)`, where None breaks out. `_witness_satisfies` uses `!=`, with the same None
  behaviour.
- **Sorts:** `raw.sort(key=level, reverse=True)` keeps equal keys in their original order, so use a stable sort on
  the descending key, not sort-then-reverse. `_reduce_db` is a stable sort by `act` (not exercised here).
- **Dict order:** `_mention`'s `pend` is insertion-ordered. Don't use a `HashMap` for it.
- **Watch lists:** no blockers. A blocker hit would keep a watch that Python moves, which changes list order and so
  search order.
- **`_learn`:** bumps the new clause **before** appending it to `_learnts`, so a rescale misses it. `_n_decisions`
  counts a pick that returns -1.
- **`_theory_conflict`:** a unit clause, or a clause with `ml == 0`, is returned but not stored; `Clause([l])` as a
  reason is neither learnt nor watched. A block conflict is a plain list, not a `Clause`. `_is_learnt` guards the bump.
- **Masks:** blocks have up to 64 variables, so masks are u128 and model sets need their own check (44 models here;
  the Python limit is 65,536).
- **Helpers:** `_common`, `explain`'s greedy choice (first best wins) and `lits_of` (ascending) must match exactly.
  The memos in `_BlockClosure` are pure, so they can differ.
- **`_rb_room`:** the base-indexed arrays grow separately from `_grow`.

## Then: the crossing-cost step (not started)

Task 3 of the brief, PyO3 on pareto1, plus task 4. Build the extension against Python 3.12 inside `sa-cy-build:1`, and
measure against real SymPy objects. I had leaned to PyO3 without abi3, because abi3 slows list and tuple access, but
that hasn't been compared. Combine with the report's counts: 283k asks on dev, 5.9M on fuzz, mostly hash.

## Open question for the report

`rc.py`'s `base` was 0.578 s dev and 8.133 s fuzz in the ceiling report. Take the solver's share from `base` runs in
the same invocation, not from those numbers.
