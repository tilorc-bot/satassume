# Wiring step: component 6's ported parts on the default Rust backend (issue 323)

## What moved
`knowledge_live.from_env()` installs realroots, `_rows_runtime`, atoms' units and `_common`'s resolve and Pattern wherever the Rust backend installs term_live (`rust_plugin.py`, `live.py` in rust mode). `SLICE_KNOWLEDGE=py` or `SLICE_TERM=py` keeps them off. A second install raises. The owed `rows_kept` KnowledgeFault guard and its plant are here, so 6e doesn't repeat them.

## SHAs
Tested 56f3be3 on pareto1 (`.so` sha256 d4694666…), with all phases except seed1. 4dd9984 (the ownership ruling carried into PORT-INVENTORY.md, ownership TSV recounted, 812 to 742 port items) and the handoff/report commits are doc only. Rows: pareto1 `~/sp19/sa-rust-ids-work/sa-port-99/` (`sum.txt`), by `bar.sh`. Base: 5c1's rows (sa-port-96).

## The bar
1. **Suite by id against 5c1's rows:** 5,959 passed, 125 failed, 23 skipped, 18 xfailed, 6,125 ids. New 0, gone 0, changed outcome 0. Passed: 5,958 with no firing and 1 with a firing (`test_ci_stream_reports_only_what_replays`). S's gate is met except for the 46 named stub failures, which have one cause. Tests phase: 364 passed (the 6 `test_knowledge_*` files, `test_session_limits.py`, `test_discovery_core.py`).
2. **Fresh dev and fuzz:** answers and state MATCH in four comparisons each, and the control MATCHes. The answer shas are unchanged (dev 31cd0945c07f02a6, fuzz 173502b6ef285ad6). Rust made 0 Python solvers.
3. **Plants:** `knowledge-pattern-drop` fired 81 times on dev and 61 on fuzz. Both DIFFER (dev: 10 answers, 59 stream states; fuzz: 270 stream states, 463 lra). `knowledge-rows-kept-raise` fired once on each and is loud: KnowledgeFault "rows_kept: NameError: planted" aborts the run. realroots' and atoms' own plants are in 6/6b/6c's reports, under opt-in install, and weren't rerun on the default path.
4. **Quiet handlers in the suite:** 39 rows in 2 tests, the same multiset as base. `_consistent` AttributeError: 34 `_ok` + 4 `_rb_clauses` in `test_ci_stream_reports_only_what_replays` (the named needs-internals case). `_build_context` "Already mutably borrowed": 1 in `test_protocol_on_fuzz` (the 46-stub cause). Caught rows per id: 0 ids differ from base. **Quiet catches at engine.py:1906: 1** (`complete_check`, in the suite, as on base). Dev and fuzz handler files have 0 rows (12 files, plus 4 plant files). TermFault 0, KnowledgeFault 0 outside the plant.
5. **Known differences:** none.

## Module count
Before: 5 of 32 (solver, euf, lra, transfer, lra_cert), plus 2 ported but not wired (realroots.py, atoms.py). **After: 7 of 32.** Per module, from the live and suite knowledge counts:
- **realroots.py** runs on the default backend in the suite: root_facts 133, real_root_counts 5, imaginary_root_count 4, squarefree 1. It is reached 0 times on dev and fuzz, so only the suite by id speaks for it.
- **atoms.py** runs on the default backend: symbol:input 2,395 in the suite, 13 on dev, 2 on fuzz; constant:input 209 / 12 / 6. `value:*` is 0 everywhere: value_units is wired but unexercised by the suite, dev and fuzz, and only `test_knowledge_value_units.py` covers it.
- **`_rows_runtime.py`** (partial) runs on the default backend: rows:constant_value 4,796 in the suite, 27 on dev, 6 on fuzz; rows:gen 1,378 / 19 / 0; rows:kept 50 in the suite.
- **`_common.py`** (partial: resolve and Pattern) runs on the default backend: pattern 23,712 / 83 / 61, resolve 41,253 / 81 / 60. The rest stays for 6d.

Scaffolding: `scaffold:rebuilt` is 65 on dev and 332 on fuzz, all at term_live sites (`_eq_links`, `glue_objects`, `relation_atom`). None is at a knowledge site, and this step didn't change those sites. Base wrote no knowledge.json, so there is no base count beside it.

## Shared files touched
`rust_plugin.py:101-102` and `live.py:346-347` add one `from_env()` call each. `knowledge_suite.py` no longer installs a second time.

## Backend PR list
Rust raises NotImplementedError on the public Solver methods `BlockOwner`, `provenance` and `root_step`. That is a contract difference; it goes next to the hook re-entry note. It is already appended (OWED line 52). After 4dd9984, 2 port items have no owner: `_basis_models` and `_applied_to_nan`.

## Not run
seed1. Also everything moved to "before any backend PR", none of it quoted as met: the mutant 2, 5, 6, 7, 9 rerun and mutlive's control, the boundary rescore and suite column, the final drop score, the suite split with Python's counter, `order:_rows`' evidence (not caught meanwhile), the `_forms` guard test, history and seed reruns, forced moves, the native path, timing. **Speed not measured.** The `_n_conflicts` view in `rust_plugin.py` is a test-plugin shim (64 tests), not a port. No evaluator asked for.
