# Handoff: sa-port-18 to the next session (issue 323), components D and 0

Read the brief first: `~/.local/state/agent/briefs/sa-port-18-20261107T083750Z.txt`; its terms, rulings and slice order still apply. Branch `port/D0`, clone `~/dev/sa-port-5`. Nothing is on `rust-slice`. Modules of the 32 running in the real engine because of this: **0**; the shadow decides nothing. `HANDOFF-sa-port-14.md` still holds for the file:line map and what its results were; the results below replace its table where they overlap. No source changed this session: the crate is still 446d68d.

## Read this first: jobs left running at handoff (09:02 UTC)

| Job | Output, under `~/sa-rust-ids-work/sa-port-18/` | If it died |
|---|---|---|
| **The suite**, `.so` sha 5e6231ab, started 08:41:56 | `suite/rust/` (rows, `pytest.log`, `exit.txt` last) | Rerun, below |
| `union.sh`, at fuzz budget 400 | `union.log`, `union/` | Rerun `bash union.sh` |
| `handler.sh`, detached, corrected | `handler.log` | Rerun `bash handler.sh` |

- **The suite runs under my session's shell, so stopping my session may kill it, and then `exit.txt` is never written. Don't wait on that file alone.** Alive means a process whose environment holds `SLICE_SUITE_OUT=$HOME/sa-rust-ids-work/sa-port-18/suite/rust`: read `/proc/PID/environ` for `pgrep -f "[r]ust_plugin"`, since siblings run suites too. Dead with no `exit.txt`: rerun with `SLICE_SUITE_SHUFFLE=1 PYTEST_N="-n 3" bash rust-spike/slice/run_suite.sh ~/sa-rust-ids-work/sa-port-18/suite/rust2 rust`. About 40 minutes at this load.
- **At 09:02 it had 3,578 rows: 3,481 passed, 75 failed, 12 skipped, 10 xfailed. That's partial and not a result; nothing has been compared by id.** Don't rebuild `sa_solver.so` while it runs.
- `union.sh`'s `.py` paths were rewritten to `tools/`, but the copy already running read the scratchpad's; both hold the same code.

## Results, on `.so` sha 5e6231ab (first build with the `oo` rule), orion, seed 0

- `tests_offline.py`: ALL PASS.
- **Dev:** answers a5349612416b55ef, same as plain. Mismatches 0, **refusals 12 to 0**. Cones 5,749 of 5,749 known, used keys 6,817, 0 unknown, `struct:calls` 7,975.
- **Corpus:** answers 544a8c885fcd4911, same as plain. Mismatches 0, **refusals 28 to 18**, kept 190, all out-of-scope. The 18: derived key, power base not an input term 8; `__mul__` infinity or nan 4; Float in `__mul__`, `__sub__`, `__truediv__` 1 each; `__truediv__` denominator 1; `x**1.4` against `x`, both ways, 2.
- **`oo*I` and `-oo*I` against `I`: the rule covers them.** The 10 refusals are gone, and `tools/oo_pairs.py` checks 17 pairs through `TermTable.key_cmp` both ways, all equal to Python.
- **Pow, corpus seed 0:** 9 such terms, 9 queries holding one, 0 refused at a used key, 9 finished without refusing. The 8 `derived key` refusals are still read as the shadow's own ask; handoff 14 asked for that reading to be checked and I didn't. Seeds 1 and 2 not run, so the "must not change across seeds" requirement is still unmet.

## Named this session

**`struct:calls` and hash seed: the count's cause is named.** `Engine._union` (`engine.py:1767`) iterates the set `objs` from `:1744`, and `:1777` calls `_struct` only when a cone partly overlaps what has accumulated. Dev by caller at seeds 0, 1, 2, reconciling exactly with 7,975 / 8,412 / 8,399: `:1777` 814 / 1,251 / 1,238; `_cone_info`'s walk, `:1696` + `:1711`, 7,161 at every seed. Smallest case: `ask(Q.zero(x), Q.ge(x, -pi/2))`, 7 / 9 / 7 calls. Fuzz not run: `sites-fuzz.sh`.

