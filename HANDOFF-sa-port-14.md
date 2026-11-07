# Handoff: sa-port-14 to the next session (issue 323), components D and 0

Read the brief first: `~/.local/state/agent/briefs/sa-port-14-20261107T081246Z.txt`; its terms, rulings and slice order still apply. Branch `port/D0`, clone `~/dev/sa-port-5`. Nothing is on `rust-slice`. Modules of the 32 running in the real engine because of this: **0**; the shadow decides nothing. `HANDOFF-sa-port-13.md` still holds for the algebra's design choices, and `-10` for the conversion and the Pow ruling.

## Read this first: what the results below ran on

- **Every run below used `sa_solver.so` sha 128d4450, built from before the `oo` rule.** The rule is in the source at e88e1a5 but has only been test-built, into `sa-port-14/ckbuild`. **It has never run.** First step: `sh rust-spike/slice/build_solver.sh`, then rerun. Don't report item 2's rule as working until then.
- **The shadow changed during the chain, additively:** `fuzz-s0` ran on the shadow of 3f4cf71, so it has no Pow query counters (its `pow_base_not_input` is 0, so nothing is lost). The later runs have them.
- **Written and not run at all:** `synthetic` in `term_shadow.py` (`term_shadow_fresh.py --synthetic`). **`mutate_term.py` has never run:** its 27 plant sites were checked for exactly one match, then I changed `no-merge-with-known`'s text and didn't recheck it. A plant that fails reports itself.
- **`term_history.py`: 60 dev queries only** (recorded fresh against reverse dirty, 0 differ). That's a smoke test, not the history result.
- **The suite has no numbers.** I stopped my run at about 28% because the crate had changed. `suite/rust-stopped-early` is not a result; don't read it. Sibling processes weren't touched (checked by `SLICE_SUITE_OUT`).

## Results so far, fresh engine per query, orion

Output under `~/sa-rust-ids-work/sa-port-14/`. `brief.py OUT.json` summarises a shadow run; `counts_summary.py counts/WL` joins ruling 6's two modes.

| Run | Answers sha, same as plain | Ops / derived | Cones fully known | Used keys, unknown | Mismatches | Refusals |
|---|---|---|---:|---:|---:|---|
| dev, seeds 0, 1, 2 | a5349612416b55ef, yes | 12,129 / 4,919 | 5,749 of 5,749 | 6,817, 0 | 0 | 12, the same 12 |
| fuzz 424242, seeds 0, 1 | d4006a14c365ecdf, yes | 122,569 / 27,647 | 31,431 of 31,431 | 172,936, 0 | 0 | 0 |
| corpus, seed 0 only | 544a8c885fcd4911, yes | 12,408 / 5,939 | 5,210 of 5,210 | 2,165, 0 | 0 | 28, below |

Dev seed 0 is `dev4/shadow.json`. Dev keeps 50 and corpus 190 on Python, all `out-of-scope`; fuzz keeps none. Unknown objects are 0 by site and class on all of these.

**Limits on that table:**
- **Over-budget cones: 0 on all three workloads,** so that branch has only the per-object check and hasn't run here. Step 4's boundary-value test is where it gets exercised.
- **Weights are still Python's own `_struct`.** The check shows cone objects map one to one onto Rust ids, so Rust's node count would equal Python's. It doesn't show Rust computing a weight.
- **Fuzz's zero refusals don't exercise the refusal paths.** The corpus is the only workload here that does, and it has one seed.
- **Inference, not checked:** dev's derived terms rose from 4,870 to 4,919, which I reported as the 49 rationals now registered by value. `alg:same-as-known` rose by 51 too. No run separates these.

**Item 1, closed on all three workloads.** Cause of the 659 cones and 725 struct calls: a shadow bug, `cone_id` read `o.arg` and P's field is `expr`. Keys and nodes: rationals registered by value only for operands.

**Item 2.** Dev's 12 are one pair, `0` against `oo`, both ways, 6 queries: `V::Rat` against `V::Term`, which `value_cmp` refused where Python's tuple `<` reaches SymPy's `Zero < oo`. No used key refused. Corpus has more pairs: `oo*I` and `I` (3 each way), `-oo*I` and `I` (1 each way), `1` and `oo` (1 each way). The new rule should cover `1` and `oo`; **whether it covers the `oo*I` pairs is unknown.** Float and nan still refuse by design. I checked the rule's expected values by hand in Python only for 0, 1/3, 1/2, 10**100 against +/-oo.

**Corpus's other refusals, by reason:** `derived key: power base not an input term` 8; `__mul__: infinity or nan` 4; `__mul__`, `__sub__`, `__truediv__`: Float, 1 each; `__truediv__`: denominator not a nonzero rational, 1.

**Pow, corpus seed 0:** 9 such terms, 9 queries holding one, **0 refused at a used key, 9 finished without refusing.** The 8 `derived key` refusals above come from the shadow asking for a derived term's key, not from the query using it, so I didn't count them as refusals at key time; check that reading. This isn't the same measure as the earlier 82 from the synthetic Python check. **The seed requirement isn't met yet:** dev and fuzz hold no such Pow, and corpus ran at one seed. Run corpus at seeds 1 and 2.

### Not explained: `struct:calls` moves with the hash seed

