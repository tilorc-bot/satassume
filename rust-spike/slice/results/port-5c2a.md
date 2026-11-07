# Step 5c2a: the compile loop's first part in Rust (issue 323)

5c2a doesn't land on its own. It lands inside 5c2 (results/port-5c2.md), whose bar was rerun on the source rebased onto 6e. This file keeps 5c2a's own bar, which was run before 6e landed.

## What moved
`want_of`, `_split` (engine.py:2311-2350), `Session._emit_pattern`, `_flush`, `_compile`, `_compile_pending`, `_compile_patterns` (engine.py:614-771, minus `_custom` at :707-733) run in `solver_rs/src/compile_loop.rs` over the session's own Python containers. They're wrapped by `session_live.py` `_LOOP_METHODS`. `_custom`, `_visit` and `core.visit` are called back by name, and they're 5c2b. Counters `ses:want_of` .. `ses:compile_patterns` (session.rs NAMES). No module newly counts whole.

## SHAs
Tested afcc6eb: 5c2a on rust-slice d2d3234 (the wiring step), rerun because the wiring changed code the runs execute. Rows are on pareto1 at `~/sp19/sa-rust-ids-work/sa-port-103a/` (`sum.txt`, `commands.txt`), `.so` sha256 734f0a2d…, base sa-port-99's suite rows. The first bar was sa-port-100's, tested 3246bb4 on base sa-port-96, and it gave the same numbers. Not landed separately.

## The bar (sa-port-103a)
1. **Suite by id against sa-port-99's rows:** 5,959 passed, 125 failed, 23 skipped, 18 xfailed, 6,125 ids. New 0, gone 0, changed 0. Passed: 5,958 with no firing, 1 with a firing (`test_ci_stream_reports_only_what_replays`).
2. **Fresh dev and fuzz:** answers and state MATCH, four comparisons each, control MATCH. dev 31cd0945c07f02a6, fuzz 173502b6ef285ad6. Rust runs made 0 Python solvers.
3. **Plants** (fired on dev / fuzz):

| plant | method | dev | fuzz | caught by |
|---|---|--:|--:|---|
| want-empty | want_of | 5,348 DIFFER | 51,089 DIFFER | dev, fuzz, direct |
| drop-split-later | _split | 291 DIFFER | 455 DIFFER | dev, fuzz, direct |
| drop-emit-ment | _emit_pattern | 3,346 DIFFER | 33,238 DIFFER | dev, fuzz, direct |
| drop-flush-custom | _flush | 506 DIFFER | 10,086 DIFFER | dev, fuzz, direct |
| drop-pat-demand | _compile_patterns | 2,119 DIFFER | 18,498 DIFFER | dev, fuzz, direct |
| drop-pend-compile | _compile_pending | 0 | 0 | suite (fired 474, 57 changed outcomes), loop, direct |
| drop-compile-demand | _compile | 0 | 0 | loop (fired 3,286, DIFFER), direct; suite fired 26,753, 0 changed |

**Void on dev and fuzz (fired 0, so their MATCH means nothing):** drop-compile-demand and drop-pend-compile. Dev and fuzz register no vocabulary function, so `_compile` is never reached on them (`ses:compile` 0). `loop_wl.py` (`live.py loop`, 420 queries) registers four of them, and on it `ses:compile` is 1,159 and the plant DIFFERs. That is the gaps ruling's workload, and the run is described in port-5c2.md.
4. **Quiet handlers, suite:** 39 rows in 2 tests, the same multiset as base: `_consistent` AttributeError 34 `_ok` + 4 `_rb_clauses` (named needs-internals case), and `Engine._build_context` "Already mutably borrowed" 1 in `test_protocol_on_fuzz` (the 46-stub cause). **Quiet catches at engine.py:1906: 1**, in the suite, as on base. 0 on dev and fuzz: the handler files have 0 rows (12) and so do the plant files (14). TermFault 0.
5. **Known differences:** none. Tests: 434 passed; `relations_direct.py` exit 0.

## Not run
seed1. Everything else the "before any backend PR" list in port-5c2.md names.
