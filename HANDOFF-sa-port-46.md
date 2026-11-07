# Handoff: sa-port-46, component 1b (LRA constants), issue 323

Written 2026-11-07 about 13:00 UTC, at the context note. Start here, then `HANDOFF-sa-port-43.md`'s "Unverified decisions" and "File map", `HANDOFF-sa-port-42.md`'s "Corrections", `HANDOFF-sa-port-41.md`'s "What will bite". **Not landed. None of the bar's 5 items is met on the landing source.** `port/1b` is at this commit. It still has rust-slice 6827bf7 merged, not dc3f15d.

## New since 43

- **Planner's gcd ruling:** `~/dev/architect/briefs/addenda/sa-port-1b-gcd-ruling.txt`. It's carried in NEXT-port-1b.txt and arrived after the gcd below was written.
- **Fuzz from 43, read:** MATCH. 3,000 queries, 4,943 sessions, 3,192 LRA sessions all group `rust`, answer, end, stream and lra diffs all 0, python solvers 4,943 / 0, `answers_sha` 173502b6ef285ad6 both. `sa_solver.so` kept its 12:47 mtime throughout, so the result isn't void. It ran before the rebase and on the PRS build, so **it isn't the bar's run**.
- **Handlers:** `fuzz-*.jsonl.handlers` are 0 lines. **Not evidence**: no planted raise has been shown firing on this tree.
- **`_from_sympy`:** planner ruled it stays on Python, no per-query table, `constfield.py` not counted whole. Report `Num::from_py`'s call count beside any speed number. No counter exists yet.
- **Install patch of `_sympy_inner_gcd`:** ruled out. It was never written, so there's nothing to remove. My question report (1068501) proposed it; that part is dead.

## The open choice: heuristic gcd or the ruling's callback

**I wrote `heu_gcd` (`constfield.rs`, before `gcd`) before the ruling arrived.** The ruling's default is different: Rust keeps the shapes the differential covered, every other non-trivial gcd goes to Python's `_sympy_inner_gcd` by a counted read-only callback, chosen by shape only, `TooLarge` first. It allows the heuristic in 1b "only if it's quicker than the callback". So this code has no standing yet.

What's known about it:
- `test_cf_diff.py 7 1500` with `CF_GCD=2500 CF_GCD_VARS=4 CF_GCD_DEG=3 CF_CERT=100`: 24,991 compared, 0 mismatches, gcd phase done at 17.3 s on 4 vars, degree 3. Output `gcd/run-4v3d.txt`. PRS stalled over 100 s on this kind of input by sa-port-42's account. One seed only.
- **No counter of heuristic against PRS exists**, so I can't say how many of those gcds took which path.
- Constants checked against `euclidtools.py` (`HEU_GCD_MAX` 6, `2*min+29`, the `73794` step). The body was written from memory of it, not ported line by line.
- It differs from SymPy in two ways: it starts at `B`, where SymPy can start lower, and it has no cofactor retries. So it can fail where SymPy succeeds.
- **On failure it falls to `rgcd`, which can still hang where Python answers. That fails the bar as the ruling reads it.** Keeping the heuristic as written doesn't settle the ruling.
- The "a divisor that passes is the gcd" comment is my argument, shown for one variable by the root bound and assumed for several. Only the differential backs it.
- Mutant 108 moved into `sympy_inner_gcd`, not rerun. `rgcd` and its helpers remain.

**Recommendation:** read the large run. If it completes clean, keep `heu_gcd` and replace the `rgcd` fallback with the counted callback. That removes the hang. It also means the callback fires on the heuristic's failure, which is deterministic and not time-based but isn't "by input shape" as the ruling says. **That's a departure, so the planner has to accept it; I've put it in my report.** Otherwise do the ruling's shape-chosen callback and drop `heu_gcd`. Either way the differential has to rerun with the callback on.

**Large differential: running, detached, not read.** `~/sa-rust-ids-work/sa-port-46/gcd/run-large.txt`, `run-large.done` marks the end. Started about 12:55 UTC: seed 20261107, 20,000 ops, `CF_GCD_VARS=4 CF_GCD_DEG=3`, loading the copy in `gcd/so`, with **no callback**. `CF_DUMP=1500` makes it dump a traceback and exit at about 13:20: a traceback there means a stall, not a completion. The wider generator means it probably doesn't draw the same inputs as sa-port-42's stalled run; I didn't check.

## Also running, detached

`identity_rule.py`, rewritten, on the `gcd/so` build: `~/sa-rust-ids-work/sa-port-46/identity/{out.txt,result.json,done}`. Duration unknown, first run since the rewrite. It compares Python and fresh Rust to the end of the session, and its `calls` part reads through the state view. Read `session_differs` and `differs`. It's no longer the move result, so don't quote it as 14,424 moved sequences.

## Transfer's users: done, mostly not run

