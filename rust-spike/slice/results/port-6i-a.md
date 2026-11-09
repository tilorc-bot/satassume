# 6i, part (a): the outer templates of special, rootof, nodes, physics and stats on Rust (issue 323)

Work by sa-port-201 (6c52df3, b11b5a2) and sa-port-204 (bar, probe, plants, this report).

## What moved
- **outer_tpl.rs** (new, `solver_rs/src/term/`) answers the six outer templates that dispatch.rs:242 used to run as Python
  (`registry:python`): `multigamma_templates` (special.py :87), `crootof_units` (rootof.py :44), `accumbounds_templates`
  and `idx_units` (nodes.py :29/:36), `quantity_units` (physics.py :21), `randomsymbol_units` (stats.py :21).
  dispatch.rs gets `Tpl::Outer`, recognised by `__module__` and qualname for the built-in templates, after the rows check.
  A query that is kept still runs the Python template (`registry:kept:NAME`).
- **Conversion reads, per the 6f reclassification ruling:** crootof's coefficients (`expr.poly`, its domain,
  `rep.to_list()`, None for a non-ZZ domain) and randomsymbol's declared facts (`is_positive`/`is_integer`, `is_real`,
  `pspace.is_real`) are read at the boundary (`outer:conversion:{crootof,random}`). The template work after the reads, meaning
  the unit facts, crootof's `root_facts` through realroots.rs and randomsymbol's units, is Rust (`outer:rust:*`). This
  follows the way `symbol_units` was ported.
