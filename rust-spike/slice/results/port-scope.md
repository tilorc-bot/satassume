# Step scope: scope.py whole in Rust (issue 323)

## What moved
- **scope.py's six port rows** (sa-port-124, sa-port-126), in `solver_rs/src/scope_core.rs`: `Scope` (pyclass `ScopeRs` :42),
  `_custom_pred` :143, `linked_terms` :167, `scope_of_atoms` :201, `extension_atoms` :240, `theory_scope` :281, plus
  `scope_install` :311, which builds `EMPTY`. `session_live.py` `_install_scope` patches scope.py's module attributes and the
  by-name imports in engine.py (`Scope`, `_EMPTY_SCOPE`, `scope_of_atoms`, `theory_scope`) and sympy_api.py
  (`_theory_scope`), and rebinds the `scope=EMPTY` defaults of `Session.__init__` and `Engine._fresh_session`. `undo`
  restores all of them. ref.py is left Python's on purpose, as for `_REL_FUNCS`.
- **Counters 123-132** (session.rs; NAMES/COUNTS 133) and **plants 91-96** (relations_core.rs, after `spec-row-flip` 90).
  These numbers were renumbered in the rebase on adapters part A, which kept 122 (`rel:cb_spec_read`) and plant 90.
- **Called back, all ruled:** `atoms_of` (sat/formula.py, Formula input until the formula step), `affine_pair` (term_live's
  C1 wrapper; Python's body runs only in kept queries), `transfer_wanted` (theories/transfer.py) and each extension's
  `facts_for` (the user's input).
- **New workload `scope`** (`scope_wl.py`, `live.py scope`): 169 queries built from the code reached, with custom
  predicates and extensions. It's in the repo, and its answers are compared Python against Rust.
- **term_live's `linked-drop` plant (C1) is superseded by the move.** Rust's `scope_of_atoms` doesn't call the module's
  `linked_terms` attribute, so `linked-drop` can't fire. `linked-no-rel` takes its place.

## SHAs
Tested **c52a5bd**: port/scope rebased on rust-slice d91ee15 (adapters part A), with the rebase done before testing. Rows
are on pareto1 at `~/sp19/sa-rust-ids-work/sa-port-126/bar-scope2/` (`sum.txt`, `commands.txt`, `config.txt`). The
`.so`'s sha256 is 2143124f…, and the base is 5c5's suite rows (`sa-port-122/bar-5c5/suite`). The landing source is the
commit carrying this file. Between it and c52a5bd are only docs, which no run executes: sa-port-126's handoff,
port-ownership.md/.tsv and this report. **Incoming diff at landing:** empty, because rust-slice was still d91ee15.

Bar 1 (`bar-scope/`, on 7d80f75 before the rebase) is kept as evidence. Its numbers equal bar 2's except where noted
below. It was rerun because the rebase brought in code the run executes: adapters part A (relations_core.rs, session.rs,
session_live.py) and 6g(a) (knowledge_live.py, term/dispatch.rs).

## The bar (sa-port-126/bar-scope2)
1. **Suite by id against 5c5's rows:** 5,958 passed, 126 failed, 23 skipped, 18 xfailed, 6,125 ids. New 0, gone 0,
   changed outcome 0. Passed: 5,957 with no firing and 1 with a firing (`test_ci_stream_reports_only_what_replays`). S's
   standing: S's gate is met except for the 46 named stub failures, one cause.
2. **Fresh dev, fuzz, loop and scope:** answers and state MATCH, with every control MATCHing. Answers are unchanged:
   dev 31cd0945c07f02a6 (1,985 q), fuzz 173502b6ef285ad6 (3,000 q), loop 09238b2537e54383 (420 q). The new workload's
   answers are scope 12e06b0586faee40 (169 q). Rust runs made 0 Python solvers.
3. **Plants:** see the table below. Each moved item has a plant that fires and is caught. Two plants are caught by no live
   workload, because nothing in the engine reads `Scope.linked_terms`. The suite and `funcs` catch them.
4. **Quiet handlers, suite:** 39 rows in 2 tests, the same multiset as base:
   - `_consistent` AttributeError: 34 on `_ok` and 4 on `_rb_clauses` (the named needs-internals case);
   - `Engine._build_context` "Already mutably borrowed": 1, in `test_protocol_on_fuzz` (the 46-stub cause).

   `caught` rows per id match base. **Quiet catches at engine.py:1906** (inside `_build_context`, :1878): 1, in the
   suite, as on base. There are 0 on dev, fuzz, loop and scope, where all 14 handler files have 0 rows. The 12 dev/fuzz
   plant handler files also have 0 rows. TermFault 0, in the plain suite and in both suite-plant runs.
5. **Known differences in answers or read state:** none. Tests: 510 passed (5c5's ten files plus test_scope_core.py),
   and `relations_direct.py` exited 0.

## Plants (fired; D = DIFFER)
| plant | item | dev | fuzz | loop | scope | caught by |
|---|---|--:|--:|--:|--:|---|
| theory-no-assume | theory_scope | 1,087 D | 5,918 D | 244 | 299 D | dev, fuzz, scope, funcs |
| scope-no-affine | scope_of_atoms | 727 | 33 D | 244 | 41 | fuzz, funcs |
| custom-never | _custom_pred | 12 | 0 | 0 | 308 D | scope, funcs |
| ext-shallow | extension_atoms | 0 | 0 | 0 | 496 D | scope, funcs; suite by chance (below) |
| linked-no-rel | linked_terms | 586 | 11,039 | 0 | 294 | funcs only |
| scope-linked-empty | Scope (`linked_terms` field) | 0 | 0 | 0 | 0 | suite (2 changed), funcs |
| `linked-drop` (term_live, C1) | — | | | | | **superseded by the move** (see above) |

"funcs" is `test_scope_core.py::test_scope_plant_is_seen`. It runs Python's and Rust's version of each function on the
same arguments, call by call, and every plant there fires and is caught. The `scope` workload's DIFFERs show up in the
session counts and stream; no answer moved under any plant.

**Not caught by any live workload: `scope-linked-empty` (void) and `linked-no-rel` (fires but MATCHes on every
workload).** Both change only `Scope.linked_terms`, and nothing in the engine reads it: Relations reads only `.glue` and
`.transfer` (relations.py:861-865). Its only readers are ref.py, on its own Python scope, and tests/test_scope.py. Under
`scope-linked-empty` the suite changed 2 ids, passed to failed: `test_scope.py::test_glue_from_a_relation_atom_on_either_side`
and `::test_linked_terms_are_arguments_and_sides_without_numbers`. The suite wasn't run under `linked-no-rel`, because
`zero` selects only plants that fire 0 on dev.

**ext-shallow in the suite is caught by chance.** It fired 308 times in both bars. Bar 1 changed one id
(`test_verify_soundness.py::test_fuzz_old_style_symbols`, passed to failed, a wrong True on
`ask(Q.positive(-c), Q.lt(c, c) | Q.eq(c + k, -k))`). Bar 2 changed none. That test is a Hypothesis fuzzer that isn't
derandomized (`FUZZ`, tests/test_verify_soundness.py:55), so whether it draws a case the plant breaks varies by run. The
`scope` workload catches this plant deterministically (496 D).

## Reached (and by which workload)
Counters on Rust, dev / fuzz / loop / scope:
- `scope:theory_scope`: 1,089 / 5,970 / 244 / 301
- `scope:extension_atoms`: 1,089 / 5,970 / 244 / 301
- `scope:scope_of_atoms`: 1,089 / 5,970 / 244 / 301
- `scope:custom_pred`: 3,155 / 20,372 / 560 / 1,629
- `scope:new` (Scope): 362 / 5,937 / 0 / 260
- `scope:linked_terms`: 362 / 5,937 / 0 / 260

Callbacks:
- `cb_atoms_of`: 1,865 / 8,702 / 488 / 1,003
- `cb_affine_pair`: 727 / 35 / 244 / 41
- `cb_transfer_wanted`: 362 / 5,935 / 0 / 260
- `cb_facts_for`: 12 / 0 / 0 / 536

Coverage by workload:
- dev and fuzz reach all six items.
- loop reaches every item except `Scope` and `linked_terms`.
- **`_custom_pred`'s true case and `extension_atoms`' extension path are caught only on the `scope` workload.** On dev,
  `custom-never` fires 12 times and changes nothing, and ext-shallow is void on dev, fuzz and loop.

The counters fire: `test_scope_funcs_agree` asserts every `scope:` counter is above 0.

## Kept reasons (planner ruling, 03:42 UTC 8 Nov)
Share of queries kept, per reason, of the queries the engine converts or keeps (`converted` plus every `kept:*`, as
counted in term_live.py:211-214). Base is 5c5's bar (`sa-port-122/bar-5c5`, live and extra knowledge.json).

| workload | queries at conversion | out-of-scope | refused | other named exceptions | base |
|---|--:|--:|--:|--:|---|
| dev | 1,221 | 24 (1.97%) | 0 | 0 | the same: 24 of 1,221, refused 0 |
| fuzz | 2,998 | 0 | 0 | 0 | the same |
| loop | 384 | 0 | 0 | 0 | the same |
| scope | 169 | 0 | 0 | 0 | new workload; no base |

**No rise in any share.** `refused` is term_live's whole-query counter (term_live.py:913). It's absent from all four
files, which means 0. The same dict is written to `.knowledge.json` (knowledge_live.py:52, :196). A planted refusal
showed it reaching live output in port-4d.md (dev 1,985 refused). Per-row `*:kept` counters (`core:kept`, `py:kept` and
the like) aren't whole-query fallbacks and aren't in the table. `const_value`'s fire count isn't counted on this branch:
its counter comes with 6d.

## Module count (count rule)
**scope.py counts whole.** Of its seven functions, six are Rust (above). The seventh, `affine_pair`, runs as term_live's
C1 wrapper, and its Python body runs only in kept queries. The rest of scope.py is a docstring, imports and the `SIGN_PREDS` frozenset, which engine.py and term_live read as data; it isn't code that runs.
`_is_number`'s fallback (`rel:py_is_number`) is relations.py's ruled C1 path, not scope.py's.

**`term:no-query:affine_pair` is 0 on bar 2's dev run** (absent from dev-rust.knowledge.json), against `term:no-table`
9 and `kept:out-of-scope` 24. The same holds on bar 1. All 9 no-table calls ran inside kept queries, the ruled case.
Fuzz, loop and scope have neither counter. The counter fires: calling the installed wrapper outside a query on orion
gave no-table 1 and no-query 1 (sa-port-126).

So scope.py adds one to the module count. I haven't recounted the total, because the last two reports on rust-slice give
different totals: port-6g.md says 9 of 32 and port-adapters.md says 7 of 32. The realroots/`value_units` footnote stands.
The ownership TSV's counts after this step are: landed Rust 462, landed called back 17, landed Python 18, kept as type 2,
named Python 239, named called back 2. The summary table at the top of port-ownership.md predates 5c4 and 5c5 and isn't
redone here.

## Owed-list additions
- **`Scope.linked_terms` is computed per query and has no engine reader:** a Python removal candidate. The architect
  already holds this at OWED-satassume-rust.md [84:17]. Until it's removed, `scope-linked-empty` and `linked-no-rel`
  have no live catch.
- ext-shallow's suite catch depends on Hypothesis' draw. The `scope` workload is its deterministic catch.

## Not run
Moved to "before any backend PR", and none quoted as met:
- the mutant 2, 5, 6, 7, 9 rerun and mutlive's control;
- the boundary rescore and suite column;
- the final drop score and its lost rows;
- the suite split with Python's counter;
- `order:_rows`' evidence (not caught meanwhile);
- the `_forms` guard test;
- history and seed reruns (seed1 not run);
- forced moves;
- the native path;
- timing.

Also not run: the suite under the four plants that fired on dev (`zero` doesn't select them; `funcs` catches them).

Other notes:
- Mutants 2, 5, 6, 7, 9 still rest on the API fuzzer alone. 10 of the 25 boundary mutants have no real-engine catch, and
  the boundary suite column wasn't run.
- **Speed not measured.**
- The `_n_conflicts` view in rust_plugin.py is a test-plugin shim, not a port (64 tests).
- The public-API `test_incremental_matches_fresh` family is still owed, as a test-only step before 5c7 (pure Python first,
  adds only, and a Python failure is a finding against main).
- `tests/test_relations.py::test_equality_sharing_is_needed_and_works` is unedited and still named needs-internals. This
  step doesn't touch it.
