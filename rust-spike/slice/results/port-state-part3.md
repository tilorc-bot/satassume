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

## Sub-part 5: the session's own state in the core (after (iii); sa-port-230, -241, -242, -245, -247)

Commits on port/state-part3 (rebased onto rust-slice 0192b35): 0414c4f first part, 02354d4 `Session.solver` write, 7a18df2
containers, e82147a digest extension (test-only), 4d14638 scope fix, fd0fabb `core_of`, 4ce60ab container tests (test-only).

**First part (0414c4f).** Rust's 15 reads of `Session.solver` go through session.rs `solver_of` (the core's copy; a session
with no core is read by attribute, counted `sb:attr`). `truncated`, `_link_pending`, `_neg_shared`, `sel`, `n_hold` and
`verdict` are SessionCore scalars; Python sees them through views (session_live `_ses_sview`) whose setters are the core's
record methods. The writes of `defvars`, `_dv` and `_dv_node` are dropped. `_interpret`, `_link`, `_share_guard` and `_visit`
are called directly from Rust (session.rs `named`: by name only when the method was replaced). Counters 559-564 (`sb:*`),
plants 431-438.
- Inventory correction: sub-part 1 listed `_neg_shared` as dead. It is not (session.rs `dvar_def` reads it), so it moved
  with the other scalars.
- OWED [100]: the two `truncated` sites are closed by 0414c4f.
- The four wrappers `_rel_interpret`, `_rel_link`, `_rel_share_guard`, `_ses_visit` each do more than forward, so they are
  kept for Python callers and listed, not deleted: each sends a session with no core to Python's own copy (ref.py), and each
  is the by-name hook Rust calls when a test replaced the method or SLICE_REL/SLICE_LOOP=py is set. On converted queries
  all four are 0 on all seven probe workloads. No unruled callback; no question was sent.

**`Session.solver` written after bind (02354d4).** slice-5b (every slice test in one shared process: 8 failed, 34 errors,
1257 passed) had one real change: a solver assigned to a session after `TableView.bind` no longer reached Rust. `Session.solver`
is now a property whose setter records into the core (test_session_boundary.py `solver-write`). The other failures came from
the shared process (install() refuses after another file's Engine) or missing `-p rust_plugin -p handler_count`, so slice
test files run one process per file (bar.sh `TESTS_SPLIT=1`). test_glue_plain's rewrap test asserts the refusal;
test_term_live's two stale `_Mark` tests were fixed (they fail the same on the base). The install list stays 191.

**Containers (7a18df2, keys 4d14638).** `frontier`, `deferred` (sequences) and `pending`, `pending_c`, `demand`, `literals`,
`_groups` (dicts) are held in SessionCore (ses_cont.rs); Rust's sites use them natively through `Ses`, Python through the
views `SesSeqView`/`SesDictView` and the record methods behind an assignment. Counters 565-567 `sc:core`, `sc:view`,
`sc:record`; plants 439-445 `sc-<name>-drop`.
- The scope difference. On 7a18df2, workload scope differed with the digest off (query 5: Python 3 sessions, Rust 2, equal
  answers). Bisect: d8f9146, 0414c4f and 02354d4 MATCH (171 sessions), so 7a18df2 was the cause. scope's custom fact passes
  the int `1` to `relation_atom`, so `Session.demand` holds the int and `Relations._xside` holds SymPy's `One`; 7a18df2 keyed
  the session's dicts by the session's RelKeys ids, so both shared one object per equal class, `_xside` gave back the int,
  `_transfer_terms` saw no `Rational`, and `_number_basis(1)` with its `is_many` session was lost.
- The fix: each session dict is a `SesDict`, keyed as the Python dict it replaces (`hash()`, then the same object or `==`)
  and holding the key object first set in it. Nothing in ses_cont.rs reads or writes RelKeys; relkeys.rs has no diff against
  rust-slice. Counters 568 `sc:key_hash`, 569 `sc:key_eq` (calls into Python on a key). Plant 446 `sc-key-shared` puts the
  fault back: caught by workload scope and by test_session_boundary.py's `keys` case.
- relevance.rs (a shared file): the extended digest then found that an opaque `Split` gave `comps == []` and
  `consistent is None` on Rust where Python's `_Split` leaves them unset. Both getters now raise AttributeError on an opaque
  split. No reader in satassume or the slice reads them there; the digest does.
- Nothing was stopped on under condition 2.

**`core_of` off the `table` property (fd0fabb).** session.rs `core_of` did `s.getattr("table")`, which runs session_live's
property getter `_table_get`, a Python frame per read, and the count rose when the containers moved. `_table_set` now stores
the core beside the view (`_core`, a plain instance attribute) and `core_of` reads it; `table_of` does the same for
`_table_view` at the 11 other `getattr("table")` sites (compile_loop.rs 5, session_glue.rs 4, query.rs 2); compile_loop.rs
and discovery.rs use session.rs's `core_of` in place of their copies; session_live's own 44 dispatch tests read `__dict__`.
A session without the attribute is read through the property, counted 570 `sb:core_prop`. Plants 447 `sb-core-unset`
(equal answers by construction; caught by `sb:core_prop` firing and `_table_get`'s count rising) and 448 `sb-core-stale`
(rows differ).
- Still reading the property from Rust, not touched under condition 2: relations_core.rs :786 (`s.table.core`), :2270,
  :2332, :2468. (:742 and :2577 read a query's table, not a session's.) These and Python's own `.table` reads (`_node`,
  the Relations field views) are what is left of `_table_get`.

Module-wide probe of session_live.py (pycalls.py, every function, seven workloads, Rust, `--check plain`, all exit 0).
`_table_get` and all Python calls into session_live.py on converted queries, at d8f9146 (before the containers), 7a18df2
(containers) and fd0fabb (`core_of`):

| workload | queries | `_table_get` d8f9146 -> 7a18df2 -> fd0fabb | converted calls d8f9146 -> 7a18df2 -> fd0fabb | sc:core | sc:key_hash | sc:key_eq |
|---|---|---|---|---|---|---|
| fuzz | 3000 | 2,079,683 -> 2,268,435 -> 218,742 | 3,009,742 -> 3,137,531 -> 1,087,838 | 908,133 | 478,541 | 1,193 |
| dev | 1985 | 120,618 -> 149,444 -> 10,775 | 201,983 -> 228,016 -> 89,347 | 66,462 | 28,951 | 0 |
| zero | 854 | 418,024 -> 455,128 -> 46,702 | 593,181 -> 618,776 -> 210,350 | 145,552 | 73,045 | 0 |
| loop | 420 | 24,873 -> 39,288 -> 2,483 | 58,863 -> 71,762 -> 34,957 | 36,879 | 14,880 | 16 |
| scope | 169 | 43,720 -> 50,202 -> 4,472 | 69,286 -> 74,649 -> 29,003 | 22,079 | 10,220 | 0 |
| budget | 28 | 6,245 -> 9,430 -> 533 | 20,333 -> 21,591 -> 12,694 | 53,922 | 46,412 | 0 |
| cert | 61 | 24,016 -> 27,541 -> 2,411 | 36,798 -> 39,799 -> 14,669 | 12,904 | 6,513 | 0 |

`sb:core_prop`, `sb:attr`, `sb:fwd_named`, `sc:view` and `sc:record` are 0 on all seven at fd0fabb (each is shown to fire in
test_session_boundary.py: `sb:core_prop` under plant 447, `sc:view`/`sc:record` on the default run and under
SLICE_DISC=py SLICE_LOOP=py SLICE_GLUE=py). session_live.py still has 27 to 40 nonzero function names per workload on
converted queries (largest at fd0fabb: `TableView`'s methods, `_table_get`, `_rel_m`, `_ses_ensure`), so the module does
not count yet. `sc:key_hash` is a Python call per key lookup (160 per query on fuzz); not fixed in this step.
Outputs: orion `~/sa-rust-ids-work/sa-port-241/pyc/before`, `sa-port-241/pyc/after` (read in `sa-port-242/pyc/after-summary.txt`),
`sa-port-247/pyc/core`.

**Container tests (4ce60ab), test_session_boundary.py, 27 passed.** Each container's content (keys with their class, values,
in order), Python against Rust, after `_build_context` and after the asks for ten assumption sets, on a session cut by
`escalate(1)` before and after, and at each `_visit` of a like session with a vocabulary function registered for `Add`
(`frontier` and `pending` are empty between calls). The core's export `sc_snapshot` equals the views at each point; a write
through a view and an assignment are read back from the core; one Rust run with SLICE_DISC=py SLICE_LOOP=py SLICE_GLUE=py
gives Python's rows.

| plant | container | fired in the test | rows that differ besides the container's content |
|---|---|---|---|
| 439 `sc-frontier-drop` | `frontier` | yes | answers: ask, ctx, trunc, solver dump |
| 440 `sc-pending-drop` | `pending` | yes | none: content only; its native write is reached only with a registered vocabulary function under a demand |
| 441 `sc-pending_c-drop` | `pending_c` | yes | answers: ask, ctx, trunc, solver dump |
| 442 `sc-demand-drop` | `demand` | yes | solver dump, the keys case's session counts |
| 443 `sc-deferred-drop` | `deferred` | yes | the cut session's row |
| 444 `sc-literals-drop` | `literals` | yes | none: content only (a memo of compound formula -> literal) |
| 445 `sc-groups-drop` | `_groups` | yes | answers: ask, ctx, solver dump |
| 446 `sc-key-shared` | the dicts' keys | yes | the keys case; workload scope |

Whether each fires and is caught on the workloads is the landing bar's plant table.

**Digest extension (e82147a, test-only).** The moved containers' digest covers every container moved so far: the seven
session containers and six scalars, the (ii) handles, the LRA slot per query, every engine a workload builds; 5c9a's native
tables are checked in the process, not compared across backends (they exist on Rust only). known_moved.json holds the
exact known `_SPLIT`/`_CACHE` rows per workload and engine point (known_moved.py writes them), inside the verdict;
scope's row was added at 4d14638. On a Rust run the digest reads the handles through their views (`xf:*` view counters
rise by three reads per `Relations` and one per session) and `memo:native_items` ticks at each engine point.
memo_check.`_canon` (a shared file) was changed for it. Details: results/digest-coverage.md, last section.