- **multigamma:** rules for p are built in Rust. The derived slots `2*x` and `2*x - p + 1` go through `term_live.scaffold`
  (temporary construction, `scaffold:rebuilt:f6`, checked against Rust's form, refused on a mismatch). Its value at a
  constant x is `expr.func(x, p)`, called from Rust; ValueError, TypeError and ArithmeticError give None, as
  `special._multigamma_value` does, and any other exception is loud (`Common.fault` → KnowledgeFault
  `outer:multigamma_value:sympy: ...`). That call is the one SymPy callback left (`outer:multigamma_value:sympy`), and **it
  is unruled; see the count section**. Its `value_units` goes through `special.value_units`, the name knowledge_live rebinds
  to `rust_value_units`, so the `value:*` counters and the `knowledge-value-multigamma-drop` plant still apply.
- **kf6:230:** the eager `_multigamma_rules` call is now lazy (knowledge_f6_live.py, a lambda), per the 6i ruling.
- **Counters** (Common's counts, `outer:` prefix): `outer:rust:{multigamma,crootof,accum,idx,quantity,random}`,
  `outer:conversion:{crootof,random}`, `outer:python:multigamma_templates:{no-query,derived-x}`,
  `outer:multigamma_value:sympy`, `outer:value_units`, `realroots:root_facts`.
- **Plants** 280-286 (outer_tpl.rs PLANTS, added to knowledge_common_live.PLANTS, accepted by common.rs `set_plant`), plus
  the unnumbered control `dispatch-outer-off`. 287-319 are unused.
- **Shared-file changes, kept minimal:** common.rs `units`, `const_key` and `fault` are made pub(crate);
  knowledge_common_live.PLANTS gains one line.
- **Test edit:** test_knowledge_f6_fallback.py's multigamma case now plants its raise in `multigamma.eval`, because the
  callback moved, and reads counts through a `count()` helper (K.COUNTS plus Common counts not yet flushed).
- **Ownership:** port-ownership.tsv's 6 rows → "landed 6i(a)", finisher 6i(a); port-ownership.md has an "Updated by
  sa-port-201" paragraph.

## SHAs
- Base: rust-slice c3d0999. Tested: **b11b5a2** (6c52df3 + b11b5a2). Landed: **b11b5a2** plus this report's commit
  (results/ only, outside bar.sh's push guard).
- Incoming diff: **empty.** origin/rust-slice was still c3d0999 at 13:34Z, after the bar.
- Stacked: sa-port-205's state part 2 (ii) bar ran on port/state-relations-stack 997a54f, which is b11b5a2 plus its own
  commits. So b11b5a2 lands exactly as tested, with no rebase edits.

## The bar (pareto1, `~/sp19/sa-rust-ids-work/sa-port-204/bar-6i-a` on b11b5a2)
Run 12:00Z-13:32Z under shared lease c8880888, released after 1h31m (exit 0). Every phase exited 0; seed1 was not run.
`.so` sha256 0468b702…. Base suite rows: `sa-port-200/bar-state-relations-i/suite`. The summary is copied to
`~/sa-rust-ids-work/sa-port-204/bar/sum.txt`, and the fallback counts to `~/sa-rust-ids-work/sa-port-204/fb-cand.txt`
(base: `fb-c6c9.txt`, the 6g c6-c9 bar on cec872d, the last bar that ran the six hidden-gap workloads).
WLS: f6 value rootof opaque core scope loop zero wiring cert budget. Tests phase: sa-port-200's list plus
test_knowledge_f6_fallback.py, test_knowledge_realroots.py, test_knowledge_value_units.py and test_knowledge_lazy.py:
**723 passed, 4 skipped**, exit 0. DIRECT `relations_direct.py 300 0`: exit 0.
1. **Suite by id:** 5,991 passed, 127 failed, 23 skipped (plus 18 xfailed), over 6,159 ids. **Against base: new 0, gone 0,
   changed outcome 0.** Passed splits into 5,990 with no handler firing and 1 with a firing:
   `tests/test_invariants.py::test_ci_stream_reports_only_what_replays`, the named case.
2. **Fresh dev and fuzz: answers and state MATCH** (Rust against Python, traced and untraced; Python against Python as the
   control). dev answers_sha 31cd0945c07f02a6, fuzz 173502b6ef285ad6. All 11 extra workloads MATCH, Rust against Python.
3. **Plants caught:** all seven are caught by the live comparison on the workload that reaches them, and five of them also by
   the suite. Table below.
4. **Quiet handler firings on Rust: the handler multiset is the same as base.** 39 rows in 2 tests:
   - 34 × `_consistent` AttributeError `'Solver' object has no attribute '_ok'`, in test_ci_stream_reports_only_what_replays;
   - 4 × `_consistent` AttributeError `_rb_clauses`, in the same test;
   - 1 × `Engine._build_context` RuntimeError "Already mutably borrowed", in test_protocol_on_fuzz (the named 46-stub cause).

   **engine.py:1906's catches (`ctx:caught`): 0 on all 13 workloads** (dev, fuzz and the 11 WLS). This step didn't re-show
   the counter firing on a planted raise; earlier steps did. TermFault in pytest.log: 0. The live and extra handler files have
   0 rows.
5. **Known differences in answers or read state: none.**

Before the bar, on orion with b11b5a2's build: the 7 knowledge test files (f6_fallback, realroots, value_units, wire, common,
rows, lazy) gave **119 passed**. `cargo check` shows no warnings in outer_tpl.rs or dispatch.rs; 13 others are elsewhere and
were already there.

## Plants
Fired counts are from the bar (`fired` reads the session report). In the suite-plant rows, sum.txt's "plant fired in the
suite: 0" is **void for these plants**, because the outer plants count in Common's counts and not in `rel:plant_fired`. The
suite catch is read from changed outcomes instead.

| plant | fired on its workload (bar) | caught by | suite (SUITE_PLANTS `zero`, against the plain suite) |
|---|---|---|---|
| `outer-multigamma-p` (280) | value 15 | value DIFFER | 0 changed: **void in the suite** |
| `outer-multigamma-value` (281) | value 10 | value DIFFER | 0 changed: **void in the suite** |
| `outer-rootof-index` (282) | rootof 368 | rootof DIFFER | 3 changed |
| `outer-accum-real` (283) | f6 6 | f6 DIFFER | 1 changed (`test_notmpl_nodes.py::test_reproducers[expr0-real-True]`) |
| `outer-idx-integer` (284) | f6 2, opaque 1 | f6 and opaque DIFFER | 8 changed (test_notmpl_nodes.py) |
| `outer-quantity-positive` (285) | f6 3 | f6 DIFFER | 8 changed (test_notmpl_physics.py) |
| `outer-random-real` (286) | f6 3 | f6 DIFFER | 2 changed |

Every outer plant fires 0 on dev, fuzz, core, scope, loop, zero, wiring, cert and budget, and those all MATCH, as expected,
since none of them reaches these templates. No plant is void on every workload.
Run on orion with b11b5a2's build, not in the bar:
- `knowledge-value-multigamma-drop`: value, fired 10, DIFFER.
- `dispatch-outer-off` (the control, the port off): f6, value and rootof MATCH.

## Per-query calls into the five modules, before (c3d0999) and after (b11b5a2)
Module-wide probe (sa-port-199's count7.py, every function in each file traced, pass 1, `kind query`), 15 runs each: dev,
fuzz, the 11 WLS, dev-seed1 and fuzz-seed1. Base is `~/sa-rust-ids-work/sa-port-201/probe-base`, at c3d0999 rather than
a8a4bae. c3d0999 is a8a4bae plus state part 2 (i), which doesn't touch these templates. Candidate is
`~/sa-rust-ids-work/sa-port-204/probe/probe-cand`, rerun whole on the final build. sa-port-201's earlier cand run was void,
because the .so was rebuilt under it. Workloads not listed are 0 before and after.

| module | before | after |
|---|---|---|
| special.py | value 111 (`multigamma_templates` 21, its genexpr 60, `_multigamma_rules` 15, `_multigamma_value` 15) | **0** |
| rootof.py | rootof 4,130 (`crootof_units` 368, its lambda 368, `_coefficients` 368, its genexpr 3,026) | **0** |
| nodes.py | f6 8 (`accumbounds_templates` 6, `idx_units` 2), opaque 1 (`idx_units`) | **0** |
| physics.py | f6 3 (`quantity_units`) | **0** |
| stats.py | f6 6 (`randomsymbol_units` 4, its lambda 2) | **0** |

Remaining calls, before and after alike: special.py on value's 6 `kept:refused` queries (`multigamma_templates` 6, its
genexpr 24, `_multigamma_rules` 6 and its `build` 6, `_doubled` 6, `_multigamma_value` 6). These are the named kept reason
(refused: `algebra: Float`), not per-query Python on a converted query. sa-port-199's numbers at 2742b66 (count-6g.md) hold
at c3d0999.

## Module count (STATUS "Counted modules", 14 of 32)
**18 of 32**, with special.py waiting on one ruling (19 if the planner rules its callback). Each module joined on the
module-wide probe above, not a targeted counter.
- **rootof.py** joins. Footnote: `_coefficients`' reads are conversion (6f ruling).
- **nodes.py** and **physics.py** join.
- **stats.py** joins. Footnote: `randomsymbol_units`' fact reads are conversion (6f ruling); its units are on Rust.
- **special.py:** none of its Python runs per query on a converted query. What's left is multigamma's value at a constant x,
  `expr.func(x, p)` called from Rust (`outer:multigamma_value:sympy`; it was `f6:multigamma_value:python` at 2742b66, value
  15 there too). It is SymPy evaluation of an input constant's function value, so it looks like the SymPy-arithmetic group
  of named callbacks (`enclose`, `const_value`). **Fire counts: value 15; 0 on dev, fuzz and the other 10 workloads.**
  **Question for the planner:** is it a named callback? If yes, special.py counts and the total is 19 of 32. Until then
  special.py isn't counted.
- **Scaffolding, counted per the port rulings:** `scaffold:rebuilt:f6` value 221, f6 45, opaque 15, dev 3. These equal the
  c6-c9 bar's, because multigamma's two derived slots went through the same scaffold under kf6. `scaffold:mismatch` f6 2,
  also equal to base. These are the refusals, `refused:scaffold: rebuilt form differs from Rust` 2.
- **Footnotes on what's already counted:**
  - realroots.py: its Rust side is now reached from crootof on Rust: rootof `realroots:root_facts` 368. The plant there is
    `outer-rootof-index`, which reads the next root from realroots.rs. It fired 368 and was caught on rootof, and also in 3
    suite tests. It changes the index fed into realroots.rs's `root_facts`; it is not inside realroots.rs. **For the planner
    to confirm** whether that meets "a plant in realroots' Rust side caught there". If it does, the realroots footnote goes.
  - `value_units` (atoms): reached through multigamma on value (`value:derived` 234, `value:input` 12). Its own plant,
    `knowledge-value-multigamma-drop`, fired 10 and was caught on value (the orion run above). Under the 6f ruling the
    `value_units` footnote goes.

## Which moved items are reached, and by what
- crootof: rootof (368). accumbounds: f6 (6). idx: f6 (2) and opaque (1). quantity: f6 (3). randomsymbol: f6 (4).
  multigamma: value (21 on Rust; `outer:value_units` 10, `outer:multigamma_value:sympy` 15).
- dev and fuzz reach none of them. The suite reaches crootof, accumbounds, idx, quantity and randomsymbol, shown by their
  plants. It doesn't reach multigamma's rules or value: both multigamma plants changed 0 suite outcomes. The value workload
  reaches them.

## Kept reasons (planner ruling, 03:42 UTC 8 Nov)
Every share equals base.
- Base for dev, fuzz, budget, cert, loop, scope and zero: sa-port-200's bar.
  - Out-of-scope: dev 24/1,985 (1.21%); every other workload 0.
  - Refused: 0.
- Base for f6, value, rootof, opaque, core and wiring: the c6-c9 bar.
  - f6: refused 13/2,902 (0.45%): `algebra: Float` 10, `lra: a callback on a derived term` 1,
    `scaffold: rebuilt form differs from Rust` 2.
  - value: refused 15/3,742 (0.40%), all `algebra: Float`.
  - opaque: refused 7/2,546 (0.27%): `algebra: infinity or nan` 5, `algebra: holds an infinity, nan or Float` 2.
  - wiring: refused 1/6,512 (0.02%), `lra: a callback on a derived term`.
  - rootof and core: 0.
  - Out-of-scope: 0 on all six.

## Fallbacks to Python inside ported code (planner's fallback-reporting ruling)
`registry:python` is dispatch.rs:242's fallback and `rows:python` is rows_tpl.rs's; both are per template, from the bar's
knowledge files (`fbcounts.py`, extended with the `outer:`, `scaffold:`, `value:` and `realroots:` prefixes). **The six
outer templates are gone from `registry:python` on every workload.** Nothing else moved: every `rows:python` count equals
the c6-c9 bar's, and `registry:python` differs only by the outer names.

| workload | `registry:python` before (c6-c9 bar) → after | outer names removed |
|---|---|---|
| f6 | 226 → 211 | `accumbounds_templates` 6, `idx_units` 2, `quantity_units` 3, `randomsymbol_units` 4 |
| value | 534 → 507 | `multigamma_templates` 27 (21 now Rust; the 6 on kept queries are `registry:kept`) |
| rootof | 395 → 27 | `crootof_units` 368 |
| opaque | 102 → 101 | `idx_units` 1 |
| core, wiring | 35, 75, unchanged | none |

After, by template:
- f6 211: `_load` 54, `_unary.<locals>.template` 97, `nary.<locals>.template` 49, `symbol_units` 7, `constant_units` 4.
- value 507: `_unary.<locals>.template` 327, `constant_units` 150, `_load` 29, `symbol_units` 1.
- rootof 27: `_load` 26, `symbol_units` 1.
- opaque 101: `_unary.<locals>.template` 59, `_load` 39, `symbol_units` 3.
- dev 126, fuzz 38, zero 43, loop 31, cert 24, scope 26, budget 469: all equal to sa-port-200's bar, by template.

**What still falls back, and why.** `_unary`/`nary` templates are 6i(b)'s. `symbol_units`/`constant_units` are atoms'
input-fact templates. `_load` is :200's registry load.
- `rows:python`: `Integer` and `const_value` (the named SymPy callback) on every workload, plus the kcl shells
  (`_bound_split`, `_half_split`, `_imag_split`, `_mul_factor_sets`, `_quotient_templates`, `Add`, `Mul`,
  `_pow_bound_templates`, `_unit_power_units`, `ipi_split`, `constant_value`) as before.
- `registry:kept`: dev 4 (`add_rows_templates` 2, `mul_rows_templates` 2), f6 2 and opaque 2 (`add_rows_templates`),
  value 6 (`multigamma_templates`).
- `ad:cbm_noid`: 0 on every workload; this step doesn't touch it.

So dispatch.rs:242 and rows_tpl.rs:413 don't yet report 0 outside named callbacks. The templates that still fall back are
named above with their owners; 6i(a)'s templates no longer do.

## State: each container this step touches
None. The outer templates are stateless: outer_tpl.rs holds no static, cache or memo. Each answer is a pattern built per
call from the term's own reads, and goes into dispatch's existing per-query clause list like any other template's. The bar's
live state comparison MATCHes on all 13 workloads.

## Not run
Moved to "before any backend PR", none quoted as met: the mutant 2, 5, 6, 7, 9 rerun and mutlive's control; the boundary
rescore and suite column; the final drop score and its lost rows; the suite split with Python's counter; `order:_rows`'
evidence (not caught meanwhile); the `_forms` guard test; history and seed reruns (the bar's seed1 phase not run; the probe
ran dev-seed1 and fuzz-seed1); forced moves; the native path; timing.
Also not run: a re-shown `ctx:caught` firing on a planted raise in this step; `knowledge-value-multigamma-drop` and
`dispatch-outer-off` inside the bar (run on orion only).

Other notes:
- S's standing: S's gate is met except for the 46 named stub failures, one cause.
- The `_n_conflicts` view in rust_plugin.py is a test-plugin shim, not a port (64 tests).
- `tests/test_relations.py::test_equality_sharing_is_needed_and_works` is unedited and still named needs-internals.
- `tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence`: the known id()-reuse
  failure (a28c548), unedited.
- Mutants 2, 5, 6, 7, 9 still rest on the API fuzzer alone. 10 of the 25 boundary mutants have no real-engine catch, and the
  boundary suite column wasn't run.
- `test_performance_smoke_300_vars`: same outcome as base in the bar's suite (changed outcome 0 overall); not chased.
- **Speed not measured.**
