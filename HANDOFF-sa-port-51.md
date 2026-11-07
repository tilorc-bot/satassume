# Handoff: sa-port-51, component 1b (LRA constants), issue 323

Written 2026-11-07 about 13:38 UTC, at the context note. **Not landed.** `port/1b` head is the commit carrying this file, on top of `cae6663`, the tested source. This commit adds only this file. Start here, then `HANDOFF-sa-port-47.md`'s "What's left" items 6-9 and "Must stay in every report".

## The gcd is settled: keep `heu_gcd`, with the guard

| Planner's check | State | Evidence, under `~/sa-rust-ids-work/sa-port-51/gcd/` |
|---|---|---|
| 1. Acceptance checked | Met by sa-port-47, on the **pre-guard** build | Plants 108, 111. Not rerun on the guard. |
| 2. Counter | Met | `cf_gcd_counts`, plus new `cf_gcd_guard_count` |
| 3. Hang gone | Met on sa-port-42's input by 47; the guard's probe is below | `sa-port-47/gcd/stall/` |
| 4. Differential, multivariate, 0 mismatches | **Met on the guarded build** | `large-dump.txt`: seed 20261107, 20,000 ops, 4 vars, degree 3: 43,844 compared, 0 mismatches, 5,273 heuristic, 30 callback, 30 guard rounds, largest image 410,759 bits, finished in about 2.5 min. `large-guard.txt` is the same seed, rc=0; its body not read. `deg-guard.txt`: seed 11, 4,000 ops, 3 vars, degree 10: 26,544 compared, 0 mismatches, 3,485 heuristic, 148 callback (natural callbacks, which no earlier run had) |

**Guard:** `MAX_IMAGE_BITS = 1 << 15` at the top of each round. Set from `probe-noguard.txt` (plant 113, guard off, 60 s limit): 36,024 bits 0.91 s, 90,908 bits 30.7 s, and 2 of 18 shapes hit the limit, so the plant stalls and the probe catches it. `probe-guard.txt`: all 18 match Python's hash, slowest Rust 0.27 s against Python's 0.05 s.

Limits to report:
- **One seed per shape.** 18 shapes, seed 1 each.
- **The guard bounds each image, not the whole gcd.** Up to 6 rounds at each level multiply, and that worst case wasn't constructed.
- **The probe's limit is a judgement from timings on loaded orion**, which the ruling allows since firing is only a speed number. The Python times in `probe-noguard.txt` include SymPy's import; `probe-guard.txt`'s don't.
- **Speed, not a gate:** slowest Rust gcd in the degree 10 run 0.27 s against Python's 0.0091 s on that input. **`Num::from_py` still has no counter** (`constfield.rs`), so no speed number can be quoted as one yet.
- **sa-port-47's unguarded `large.txt` hadn't printed `ops done` at 13:30**, and dumps at about 14:00. Read the traceback: that the stall is `heu_gcd` is my inference from the guarded run finishing, not shown. The process isn't ours; leave it.
- **Mahler:** (4) `L(f) <= 2^(m1+...+mn) M(f)` and (5) `M(f) <= L(f)` checked in the ems.press reprint by extracted text. The OCR garbles the comparison sign in (4); the text says "best possible, with equality". Cited in the docstring. I changed its `M(f) <= |f|_2` to `|f|_1`, which is (5). The argument itself remains checked only by the planner's reading.

## The landing job is running, detached: don't restart it

`machine run pareto1 --shared`, lease 90f6be2d, wrapper log `~/sa-rust-ids-work/sa-port-51/land/machine.out`. Runs `~/sp51/p1_job.sh p1/p1_land_1b.sh` on `cae6663` in pareto1's `~/sp51/dev/sa-port-19`, x86-64 build sha256 `1cb066f17514`. **Output `pareto1:~/sp51/out/land/`, end marker `ALL.done`.** Copy with `rsync -a --exclude target --exclude hyp pareto1:sp51/out/land/ ~/sa-rust-ids-work/sa-port-51/land/out/`. To stop it, use only a path match on `sp51`.

Order: build, fresh dev/fuzz beside the Rust suite, `LRA_MUT` 0, 6, 7 (`lramut/m*/dev.cmp`), Python suite, handler plants (`plant-rust`, `plant-python`), history (`hist/cmp.txt`).

