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
