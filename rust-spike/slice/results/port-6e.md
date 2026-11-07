# Step 6e: knowledge/templates/core.py on Rust (issue 323)

Tested source ac0f88d (rows pareto1 `~/sp19/sa-rust-ids-work/sa-port-104/`, .so dd0f2ce8). Landing source 714630d..HEAD on
rust-slice d2d3234. Incoming diff: port-ownership.md/.tsv only (docs), so no rerun by the rebase rule: rebuilt on orion, 384
step tests pass, dev-400 and core wl plain vs atoms MATCH (`~/sa-rust-ids-work/sa-port-107/short/`). Runs on the default
Rust backend through `knowledge_live.from_env()`.

**Import time (core_trace.py, HANDOFF-sa-port-97.md:17-40):** only `<module>` (constants, data). `_table`/`_ipi_table_rows`
run once per process at the first `ipi_rules` (dev 0, fuzz 0, suite 50/3), so they move as Rust data. `__getattr__` is
attribute probes (dev and fuzz 2 per process, suite 362), not a port item. All three are out of the count.

**Ownership, core (port-ownership.tsv):** before: 30 rows, 27 `port` (Python), 3 not port. After: 27 Rust: 21 swapped,
2 absorbed into Rust's splits (`_coeff_term`, `_imag_term`), 4 Python shells over Rust (`ipi_split`, `pi_split`,
`_half_templates`, `_bound_templates`); 2 of the 21 carry named callbacks. Table total: Rust 393 to 420, Python 391 to 364.
`_common` helpers ported for core: none (facts, const_key, consts_of stay for 6d). **Module count: 8 of 32** if core counts
with its named callbacks, 7 if the planner counts it partial (realroots and `value_units` footnote unchanged).

**Bar**
1. Suite by id: 5,958 / 126 / 23 / 18 against the wiring's 5,959 / 125 (6,125 ids, 0 new, 0 gone). Passed with no firing
   5,957, with a firing 1 (test_ci_stream_reports_only_what_replays). One changed id, explained:
   `test_template_tables.py::test_comparison_detects_a_wrong_row` patches Python's `core.IPI_TABLE`; Rust's `ipi_rules`
   reads its own table, so the patch isn't seen. Needs-internals, not an answer difference.
2. Dev (1,985 queries) and fuzz (3,000): answers and end state MATCH, py vs rust and traced vs untraced; Python control MATCH.
3. Plants. Python-side: half-parity (dev 38, fuzz 87 fired) and rules-drop-last (dev 18, fuzz 32) DIFFER on both; pi-coeff
   and mul-drop-ipi fire 0 on dev/fuzz (void there), caught on the core wl and on the suite (3 and 2 changed ids). Rust
   mutants, 30: 17 caught by the dev/fuzz/value/core comparison; 8 by crafted-query comparison
   (test_knowledge_core_shapes.py, shadow vs Python); 3 only by unit tests (half-rules-max, recip-rules-noswap,
   imag-number-rules); 2 void as equivalent mutants (mul-sets-ct-two, mul-sets-ipi-any: the Python shell's own `is_Mul`
   test drops a one-factor rest, as Python does).
4. Quiet handlers (suite): 39 rows in 2 tests, multiset same as base (`_consistent` 34 `_ok` + 4 `_rb_clauses`; engine.py:1906,
   `_build_context`, 1 "Already mutably borrowed", the 46-stub cause). Dev and fuzz handler files: 0 rows. TermFault 0.
5. Differences: the one id above. None in answers or state.

**Python fallbacks (dev / fuzz / suite):** named SymPy-semantics callbacks, loud (an exception is a KnowledgeFault):
`core:unit_power:python` 0 / 0 / 41, `core:imag_number:python` 0 / 0 / 2. Counted: `core:kept` 12 / 0 / 1,174,
`core:no-query` 0 / 0 / 49,237 (tests calling Engine directly), derived Adds with no row `core:derived` 9 / 72 / 162,
`kept_product` scaffolding 33 / 0 / 152 (26 unchecked in the suite, where Rust's algebra refuses the product).
`_imag_templates`' Rust path: 0 on dev, fuzz, suite and the core wl; reached only by the shape test.

**Not run:** seed1, history, forced moves, the native path, timing; the mutant 2/5/6/7/9 rerun, the boundary rescore,
order:_rows evidence (not caught meanwhile), the `_forms` guard test. The Python-side suite rerun wasn't needed to land.
The `_n_conflicts` view in rust_plugin.py is a test-plugin shim (64 tests), not a port. No evaluator asked for.
