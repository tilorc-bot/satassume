# State part 3: the session/solver boundary (issue 323)

Branch port/state-part3 from rust-slice c822173. Unbarred, unlanded: landing waits for (iii) (sa-port-225), then a rebase and
a full bar on the merged tree (planner's state part 3 go, condition 3). Plants 420-449, counters 550-579.

## Sub-part 1: Session's state inventory (sa-port-229)
Readers measured by session_readers.py over every Session attribute (engine.py:304-376 that isn't already a property), seven
workloads, Rust, --check plain, at 042598c (pareto1 ~/sp19/sa-rust-ids-work/sa-port-229/inv, inv_summary.txt). Every runtime
reader on a converted query is session_live wiring frame around Rust (Rust reading the Python attribute through the C API under
that frame): **no engine.py, relations.py or ref.py frame reads any of them**. Tests by static grep (files); public API: none
(`Session` isn't exported; `satassume.__all__` has `Engine`). Kept queries: under 0.1% of reads on every row.

Overlap with (iii): **struct** = moving it into SessionCore changes SessionCore's struct/constructor (go ruling condition 1:
waits for (iii) incl. 225 and the rebase); **RelKeys** = term- or atom-keyed, so it takes the query table's ids / RelKeys
interning (RelKeys ruling (1)); **Relations** = (iii)'s own object; **none**.

| attribute | state on Rust | runtime reads (writes), top frames | tests | decision | overlap (iii) |
|---|---|---|---|---|---|
| `table`, `base` | properties onto SessionCore (earlier state steps) | — | 5 / 3 files | done | none |
| `xfer` | property onto SessionCore ((ii) 9e10f0d) | — | 4 files | done | Relations |
| `solver` | Python attr + core copy (`set_solver`) | 756,677 (5,377): `_rel_interpret` 323k, `_rel_link` 148k, `_rel_share_guard` 47k, `_ses_visit` 45k, `_compile_formula` 41k | 14 files | sub-part 5: wrappers removed, Rust readers on `solver_direct`; attribute stays as a read-only view for tests | Relations (relations_core.rs sites) |
| `frontier` | Python deque | 254,832 (159,372): `_ses_ensure`, `_ses_discover`, `_ses_escalate` | test_discovery_core | Rust-native in SessionCore, sub-part 5; record/view for the test | struct, RelKeys (node-keyed) |
| `pending`, `pending_c` | Python dicts node -> list | 291,416 / 322,270: `_ses_ensure`, `_ses_discover`, `_ses_escalate`, `_ses_incomplete` | compile_loop, discovery core tests | same | struct, RelKeys |
| `demand` | Python dict node -> set | 182,924: `_ses_ensure`, `_ses_visit` | same | same | struct, RelKeys |
| `deferred` | Python list | 20,936: `_ses_escalate`, `_ses_incomplete` | test_discovery_core | same | struct, RelKeys |
| `literals` | Python dict formula -> literal | 4,886: `_q.f` | test_query_core | same; keys are Formula objects: formula step's atoms | struct, RelKeys (atoms) |
| `verdict` | Python attr | 9,874 (10,314): `_context_session`, `verdict` | test_set_verdict | SessionCore scalar, sub-part 5 | struct |
| `truncated` | Python attr | 9,740 (5,377): `_ent.f` (entry.rs:511), `_context_session` (context.rs:295) | discovery core, test_budget_cone | SessionCore scalar, sub-part 5 (closes OWED [100] :2145/:2248) | struct |
| `sel`, `n_hold` | Python ints | 9,495 / 7,756: `_ses_assumption_lits`, `_ent.f` | test_switched_glue (sel) | SessionCore scalars, sub-part 5 | struct |
| `_groups`, `_link_pending` | Python dict / bool | 7,142 / 8,305: `_ses_assumption_lits`, `_g.f` | none | SessionCore, sub-part 5 | struct (+ RelKeys for `_groups`' keys) |
| `assumption_formula`, `_a_raw`, `_a_zs`, `_a_under`, `_a_all`, `_a_atoms` | Python attrs | 224 / 14,799 / 20,505 / 2,973 / 7,444 / 7,444 | none | the assumption's conversion: formula step (input-side atoms), not moved by part 3 | RelKeys (atoms) |
| `defvars`, `_dv`, `_dv_node`, `_neg_shared` | Python attrs, **written once per session (`_ses_init`), never read** on any workload; Rust's `St.defvars/dv/dv_node` hold the live state | 0 reads | none | drop the dead writes in session_glue.rs with sub-part 5 (Python's Session keeps them) | none |
| `relations` | Python attr (the Relations object) | 78,598: `_ses_custom`, `_ses_assumption_lits`, `_q.f` | 9 files | (iii)'s object; reference held by the core in sub-part 5 | Relations |
| `engine`, `scope` | back references | 123,934 / 3,968 | — | configuration, stays | none |

## Sub-part 2: install() refuses once an Engine exists (d44b817, sa-port-226)
- **Refuse, chosen over refresh because it is shorter**: one gc scan (`session_live.refuse_built_engines`, called first in
  `session_live.install()` and `backend.install()`). Refresh would have to rewrap every binding `Engine.__init__` takes
  (engine.py:1318-1341). (iii)'s rewrap of a pre-built default engine's `with_closed_units` is removed (dead under refuse).
- Install list: test_install_order.py diffs module attributes across live.py --check plain's install sequence: **191 entries**,
  each with a test `test_install_list_entry[<module>.<name>]` (the handoff's "194" was a miscount: 197 passed = 191 + 6).
- Engine-first planted-bug test: `test_engine_first_refused`, plant **420 inst-no-refuse** (caught). Also 421 inst-slot-skip,
  422 inst-cache-new-skip, 423 inst-importer-skip, all caught (`test_plants_are_caught[...]`).

## templates/_rows.py's stale generator/constant_value (planner's _rows ruling, ~06:47 10 Nov)
Before: `_rows.py:143` bound `_rows_runtime`'s `generator` and `constant_value` at import. install() fills `wiring`'s slot
(knowledge_live.py:501), so `_rows`' names stayed Python's after the install.

Probe `rows_probe.py` (counters 550 rows:generator, 551 rows:constant_value, 552 rows:rules, 553 rows:py_generator, 554
rows:py_constant: PY_START of Python's implementation by any path). Control: on scope under Python, 553 fires 2 and 554 fires 1.

| run (Rust) | `_rows.generator` (550) | `_rows.constant_value` (551) | `_rows.rules` (552) |
|---|---|---|---|
| seven workloads, pre (1dddb76) and post (11af121): dev 1,985, fuzz 3,000, zero 854, loop 420, scope 169, budget 28, cert 61 queries | 0 | 0 | 0 (553/554 also 0) |
| full suite, pre (1dddb76); post: 0/0, rules 95 (553: 12, 554: 2,398 by other paths) | 717 calls in 177 tests | 14,708 in 4 tests | 95 in 50 tests |

Readers: tests only (test_mul_rows, test_rows_numeric, test_rows_baseline import `generator`/`constant_value`;
test_complex_parts_rows, test_beta_functions_rows import `rules`) and tools/totality.py (offline). No engine or wiring reader.

**Outcome:** ruling (2) applies (no non-test calls). The binding can't simply be deleted: the test files import the names from
`_rows`, and tests aren't edited. So it becomes a module `__getattr__` that looks them up in `wiring` at each use, and `rules`
calls `wiring.generator` (11af121, +13/-3 lines). After the install, `_rows.generator is wiring.generator` (Rust's):
`test_rows_names_resolve_at_call_time`. `_rows` leaves NAMED_HOLDERS.

Suite, Rust, pre 1dddb76 against post 11af121: **127 failed, 5991 passed both, same failed ids** (not compared by id against
base here; sa-port-217's bar on 022630c had 128 failed/5990 passed; pre = post, so none comes from this change).

Wrong-value plants (full suite, Rust; failures beyond the unplanted 127):
| plant | where | pre | post |
|---|---|---|---|
| 424 rows-gen-wrong | `_rows.generator` drops the first rule of each spec | +32 caught | name gone (no binding) |
| 425 rows-cv-wrong | `_rows.constant_value` at c + 1 | +2 caught | name gone |
| 426 rows-gen-slot-wrong | install's slot `wiring.generator` | +139 | **+171** |
| 427 rows-cv-slot-wrong | install's slot `wiring.constant_value` | +22 | **+23** |

426/427 show the call-time lookup: after the change the slot plant also reaches the tests that held `_rows`' old binding
(+32 = exactly 424's catch; +1 for constant_value). On the workloads 424/425 are void (0 calls; see the table).
constant_value: the `_rows` name is not the const_value callback (`_common.const_value`); the template's constant_value is
`wiring.constant_value`, now reached through install's slot from `_rows` too. No generator calls per query on workloads, so
nothing goes to the formula step from `_rows`.

## Sub-part 3: Session.solver boundary
`session_readers.py` (Python reads/writes of `Session.solver`/`truncated`/`verdict`, filed by reading frame and query state),
seven workloads, Rust, --check plain, at 6df4ad8. Reads in total: budget 39,635, cert 6,567, dev 38,720, fuzz 580,673, loop
14,064, scope 12,780, zero 102,518. Top readers (converted queries, all workloads):

| reader | attr | reads |
|---|---|---|
| session_live `_rel_interpret` | solver | 323,365 |
| session_live `_rel_link` | solver | 147,514 |
| session_live `_rel_share_guard` | solver | 47,072 |
| session_live `_ses_visit` | solver | 45,184 |
| session_live `_compile_formula` | solver | 41,113 |
| session_live `_rel_sync_transfer` | solver | 37,358 |
| session_live `_q.f` / `_rel_m.f` / `_ses_escalate` | solver | 26,926 / 16,768 / 16,418 |
| engine.py `_gave_up` | solver | 13,915 |
| engine.py `_exhausted` | solver | 4,733 |
| session_live `_install_context._context_session` | verdict / solver / truncated | 9,274 / 4,637 / 4,440 |
| session_live `_ent.f` | solver / truncated | 7,756 / 5,028 |

Every Python reader on a converted query is slice wiring (session_live.py's wrappers handing `s.solver` to Rust on each call,
although `SessionCore` already holds the solver: `TableView.bind`'s `set_solver`), plus engine.py's `_gave_up`/`_exhausted`.
None of OWED [100]'s relations.py (:1689/:1812/:1851) or engine.py (:2145/:2248) sites appear: Rust replaced them.
Writes: only `_ses_init` (solver, truncated, verdict, once per session) and `_context_session` (verdict).
The frame is the nearest Python frame, so a Rust read under a Python caller is filed under that caller.

Boundary plan, as ruled (planner's Session.solver readers ruling, ~07:09 10 Nov): the `_rel_*` wrappers and `_ses_visit` are
**removed** in sub-part 5, after (iii) lands and part 3 rebases, not re-signed; any wrapper that does more than forward gets
listed. engine.py's two readers are done now (next section).

### engine.py `_gave_up` / `_exhausted` in Rust (042598c, sa-port-229)
context.rs (`_build_context`'s fallback, `_complete_check`) and entry.rs (`_ask`'s `theory_gave_up`) called the helpers back by
name. `theory_flags.rs` now reads each theory of **the session core's solver** (`solver_direct`, not `Session.solver`): an LRA
core's fields directly (`th:gave_up` 555, `th:exhausted` 556), any other theory by `getattr(t, name, False)` as Python does
(`th:py_flag` 557), a session with no core through the Python helper (`th:py_helper` 558). The helpers stay in engine.py (pure
Python; tests import them). Plants set by theory_flags.rs's own `th_plant` (relations_core.rs untouched, condition 2).
`lra_py.rs` gains a crate-only `flags()` accessor (component 1a's file, 4 lines).

| check | result |
|---|---|
| test_theory_flags.py (in repo): Rust read = helper on 2 gave-up and 10 exhausted sessions | equal on all 12 |
| plant 428 th-gave-up-skip | caught (2 rows); also moves `stats["theory_gave_up"]` 1 -> 0 on both gave-up cases |
| plant 429 th-exhausted-skip | caught (10 rows); answers on those cases unchanged |
| plant 430 th-first-only | caught (12 rows); moves `theory_gave_up` as 428 |
| session_readers on seven workloads at 042598c: engine.py frames | **0** (were `_gave_up` 13,915, `_exhausted` 4,733 at 6df4ad8) |
| answers, seven workloads, Rust --check plain, 042598c vs 1a6d38a | same answers_sha on all seven; dev 31cd0945, fuzz 173502b6 = Python's on 225's bar |
| th:* (dev/fuzz/zero/loop/scope/budget/cert) | gave_up 523/7,996/1,285/0/383/0/183; exhausted 164/2,725/381/0/125/0/61; py_flag 859/13,995/4,323/0/335/0/244; py_helper 0 everywhere (loop, budget: no theory attached) |
| ctx:cb_helpers (now `_noncommutative_atoms` only) | dev 64 (was 2,563 with the two helpers on 225's bar), fuzz 315 (8,589) |
| ctx:caught, handler rows | 0 on all seven |
| core tests: test_context_core, test_entry_core, test_install_order | 233 passed, 3 skipped |
| suite subset (lra_exhaustion, lra_constant_coefficients, p3_review, test_engine), Rust | 205 passed, 1 failed: test_split_beyond_the_certificate_bound_counts_as_exhausted, also failed in sa-port-227's unplanted run (post/suite-none, 127 failed) |

### OWED [100]'s Session sites, each with its reason (lines as at 5c10b's landing 4215655)
| site | what | now | reason |
|---|---|---|---|
| relations.py:1689 `_engage_transfer` (`s.xfer = self`) | write | relations_core.rs `engage_transfer` (12a980d, C2c) writes through `SessionCore.xfer_engage` (7a5e229, landed (ii) 9e10f0d) | **gone**: `Session.xfer` is a property onto the core |
| relations.py:1812 `sync_transfer` (`s.solver`) | read | relations_core.rs `sync_transfer` uses `Cx::solver()` = `solver_direct` (7a5e229, landed 9e10f0d) | **gone** |
| relations.py:1851 `_xswitch` (`self.session.solver`) | read | relations_core.rs `xswitch` uses `Cx::solver()` (same commits) | **gone** |
| engine.py:2145 `_put_result` (`s.truncated`) | read | entry.rs:511 (5c10d, landed 9529850) still reads the Python attribute: filed under `_ent.f`, 5,028 reads | **open, reached by every workload**; `truncated` moves into SessionCore in sub-part 5 (a struct change, after (iii)). The raise branch is plant 214's class: no workload makes it true |
| engine.py:2248 `_note_budget` (`s.truncated`) | read | budget.rs:580 (5c7 b4f0663, landed with 5c10d) reads the Python attribute | **open, reached** (budget workload); same owner |
Other Rust readers of `Session.solver` through the Python attribute (not OWED sites): relations_core.rs :1048/:1070/:1093/:1207
(rel_link_integer, fresh, bound, rel_interpret) — condition 2, sub-part 5 after the rebase; compile_loop.rs, session_glue.rs,
entry.rs:802, context.rs:265, query.rs — sub-part 5 with the wrappers.

## Sub-part 4: public-entry dispatch list
From test_install_order.py's public rows (each with its per-entry test):
| public name | held as | dispatch | test |
|---|---|---|---|
| `satassume.DictCache`, `ObjectCache` (also `engine.`, `sympy_api.DictCache`) | type | `DictCache.__new__` (session_live.py `_install_factcache`) | `test_install_list_entry[satassume.DictCache]` etc.; plant 422 |
| `satassume.relations.relation_atom`, `sympy_api.relation_atom` | function | `RELATION_ATOM_IMPL` slot (term_live.py:993) | `test_install_list_entry[satassume.relations.relation_atom]`; plant 421 |
| `P`, `And`, `Or`, ... (satassume.sat.formula) | classes | `p_install` import hook, refuses after the module is imported | p_install's own refusal |

## Sub-part 6: readouts ([108], [109]) per workload (sa-port-229)
Seven workloads, Rust, --check plain, SESSION_REPORT, on A = 225's (iii) head 1a6d38a (RelKeys' counters exist only there) and
B = 042598c (pareto1 ~/sp19/sa-rust-ids-work/sa-port-229/readouts, summary.txt). Answers: A = B on all seven.

| workload (queries) | rk:intern:engine | rk:intern:input | rk:term | rk:outlive (session-lasting ids) | rk:migrate | rk:dict:hit |
|---|---|---|---|---|---|---|
| dev (1,985) | 4,067 | 511 | 8,971 | 0 | 0 | 22,160 |
| fuzz (3,000) | 93,286 | 9,539 | 217,752 | 0 | 0 | 584,041 |
| zero (854) | 18,338 | 1,027 | 57,170 | 0 | 0 | 114,108 |
| loop (420) | 0 | 0 | 0 | 0 | 0 | 0 |
| scope (169) | 1,953 | 303 | 2,112 | 0 | 0 | 9,050 |
| budget (28) | 0 | 0 | 0 | 0 | 0 | 0 |
| cert (61) | 902 | 192 | 2,699 | 0 | 0 | 4,792 |
rk:intern:engine target 0 before any backend PR (atoms: formula step; terms: term-id step). rk:outlive 0 on all seven: no
session outlives its query on these workloads (context sessions included), so no session-lasting ids are needed there; the
counter's own firing is (iii)'s to show. loop and budget build no Relations.

**Scope fallback rise ([108], faddcda):** at A and B, scope: registry:python 33 (`_load` 27, `symbol_units` 4,
`constant_units` 2), rows:python 64 (`Integer` 32, `const_value` 32): unchanged from the corrected-order numbers (26 -> 33,
0 -> 64), no further rise. Other workloads, registry:python / rows:python: dev 126/625, fuzz 38/378, zero 43/119, loop 31/161,
budget 469/80, cert 24/208, equal on A and B; kept:out-of-scope dev 24, others 0.

**Memo cost ([108]):** not measured. It's a timing comparison owed in the speed report before any backend PR (OWED [108]); it
needs a quiet lease and is not a bar item. The counts above (rk:term, rk:intern:*) are the per-query id work standing where
cross-query memos were.

## Not run
The landing bar (suite by id against base with handler rows, dev/fuzz MATCH with planted bugs on the workloads; plants 428-430
on dev/fuzz); the full suite on 042598c; sub-part 5 (waits for (iii)); the memo-cost timing; the needs-internals list for the
test readers in sub-part 1's table (made with sub-part 5's moves).
