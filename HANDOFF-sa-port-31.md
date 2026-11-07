# Handoff: sa-port-31, component 6, atoms (issue 323)

Clone `~/dev/sa-port-24`, branch `port/6`. Nothing is on `rust-slice`; 0 of the 32 count. `HANDOFF-sa-port-27.md` and `HANDOFF-sa-port-24.md` keep their maps; this file overrides their "owed" lists.

## The bar changed

`~/dev/architect/briefs/addenda/sa-port-landing-bar-ruling.txt` replaces HELD TO for landing. On the landing source after rebase: (1) suite by id with three numbers, any change explained; (2) fresh dev and fuzz MATCH; (3) at least one planted bug caught by that comparison; (4) quiet handler firings on Rust listed from that suite run, anything but the named needs-internals case is a finding; (5) a cause for any known difference. **Don't start** backend-PR-list work: corpus history, corpus leak, counts, timing, boundary rescore, suite column for mutants. The landing report lists them as not run.

Architect, process: new suites, mutants and history go on pareto0 or pareto1 under `machine run HOST --shared --wait 4h`, not orion. pareto0 has `~/sp19` but no cargo, so copy the x86-64 `.so`; no suite has run there yet. `Status: progress` goes to the journal with no SendMessage. A handoff's last step writes `~/dev/architect/briefs/NEXT-port-6.txt`.

**Blocked on sa-port-35 (lazy reads, `port/lazy`, was cb1370c, behind `rust-slice` e5dd23f).** Atoms can't land before it.

## What the rebase must do

A trial rebase of port/6 on cb1370c conflicts at the first commit, fe85470, in `convert.py`, `term/py.rs`, `term/table.rs`. Aborted, not resolved. **The real work is there:** `_Walk.atom_rows` reads `const_value` and facts eagerly at conversion, which is the kind of read the ruling removes. Make atom rows lazy on the same path: read when a template visits the atom, which is when Python reads them. Drop `complex-unbounded` (`convert.py:43`, the checks in `closed` and `convert`).

## Suite, run1, pre-lazy: partial and hung

`run1/suite-atoms` is **not a result**: 5,835 of 6,125 ids. Worker 4103627 has been stuck since 10:38 in `test_constants_evalf_cannot_bound_rigorously_are_not_read`, so `suite-rust` never started. Python's run finished: 6,080 passed, 4 failed, 23 skipped, 18 xfailed. Against the base by id (base 5,961 passed, 123 failed = 77 + 46): 80 fail in both, 0 fixed, 8 new.

| New failure | Cause | On port/lazy's conversion, without atom rows |
|---|---|---|
| `test_lra_constants` hang: `ask(Q.lt(x, sin(exp(exp(exp(5))))), Q.positive(x))` | `convert.py:315` `complex(t)`, plain 0.12 s, atoms over 60 s | converts in 0.3 s |
| `test_add_rows::test_a_node_of_one_term_is_that_term`, `test_mul_rows::test_a_node_of_one_factor_is_that_factor` | `Basic.__new__(Add, z)` has no `is_commutative`; KnowledgeFault from conversion | converts |
| `test_shared_facts::test_engine_does_not_write_sympy_assumptions` | conversion's reads write `_assumptions` | my probe sees no writes |
| `test_wide_derived`: `compiles_in_linear_time` 1, `derived_or_against_or_is_fast` 4 | wall clock asserts, 3.8 to 8.9 s against limits of 1 and 2; load or conversion's cost **not separated** | not run |

The last column ran `convert.convert` alone from lazy's tree, **with no atom rows**, so these can come back once rows are rebased if the rows read eagerly. Probes: `~/sa-rust-ids-work/sa-port-31/hang/`.

Unplanted firings so far, partial: `_consistent` AttributeError `_ok` 34 and `_rb_clauses` 4 (`test_ci_stream_reports_only_what_replays`, the named case). **New, unexplained: `Engine._build_context` RuntimeError "Already mutably borrowed", `tests/test_transfer.py::test_protocol_on_fuzz`, 1 firing.** It's a PyO3 borrow failure, so re-entry into a Rust object, and that handler can hide a wrong answer. Not known whether the base has it, because `suite-rust` never ran. Needs its smallest case under the bar's item 4.

Suite reach, two workers of three (the hung one wrote no totals): 18,594 converted, 1,789 symbol:input, 101 constant:input, 3 constant:derived. Thin against 18,594 conversions: the suite hardly drives atoms.

## Other results

- **Recount, run1 (0d4620b):** atoms same as plain on dev, fuzz **and corpus**, corpus's first complete run. Quiet scans on fuzz and corpus: `units` raising at 1107 reached on fuzz and escaped, counter 0; 1906 not reached by a real query on either; forced nest escaped at all four, counter 0.
- **Planted bugs, 36 plus base, base clean, all loaded (`mut/work/results.jsonl`):** 23 caught by a comparison in some column, 3 only by a crash (`atom-row-wrong-id`, `conv-no-constant-rows`, `conv-no-symbol-rows`), 10 caught by nothing: `expand-no-clause-dedupe`, `expand-no-literal-dedupe`, `unsubsumed-keeps-duplicates`, `in-vocab-keeps-commutative`, `conv-symbol-facts-sorted`, `live-all-derived`, `live-derived-keeps-commutative`, `live-any-class-row`, `live-stack-not-popped`, `live-fault-quiet`. I haven't analysed whether any of these are equivalent. Only 12 compare-catches are in `off`, the real run; 11 need `direct` or `shadow`. No suite column ran. `off` catches e.g. `expand-pos-neg-swap`, which serves bar item 3 once rerun on the landing source.
- **Leak, history, discard:** report 6cee807. All pre-lazy and dev and fuzz only. Don't quote `run1/leak-*.txt` or `disc1/leak-*`; `disc2/` holds the corrected ones.

## Jobs

`run1/suites.sh` is **still running and will not finish**: PIDs 4103476 (suites.sh), 4103479, 4103506, worker 4103627 burning a core on orion. I didn't kill it, because the architect said to leave running jobs alone; I asked in the handoff message. Check before assuming it's gone.

## File:line map

| Topic | Where |
|---|---|
| Lazy's plan and files | `~/dev/sa-port-5`, `origin/port/lazy`: `lazy_reads.py`, `test_lazy_reads.py`, `TERMS-INTERFACE.md`, `HANDOFF-sa-port-33.md` |
| Atom rows, to go lazy | `convert.py`: `_Walk.atom_rows`, `_CONSTANT`; `term/table.rs`: `AtomRow`, `read_atoms` |
| Wiring | `knowledge_live.py`: `install`, `rust_units`, `_ask` at :159 |
| Fresh and plants | `knowledge_fresh.py --mode --shuffle --plant`, `knowledge_plants.py`, `knowledge_histcmp.py` |
| Leak | `knowledge_leak.py run, cmp, fire` |
| Suite | `SLICE_KNOWLEDGE=atoms bash run_suite.sh WORK rust -p handler_count -p knowledge_suite tests`; `suite_split.py`. A single test needs `SLICE_SUITE_OUT`, `SLICE_SUITE_BACKEND`, `PYTHONPATH` with `rust-spike/slice`: `hang/one.sh` |
| Base rows | `~/sa-rust-ids-work/port-census/pr328-check/suite-rust`, `suite-python` |
| Mutants | `mutate_knowledge.py` |
| pareto recipe | `~/sp19/p1_job.sh` on the host |