**Do the results depend on hash order?** `tools/union_order.py`, seeds 0, 1, 2. Dev at budgets 400, 25, 5: answers, `_within_budget`, budget-limited counts and fitting cones' (weight, rel, size) differ in 0 of 1,985, and weight equals the sum of struct weights at every `_union` return with a cone (0 failures). **At budget 5, over-budget cones ran: 188 None returns, 133 queries, 189 limited. There the `(weight, rel)` of a None result differs on 8 queries (519-523 and others) with the hash seed, and no answer moves.** So that early return is order-dependent, as the code reads: `:1798` reads `rel_a` before the None check. My argument that it can't move an answer: `rel` only changes `link`, `link` only grows cones, so an over-budget cone stays over budget and those paths return False. That argument plus these runs is the evidence; it isn't proof. **Rust's `_union` must not copy this if anything ever reads those values.** I didn't separate whether `weight` or `rel` is what moved. Fuzz and corpus are running; budget 25 had no over-budget cone on dev.

**Pure Python's construction count isn't reproducible between identical runs at one hash seed. This is new.** Dev on orion, two runs: 16 of 1,985 queries differ. Not architecture, not ASLR (`setarch -R`: 26 differ). Cause: SymPy's own `_assumptions_shuffle`, `core/assumptions.py:596`, with a per-process RNG. Smallest: `ask(Q.positive(a), Q.integer(a/b))`, 7 or 5 over 12 fresh processes (`tools/one_query.py`). **Seeding only that RNG: three full dev runs, 0 queries differ, 8,001 each** (`tools/seeded_counts.py`). Answers didn't move in these dev runs, **but don't write this up as affecting counts only (planner, point 5).** It's the same site PR 330 pins in the harness (`sympy.core.assumptions.shuffle = list.sort`), for issue 329, where an answer moved between True and ValueError. PR 330 is open and isn't in this clone, and I haven't run with its pin. Issue 329's text says "not caused by ... the shuffle", which I took to mean the order test's shuffle; I read only its opening, so check that. Construction counts here carry noise of about 10 in 8,000. That this explains the gap to sa-port-14's 7,712 / 7,415 is an inference from noise of the same size, not a direct check; `conv_new`'s one differing query (933, 24 against 25) wasn't traced.

## Ruling 6: the planner has ruled (forward-chain-3b, 7 Nov; Tilo can overrule). Work still owed

