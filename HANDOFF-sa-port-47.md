# Handoff: sa-port-47, component 1b (LRA constants), issue 323

Written 2026-11-07 about 13:15 UTC, at the context note. Start here, then `HANDOFF-sa-port-46.md`'s "What's left" and "Must stay in every report". **Not landed. None of the bar's 5 items has been run on this source.** `port/1b` is pushed; it has `origin/rust-slice` 19ed342 (component 3) merged at 51d30d1, and the head is the commit carrying this file.

## The hold is over

Component 3 is on rust-slice at 19ed342 (architect, 13:0x UTC). Landing runs may start once the gcd is settled. `rust` mode now means Rust EUF, LRA and transfer together. `lib.rs` calls `term::py::register` at import, so the crate's `term/` is reached. Check `origin/rust-slice` again before the runs: `_common` (sa-port-48) may land, and by the planner's rule it gives no rerun if its diff check agrees.

## gcd: three of the planner's four checks pass, the fourth is running

`heu_gcd` is kept for now, `rgcd` and its helpers are deleted, and failures go to the counted callback.

| Check | State | Evidence |
|---|---|---|
| 1. Acceptance checked, argument for "greatest" | **Met, with a departure below** | Docstring at `heu_gcd`. Plant 108 (common, not greatest): 870 gcd mismatches. Plant 111 (no division check): 35 mismatches. Control 0. Each also shows `weak:ValueError`, the short run not drawing that exception, not a difference. `plant-{0,108,111,112}.txt` |
| 2. Counter | **Met** | `cf_gcd_counts`. Seed 7, 4 vars, degree 3: 5,441 heuristic, **0 callback**, 24,991 compared, 0 mismatches. |
| 3. The hang is gone | **Met on the one input** | sa-port-42's input **located, not assumed**: its original generator (2b7cfe1), seed 7, 4,000 ops, on the saved PRS build sat in `cf_inner_gcd` for the 200 s dump limit on gcd no. 33. On it, new build: Rust 0.0114-0.0117 s, Python 0.0067-0.0068 s (first Python row 0.73 s includes importing SymPy), equal, 0 callbacks. `stall/prs-7.rec`, `stall/direct.txt` |
| 4. Differential completes, 0 mismatches, multivariate | **Running, not read** | `large.txt`, marker `large.done`: seed 20261107, 20,000 ops, 4 vars, degree 3, this build, callback on. `CF_DUMP=3000` makes it dump and exit about 14:00 UTC: a traceback there is a stall. Started 13:10. |

Also running: `stall/new-7.txt`, marker `stall/new-7.done`, the original generator's whole stream on this build, with `stall/new-7.rec.slowest` holding the slowest input. All under `~/sa-rust-ids-work/sa-port-47/gcd/`. These load `gcd/so`, a copy built **before** the merge with the same gcd, so rebuilding doesn't void them. The plants used `gcd/mut`, also pre-merge.

### Tell the planner: the departure and its limits

- **I changed the start point, which the ruling didn't foresee.** The ruling accepted starting at `B = 2*min(norm)+29`. I could prove "greatest" at that start for one variable only: with several variables the root-bound argument needs more than the largest coefficient. So `x` now starts at `2*min(factor_bound)+29`, `factor_bound = 2**(sum of degrees) * 1-norm`, and the docstring gives a full argument for any number of variables.
- **The argument is mine and nobody has checked it.** The norm lemma (`|c|_1 <= 2**(sum of degrees) * M(c)`) is cited from memory, not looked up. The differential can't test the argument itself: on these inputs both starts give the same answers.
- **The larger start has a cost, and I don't know how far it goes.** Larger evaluation points mean larger integers. Slowest single Rust gcd in the seed 7 run: 0.17 s against Python's 0.008 s on that input, about 21x. The gcd phase took 62 s here and 17.3 s on 46's build, under different load, so that isn't a timing. **Nothing has tried high-degree inputs: `heu_gcd` has no size guard, so a stall could return in a new form, in big-integer gcds, where Python answers.** The one stalled input says nothing about that.
- **The callback hasn't fired naturally on any run.** It's shown only by plant 112, which forces it: 0 heuristic, 1,727 callback, 0 mismatches beyond the weak flag. Because natural failures are this rare, the hang protection depends on `heu_gcd` itself ending in reasonable time, not on the callback.
- **sa-port-46's large run** (`sa-port-46/gcd/run-large.txt`) is on the old start with the `rgcd` fallback. It isn't check 4. Read it for the stall only; at 13:13 it had printed no `ops done` after 17 minutes, and mine hadn't after 3.

**If the large run stalls or mismatches, or a high-degree probe hangs where Python answers: the ruling says use the shape-chosen callback and drop `heu_gcd`.** Don't patch around it. The stall in `cf_op` during ops at about 165 s (sa-port-42) was only inferred to be the gcd, so if the traceback is in `cf_op`, find out what it's doing before blaming either.