## The landing bar (tested f252daf on rust-slice 0192b35; read by sa-port-249, gate items by sa-port-262)

pareto1 `~/sp19/sa-rust-ids-work/sa-port-247/bar-part3`, 17:47Z-22:09Z 10 Nov, every phase exit 0, seed1 not run; .so sha256
e9aaf5052540; base rows (iii)'s bar (`sa-port-236/bar-iii-b3`). Copies and tables: orion `~/sa-rust-ids-work/sa-port-249/bar`.
The incoming diff at landing: none (rust-slice was still 0192b35, the branch's base; `bar.sh land f252daf` printed an empty
stat), so tested = landed source; the commits after f252daf add only HANDOFF files and this file.

**Suite.** 126 failed, 5992 passed, 23 skipped, 18 xfailed; 6159 ids; against the base new 0, gone 0, changed outcome 0.
Passed 5992 = 5991 with no handler firing + 1 with a firing (tests/test_invariants.py::
test_ci_stream_reports_only_what_replays). Handler rows 39 in 2 tests, the multiset the same as the base's (34 `_ok`,
4 `_rb_clauses`, 1 `Already mutably borrowed` in test_transfer.py::test_protocol_on_fuzz). TermFault 0. ctx:caught 1,
ctx:fallback 37, rv:consistent_caught 45, all equal to the base (the quiet catches of engine.py's complete check).
ad:cbm_noid 293 (base bar 94; it varies between runs of one source; formula's fix) and 25 on twin, 0 on the other 15.

**Slice tests.** 53 files, one process per file (bar.sh `TESTS_SPLIT=1`, f252daf: a shared-file change): not exit 0 only the
known base failures test_cf_diff.py (exit 2, 1 error: a script), test_catch_count.py (3 failed) and test_handler_count.py
(2 failed) (the last two need `-p rust_plugin -p handler_count`). test_term_live.py 20 passed, 1 skipped (it fails on the
base). test_install_order.py 198 passed (the 191-entry install list, a test per entry, and
test_install_order.py::test_engine_first_refused, plant 420); test_session_boundary.py 27 passed.

**Workloads, digest on (`--check entry`).** All 16 MATCH Python against Rust (dev, fuzz, twin, scope, loop, zero, cert,
budget, core, f6, opaque, rootof, value, wiring, transfer:7:60, transfer2:3:40); the Python against Python controls MATCH;
0 handler rows on every Python and Rust run (so relevance.rs's AttributeError on an opaque Split adds no firing). The only
differences inside the verdict are the known `_SPLIT`/`_CACHE` rows per engine point, equal to known_moved.json's (dev 80,
fuzz 120, scope 7, twin 1, loop 17, zero 35, cert 3, budget 2, core 66, f6 117, opaque 102, rootof 208, value 150, wiring
261, transfer:7:60 3, transfer2:3:40 2), and scope's known row.

**Workloads, digest off (`--check plain`, answers only; the planner's gate addition of ~22:25Z 10 Nov; sa-port-262).** The
digest (moved_digest.py:137) replaces `Relations._interpret` and `_link` with its trackers, so in the digest-on runs Rust
calls them by name (session.rs `named`, `sb:fwd_named`) and not directly: those runs did not take the path a user gets.
One run of all 16 with the digest off, on the bar's tree and .so (pareto1 `~/sp19/sa-rust-ids-work/sa-port-262/dgoff`,
copy on orion without the .jsonl): **all 16 MATCH, answer_diff 0, 0 handler rows**, and plant 437 (sb-fwd-skip-link), which
fired 0 on all 16 with the digest on, fires and is caught on 8.

| workload (queries) | verdict, digest off | sb:fwd_direct off | sb:fwd_named off | sb:fwd_direct on | sb:fwd_named on | plant 437 fired (off) | plant verdict (answers changed) |
|---|---|---|---|---|---|---|---|
| dev (1,985) | MATCH | 4,634 | 0 | 2,758 | 1,876 | 375 | DIFFER (33) |
| fuzz (3,000) | MATCH | 67,229 | 0 | 21,427 | 45,802 | 9,421 | DIFFER (96) |
| twin (2) | MATCH | 38 | 0 | 12 | 26 | 6 | DIFFER (2) |
| scope (169) | MATCH | 1,377 | 0 | 502 | 875 | 174 | DIFFER (1) |
| loop (420) | MATCH | 2,284 | 0 | 2,284 | 0 | 0 | MATCH |
| zero (854) | MATCH | 12,843 | 0 | 4,832 | 8,011 | 1,903 | DIFFER (166) |
| cert (61) | MATCH | 698 | 0 | 243 | 455 | 81 | DIFFER (30) |
| budget (28) | MATCH | 1,961 | 0 | 1,961 | 0 | 0 | MATCH |
| core (1,636) | MATCH | 6,365 | 0 | 6,365 | 0 | 0 | MATCH |
| f6 (2,902) | MATCH | 11,575 | 0 | 11,575 | 0 | 0 | MATCH |
| opaque (2,546) | MATCH | 3,007 | 0 | 3,007 | 0 | 0 | MATCH |
| rootof (5,187) | MATCH | 5,520 | 0 | 5,520 | 0 | 0 | MATCH |
| value (3,742) | MATCH | 4,555 | 0 | 4,358 | 197 | 0 | MATCH |
| wiring (6,512) | MATCH | 48,945 | 0 | 48,945 | 0 | 0 | MATCH |
| transfer:7:60 (60) | MATCH | 2,183 | 0 | 1,069 | 1,114 | 198 | DIFFER (3) |
| transfer2:3:40 (40) | MATCH | 1,989 | 0 | 1,032 | 957 | 148 | DIFFER (2) |

On every workload direct (off) = direct + named (on): the digest moves calls from the direct branch to the by-name one and
changes no count. sb:attr 0 on all 16, both ways. The suite has no digest: sb:fwd_named 0, sb:fwd_direct 1,657,074. The
answers' hashes are the bar's (dev 31cd0945c07f02a6, fuzz 173502b6ef285ad6, scope 12e06b0586faee40). The digest that only
observes is formula's next bar (RULINGS 14).

**Subs twins (RULINGS 13; sa-port-255's repro.py, one process per row, a new Engine per ask, nothing cleared).** Run on
orion on a worktree of each SHA with its own built .so (base 0192b35 .so bfc06f0cd68a, step f252daf .so a10068f4febd;
`~/sa-rust-ids-work/sa-port-262/tw/rows-{base,step}.txt`). The rows are equal on base and step, so the difference is the
base's and the step does not change it:

| case | order | Python, base = step | Rust, base = step |
|---|---|---|---|
| oo:lra | 12 | [None, None] | [None, None] |
| oo:lra | 21 | [True, True] | [True, None] |
| one:lra | 12 | [None, None] | [None, True] |
| one:lra | 21 | [True, True] | [True, None] |

Single asks (orders 1 and 2) agree on both: [None] and [True] for each case. Known-difference rows: oo:lra 21,
one:lra 12, one:lra 21.

**Plants (22 in the bar; fired, then caught or not).** Caught on workloads: sb-core-stale, sb-hold-zero, sb-sel-zero,
sb-solver-fresh, sb-verdict-none, sc-demand-drop (442), sc-frontier-drop (439) on 16 of 16; sc-pending_c-drop (441) 15 (twin
fired 0); sc-literals-drop (444) 9; sc-groups-drop (445) 8; sc-deferred-drop (443) 6; sc-pending-drop (440) 5 (budget 145,
core 150, f6 252, loop 598, wiring 571 fired); sb-link-pending-stale 5; sc-key-shared (446) 3 (dev, fuzz, scope);
rk-class-split (409) on twin; th-exhausted-skip and th-first-only on dev, fuzz, transfer:7:60, transfer2:3:40; 450, 451, 453
by the verdict and 452 by the guard in test_split_order.py / test_moved_digest.py. Not caught on a digest-on workload:
sb-fwd-skip-link (437): fired 0 with the digest on (the cause above), caught digest-off on 8 workloads (table) and in the
suite (fired 87,333, 216 ids changed); sb-core-unset (447): fired on all 16, equal answers by construction, caught by
sb:core_prop and `_table_get` rising in test_session_boundary.py::test_core_read_without_the_property;
sb-truncated-stale: fired on all 16, MATCH, caught only by test_session_boundary.py's trunc case (no workload has a
truncated session whose stale flag changes an answer); sb-neg-shared-stale: workloads fired 0 on 14, MATCH on
transfer2:3:40 (8) and transfer:7:60 (10), caught in the suite (fired 26,194, 24 ids changed); th-gave-up-skip (428):
MATCH on all 16 (no workload has a theory that gave up; th:gave_up read dev 523, fuzz 7,996), caught in the suite (6 ids)
and test_theory_flags.py. **Void:** the bar's "fired 0" for the three th-* plants is unmeasured (theory_flags.rs's
`th_plant` does not feed plant_fired), not a zero. Suite under plants: rk-class-split 132 failed (6 changed, fired 681);
sb-fwd-skip-link 330 (216); sb-neg-shared-stale 150 (24); sc-pending-drop 185 (59, fired 456); th-exhausted-skip 128 (2);
th-first-only 131 (5); th-gave-up-skip 132 (6). tests/test_public_incremental.py::
test_public_comparison_catches_a_planted_history_dependence goes passed -> failed in several plant suites: the known
id()-reuse test; it passes in the plain suite, as on the base.

**Counters, Rust runs of the bar (digest on).**

| workload | sc:key_hash | sc:key_eq | sc:core | rk:intern:engine |
|---|---|---|---|---|
| dev | 28,951 | 0 | 66,462 | 4,067 |
| fuzz | 478,541 | 1,193 | 908,133 | 93,286 |
| budget | 46,412 | 0 | 53,922 | 0 |
| cert | 6,513 | 0 | 12,904 | 902 |
| core | 31,346 | 333 | 92,847 | 0 |
| f6 | 56,852 | 0 | 156,933 | 0 |
| loop | 14,880 | 16 | 36,879 | 0 |
| opaque | 13,385 | 0 | 39,380 | 0 |
| rootof | 32,384 | 0 | 76,703 | 0 |
| scope | 10,220 | 0 | 22,079 | 1,953 |
| transfer2:3:40 | 11,680 | 17 | 21,289 | 2,080 |
| transfer:7:60 | 14,752 | 2 | 26,844 | 2,476 |
| twin | 140 | 1 | 300 | 56 |
| value | 25,145 | 0 | 59,710 | 1,183 |
| wiring | 283,608 | 67 | 601,128 | 0 |
| zero | 73,045 | 0 | 145,552 | 18,338 |
| suite | 10,005,845 | 27,692 | 20,782,325 | 992,243 (base 994,158) |

sb:attr, sb:core_prop (570), sc:view, sc:record, sb:scalar_record, th:py_helper, rk:outlive (session-lasting ids),
rk:migrate, xf:record, bud:py_fallback: 0 on all 16 and in the suite; sb:scalar_view 0 on workloads, 23 in the suite.
rk:intern:engine and rk:intern:input equal the base on its seven workloads. The digest's own view reads on a Rust run:
memo:native_items dev 560, fuzz 840, scope 49; xf:session_view dev 918, fuzz 3,133; xf:rel_view dev 594, fuzz 9,054.

**Fallbacks and kept shares per workload (RULINGS 7, 11; the bar's `*-rust.knowledge.json`, equal in the digest-off run).**
scaffold:core:kept_product:mismatch is 0 on all 16 workloads. The suite's counts files hold no knowledge counters, so the
mismatch and the two fallback rows are not measured in the suite.

| workload | registry:python | rows:python | scaffold:core:kept_product | kept:out-of-scope | refused |
|---|---|---|---|---|---|
| dev | 95 | 521 | 33 | 24 of 1,985 | 0 |
| fuzz | 38 | 272 | 0 | 0 | 0 |
| twin | 34 | 0 | 0 | 0 | 0 |
| scope | 33 | 64 | 0 | 0 | 0 |
| loop | 31 | 129 | 2 | 0 | 0 |
| zero | 38 | 72 | 0 | 0 | 0 |
| cert | 24 | 208 | 0 | 0 | 0 |
| budget | 469 | 80 | 0 | 0 | 0 |
| core | 35 | 1,688 | 163 (`:none` 14) | 0 | 0 |
| f6 | 65 | 760 | 82 | 0 | 13 |
| opaque | 42 | 48 | 0 | 0 | 7 |
| rootof | 27 | 16 | 0 | 0 | 0 |
| value | 180 | 1,208 | 0 | 0 | 15 |
| wiring | 75 | 478 | 10 | 0 | 1 |
| transfer:7:60 | 55 | 144 | 2 | 0 | 0 |
| transfer2:3:40 | 57 | 120 | 2 | 0 | 0 |

On the base's seven workloads (dev, fuzz, scope, loop, zero, cert, budget) registry:python, rows:python, the mismatch and
kept:out-of-scope are equal to (iii)'s bar; the base has no rows for the other nine. scope stays at 33 / 64 (the rise to
these from 26 / 0 came with the corrected install order, faddcda; no further rise).

**Group D (C API from Rust on Python-held state; RULINGS 12), shares.** sa-port-146's method (pysampler, 1 ms CPU time;
dev 10 runs, fuzz 3; Rust mode), sampled 22:14Z 10 Nov on pareto1 under a shared lease for both trees, each with its own
.so (orion `~/sa-rust-ids-work/sa-port-249/gd/run-{0192b35,f252daf}`: SUMMARY.md, SUMMARY-rel.md; the table by
`~/sa-rust-ids-work/sa-port-262/gdt/dmods.py`, which counts relkeys.rs and ses_cont.rs, which sum202.py's (a) leaves out).

| tree, workload | samples | all D | relations_core | session_glue | relkeys | ses_cont | session | discovery | compile_loop | query | context |
|---|---|---|---|---|---|---|---|---|---|---|---|
| base 0192b35 dev | 18,596 | 4,889 (26.3%) | 484 (2.60%) | 229 (1.23%) | 104 (0.56%) | none (no ses_cont.rs) | 235 (1.26%) | 271 (1.46%) | 796 (4.28%) | 141 (0.76%) | 151 (0.81%) |
| step f252daf dev | 15,420 | 3,872 (25.1%) | 391 (2.54%) | 146 (0.95%) | 104 (0.67%) | 18 (0.12%) | 175 (1.13%) | 68 (0.44%) | 706 (4.58%) | 97 (0.63%) | 133 (0.86%) |
| base 0192b35 fuzz | 45,620 | 16,133 (35.4%) | 2,564 (5.62%) | 398 (0.87%) | 684 (1.50%) | none | 1,066 (2.34%) | 1,062 (2.33%) | 2,199 (4.82%) | 224 (0.49%) | 261 (0.57%) |
| step f252daf fuzz | 50,968 | 17,599 (34.5%) | 2,849 (5.59%) | 403 (0.79%) | 802 (1.57%) | 94 (0.18%) | 1,074 (2.11%) | 481 (0.94%) | 2,330 (4.57%) | 240 (0.47%) | 233 (0.46%) |

- The session's own modules (session_glue + ses_cont + session + discovery): dev 735 (3.95%) -> 407 (2.64%), fuzz 2,526
  (5.54%) -> 2,052 (4.03%). discovery's D falls most (its containers are native now); ses_cont's own D is the hash and
  `==` of the Python key objects each session dict holds.
- The relations path (sum202.py's (a)+(b)+(c)+(d)): dev 1,239 (6.7%) -> 981 (6.4%), fuzz 5,768 (12.6%) -> 6,432 (12.6%).
- Sample counts on a shared lease (load 9 to 16) are not timings: fuzz's total is 12% higher on the step and dev's 17%
  lower, which is the machine, not the trees, until the pinned medians say otherwise.
- Conversion (term_live._convert) holds 39.7% of dev's samples and 16.4% of fuzz's at f252daf (base 38.8% / 16.5%).

**Group D in seconds and the memo cost ([108]): NOT measured; owed, moved to formula's bar.** Both need pinned medians
under a quiet lease on pareto1, and from 22:24Z 10 Nov the machine was held by another project's shared lease with no end
time. Planner (~22:35Z 10 Nov, on report 93774a0): pinned timing is not one of the five landing-bar items, so part 3 lands
without it; RULINGS 12's "first to land reports it" moves to formula's bar, for Group D in seconds and the memo cost
together, and both stay on OWED until then. Ready for that run: pareto1 `~/sa-rust-ids-work/sa-port-249/gd/bench-{0192b35,
f252daf}` (each tree with its .so), `gd/tools262/time262.sh` (one bench-container invocation, the two trees and Python and
Rust mode alternating, dev and fuzz, 11 rounds, about 20 minutes), `~/sa-rust-ids-work/sa-port-262/gdt/onlease262.sh`
(CPU 2, sa-eval-bench:1), and on orion `~/sa-rust-ids-work/sa-port-262/gdt/med262.py TIME.JSONL dmods.json` (medians, and
seconds = all-D share x the Rust median, against sa-port-146's 0.158 s dev / 1.990 s fuzz at 034e6bc's medians 0.767 s /
6.802 s). Unpinned rows, context only and not a result (job195's `--cpus 1` container, one run each, load 9 to 16): dev
Rust mode 2.23 s at f252daf and 2.68 s at the base against Python's 1.01 s; fuzz Rust 15.3 s against Python's 16.7 s at
f252daf. A one-round smoke test of time262.sh, also unpinned, gave dev Rust 2.57 s (base) and 2.46 s (step) against Python
1.47 s and 0.96 s. If the pinned medians agree, Rust mode on dev is now slower than Python and about three times
sa-port-146's 0.767 s: that is the size the memo-cost report has to explain.

## Not run
At the landing (tested f252daf): Group D in seconds and the memo-cost timing (above; owed, formula's bar); seed1
(PYTHONHASHSEED=1) in the bar; the fallback rows and scaffold:core:kept_product:mismatch in the suite (its counts files
hold no knowledge counters; read on the 16 workloads only); the three th-* plants' fired counts (unmeasured, `th_plant`
does not feed plant_fired); a workload on which th-gave-up-skip, sb-truncated-stale or sb-neg-shared-stale changes an
answer (suite or test only); the count step for session_live / ses_cont (the module-wide probe on the landed SHA, all
workloads plus the suite, with sc:key_hash listed: no count change without it); "relations' reference held by the
core" (the brief's item, not in the gate); SesDict by term id and session_live's converted calls per function (the next
part 3 step); relations_core.rs :786, :2270, :2332, :2468 still reading the `table` property (formula's, condition 2);
the digest that observes without replacing `_interpret`/`_link` (formula's next bar, RULINGS 14); the needs-internals
list for the test readers in sub-part 1's table.

## The count step: module-wide probe of session_live.py on landed 9151316 (sa-port-263)
**Verdict: session_live.py does not count, and ses_cont does not count.** No function of session_live.py that runs on a
converted query is a named callback or a conversion: 72 function rows are nonzero on the 16 workloads (40 to 70 per
workload) and 73 in the suite, and `sc:key_hash` (one Python `hash()` per session-dict lookup, ses_cont.rs:88) is nonzero on
all 16 workloads and in the suite. Owners are in the last table of this section.

Method (RULINGS 1; rust-slice 9151316, source equal to tested f252daf). Every PY_START of a code object of
rust-spike/slice/session_live.py, filed by the query state read from term_live's stack top as pycalls.py reads it.
- Workloads: sa-port-262's pycalls.py run (orion `~/sa-rust-ids-work/sa-port-262/pyc/landed`, 22:33Z-22:34Z 10 Nov, 16
  workloads, Rust, `--check plain`, all exit 0, every .err empty, .so a10068f4febd). Read, then run again by sa-port-263
  with the nearest Python caller and the wrapped method name recorded (`~/sa-rust-ids-work/sa-port-263/p1/pc263.py`, output
  `sa-port-263/wl`): per function, per state and in every sb:/sc: counter the second run equals the first on all 16
  (`p1/cmp.py`). The tables below are the second run's. `_rel_m[x]`, `_q[x]`, `_g[x]`, `_ent[x]`, `_bud[x]` are the closure
  wrappers split by the method they wrap.
- Suite: pareto1 under a shared lease, a copy of the tree at 9151316 (`~/sp19/dev/sa-port-263-landed`) with the bar's
  x86-64 .so of the same source (e9aaf5052540), `-p rust_plugin -p handler_count -p pc263_suite -n 6`
  (`~/sp19/sa-rust-ids-work/sa-port-263/suite-probe`, copy on orion `sa-port-263/suite-probe`): 127 failed, 5,991 passed,
  23 skipped, 18 xfailed. The bar had 126 / 5,992; the one more failure is
  tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence, the known id()-reuse
  test; the other 126 failed ids are the bar's. A second pass without the probe (`suite-counts`, below) fails the same 127,
  so the probe is not the cause.
- `_census` (107,547 on the workloads, 0 in the suite) runs only because the probe sets SESSION_REPORT
  (compile_loop.rs:432); it is the probe's instrument, not a call of a normal run. In the suite
  `_complete_check` (35,166) and 4,000 of `verdict` are called by catch_count.py, the handler-count plugin's wrapper.
- The four wrappers that Rust now calls directly (`_rel_interpret`, `_rel_link`, `_rel_share_guard`, `_ses_visit`) are 0
  on all 16 workloads and in the suite, as `sb:fwd_named` 0 says.

Per run (converted = calls into session_live.py on converted queries; kept = on queries Python answers):

| run | queries | converted calls | nonzero functions | noquery | kept | sc:key_hash | sc:key_eq | sc:core | sc:view | sc:record | sb:attr | sb:fwd_named | sb:core_prop |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| fuzz | 3000 | 1,087,838 | 70 | 12,139 | 0 | 478,541 | 1,193 | 908,133 | 0 | 0 | 0 | 0 | 0 |
| dev | 1985 | 89,347 | 70 | 6,555 | 464 | 28,951 | 0 | 66,462 | 0 | 0 | 0 | 0 | 0 |
| zero | 854 | 210,350 | 70 | 3,331 | 0 | 73,045 | 0 | 145,552 | 0 | 0 | 0 | 0 | 0 |
| loop | 420 | 34,957 | 40 | 1,751 | 0 | 14,880 | 16 | 36,879 | 0 | 0 | 0 | 0 | 0 |
| scope | 169 | 29,003 | 63 | 819 | 0 | 10,220 | 0 | 22,079 | 0 | 0 | 0 | 0 | 0 |
| budget | 28 | 12,694 | 43 | 255 | 0 | 46,412 | 0 | 53,922 | 0 | 0 | 0 | 0 | 0 |
| cert | 61 | 14,669 | 57 | 387 | 0 | 6,513 | 0 | 12,904 | 0 | 0 | 0 | 0 | 0 |
| twin | 2 | 756 | 62 | 152 | 0 | 140 | 1 | 300 | 0 | 0 | 0 | 0 | 0 |
| core | 1636 | 85,497 | 42 | 6,683 | 0 | 31,346 | 333 | 92,847 | 0 | 0 | 0 | 0 | 0 |
| f6 | 2902 | 134,694 | 43 | 11,751 | 520 | 56,852 | 0 | 156,933 | 0 | 0 | 0 | 0 | 0 |
| opaque | 2546 | 59,366 | 44 | 10,327 | 210 | 13,385 | 0 | 39,380 | 0 | 0 | 0 | 0 | 0 |
| rootof | 5187 | 124,168 | 42 | 20,085 | 0 | 32,384 | 0 | 76,703 | 0 | 0 | 0 | 0 | 0 |
| value | 3742 | 120,270 | 65 | 15,061 | 354 | 25,145 | 0 | 59,710 | 0 | 0 | 0 | 0 | 0 |
| wiring | 6512 | 506,690 | 43 | 26,191 | 42 | 283,608 | 67 | 601,128 | 0 | 0 | 0 | 0 | 0 |
| transfer:7:60 | 60 | 30,456 | 68 | 383 | 0 | 14,752 | 2 | 26,844 | 0 | 0 | 0 | 0 | 0 |
| transfer2:3:40 | 40 | 25,384 | 65 | 303 | 0 | 11,680 | 17 | 21,289 | 0 | 0 | 0 | 0 | 0 |
| suite | n/a | 11,806,173 | 73 | 12,545,780 | 271,333 | 10,006,834 | 26,491 | 20,784,215 | 0 | 0 | 0 | 0 | 0 |

Where the converted calls come from. The nearest Python caller of almost every call is another session_live.py wrapper,
so the caller is Rust code that was entered through that wrapper and calls a `Session`, `Relations` or `Engine` method by
name (or reads `table.new_nodes`, `table.base_of.get`, `len(table)`, `.table`), which runs a Python dispatch frame and goes
straight back into Rust. The row names the Rust file the outer wrapper enters; the calling site itself can be in another
Rust file reached from it (the `table.new_nodes` / `new_custom` / `base_of.get` reads under `_ses_ensure` and
`_ses_discover` are compile_loop.rs:127-151 and :254-308).

| calls come from | 16 workloads | functions | suite | functions |
|---|---:|---:|---:|---:|
| Rust under a `Relations` wrapper (relations_core.rs entered), calling back by name or reading a view | 689,217 | 20 | 5,040,907 | 20 |
| Rust under a `Session`/`Engine` wrapper (compile.rs entered), calling back by name or reading a view | 106,743 | 2 | 321,701 | 2 |
| Rust under a `Session`/`Engine` wrapper (compile_loop.rs entered), calling back by name or reading a view | 47,912 | 5 | 332,677 | 5 |
| Rust under a `Session`/`Engine` wrapper (context.rs entered), calling back by name or reading a view | 72,251 | 8 | 259,739 | 8 |
| Rust under a `Session`/`Engine` wrapper (discovery.rs entered), calling back by name or reading a view | 761,937 | 6 | 3,376,218 | 6 |
| Rust under a `Session`/`Engine` wrapper (entry.rs entered), calling back by name or reading a view | 181,396 | 12 | 424,357 | 11 |
| Rust under a `Session`/`Engine` wrapper (query.rs entered), calling back by name or reading a view | 157,706 | 14 | 1,010,321 | 14 |
| Rust under a `Session`/`Engine` wrapper (session_glue.rs entered), calling back by name or reading a view | 146,541 | 11 | 447,011 | 11 |
| session_live.py calling itself (TableView.bind) | 159,102 | 6 | 263,220 | 6 |
| session_live.py calling itself (_dvar_public) | 404 | 1 | 3,935 | 1 |
| session_live.py calling itself (_node) | 25,431 | 1 | 66,056 | 1 |
| session_live.py calling itself (_rust_call) | 20,758 | 1 | 85,153 | 1 |
| session_live.py calling itself (_table_set) | 26,517 | 1 | 43,870 | 1 |
| entry frame: sympy_api.py (conversion code) calling an `Engine` method | 61,927 | 7 | 84,479 | 6 |
| Python's compiler on a converted query (`_compile_formula`'s fallback) | 750 | 2 | 7,239 | 3 |
| suite only: catch_count.py (Python) | 0 | 0 | 39,166 | 2 |
| suite only: test_budget_cone.py (Python) | 0 | 0 | 13 | 1 |
| suite only: test_history.py (Python) | 0 | 0 | 110 | 1 |
| suite only: test_invariants.py (Python) | 0 | 0 | 1 | 1 |
| instrument: `_census` (the probe sets SESSION_REPORT; compile_loop.rs:432) | 107,547 | 1 | 0 | 0 |
| total | 2,566,139 | | 11,806,173 | |

Per function on converted queries, 16 workloads and the suite:

| function | fuzz | dev | zero | loop | scope | budget | cert | twin | core | f6 | opaque | rootof | value | wiring | transfer:7:60 | transfer2:3:40 | suite |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `_table_get` | 218,742 | 10,775 | 46,702 | 2,483 | 4,472 | 533 | 2,411 | 164 | 2,293 | 3,449 | 2,396 | 5,152 | 9,548 | 11,454 | 7,379 | 6,654 | 2,364,823 |
| `TableView.new_nodes` | 133,977 | 8,939 | 23,766 | 5,090 | 3,100 | 2,349 | 1,639 | 76 | 7,349 | 12,015 | 1,200 | 6,256 | 6,557 | 59,846 | 3,238 | 2,638 | 1,512,644 |
| `_ses_ensure` | 84,724 | 5,204 | 14,541 | 700 | 1,710 | 175 | 1,037 | 42 | 1,945 | 2,891 | 2,396 | 5,152 | 3,853 | 35,630 | 2,498 | 1,919 | 1,233,651 |
| `TableView.new_custom` | 108,970 | 5,246 | 19,502 | 1,403 | 3,267 | 194 | 1,344 | 60 | 492 | 233 | 31 | 368 | 1,698 | 5,504 | 2,332 | 1,787 | 907,711 |
| `_rel_m[_adapter]` | 83,110 | 3,395 | 14,839 | 0 | 1,587 | 0 | 829 | 48 | 0 | 0 | 0 | 0 | 592 | 0 | 2,094 | 1,806 | 757,719 |
| `_ses_discover` | 58,720 | 3,242 | 10,792 | 244 | 1,368 | 23 | 708 | 34 | 300 | 6 | 31 | 368 | 1,107 | 5,004 | 1,368 | 1,112 | 534,495 |
| `_BaseOf.get` | 33,395 | 4,177 | 3,086 | 3,872 | 684 | 5,436 | 399 | 2 | 16,407 | 26,623 | 2,025 | 6,256 | 7,086 | 62,716 | 1,006 | 897 | 320,222 |
| `_q[emit]` | 14,860 | 2,944 | 5,058 | 560 | 346 | 159 | 365 | 10 | 672 | 12 | 62 | 736 | 638 | 70,807 | 648 | 493 | 331,521 |
| `TableView.__len__` | 33,176 | 3,286 | 3,297 | 2,798 | 958 | 290 | 606 | 2 | 11,342 | 19,824 | 1,730 | 6,319 | 5,785 | 15,119 | 920 | 819 | 303,774 |
| `_ses_custom` | 36,397 | 1,494 | 6,278 | 0 | 989 | 0 | 374 | 20 | 0 | 0 | 0 | 0 | 197 | 0 | 916 | 809 | 332,038 |
| `_rel_m[enqueue]` | 36,397 | 1,494 | 6,278 | 0 | 701 | 0 | 374 | 20 | 0 | 0 | 0 | 0 | 197 | 0 | 916 | 809 | 331,440 |
| `_rel_m[_atom_var]` | 30,732 | 1,256 | 6,213 | 0 | 539 | 0 | 253 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 886 | 726 | 293,816 |
| `_ses_query_literal` | 7,974 | 1,673 | 1,219 | 1,024 | 499 | 21 | 188 | 32 | 3,734 | 6,467 | 4,751 | 5,869 | 6,696 | 11,922 | 139 | 153 | 135,873 |
| `_rel_m[_link_later]` | 17,762 | 912 | 3,183 | 0 | 224 | 0 | 343 | 10 | 0 | 0 | 0 | 0 | 394 | 0 | 394 | 365 | 126,025 |
| `_rel_m[_note_sides]` | 11,212 | 432 | 2,612 | 0 | 185 | 0 | 81 | 8 | 0 | 0 | 0 | 0 | 394 | 0 | 434 | 415 | 120,434 |
| `_ses_incomplete` | 8,208 | 2,145 | 1,756 | 812 | 501 | 36 | 183 | 6 | 1,906 | 2,301 | 2,232 | 1,409 | 1,704 | 13,402 | 143 | 71 | 96,067 |
| `_rel_sync_transfer` | 5,441 | 170 | 3,127 | 0 | 52 | 0 | 0 | 8 | 0 | 0 | 0 | 0 | 592 | 0 | 314 | 165 | 109,864 |
| `_census` | 16,537 | 2,476 | 2,804 | 2,284 | 490 | 1,961 | 223 | 8 | 6,365 | 11,549 | 2,996 | 5,520 | 4,343 | 48,942 | 573 | 476 | 0 |
| `_node` | 867 | 839 | 336 | 384 | 144 | 6 | 27 | 30 | 1,629 | 2,885 | 2,365 | 4,784 | 5,287 | 5,627 | 102 | 119 | 66,056 |
| `_q[query_lit]` | 867 | 839 | 336 | 384 | 144 | 6 | 27 | 30 | 1,629 | 2,885 | 2,365 | 4,784 | 5,287 | 5,627 | 102 | 119 | 66,056 |
| `_rel_add_role` | 3,333 | 171 | 1,612 | 0 | 6 | 0 | 10 | 4 | 0 | 0 | 0 | 0 | 197 | 0 | 343 | 418 | 84,913 |
| `_q[_ensure_twins]` | 5,602 | 1,605 | 1,309 | 488 | 334 | 29 | 122 | 4 | 594 | 8 | 61 | 736 | 834 | 9,818 | 113 | 58 | 67,142 |
| `_ses_assumption_lits` | 5,602 | 1,605 | 1,309 | 488 | 334 | 29 | 122 | 4 | 594 | 8 | 61 | 736 | 834 | 9,818 | 113 | 58 | 66,989 |
| `_rust_call` | 4,909 | 871 | 987 | 2,099 | 507 | 520 | 121 | 2 | 664 | 564 | 31 | 368 | 516 | 5,827 | 67 | 51 | 60,754 |
| `_rel_m[_share]` | 8,009 | 504 | 1,794 | 0 | 274 | 0 | 132 | 6 | 0 | 0 | 0 | 0 | 394 | 0 | 187 | 104 | 66,666 |
| `_q[_ensure_atoms]` | 4,909 | 871 | 987 | 244 | 219 | 23 | 121 | 2 | 300 | 6 | 31 | 368 | 516 | 5,004 | 67 | 51 | 59,698 |
| `_ses_init` | 3,133 | 912 | 667 | 384 | 171 | 17 | 87 | 4 | 1,635 | 2,889 | 2,366 | 4,784 | 3,535 | 5,817 | 68 | 48 | 43,870 |
| `_ses_solver_set` | 3,133 | 912 | 667 | 384 | 171 | 17 | 87 | 4 | 1,635 | 2,889 | 2,366 | 4,784 | 3,535 | 5,817 | 68 | 48 | 43,870 |
| `_table_set` | 3,133 | 912 | 667 | 384 | 171 | 17 | 87 | 4 | 1,635 | 2,889 | 2,366 | 4,784 | 3,535 | 5,817 | 68 | 48 | 43,870 |
| `TableView.bind` | 3,133 | 912 | 667 | 384 | 171 | 17 | 87 | 4 | 1,635 | 2,889 | 2,366 | 4,784 | 3,535 | 5,817 | 68 | 48 | 43,870 |
| `_core_rules` | 3,133 | 912 | 667 | 384 | 171 | 17 | 87 | 4 | 1,635 | 2,889 | 2,366 | 4,784 | 3,535 | 5,817 | 68 | 48 | 43,870 |
| `_ses_solver_get` | 3,133 | 912 | 667 | 384 | 171 | 17 | 87 | 4 | 1,635 | 2,889 | 2,366 | 4,784 | 3,535 | 5,817 | 68 | 48 | 43,870 |
| `_Custom.__init__` | 3,133 | 912 | 667 | 384 | 171 | 17 | 87 | 4 | 1,635 | 2,889 | 2,366 | 4,784 | 3,535 | 5,817 | 68 | 48 | 43,870 |
| `_BaseOf.__init__` | 3,133 | 912 | 667 | 384 | 171 | 17 | 87 | 4 | 1,635 | 2,889 | 2,366 | 4,784 | 3,535 | 5,817 | 68 | 48 | 43,870 |
| `_Slots.__init__` | 3,133 | 912 | 667 | 384 | 171 | 17 | 87 | 4 | 1,635 | 2,889 | 2,366 | 4,784 | 3,535 | 5,817 | 68 | 48 | 43,870 |
| `_Base.__init__` | 3,133 | 912 | 667 | 384 | 171 | 17 | 87 | 4 | 1,635 | 2,889 | 2,366 | 4,784 | 3,535 | 5,817 | 68 | 48 | 43,870 |
| `_base_set` | 3,133 | 912 | 667 | 384 | 171 | 17 | 87 | 4 | 1,635 | 2,889 | 2,366 | 4,784 | 3,535 | 5,817 | 68 | 48 | 43,870 |
| `_Custom.__contains__` | 2,445 | 137 | 1,014 | 0 | 6 | 0 | 10 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 248 | 278 | 62,667 |
| `_ent[ent_clear_budget_flag]` | 2,998 | 1,197 | 740 | 384 | 169 | 28 | 61 | 2 | 1,634 | 2,902 | 2,606 | 4,784 | 3,717 | 6,512 | 60 | 40 | 37,238 |
| `_rel_selectors_of` | 6,217 | 399 | 1,097 | 0 | 72 | 0 | 122 | 4 | 0 | 0 | 0 | 0 | 197 | 0 | 113 | 58 | 51,798 |
| `_rel_m[note_formula]` | 5,564 | 392 | 1,097 | 0 | 268 | 0 | 122 | 4 | 0 | 0 | 0 | 0 | 197 | 0 | 113 | 58 | 50,499 |
| `_rel_process` | 5,564 | 392 | 1,097 | 0 | 268 | 0 | 122 | 4 | 0 | 0 | 0 | 0 | 197 | 0 | 113 | 58 | 50,499 |
| `_q[_relations]` | 5,564 | 392 | 1,097 | 0 | 268 | 0 | 122 | 4 | 0 | 0 | 0 | 0 | 197 | 0 | 113 | 58 | 50,499 |
| `_compile_formula` | 2,952 | 827 | 665 | 2,099 | 454 | 513 | 61 | 2 | 664 | 564 | 31 | 368 | 319 | 5,827 | 64 | 40 | 36,355 |
| `_bud[bud_within_budget]` | 3,127 | 834 | 724 | 244 | 166 | 37 | 61 | 2 | 308 | 8 | 31 | 369 | 638 | 5,005 | 64 | 40 | 39,389 |
| `_ses_escalate` | 3,622 | 489 | 746 | 493 | 174 | 19 | 101 | 0 | 1,557 | 2,254 | 350 | 1,041 | 534 | 3,290 | 59 | 34 | 34,986 |
| `_ent[ent_ask]` | 2,812 | 776 | 699 | 244 | 166 | 26 | 61 | 2 | 299 | 4 | 30 | 368 | 636 | 4,814 | 60 | 40 | 35,332 |
| `_ent[ent_fresh_session]` | 2,952 | 827 | 665 | 244 | 166 | 16 | 61 | 2 | 300 | 6 | 31 | 368 | 319 | 5,004 | 64 | 40 | 35,299 |
| `_g[assume_formula]` | 2,952 | 827 | 665 | 244 | 166 | 16 | 61 | 2 | 300 | 6 | 31 | 368 | 319 | 5,004 | 64 | 40 | 35,299 |
| `_rel_m[wants_transfer]` | 6,088 | 351 | 925 | 0 | 21 | 0 | 122 | 2 | 0 | 0 | 0 | 0 | 197 | 0 | 113 | 58 | 37,902 |
| `_rel_m[_atom_selector]` | 1,827 | 48 | 655 | 0 | 22 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 197 | 0 | 273 | 219 | 41,888 |
| `_install_context.<locals>._context_session` | 2,772 | 776 | 699 | 244 | 166 | 12 | 61 | 2 | 299 | 4 | 30 | 368 | 636 | 4,814 | 60 | 40 | 33,932 |
| `_g[link_set]` | 2,758 | 827 | 661 | 244 | 166 | 16 | 61 | 2 | 295 | 4 | 31 | 368 | 318 | 5,004 | 53 | 18 | 33,556 |
| `_q[prepare_query]` | 2,605 | 776 | 643 | 244 | 166 | 13 | 61 | 2 | 294 | 2 | 30 | 368 | 318 | 4,814 | 49 | 18 | 31,548 |
| `_rel_transfer_terms` | 1,722 | 66 | 1,125 | 0 | 22 | 0 | 0 | 4 | 0 | 0 | 0 | 0 | 394 | 0 | 120 | 67 | 36,454 |
| `_install_context.<locals>._complete_check` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 35,166 |
| `_rel_init` | 3,018 | 197 | 556 | 0 | 135 | 0 | 61 | 2 | 0 | 0 | 0 | 0 | 198 | 0 | 64 | 40 | 26,852 |
| `_q[_query_all]` | 1,037 | 667 | 74 | 552 | 303 | 1 | 0 | 2 | 1,777 | 2,531 | 2,492 | 2,809 | 1,878 | 6,073 | 33 | 8 | 8,952 |
| `_formula_literal` | 1,957 | 44 | 322 | 0 | 53 | 7 | 60 | 0 | 0 | 0 | 0 | 0 | 197 | 0 | 3 | 11 | 24,399 |
| `_q[literal_of]` | 1,957 | 44 | 322 | 0 | 53 | 7 | 60 | 0 | 0 | 0 | 0 | 0 | 197 | 0 | 3 | 11 | 24,399 |
| `_rel_fresh` | 960 | 34 | 598 | 0 | 22 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 197 | 0 | 139 | 144 | 23,344 |
| `_Custom.get` | 888 | 37 | 822 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 197 | 0 | 98 | 140 | 22,676 |
| `_ent[ent_is]` | 783 | 433 | 1 | 140 | 3 | 2 | 121 | 0 | 1,335 | 2,896 | 2,360 | 4,416 | 3,081 | 1,360 | 0 | 0 | 7,563 |
| `_rel_m[_eq_links]` | 888 | 34 | 598 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 197 | 0 | 95 | 140 | 22,246 |
| `_rel_engage_transfer` | 911 | 34 | 550 | 0 | 11 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 198 | 0 | 64 | 40 | 18,741 |
| `_ent[ent_record_relevant]` | 1,203 | 570 | 84 | 0 | 0 | 0 | 0 | 0 | 226 | 2 | 246 | 367 | 317 | 2,586 | 4 | 0 | 10,130 |
| `_install_context.<locals>.verdict` | 315 | 58 | 25 | 0 | 0 | 4 | 0 | 0 | 9 | 4 | 1 | 1 | 2 | 191 | 4 | 0 | 4,000 |
| `_dvar_public` | 120 | 21 | 144 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 101 | 18 | 3,935 |
| `_ent[ent_is_many]` | 6 | 2 | 1 | 0 | 2 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 150 | 0 | 4 | 8 | 3,952 |
| `_rel_mention_number` | 342 | 112 | 0 | 0 | 0 | 0 | 101 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1,030 |
| `_ent[ent_record_cache_hit]` | 17 | 130 | 40 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 216 | 0 | 0 | 338 | 0 | 0 | 388 |
| `_ses_flush` | 0 | 0 | 139 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 283 |
| `_ent[ent_keep_budget_flag]` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 60 | 0 | 0 | 0 | 0 | 0 | 14 |
| `TableView.true_var` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |

Per function, where its calls come from (same mapping as above):

| function | 16 workloads | suite | called from (16 workloads) | called from (suite) |
|---|---:|---:|---|---|
| `_table_get` | 334,607 | 2,364,823 | relations_core.rs 288,014, session_live.py:_node 25,431, session_live.py:_rust_call 20,758, session_live.py:_dvar_public 404 | relations_core.rs 2,209,679, session_live.py:_rust_call 85,153, session_live.py:_node 66,056, session_live.py:_dvar_public 3,935 |
| `TableView.new_nodes` | 278,035 | 1,512,644 | discovery.rs 277,751, compile_loop.rs 284 | discovery.rs 1,512,078, compile_loop.rs 566 |
| `_ses_ensure` | 164,417 | 1,233,651 | relations_core.rs 100,874, query.rs 48,379, entry.rs 15,164 | relations_core.rs 632,842, query.rs 593,579, entry.rs 7,230 |
| `TableView.new_custom` | 152,431 | 907,711 | discovery.rs 152,280, compile_loop.rs 151 | discovery.rs 907,374, compile_loop.rs 337 |
| `_rel_m[_adapter]` | 108,300 | 757,719 | relations_core.rs 108,300 | relations_core.rs 757,719 |
| `_ses_discover` | 84,427 | 534,495 | relations_core.rs 70,708, session_glue.rs 11,065, query.rs 2,654 | relations_core.rs 474,893, session_glue.rs 35,229, query.rs 24,373 |
| `_BaseOf.get` | 174,067 | 320,222 | discovery.rs 174,067 | discovery.rs 320,222 |
| `_q[emit]` | 98,370 | 331,521 | compile.rs 88,639, session_glue.rs 9,385, compile.py (Python) 346 | compile.rs 260,947, session_glue.rs 67,272, compile.py (Python) 3,302 |
| `TableView.__len__` | 106,271 | 303,774 | discovery.rs 106,271 | discovery.rs 303,774 |
| `_ses_custom` | 47,474 | 332,038 | discovery.rs 47,471, compile_loop.rs 3 | discovery.rs 332,020, compile_loop.rs 18 |
| `_rel_m[enqueue]` | 47,186 | 331,440 | compile_loop.rs 47,186 | compile_loop.rs 331,440 |
| `_rel_m[_atom_var]` | 40,625 | 293,816 | relations_core.rs 40,625 | relations_core.rs 293,816 |
| `_ses_query_literal` | 52,361 | 135,873 | entry.rs 52,361 | entry.rs 135,873 |
| `_rel_m[_link_later]` | 23,587 | 126,025 | relations_core.rs 23,587 | relations_core.rs 126,025 |
| `_rel_m[_note_sides]` | 15,773 | 120,434 | relations_core.rs 15,773 | relations_core.rs 120,434 |
| `_ses_incomplete` | 36,815 | 96,067 | context.rs 21,752, entry.rs 15,063 | context.rs 66,707, entry.rs 29,360 |
| `_rel_sync_transfer` | 9,869 | 109,864 | query.rs 3,975, relations_core.rs 3,268, context.rs 2,626 | query.rs 43,853, relations_core.rs 34,847, context.rs 31,164 |
| `_census` | 107,547 | 0 | discovery.rs 107,547 |  |
| `_node` | 25,431 | 66,056 | query.rs 25,431 | query.rs 66,056 |
| `_q[query_lit]` | 25,431 | 66,056 | entry.rs 17,435, query.rs 7,996 | entry.rs 58,602, query.rs 7,454 |
| `_rel_add_role` | 6,094 | 84,913 | relations_core.rs 6,094 | relations_core.rs 84,913 |
| `_q[_ensure_twins]` | 21,715 | 67,142 | query.rs 21,715 | query.rs 67,142 |
| `_ses_assumption_lits` | 21,715 | 66,989 | context.rs 11,065, entry.rs 10,650 | context.rs 35,166, entry.rs 31,823 |
| `_rust_call` | 18,104 | 60,754 | compile.rs 18,104 | compile.rs 60,754 |
| `_rel_m[_share]` | 11,404 | 66,666 | relations_core.rs 11,404 | relations_core.rs 66,666 |
| `_q[_ensure_atoms]` | 13,719 | 59,698 | session_glue.rs 11,065, query.rs 2,654 | session_glue.rs 35,299, query.rs 24,399 |
| `_ses_init` | 26,517 | 43,870 | entry.rs 26,517 | entry.rs 43,870 |
| `_ses_solver_set` | 26,517 | 43,870 | session_glue.rs 26,517 | session_glue.rs 43,870 |
| `_table_set` | 26,517 | 43,870 | session_glue.rs 26,517 | session_glue.rs 43,870 |
| `TableView.bind` | 26,517 | 43,870 | session_live.py:_table_set 26,517 | session_live.py:_table_set 43,870 |
| `_core_rules` | 26,517 | 43,870 | session_live.py:TableView.bind 26,517 | session_live.py:TableView.bind 43,870 |
| `_ses_solver_get` | 26,517 | 43,870 | session_live.py:TableView.bind 26,517 | session_live.py:TableView.bind 43,870 |
| `_Custom.__init__` | 26,517 | 43,870 | session_live.py:TableView.bind 26,517 | session_live.py:TableView.bind 43,870 |
| `_BaseOf.__init__` | 26,517 | 43,870 | session_live.py:TableView.bind 26,517 | session_live.py:TableView.bind 43,870 |
| `_Slots.__init__` | 26,517 | 43,870 | session_live.py:TableView.bind 26,517 | session_live.py:TableView.bind 43,870 |
| `_Base.__init__` | 26,517 | 43,870 | session_live.py:TableView.bind 26,517 | session_live.py:TableView.bind 43,870 |
| `_base_set` | 26,517 | 43,870 | session_glue.rs 26,517 | session_glue.rs 43,870 |
| `_Custom.__contains__` | 4,140 | 62,667 | relations_core.rs 4,140 | relations_core.rs 62,667 |
| `_ent[ent_clear_budget_flag]` | 27,834 | 37,238 | sympy_api.py (Python) 27,834 | sympy_api.py (Python) 37,238 |
| `_rel_selectors_of` | 8,279 | 51,798 | session_glue.rs 8,279 | session_glue.rs 51,798 |
| `_rel_m[note_formula]` | 7,815 | 50,499 | query.rs 7,815 | query.rs 50,499 |
| `_rel_process` | 7,815 | 50,499 | query.rs 7,815 | query.rs 50,499 |
| `_q[_relations]` | 7,815 | 50,499 | session_glue.rs 3,983, query.rs 3,832 | session_glue.rs 25,760, query.rs 24,739 |
| `_compile_formula` | 15,450 | 36,355 | session_glue.rs 11,065, discovery.rs 4,097, compile_loop.rs 288 | session_glue.rs 35,289, discovery.rs 750, compile_loop.rs 316 |
| `_bud[bud_within_budget]` | 11,658 | 39,389 | entry.rs 11,044, context.rs 614 | entry.rs 35,389, context.rs 4,000 |
| `_ses_escalate` | 14,763 | 34,986 | entry.rs 11,525, context.rs 3,238 | context.rs 18,561, entry.rs 16,425 |
| `_ent[ent_ask]` | 11,037 | 35,332 | sympy_api.py (Python) 11,037 | sympy_api.py (Python) 35,221, test_history.py (Python) 110, test_invariants.py (Python) 1 |
| `_ent[ent_fresh_session]` | 11,065 | 35,299 | context.rs 11,065 | context.rs 35,286, test_budget_cone.py (Python) 13 |
| `_g[assume_formula]` | 11,065 | 35,299 | context.rs 11,065 | context.rs 35,299 |
| `_rel_m[wants_transfer]` | 7,877 | 37,902 | session_glue.rs 7,877 | session_glue.rs 37,902 |
| `_rel_m[_atom_selector]` | 3,243 | 41,888 | relations_core.rs 3,243 | relations_core.rs 41,888 |
| `_install_context.<locals>._context_session` | 10,983 | 33,932 | entry.rs 10,983 | entry.rs 33,932 |
| `_g[link_set]` | 10,826 | 33,556 | context.rs 10,826 | context.rs 33,556 |
| `_q[prepare_query]` | 10,403 | 31,548 | entry.rs 10,403 | entry.rs 31,548 |
| `_rel_transfer_terms` | 3,520 | 36,454 | relations_core.rs 3,520 | relations_core.rs 36,454 |
| `_install_context.<locals>._complete_check` | 0 | 35,166 |  | catch_count.py (Python) 35,166 |
| `_rel_init` | 4,271 | 26,852 | session_glue.rs 4,271 | session_glue.rs 26,852 |
| `_q[_query_all]` | 20,237 | 8,952 | query.rs 20,237 | query.rs 8,952 |
| `_formula_literal` | 2,654 | 24,399 | query.rs 2,654 | query.rs 24,399 |
| `_q[literal_of]` | 2,654 | 24,399 | query.rs 2,407, entry.rs 247 | query.rs 24,094, entry.rs 305 |
| `_rel_fresh` | 2,096 | 23,344 | relations_core.rs 2,096 | relations_core.rs 23,344 |
| `_Custom.get` | 2,184 | 22,676 | relations_core.rs 2,184 | relations_core.rs 22,676 |
| `_ent[ent_is]` | 16,931 | 7,563 | sympy_api.py (Python) 16,038, relations_core.rs 893 | relations_core.rs 6,075, sympy_api.py (Python) 1,488 |
| `_rel_m[_eq_links]` | 1,954 | 22,246 | relations_core.rs 1,954 | relations_core.rs 22,246 |
| `_rel_engage_transfer` | 1,810 | 18,741 | relations_core.rs 1,810 | relations_core.rs 18,741 |
| `_ent[ent_record_relevant]` | 5,605 | 10,130 | sympy_api.py (Python) 5,605 | sympy_api.py (Python) 10,130 |
| `_install_context.<locals>.verdict` | 614 | 4,000 | sympy_api.py (Python) 610, entry.rs 4 | catch_count.py (Python) 4,000 |
| `_dvar_public` | 404 | 3,935 | compile.py (Python) 404 | compile.py (Python) 3,935 |
| `_ent[ent_is_many]` | 175 | 3,952 | relations_core.rs 175 | relations_core.rs 3,952 |
| `_rel_mention_number` | 555 | 1,030 | relations_core.rs 555 | relations_core.rs 1,030 |
| `_ent[ent_record_cache_hit]` | 743 | 388 | sympy_api.py (Python) 743 | sympy_api.py (Python) 388 |
| `_ses_flush` | 142 | 283 | query.rs 142 | query.rs 283 |
| `_ent[ent_keep_budget_flag]` | 60 | 14 | sympy_api.py (Python) 60 | sympy_api.py (Python) 14 |
| `TableView.true_var` | 0 | 2 |  | compile.py (Python) 2 |

**Owners** (each nonzero function; proposed where no ruling names one):
| what | functions | 16 workloads | suite | owner |
|---|---|---:|---:|---|
| Rust entered through a `Relations` wrapper calling back by name or reading a view | `_rel_m[_adapter]`, `[enqueue]`, `[_atom_var]`, `[_link_later]`, `[_note_sides]`, `[_share]`, `[_atom_selector]`, `[_eq_links]`, `_rel_add_role`, `_rel_transfer_terms`, `_rel_fresh`, `_rel_mention_number`, `_rel_engage_transfer`; and under them `_ses_ensure`, `_ses_discover`, `_Custom.get`, `_Custom.__contains__`, `_ent[ent_is]`, `_ent[ent_is_many]`, and most of `_table_get` (the `.table` property read at relations_core.rs :786, :2270, :2332, :2468) | 689,217 | 5,040,907 | the formula step: relations_core.rs is closed to part 3 (condition 2), and formula already holds the four `.table` sites |
| Rust entered through a `Session` or `Engine` wrapper calling back by name or reading a view | `_ses_ensure`, `_ses_discover`, `_ses_incomplete`, `_ses_escalate`, `_ses_custom`, `_ses_flush`, `_ses_query_literal`, `_ses_assumption_lits`, `_ses_init`, every `_q[...]` and `_g[...]`, `_bud[bud_within_budget]`, `_ent[ent_fresh_session]`, `_install_context.<locals>._context_session`, `_rel_process`, `_rel_init`, `_rel_sync_transfer`, `_rel_selectors_of`, `_rel_m[wants_transfer]`, `_rel_m[note_formula]`, `_compile_formula`, `_formula_literal`, `TableView.new_nodes`, `new_custom`, `__len__`, `_BaseOf.get` | 1,474,486 | 6,172,024 | part 3's follow-up (ruled: session_live's converted calls per function) |
| session_live.py calling itself | per `Session` built: `_table_set`, `TableView.bind`, `_core_rules`, `_ses_solver_get`, `_ses_solver_set`, `_base_set`, `_Custom.__init__`, `_BaseOf.__init__`, `_Slots.__init__`, `_Base.__init__`; `_table_get` under `_node` and `_rust_call`; `_rust_call`, `_node` | 232,212 | 462,234 | part 3's follow-up |
| entry frames: sympy_api.py's `_engine_ask`, `_ask_general`, `_ask` calling an `Engine` method | `_ent[ent_clear_budget_flag]`, `[ent_is]`, `[ent_ask]`, `[ent_record_relevant]`, `[ent_record_cache_hit]`, `[ent_keep_budget_flag]`, `_install_context.<locals>.verdict` | 61,927 | 84,479 | needs a ruling: one Python frame per `Engine` method the conversion calls (`_ent` exists because a builtin does not bind as a method). Not a named callback or conversion today. Proposed: part 3's follow-up lists them as public-entry dispatch frames or replaces `_ent` by a Rust descriptor |
| Python's compiler running on a converted query (`_compile_formula` falls back to `PY_COMPILE` when Rust's `compile` returns False: too deep or unreadable) | `_q[emit]` and `_dvar_public` from compile.py; `TableView.true_var` (suite, 2) | 750 (fuzz, dev, zero, transfer:7:60, transfer2:3:40) | 7,239 | a per-query fallback inside ported code, not read further here. Proposed: the formula step (it owns formula.rs and the compile path's node reading) |
| instruments | `_census` (SESSION_REPORT); `_complete_check` and `verdict` from catch_count.py; `_ent[ent_ask]`, `_ent[ent_fresh_session]`, `verdict` called by three test files (124) | 107,547 | 39,290 | none: the probe's and the suite plugin's own calls |
| ses_cont.rs: `sc:key_hash`, `sc:key_eq` (Python `hash()` and `==` per session-dict lookup) | counters 568, 569 | 1,127,854 / 1,629 | 10,006,834 / 26,491 | part 3's follow-up (ruled: SesDict by term id) |

`sc:key_hash` / `sc:key_eq` in the suite are from a second pass on the same tree and .so with `-p plant_count` and without
the probe (`sa-port-263/suite-counts`: 127 failed, 5991 passed, 23 skipped, 18 xfailed, 6 warnings in 207.68s (0:03:27)); the bar's suite on f252daf had 10,005,845 / 27,692.

**Files the follow-up would touch**, against the formula step's files (its branch port/formula at 08a2004 against 0192b35,
and the edits its line in the siblings file names):
- SesDict by term id: ses_cont.rs (`sd_find`, :86), session.rs (counter names; where the id of a key comes from),
  test_session_boundary.py. session.rs is formula's (153 lines changed on its branch).
- session_live's converted calls: the by-name calling sites are in relations_core.rs (formula's, and closed to part 3),
  query.rs, session_glue.rs, compile_loop.rs (formula's branch changes all three), entry.rs, context.rs, discovery.rs,
  compile.rs (not on formula's branch), session.rs (`named`, `core_of`, `table_of`; formula's) and session_live.py
  (formula edits :1001).
- So neither half is clear of formula's files. Only the entry.rs / context.rs / discovery.rs / compile.rs sites and
  ses_cont.rs itself are files formula does not change, and each still needs session.rs or session_live.py. The follow-up
  waits for formula's bar to land.

Not done in this link: no source change, no count change; the fallback in `_compile_formula` was counted, not read;
the Rust calling site of each by-name call was read only by `rg` per method name, not site by site.