Dev 7,975 / 8,412 / 8,399 at seeds 0, 1, 2. Fuzz 68,168 / 65,824 at seeds 0, 1. Cones, weights' objects, nodes, ops and answers are all the same across seeds. It's a count of calls into Python's own `_struct`, so it may be only traversal order, but nothing has shown that. It's on the reference side, and it belongs in the history section of the report until read. Start at `Engine._struct` and whatever calls it outside `_cone_info`. PR 328's own seed checks may or may not cover this; I didn't look.

### Ruling 6, so far: dev and fuzz only, times load-affected

Separate processes per mode, every memo and SymPy's cache cleared per query, `Basic.__new__` counted. Corpus not run: `sa-port-14/counts.sh corpus`.

| Converted queries | Pure Python constructs | Conversion | Ask after conversion | Together vs Python | Keys computed / key calls used | Queries using any key | Keys computed where none used |
|---|---:|---:|---:|---:|---:|---:|---:|
| dev, 1,935 | 7,712 | 4,088 | 7,415 | 1.49x | 6,532 / 6,817 | 210 | 5,328 |
| fuzz, 3,000 | 93,000 | 25,053 | 80,993 | 1.14x | 28,864 / 172,936 | 2,940 | 338 |

- **`used` is calls, not distinct keys,** so the two key columns aren't like for like.
- **Share of query time, orion at load 34-44, not usable as timing:** conversion plus table, dev median 0.50 and total 0.33; fuzz median 0.15 and total 0.14. Fuzz's pure-Python pass read 72.0s against 50.4s for conversion plus ask, which is load, not a saving. **The brief wants this from a quiet lease on pareto1, which hasn't been done.** pareto1 has no clone or env: it needs an x86-64 build (`results/step5-timing.md`, image `sa-eval-bench:1`, `sa-cy-build:1`, `bench-container`), and `term_counts.py --no-count`.
- **By site, dev (`counts/dev-site.json`), total 4,092:** `closed`'s `complex(t)` at `convert.py:291` 2,553, mostly `Float`; `default_sort_key` at `convert.py:252` 1,427; `klass` at `:219` 102. The 4 over the table's 4,088 are probably the kept queries' partial conversion; not checked.
- **Queries where the ask after conversion constructs more than pure Python:** 10 on dev, 5 on fuzz. Not read.
- **Looks like the ruling's "noticeably more" on dev.** Bring the numbers as a question to the planner with the quiet-lease share. No lazy path in the meantime.

## Next, in order

1. Build, rerun `tests_offline.py` (it passed on the old crate: ALL PASS), rerun dev under the shadow, read the 12.
2. `runs.sh` is the shape for reruns. Corpus at seeds 1, 2, and `--synthetic` on dev, fuzz and corpus in separate output directories, since it adds to the same counters.
3. `counts.sh corpus`; the quiet-lease share; send ruling 6's question.
4. **Item 4, the suite:** `SLICE_SUITE_SHUFFLE=1 PYTEST_N="-n 3" bash run_suite.sh ~/sa-rust-ids-work/sa-port-14/suite/rust rust` on the final crate, about 40 minutes at this load, then `suite_report.py` and by-id against `~/sa-rust-ids-work/port-census/pr328-check/suite-rust`. Don't rebuild the `.so` while it runs. `test_performance_smoke_300_vars` is known to fail under load.
5. `mutate_term.py WORK --jobs 2`: a cold build took 3m55s under this load. Boundary row scores the crossing both ways.
6. History: `term_history.py` on dev and fuzz at seeds 0, 1, 2, then reverse and shuffle with `--dirty`, compared with `--cmp`.
7. The section 9 bullet move (ruling, point 1), then rebase, push to `rust-slice` without force, report.

Standing report lines in the brief still apply: S's gate, the `_n_conflicts` shim, mutants 2, 5, 6, 7, 9, the boundary suite column.

## File:line map

| Topic | Where |
|---|---|
| Key order rule, `kind_of` | `solver_rs/src/term/table.rs`, `value_cmp`, about `:391` |
| Algebra | `solver_rs/src/term/algebra.rs`: `intern` `:74`, `number` `:111`, `neg` `:170`, `keep_coeff` `:192`; power-base refusal `:654` |
| Conversion's constructing reads | `convert.py`: `klass` `:219`, `default_sort_key` `:252`, `closed` `:286-291`, `power_rows` `:299-308` |
| Shadow | `term_shadow.py`: `known_id`, `cone_id`, `check_order` (`KEY_REFUSED`), `synthetic`, `top_level`, `install` (Pow counters, `counted`) |
| Drivers | `term_shadow_fresh.py`, `term_counts.py WL py\|conv OUT [--no-count] [--by-site F]`, `term_history.py`, `mutate_term.py` |
| Scripts outside the clone | `~/sa-rust-ids-work/sa-port-14/`: `env.sh`, `runs.sh`, `counts.sh`, `brief.py`, `counts_summary.py` |
| Interface | `TERMS-INTERFACE.md`, sent to the EUF sibling at f153b66 by an earlier session. Its "Built so far" line may be behind; update it when landing |

**Environment:** `. ~/sa-rust-ids-work/sa-port-14/env.sh`, cwd `$C/rust-spike/slice`, `$PY` is the venv's python (system `python3` has no mpmath). Orion's load was 34-44.