Report 102, 105, 107 as still unproven. Plant 108 was rewritten (it used `rgcd`) and is now the "common, not greatest" plant.

## What's left, in order

1. Read `large.txt` and `stall/new-7.txt`. Run a short high-degree probe, Rust against Python, by input and with a limit. Decide `heu_gcd`, and report the departure to the planner by `agent report` with Status: question if the check fails or the planner must rule. **The departure hasn't been reported as a question yet; my handoff report names it.**
2. Set up a tree on pareto1: `~/sp47`, modelled on `p1/setup_p1.sh` and `~/sp19/p1_job.sh` (`HOME`, `T`, `S` under `~/sp47`; `sa-rust-ids-work` can link to `~/sp19`'s env, data, sympy and venv; check that `env.sh` still resolves). pareto1 has cargo; pareto0's `~/sp19` has none. Copy the clone with rsync from orion. Not started.
3. Planted raise showing the handler counter fires on this tree: `suite_plant_handlers.py`, `test_handler_count.py`, `lazy_fire.py`. `live.py --handlers` hasn't been rerun since 43's fix.
4. The bar: `p1/p1_land_short.sh`, detached under `machine run pareto1 --shared --wait 4h`, with **`OUT` set under your own name** (its default names sa-port-36). It covers the suite by id, fresh dev and fuzz, and `LRA_MUT` 0, 6, 7. Whether those plants compile and fire on this core is **unchecked**; `gcd/mut` compiling only shows the crate builds with the feature. Base for the three numbers: rust-slice is 5,961 / 77 / 46 by `results/port-3.md`, with 6,125 ids; read that report's row and its suite directory for the by-id compare.
5. Constants history, added by the ruling: `run_history.sh` (recorded, shuffle, fork), `historycmp.py`. `p1_land_short.sh` doesn't run it. If the registries disagree on order, report the smallest case.
6. Keep-on-Python lists from the suite: tests patching `_certificate`, tests needing a real theory. `certified` and `certified_with` are answered from the Rust port of `lra_cert`; no test has exercised that through the theory yet.
7. `order:_rows`: `lra_text` now keeps the order, so a pivot-then-check case can supply evidence. It stays not caught until a run shows it.
8. `Num::from_py`'s call count is required beside any speed number. **No counter exists** (`constfield.rs:1937`). This report quotes no speed number: the gcd times above are for check 3 only. Add it before quoting one.
9. Push to rust-slice with no force, write `results/port-1b.md`, update `PORT-INVENTORY.md`, report.

## Shared files changed, for the report

`lib.rs`: conflict from the merge, both sides kept. Plus 43's list in `HANDOFF-sa-port-43.md`: `state.py`, `rust_plugin.py`, `handler_count.py`, new `lra_textdiff.py`. `test_cf_diff.py`: gcd counts and slowest gcd printed.

## File map

| What | Where |
|---|---|
| Route, `TooLarge` first | `rust-spike/slice/solver_rs/src/constfield.rs:791` `sympy_inner_gcd` |
| Callback, counters | `constfield.rs:765` `python_inner_gcd`, `:759` statics, `:2051` `cf_gcd_counts` |
| Bound | `constfield.rs:844` `factor_bound` |
| Heuristic and its argument | `constfield.rs:930` `heu_gcd`, docstring just above, `:948` plant 111 |
| Plants | `:775` `plant_drop_content` (108); 112 at the route; 111 above. `--features mutants`, `LRA_MUT=n` |
| Differential | `rust-spike/slice/test_cf_diff.py:136`, `:159`, `:224` |
| Merge | `solver_rs/src/lib.rs:8-20`, `:560-572` |
| Landing | `rust-spike/slice/p1/p1_land_short.sh`, `run_suite.sh`, `run_history.sh`, `historycmp.py`, `livecmp.py`, `lra_textdiff.py` |
| Base's report | `rust-spike/slice/results/port-3.md` |
| Rest | `HANDOFF-sa-port-46.md`'s and `HANDOFF-sa-port-43.md`'s file maps |
| Stall replay | My scratchpad scripts die with this session. To rebuild: 2b7cfe1's `test_cf_diff.py` with a wrapper around `S.cf_inner_gcd` that pickles `(n, a, b)` before each call. The input itself is safe in `gcd/stall/prs-7.rec`; the PRS build in `gcd/prs_so` |

## Must stay in every report

THE DROP, PLANTED PORT BUGS, QUIET COUNTER, `order:_rows` not caught and 1a's not-run list: in the brief under CARRY FROM 1a, unchanged and not rerun here. The transfer's results are in `HANDOFF-sa-port-46.md` under the same heading. `identity_rule.py`'s fresh result there names only `_forms`.

Nothing here suggests the transfer has to outlive 1b.