**Read so far, at 13:36:**
- **Fresh dev: MATCH.** 1,985 queries, 3,332 sessions, 0 differences in answers, end state, stream or LRA state; 0 Python solvers made on Rust. Fuzz was still running.
- **Rust suite: 5,960 / 124 failed (77 + 46 + 1) / 23 skipped / 18 xfailed.** 6,125 ids, none new or gone, against `~/sa-rust-ids-work/sa-port-38/s1/rust` (5,961 / 123). **One changed:** `tests/test_lra_exhaustion.py::test_split_beyond_the_certificate_bound_counts_as_exhausted`, passed to failed at :288 (`exhausted` False). It patches `LRATheory._certificate` at :282, which Rust doesn't read: the case the 1b ruling sends to the kept-on-Python list. It's the only such patch in `tests/`. **Its Python row isn't read yet, so confirm it passes there.** The test's unpatched half does run on Rust. Say what's lost: nothing else in `tests/` drives `_certificate`'s bound to a small value through the theory on Rust.

**Not read: everything else, including every firing.** Bar item 4 is open, so read the split before quoting any of this as met.

## What's left, in order

1. Wait for `ALL.done`, then copy. Check each: `fresh/fuzz.cmp` MATCH; `lramut/m0/dev.cmp` MATCH and `m6`, `m7` not (**whether 6 and 7 fire on this core is still unchecked; they sit at `lra.rs:1342`**). `hist/cmp.txt`, `hist/cmp.exit`: registries' order across orders; report any disagreement with its smallest case.
2. Firings: `python3 suite_split.py SUITE-RUST SUITE-PYTHON --base-rust ~/sa-rust-ids-work/sa-port-38/s1/rust --list FILE` (run with the env's Python, in `rust-spike/slice`). `plant-rust` and `plant-python` must show both sites fired. Anything other than the named needs-internals case and `test_protocol_on_fuzz`'s named firing is a finding, with its smallest case.
3. Quiet catches: count at `engine.py:1906` from the rows' `caught`, per the brief's QUIET FAILURES.
4. Land. **rust-slice moved to 4b2f12b (architect-64, 13:32), and you land next; the pyset-order Rust commit waits on you.** My diff check against 19ed342 says no rerun: `knowledge_live.install()` isn't called from `backend.py`, `rust_plugin.py`, `live.py` or `lra_backend.py`, and `git grep` finds `knowledge_live` in none of them. `test_knowledge_common.py` isn't under `tests/`. The crate gains code in `term/knowledge.rs` and `term/py.rs`, whose removed lines are imports only. **I read only the removed lines, so an insertion into an existing function isn't excluded: read the added hunks, or say so.** Then bring it in without force, rebuild, short check, push, and report tested SHA `cae6663`, landed SHA, incoming diff. Check `origin/rust-slice` again first. `port/1b` already holds a merge (51d30d1), so a merge may be simpler than a rebase; the push just has to be a fast-forward.
5. `results/port-1b.md`, `PORT-INVENTORY.md`, `agent report`, one-line SendMessage. DONE WHEN in the brief lists what it needs. Also from 47's list: `certified`/`certified_with` are answered from the Rust port of `lra_cert`, with no test through the theory until the suite says otherwise; `order:_rows` stays not caught unless a pivot-then-check run shows it.

## Shared files changed in this session

`test_cf_diff.py` prints the guard counts. New: `gcd_probe.py`, `p1/p1_land_1b.sh`. Earlier sessions' list: `HANDOFF-sa-port-47.md`.

## File map (`cae6663`)

| What | Where |
|---|---|
| Guard counter, limit | `rust-spike/slice/solver_rs/src/constfield.rs:762`, `:769` |
| Callback, route | `constfield.rs:774` `python_inner_gcd`, `:800` `sympy_inner_gcd` |
| Size estimate | `constfield.rs:880` `coeff_bits`, `:888` `image_bits` |
| Heuristic, argument above it, guard | `constfield.rs:958` `heu_gcd`, `:972` |
| Counts | `constfield.rs:2092` `cf_gcd_guard_count`, `cf_gcd_counts` just above |
| Probe | `rust-spike/slice/gcd_probe.py`; driver `~/sa-rust-ids-work/sa-port-51/gcd/probe.sh`, differential `gcd/diff.sh`, builds `gcd/so` (plain, sha256 `bf2ded199a9c`), `gcd/mut` |
| Landing | `rust-spike/slice/p1/p1_land_1b.sh`, `p1_land_short.sh`, `suite_split.py`, `livecmp.py`, `historycmp.py` |
| The changed test | `tests/test_lra_exhaustion.py:276-288` |
| Base rows | `~/sa-rust-ids-work/sa-port-38/s1/{rust,python}`; report `results/port-3.md` |
| Rest | `HANDOFF-sa-port-47.md`, `-46`, `-43` file maps |

## Must stay in every report

THE DROP, PLANTED PORT BUGS, QUIET COUNTER, `order:_rows` not caught and 1a's not-run list: in the brief under CARRY FROM 1a, unchanged and not rerun here. The transfer's results: `HANDOFF-sa-port-46.md`. 102, 105, 107 still unproven.

Nothing here suggests the transfer has to outlive 1b.