**No lazy path for keys.** Re-measure when 2 and 4 consume conversion. The "with the ask after it" ratios (1.49x / 1.14x / 2.58x) only last while Python's engine runs: don't quote them as final. **`complex(t)`, `convert.py:291`, is input-layer construction under point 5, with its own counter,** outside the "must reach zero" rule. Without it conversion is 0.20x / 0.14x / 0.57x of pure Python (the planner's figures, not rechecked). Owed in the report:

1. **Key order only:** the only reader of the closed value in `term/` is the key, `algebra.rs:642-645`, so a floating value never decides a fact (issue 247). My rg agrees, but it was cut at 10 lines: rerun it whole and say so in the report.
2. **Worst case:** the largest single `complex(t)` time on the three workloads, plus a few hand-built expensive closed terms. If one is much slower than pure Python on the same query, bring it to the planner as a question. That would be a reason for laziness apart from the 2%. Not started.
3. **Split the rest of conversion's time:** keys and closed explain 10% / 23% / 17% of it. One by-site profile on the quiet lease, reported. Optimize nothing. Not started.
4. **Put the shares and ceilings in the report, labelled as arithmetic, not a measurement and not a gate.** If conversion stays as it is, against pure Python: everything after conversion free, 2.2x dev, 6.7x fuzz, 2.0x corpus by total, about 1.1x on the median dev and corpus query; an assumed 10x on the rest, 1.8x / 4.0x / 1.7x. Conversion is a first version with no consumers yet, so these should move.

Numbers it ruled on:

pareto1, quiet lease, `bench-container`, `BENCH_CPU=2`, x86-64 sha 4bdc9b63, 3 rounds, 0 answer differences, rounds within about 1%. Raw: `p1/timing`, `p1/site`, `counts/`; `timing_summary.py p1/timing`.

| | Pure Python constructs | Conversion | Share, total and median | Keys computed / in queries using none | Time share: keys, closed |
|---|---:|---:|---|---|---|
| dev | 7,706 | 4,089 (0.53x) | 0.31, 0.48 | 6,532 / 5,328 | 1.8%, 1.4% |
| fuzz | 93,006 | 25,053 (0.27x) | 0.13, 0.14 | 28,864 / 338 | 2.0%, 1.0% |
| corpus | 6,070 | 9,811 (1.62x) | 0.33, 0.48 | 6,849 / 6,587 | 2.1%, 3.4% |

**Recommended: no lazy path.** Asked as well: `closed`'s `complex(t)`, `convert.py:291`, is the largest count (2,553 / 12,429 / 6,341) and point 5 of the ruling doesn't name it. **No lazy path until the planner rules.** The rest of conversion's time isn't split by site. Reports: a99329a (step 1), 79ac3e4 (ruling 6).

## Owed to the architect: `engine.py:1906` (sibling sa-port-12, report 2a5386d)

They asked whether my runs would show `except Exception` at the complete check firing, or for a count. **Partly answered: dev plain, 2,631 complete checks, 0 raised, answers a5349612416b55ef. The other five rows weren't in when this was written: read `handler.log`,** which gives complete checks and raises by type and site, plain and under the shadow, with an answers sha to compare with the digests above. What I can already say: equal answers against plain would show only a raise that happens under the shadow alone, so a raise in both modes is invisible to that comparison. Every check-side exception becomes `unknown` quietly: my own first `handler.py` had a wrapper bug, all 2,631 dev checks raised `TypeError`, and nothing crashed. **That run is invalid, kept as `handler.invalid-wrapper-bug.log`; don't read it as a count.**

## Next, in order

1. The suite: `suite_report.py` and by id against `~/sa-rust-ids-work/port-census/pr328-check/suite-rust` (`exit.txt`: 123 failed, 5,961 passed, so 5,961 / 77 / 46). `test_performance_smoke_300_vars` is known to fail under load; orion is at 54.
2. Read `handler.log` and `union.log`; answer the architect; run `sites-fuzz.sh`. Then the planner's items 2 and 3 above, on pareto1.
3. `bash runs.sh corpus,1 corpus,2 dev,0,--synthetic fuzz,0,--synthetic corpus,0,--synthetic`: each goes in its own directory. `--synthetic` has never run.
4. `mutate_term.py WORK --jobs 2`. It builds in scratch copies and only reads the live `.so`. **`no-merge-with-known`'s text is still unchecked;** a plant that fails reports itself. Boundary re-score both ways.
5. History: `term_history.py` on dev and fuzz at seeds 0, 1, 2, reverse and shuffle with `--dirty`, compared with `--cmp`. Pow counts across seeds come from item 3.
6. Section 9 bullet move, `TERMS-INTERFACE.md`'s "Built so far", rebase, rerun the suite if the rebase brings others' source, push to `rust-slice` without force, report with the standing lines (S's gate, the `_n_conflicts` shim with its 64 tests, mutants 2, 5, 6, 7, 9, the boundary suite column).

## Map

`HANDOFF-sa-port-14.md`'s table holds for the crate and shadow. Added:

| Topic | Where |
|---|---|
| `_union`, its callers | `engine.py:1759-1781`, `_query_cone` `:1726`, `_within_budget` `:1795-1827` |
| Handler | `engine.py:1903-1910`; `_complete_check` is a staticmethod, `:1952` |
| Scripts, env | `~/sa-rust-ids-work/sa-port-18/`: `env.sh`, `runs.sh` (`wl,seed[,--synthetic]`), `union.sh`, `handler.sh`, `sites-fuzz.sh`, `timing_summary.py`, `brief.py`, `counts_summary.py`, `tools/` |
| pareto1 | `~/sa-port-18`: `src`, `sympy`, `evalbench`, `data` (rsync -c: same as orion's), `build/sa_solver.so`, `p1-*.sh`. `pareto-build.sh` rebuilds; **its `src` is a copy, so rsync first if the crate changes.** Timing: `machine run pareto1 --quiet -r WHY -- bash ~/sa-port-18/p1-driver.sh` |

**Traps I hit:** `pkill -f` kills your own shell when its command line holds the pattern, so kill by PID. In `p1-timing.sh` and `p1-counts.sh`, `exit=$?` isn't Python's status in the timing script (it follows a `date` substitution), so check row counts and `done` lines, as I did. `term_counts.py --no-count` shows 0 constructions, as intended.
