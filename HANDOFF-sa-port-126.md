# HANDOFF sa-port-126: step "scope" (issue 323), bar rerunning on the rebased source; report not written

Clone /home/tilo/dev/sa-port-7, branch `port/scope` (pushed, force after rebase). Head = this handoff commit; the **tested source is
c52a5bd** (port/scope rebased on rust-slice d91ee15, adapters part A). Between c52a5bd and this commit: port-ownership.md/.tsv and
this file only (docs, no run executes them).

## Running
Bar 2 on c52a5bd, started ~03:35Z: `pareto1:~/sp19/sa-rust-ids-work/sa-port-126/bar-scope2/` (wait for `done.txt`, then read
`sum.txt` by `cut -c1-250 | sed -n`, ~140 lines). Wrapper `pareto1:~/sp19/bar-scope2-run-126.sh` (5c5's config with BASE =
sa-port-122/bar-5c5/suite, the 6 scope PLANTS, TESTS = 5c5's ten + test_scope_core.py, WLS="loop scope", SUITE_PLANTS=zero,
DIRECT and N as 5c5). Launcher log `~/sa-rust-ids-work/sa-port-126/bar-scope2.launch.log`. `machine run` returns at once
(`setsid` detaches), so the lease lapses; the job keeps running, as in 5c5's runs. Nothing to stop.
Why rerun: the rebase brought adapters part A (relations_core.rs, session.rs, session_live.py) and 6g(a) (knowledge_live.py,
term/dispatch.rs), code the run executes. Conflicts resolved: counter 122 stays adapters' `rel:cb_spec_read`, scope's move to
123-132 (NAMES/COUNTS 133); plant 90 stays `spec-row-flip`, scope's are 91-96. orion after the rebase: test_scope_core.py +
test_relations_core.py 96 passed.

## Bar 1 on 7d80f75 (pre-rebase; superseded as the landing run, kept as evidence)
`pareto1:~/sp19/sa-rust-ids-work/sa-port-126/bar-scope/sum.txt`, .so ca9dbabe…, all phases but seed1.
1. Suite vs 5c5's rows: 5,958 passed / 126 failed / 23 skipped / 18 xfailed, 6,125 ids; new 0, gone 0, changed 0. Passed 5,957 no
   firing + 1 with (`test_ci_stream_reports_only_what_replays`). Handler rows 39 in 2 tests, multiset = base (34 `_ok`, 4
   `_rb_clauses`, 1 `_build_context` "Already mutably borrowed" in test_protocol_on_fuzz). TermFault 0.
2. dev 31cd0945c07f02a6 (1,985 q), fuzz 173502b6ef285ad6 (3,000), loop 09238b2537e54383 (420): MATCH, controls MATCH, 0 Python
   solvers on Rust; all handler files 0 rows. Tests 510 passed, relations_direct exit 0.
3. Plants (fired; D=DIFFER), dev / fuzz / loop:
   - custom-never 12 / 0 / 0, all MATCH;
   - ext-shallow 0 / 0 / 0; selected by `zero` for the suite, where it fired 308 and changed `test_verify_soundness.py::test_fuzz_old_style_symbols` passed→failed;
   - linked-no-rel 586 / 11,039 / 0, all MATCH;
   - scope-linked-empty 0 / 0 / 0; suite fired 12 and changed 2 (`test_scope.py::test_glue_from_a_relation_atom_on_either_side`, `::test_linked_terms_are_arguments_and_sides_without_numbers`);
   - scope-no-affine 727 / 33 D / 244;
   - theory-no-assume 1,087 D / 5,918 D / 244.
   Suite-plant runs: handler multiset = base.
4. `scope` workload (scope_wl.py, c8d2bb4, `bar-scope-wl/`, same .so hash): 169 q, answers 12e06b0586faee40, Python against Rust
   MATCH, control MATCH, handler files 0 rows. Plants: custom-never 308 D, ext-shallow 496 D, theory-no-assume 299 D (session
   counts differ, no answer moved), linked-no-rel 294 MATCH, scope-no-affine 41 MATCH, scope-linked-empty 0.
5. Counters, dev / fuzz / scope: theory_scope 1,089 / 5,970 / 301; extension_atoms 1,089 / 5,970 / 301 (the default engine does
   pass the default registry); custom_pred 3,155 / 20,372 / 1,629; cb_facts_for 12 / 0 / 536; Scope new 362 / 5,937 / 260;
   cb_affine_pair 727 / 35 / 41.

## Facts found
- **`term:no-query:affine_pair` is 0 on dev** (absent from dev-rust.knowledge.json while `term:no-table:affine_pair` is 9, against
  `kept:out-of-scope` 24). Fuzz has neither. Shown to fire: calling the installed wrapper outside a query on orion gave no-table 1,
  no-query 1. So all 9 ran inside kept queries (the ruled case). Recheck on bar 2's dev knowledge.json.
- **`Scope.linked_terms` has no reader in the engine.** Relations reads only `.glue` and `.transfer` (relations.py:861-865).
  Only ref.py, on its own Python scope, and tests/test_scope.py read it. So `scope-linked-empty` is void on every live workload
  (the suite and `funcs` catch it), and `linked-no-rel` fires but MATCHes everywhere live (`funcs` catches it). This is a Python
  removal candidate for the owed list: `linked_terms` is computed per query and nothing reads it.
- term_live's `linked-drop` (C1) is void by the move: Rust's `scope_of_atoms` doesn't call the module attribute. `linked-no-rel`
  takes its place.
- Count rule: scope.py's Python per query is only ruled callbacks: `atoms_of` (Formula input, until the formula step),
  `affine_pair` (C1 wrapper; Python's body only in kept queries), `transfer_wanted` (theories/transfer.py, not scope.py) and
  `facts_for` (the user's extensions, input). `_is_number`'s fallback (`rel:py_is_number` 8 on dev) is relations.py's ruled C1
  path. Proposed: scope.py counts whole, 9 of 32 (8 + scope, keeping the realroots/value_units footnote), if bar 2 confirms.

## Left
1. Read bar 2's sum.txt and state the five items (as in bar 1 above). Also check `term:no-query:affine_pair` and the scope
   counters in `live/dev-rust.knowledge.json` and `live/*-rust.session.json`.
2. **New ruling (kept reasons, ~/dev/architect/briefs/addenda/sa-port-kept-reasons-ruling.txt):** report the share of queries kept
   per reason (out-of-scope, refused, each named exception) on each workload, against base (5c5's bar-5c5/live and extra
   knowledge.json `kept:*` counts). A rise is a finding even when answers MATCH.
3. Write `rust-spike/slice/results/port-scope.md` in port-5c5.md's form (all the brief's MUST STAY items). port-ownership.md
   (:85, :135) and the TSV are already updated (6 rows → "landed scope (port-scope.md)", Rust). The summary table at the top of
   port-ownership.md predates 5c4/5c5. TSV counts now: landed Rust 462, landed called back 17, landed Python 18, kept as type 2,
   named Python 239, named called back 2. Say so; don't recount it here.
4. Then `bar.sh land c52a5bd` without PUSH. If rust-slice moved again, apply the rebase rule. Then `PUSH=1 sh
   rust-spike/slice/p1/bar.sh land c52a5bd`, then `agent report`.