- Deleted: `dump_mutants.py`, `p1/p1_move.sh`, `p1/p1_drop.sh`. `dump_mutants` and `p1_drop` weren't named in the brief; `dump_mutants`' docstring says it goes with the transfer.
- `except_probe.py`: own `HOOKS`, writes its counts if the file is missing. Compiled, not run. `p1_fresh.sh` runs its first probe alone so the others don't race on that file.
- `port_mutants.py`: 3 stale patches rewritten. All 13 Python patches occur exactly once in `lra_backend.py` (checked). **Its Rust patches (`RS`) weren't checked** against the rewritten `lra_py.rs`, and nothing was run. `touch_skipped` now covers the plain constant path only.
- `p1_landing.sh`, `p1_ground.sh`: move steps cut. Syntax checked only.
- `test_lra_raises.py`: vacuous "moved" gone; 1 passed on the `gcd/so` build.
- `grep` finds no name of the transfer left in `rust-spike/slice/*.py` or `*.sh`, apart from `identity_rule.py`'s docstring describing the old result.
- **The tree's `sa_solver.so` is still the 12:47 build, without `heu_gcd`.** My build is at `~/sa-rust-ids-work/sa-port-46/target`. Run `build_solver.sh` after settling the gcd.

## What's left, in order

1. Settle the gcd as above. Implement, count the callback, rerun the large differential to completion with the callback on. Report 102, 105, 107 as still unproven.
2. Merge or rebase on `origin/rust-slice` (dc3f15d at writing; sa-port-38 and sa-port-45 are heading there). `lib.rs` is the likely conflict. Rebuild.
3. A planted raise showing the handler counter fires on this tree (`test_handler_count.py`, `lazy_fire.py`). `live.py --handlers` hasn't been rerun since 43's `handler_count.py` fix.
4. Plants for bar item 3: `p1_land_short.sh` uses `LRA_MUT` 0, 6, 7 on a mutants build. Whether they compile and fire on this core is unchecked. `mutate_slice`'s `rat` `#[path]` is not rechecked.
5. **Constants history, added by the ruling:** dev and fuzz, Rust's answers and state against Python's, persistent and fresh processes, two query orders. `run_history.sh` looks like it fits (recorded, shuffle, fork), and `historycmp.py` reads it; I read only the header. If the registries disagree on order, report the smallest case.
6. The bar on pareto0 or pareto1, detached: `p1/p1_land_short.sh` with `OUT` set under this session's name, because its default names sa-port-36. Three numbers, firings, by id.
7. `order:_rows`: `lra_text` now keeps the order, so a pivot-then-check case can supply evidence. It stays not caught until a run shows it.
8. Keep-on-Python lists from the suite (tests patching `_certificate`, tests needing a real theory). `certified` and `certified_with` are answered from the Rust port of `lra_cert` (43's choice); no test has exercised this through the theory yet.
9. Push to rust-slice with no force, `results/port-1b.md`, update `PORT-INVENTORY.md`, report.

## File map

| What | Where |
|---|---|
| Heuristic gcd | `rust-spike/slice/solver_rs/src/constfield.rs`: `heu_gcd`, `interpolate`, `eval_top`, `max_norm` just before `gcd`; `sympy_inner_gcd` :~758 is the switch; `rgcd` :~836 |
| Bridge for the differential | `constfield.rs` `cf_inner_gcd` :~2053 |
| Python's gcd | `satassume/theories/lra/constfield.py`: `_inner_gcd` :510, `_sympy_inner_gcd` :577 |
| SymPy's gcd | `$W/sympy/sympy/polys/euclidtools.py`: `dmp_zz_heu_gcd` :1301, interpolate :1284, `dmp_inner_gcd` :1605 |
| Differential | `rust-spike/slice/test_cf_diff.py`: gcd generator :134-150, `CF_SO`, `CF_GCD`, `CF_GCD_VARS`, `CF_GCD_DEG`, `CF_DUMP` |
| Python side | `rust-spike/slice/lra_backend.py`: `_register`, `_pairs`, `_state`, `install` |
| `_from_sympy` callers | `satassume/theories/lra/lra_adapter.py` :213, :243, :262 |
| Landing run | `rust-spike/slice/p1/p1_land_short.sh`, `run_history.sh`, `historycmp.py`, `livecmp.py`, `lra_textdiff.py` |
| Rest of the core | `HANDOFF-sa-port-43.md`'s file map |
| Output | `~/sa-rust-ids-work/sa-port-46/` (`gcd/`, `identity/`, `target/`); fuzz at `~/sa-rust-ids-work/sa-port-43/first/fz/` |

## Must stay in every report

THE DROP, PLANTED PORT BUGS, QUIET COUNTER, `order:_rows` not caught and 1a's not-run list: in the brief under CARRY FROM 1a, unchanged and not rerun here.

The transfer's results: dev 113 Rust / 109 moved, fuzz 2,569 / 623, suite 42,661 / 2,697 moved in 239 tests, all natural moves at level 0; `identity_rule.py` 14,424 sequences, 344,304 answers, 0 differ (hook level, plain Fractions, moves at level 0). The object rule is `port-1a.md:54-61`. Those moved sessions now run on Rust. Dev's and fuzz's are covered by the state comparison, pre-rebase only; the suite's aren't covered until it runs.

Nothing here suggests the transfer has to outlive 1b.
