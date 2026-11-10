# State part 3: the session/solver boundary (issue 323)

Branch port/state-part3 from rust-slice c822173. Unbarred, unlanded: landing waits for (iii) (sa-port-225), then a rebase and
a full bar on the merged tree (planner's state part 3 go, condition 3). Plants 420-449, counters 550-579.

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

Boundary plan (not done here): the `_rel_*` wrappers call relations_core.rs, which part 3 may not touch (condition 2), so
dropping their per-call solver argument is (iii)'s or needs the planner. The `_ses_*`/`_q`/`_ent` wrappers can use the core's
copy without changing SessionCore's struct; `_gave_up`/`_exhausted` (engine.py) are unread here. Session.solver then stays only as a read-only view for the public/test readers.

## Sub-part 4: public-entry dispatch list
From test_install_order.py's public rows (each with its per-entry test):
| public name | held as | dispatch | test |
|---|---|---|---|
| `satassume.DictCache`, `ObjectCache` (also `engine.`, `sympy_api.DictCache`) | type | `DictCache.__new__` (session_live.py `_install_factcache`) | `test_install_list_entry[satassume.DictCache]` etc.; plant 422 |
| `satassume.relations.relation_atom`, `sympy_api.relation_atom` | function | `RELATION_ATOM_IMPL` slot (term_live.py:993) | `test_install_list_entry[satassume.relations.relation_atom]`; plant 421 |
| `P`, `And`, `Or`, ... (satassume.sat.formula) | classes | `p_install` import hook, refuses after the module is imported | p_install's own refusal |

## Not run
The landing bar (suite by id against base with handler rows, dev/fuzz MATCH, workload plants); sub-part 1's full inventory;
sub-part 5 (waits for (iii)); sub-part 6 readouts ([108] memo cost, scope fallback rise, session-lasting ids; rk:intern:engine).
