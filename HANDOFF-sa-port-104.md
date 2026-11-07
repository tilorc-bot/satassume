# Handoff: sa-port-104 to the next 6e session (`knowledge/templates/core.py`, issue 323)

**State (7 Nov 23:10 UTC):** port/6e rebased cleanly on rust-slice 67106e8 (wiring landed, so core runs on the default Rust
backend through `knowledge_live.from_env()`). Tested source **ac0f88d**. After it: test_knowledge_core_shapes.py and this
handoff (test and docs only). Nothing landed. Handed off at the 142k context note.

## Done (sa-port-104)
- `knowledge_core_live.py`: `fallback(key, f, *a)` (in `install`, before `rest`): the planner's two named SymPy-semantics
  callbacks (`core:unit_power:python`, `core:imag_number:python`) are counted, and any exception in them is a KnowledgeFault.
  `_hit(name)` (top of file): core's Python plants also read `SLICE_SESSION_PLANT` and count via `knowledge_live._fired`.
- `test_knowledge_core_fallback.py` (4 tests): each callback counted on a real ask; a planted raise in each is loud.
- `test_knowledge_core_shapes.py` (9 tests): crafted queries, plain vs `install(shadow=True)`, one per core Rust plant that
  the workloads never caught (see below). All pass on the real build and all reach their function.

## Evidence so far
- Orion short (`~/sa-rust-ids-work/sa-port-104/short/`, ac0f88d's .so before the shapes test): dev-400 and core wl plain
  vs atoms MATCH; `core-pi-coeff` caught on core wl (90 answers, 536 lines); `core-mul-drop-ipi` caught (158 lines, 0 answers).
  Neither fires on dev-400.
- pareto1 job (lease 672038d6, orion wrapper PID 530663, local log `~/sa-rust-ids-work/sa-port-104/p1-run.log`; rows
  `pareto1:~/sp19/sa-rust-ids-work/sa-port-104/`, end marker `all-done.txt`; script `~/sp19/p1-job-sa-port-104.sh`, a copy at
  `~/sa-rust-ids-work/sa-port-104/p1-job.sh`). BASE = sa-port-99/suite. PLANTS = core-pi-coeff core-mul-drop-ipi
  core-half-parity core-rules-drop-last. SUITE_PLANTS = zero.
  - build, tests (375 passed), suite, live done at 23:03; plants, suiteplants and sum were still running at 23:10.
  - **Suite:** 5,958 passed / 126 failed / 23 / 18; base 5,959 / 125. One changed id: `tests/test_template_tables.py::
    test_comparison_detects_a_wrong_row` (:181) monkeypatches a row of Python's `core.IPI_TABLE`; on Rust `ipi_rules` reads
    Rust's IPI_TABLE (moved as data), so the patch isn't seen. Needs-internals, not an answer difference. Report it as
    explained. Optionally have the test plugin name it, as with other needs-internals tests; no engine change.
  - Plant cmps seen: dev half-parity and rules-drop-last DIFFER; dev mul-drop-ipi and pi-coeff MATCH (expected: they don't fire
    on dev); fuzz half-parity DIFFER, fuzz pi-coeff MATCH. Read `fired` from the plant session.json; a 0-fire plant is void
    there and the core wl orion result stands in for it.
  - **mutate_knowledge (core plants, full dev/fuzz/value/core):** base row `no` in every column, so **full dev, fuzz, value
    and core wl plain vs atoms MATCH**. 17 of 30 caught by `off` (comparison); 4 more only by `unit` (half-rules-max,
    recip-rules-noswap, imag-number-rules, imag-rules-strict). 9 caught by nothing: bound-zero-kept, recip-any-exp,
    imag-two-rest, pi-split-second-i, mul-sets-ipi-any, mul-sets-ct-two, unit-angle-neg, exp-arg-any, pow-bound-any-exp.
    `results.jsonl` under `mut/`.
- Orion shapes run (still running at 23:10): each of those 9 mutants built and run against test_knowledge_core_shapes.py +
  test_knowledge_core.py: `~/sa-rust-ids-work/sa-port-104/shapes/results.jsonl` (one line per plant; `fails` lists the
  failing tests; `loaded_here` must be true). Expected void: `core-mul-sets-ct-two`. A 2-arg Mul's rest is one factor, and
  `kept_product` of one factor is None on both sides, so the mutant can't be observed (an equivalent mutant). Report it that way.

## Left
1. Read the shapes results. Any plant not caught there: it's void (an equivalent mutant) or needs a better crafted query.
2. When `all-done.txt` exists: read `sum.txt` (quiet handler firings: expect base's 39 rows in 2 tests, plus quiet catches at
   engine.py:1906), the plant `fired` counts, suite-plant runs, and the live dev/fuzz cmps (default backend MATCH).
   Counts of the two callbacks on dev/fuzz: `live/{dev,fuzz}-rust.knowledge.json`; suite: the suite's knowledge counts
   (as port-wire.md did). The core wl had unit_power:python 75 and imag_number:python 0; dev-400 had 0 and 0.
3. Rebase rule: the shapes test and handoff are test/doc only. `git log origin/rust-slice` for new commits; then
   `sh rust-spike/slice/p1/bar.sh land ac0f88d` and PUSH=1. Write results/port-6e.md (<4 KB), `agent report`, SendMessage.
4. Report contents: see the brief (NEXT-port-6e.txt), and the ownership counts below.

## Ownership and module count (for the report)
- Table before (port-ownership.tsv, 4dd9984): core 30 rows: 27 `port` owned by 6e (today Python); 3 classed offline/not port:
  `_ipi_table_rows:448`, `_table:575`, `__getattr__:584`. Trace (sa-port-97, core_trace.py; dev, fuzz, suite counts in
  HANDOFF-sa-port-97.md:17-40): import time is `<module>` alone (constants: data, not ported). `_table`/`_ipi_table_rows`
  run once per process at the first `ipi_rules`, not at import; they move as Rust data (IPI_TABLE, IPI_GUARDS). `__getattr__`
  isn't a port item (it's attribute probes).
- After: 21 swapped onto Rust (`knowledge_core_live.py` `swap`), 2 absorbed into Rust's splits (`_coeff_term`,
  `_imag_term`), 4 Python shells over Rust (`ipi_split`, `pi_split` call the swapped `_pi_split`; `_half_templates`,
  `_bound_templates` call Rust rules and 6d's `facts`). Named SymPy-semantics callbacks (planner, 7 Nov, the same class as
  `enclose`): `_unit_power_units`' non-Rational branch and `_imag_templates`' all-number branch. Later question for each: can
  Rust's constfield do it exactly? Revisit after 5c. Also counted: derived Adds with no row (`core:derived:*`), and
  `kept_product` scaffolding (`core:kept_product`). `_common` helpers ported for core: none (facts, const_key, consts_of stay
  for 6d). Module count: proposed 8 of 32 (core with its named callbacks); 7 of 32 if the planner counts it as partial.

## Update 23:17 UTC (after handoff)
The pareto1 job finished: every phase exited 0, `all-done.txt` exists, and lease 672038d6 was released. sum.txt is ready to read.
The orion shapes run has written 9 of its 10 lines (base-none isn't an entry in M, so 9 is all of them). Read both.
