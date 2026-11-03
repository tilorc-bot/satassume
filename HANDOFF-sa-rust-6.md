# Handoff from sa-rust-6: k_lra (issue 323)

Stopped at the 120k context budget. **No timing, no port comparison, no result yet, and no comment on the issue.** Brief
steps 2 to 5 and DONE WHEN are still open. Don't read `lra.py` again unless a mismatch needs it.

## Done

- **Recorder works:** `rust-spike/lra/record_lra.py`, `common_lra.py`, `rec.sh`. Traces are on pareto1 in
  `~/sa-rust-bench/lra/traces` (`{dev,fuzz}.lra`, `.lra.res`, `.lra.meta.json`), not in git. Both runs gave the known digests
  (dev `31cd0945c07f02a6`, fuzz `173502b6ef285ad6`).
- **Written, never run:** `replay_lra.py` (modes timed, empty, check). Its check mode has not run against the traces yet.
- **Written, never compiled:** `port/Cargo.toml`, `port/src/rat.rs`, `port/src/lra.rs`. `port/src/main.rs` doesn't exist.

| recorded | dev | fuzz |
|---|---:|---:|
| LRATheory sessions, all | 199 | 3019 |
| with constants, left out | 108 | 596 |
| rational, recorded | 91 | 2423 |
| register_atom | 825 | 36571 |
| assert_lit | 1572 | 94562 |
| propagate | 1645 | 118206 |
| push_level | 1334 | 96002 |
| pop_level | 1134 | 89275 |
| check | 170 | 6730 |
| answers None / definite / other | 892 / 1093 / 0 | 2387 / 406 / 207 |

Every recorded coefficient is a Fraction and every `terms` is a tuple (`nonfrac` and `dict_terms` are 0), and no call raised.

## The boundary, as decided so far

- **Inside:** `LRATheory` public calls on rational sessions: lra.py's tableau, bounds, branch and bound, models.
- **Outside:** `lra_adapter`, `lra_bounds` (mpmath intervals), `constfield`, `lra_cert`, and every session with an Element. A
  session counts as a constants session if `_fields` was ever set. The share of those sessions is still unmeasured:
  `record_lra.py --timers` reports it, split by rational and constants and by answer. Dev has more constant sessions than
  rational ones, so the share may matter; report it.
- **Term keys are ints in both replays.** The live pass hashes SymPy keys in `_var_of`, `_forms` and `_slack_of`, so Python's
  replay is a little faster than live, which lowers k_lra. Say so in the result.
- `exhausted` is never cleared outside lra.py and `eager` is never set (checked by grep), so neither needs recording.

## Next

1. **Write `port/src/main.rs`**, args `WORKLOAD TRACEDIR MODE`, modes timed, empty, check. Same trace format as `replay_lra.py`'s
   `decode`, decoded before the clock. `Q` lines close a per-query clock, summed by class from `meta["cls"]`. Use the crate's
   `black_box` on results in timed mode. Print the same JSON as `replay_lra.py` (`run`, `wl`, `T`, `classes`, `ops`). Empty mode
   needs the same match arms calling empty `#[inline(never)]` functions.
2. **Check text.** Check mode writes exactly `common_lra.py`'s text and takes its crc32: `N`; `F` + literals; `G` + `lit:why;...`;
   `T` + `id=n/d,...`; then `|pivots,checks,conflicts,propagations,branches,exhausted,flag,nvars,nrows`. `.lra.res` has one line
   per trace line, -1 for Q, N and D. A `check` that returns None can't happen on rational sessions.
3. **Build on pareto1** inside `sa-cy-build:1`, as in `rust-spike/build-pareto.sh`: `rs` (release), `rsfx` (`--features fxhash`),
   `rslto` (`--profile tuned --features fxhash`), `rsprof` (`--features prof`, for the widths and sizes), `rsmut`
   (`--features mutants`). The crates need the network or `cargo vendor` first; check `Cargo.lock` works offline in the container.
   Name num-bigint 0.4 in the result: the arithmetic is i64 over i64 with i128 intermediates, falling back to BigInt.
4. **Check before timing:** `replay_lra.py check` and `rsmut`/`rs check` against `.lra.res`. Expect some port bugs to show here.
5. **Pinned timing:** `machine run pareto1 --quiet -r WHY -- bench-container run sa-eval-bench:1 ~/sa-rust-bench -- sh
   /work/lra/run-lra.sh` with `BENCH_CPU=2`, styled on `rust-spike/run-k.sh`: seven rounds, round 0 warmup, modes rotating, with
   `base` (`python /work/tools-rust/rc.py base`), `timers`, `py`, `pyempty`, `rs`, `rsfx`, `rslto`, `rsempty`. Report per-round
   ratio medians with ranges, net of dispatch, as `analyze_k.py` does.
6. **Mutants:** `LRA_MUT=n` on `rsmut`. In place: 1 pivot order (largest leaving variable), 2 budget off by one, 3 pivot arithmetic
   (no inverse), 4 new row reversed, 9 entering variable largest. Add two or three more, one of them in `rat.rs`. Report which are
   caught and which aren't, as RESULT-k.md does.
7. **Whole-pass table.** `rust-spike/cross/combine.py` holds the report's arithmetic (read only the part that builds the table):
   `speedup = 1 / (S + X + R + r/k_r)`. Split r into the core's share c and the rest:
   `1 / (S + X + R + c/k_lra + (r - c)/k_rest)`. Solve k_rest for 2x: `(r - c) / (0.5 - S - X - R - c/k_lra)`; say so if the
   denominator is not positive. Use k = 12.9 / 15.2 as the report does, its R column, by class and low to high, as the code stands
   and with ids.

## Things in the port worth knowing

- Row dicts stay in insertion order because conflict literal order depends on it. `_dirty` reproduces CPython's set table
  (`PySet`) because propagate's output order depends on it. `_cols` order changes nothing, and neither does `for b in rows`,
  which takes the minimum violating variable. All of that is argued from reading the code; the check will test the first two.
- Rows and columns use linear search; `prof` reports their sizes, so a tuning can be named if they turn out large.
- `prof` in `rat.rs` counts add, sub and mul results (including through div) by width: i32, i64, BigInt, plus max bits. Direct
  returns such as `mul` by zero, `neg` and `inv` aren't counted; say so.
