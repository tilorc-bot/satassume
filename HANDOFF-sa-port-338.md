# HANDOFF sa-port-338: witness check, test-only fix committed, suite by id running detached; NOTHING IS LANDED

Branch port/witness-check, worktree ~/sa-rust-ids-work/sa-port-328/wt (clone ~/dev/sa-port-19), on rust-slice 32ba9a3.
Handed off at the context budget, 10:20Z 19 Nov, with the suite job running and 337's bar not yet ended (~11:45Z).

**SHAs.** 786410d: the bar's SHA (337's rerun, pareto0), with S1, digests and iv. **81e6561e: the new SHA to land**,
786410d plus the two handoff commits (results and HANDOFF only) plus two test-only commits. Guarded source
(satassume/, rust-spike/slice/ without results/) is identical between 786410d and 81e6561e (stage338.sh refuses
otherwise), so the .so is the same build: venv .so cad764d46471b1c6, bench .so 0982a28074215658.

## Done

- (i) 32c167ee: tests/test_templates.py::test_template_key_error_is_not_read_as_inconsistent and
  tests/test_p4_review.py::test_reregistered_template_key_does_not_reuse_compiled_pattern pop their own classes'
  keys off the default registry in a `finally`, then drop what `register()` drops. Assertions unchanged (reindented).
- (ii) 81e6561e: tests/test_witness.py has an autouse fixture `clean_default_registry` (takes every user's template
  and declared module off the default registry before each test, puts them back after), and one kept test,
  `test_a_template_left_on_the_default_registry_makes_the_check_fall_through`. No assertion changed, no test dropped.
- **New finding, fixed by (ii): 786410d's test_witness.py also broke later tests.** Its `users_knowledge` fixture put
  back a copy of the registry's lists taken before `register()` loaded the built-in modules. A declared module
  registers itself only once, so after the `[template]` case the templates of rootof, special, nodes and limits
  were gone for the rest of the process. On orion, python, one process, 786410d: test_witness.py then
  tests/test_rootof.py, test_notmpl_limits.py and test_nan_arguments.py gives **21 failed** (18 in test_notmpl_limits.py,
  3 in test_rootof.py; ids in results/tools338/lost-templates-786410d-ids.txt); the three files alone, 154
  passed; the same on 81e6561e, 257 passed. The fixture now leaves the template registry to
  `clean_default_registry`, which removes users' entries only. 336's suite by id did not show it (off against base
  0 ids), which is the workers' distribution. **337's bar suite rows on 786410d can show these ids** in any worker
  that ran `[template]` before those files: check them when reading the bar, as for the 7.
- Shown on orion, python, one process, the two once-leaking tests first, switch off and on (~/sa-rust-ids-work/
  sa-port-338/indep): 786410d 7 failed, 3 users' templates at the end; 32c167ee ((i) alone) 537 passed, 0 left;
  81e6561e with the two files as on 786410d ((ii) alone) 538 passed, the 3 templates still there at the end
  (restored); 81e6561e 538 passed, 0 left. first, last, interleaved and seed:1 with the switch on: 538 passed each.

## Running detached (not read)

go338.sh 81e6561e 32ba9a3, launched 10:16Z, ends about 10:32Z: pareto1 shared lease 05d3a448, job338.sh.
**End marker: orion ~/sa-rust-ids-work/sa-port-338/go-end-81e6561e.txt** (`END rc time`). It holds:
- job-81e6561e/suite-{on,off,base}-{rust,python} (exit.txt, rows) and suite-cmp.txt (cmp329.py). Expected: off against
  base 0 ids differ, on against off 0 ids differ, on both backends, except the one new test id (absent on base).
  786410d's exit lines for comparison: python base/off 0 failed, on 7 failed; rust base/off 127 failed, on 134.
- job-81e6561e/order/*.txt and order.out: 24 one-process runs (rust and python, switch 0 and 1, modes first, last,
  interleaved, seed:1-3) of test_templates.py, test_p4_review.py and test_witness.py. Each `mode` line must say
  seven_passed 7/7; read `NOT-PASSED` lines by id (a shuffle may show an older order dependence inside
  test_templates.py: compare with the same seed on trees/786410d before calling it new).

## Not done, in order

1. Read go-end-81e6561e.txt, suite-cmp.txt and `grep -h ^mode job-81e6561e/order/*.txt`. Any moved id: Status: question.
2. Read 337's bar on 786410d after ~/sa-rust-ids-work/sa-port-337/gobar-end.txt exists (HANDOFF-sa-port-337.md item 2:
   direct.txt ends `exit 0`, "suite: no rows" absent, witness:on rows, plants 749-752 and 754, quiet handler rows,
   `python3 ~/sa-rust-ids-work/sa-port-337/tools/wall336.py ~/sa-rust-ids-work/sa-port-337/bar/bar`). For its suite
   rows say which worker ran the two leaking tests, and which ran `[template]` before the 21 ids above.
3. witness-check.md: section 8 (the 7 ids fixed, the 21, the order runs) and the bar's sections on 786410d; header SHA.
4. Land 81e6561e's head: `bash rust-spike/slice/p1/bar.sh land 81e6561e`, read it, then `PUSH=1`. The guard compares
   satassume/ and rust-spike/slice/ (results excepted), so tests/ does not trip it; `bar.sh land 786410d` passes too.
   If it refuses, Status: question; do not bypass. Then delete origin bar/witness-check-786410d. Rule [91]: not while
   another session's full bar runs.
5. `git diff --stat 786410d..HEAD` shows tests/ (3 files), HANDOFF-sa-port-336/337/338.md and rust-spike/slice/results/
   only; nothing under satassume/ or other source.
6. OWED to name: [148] as ruled; Engine.stats' 13th key on the default path; ent_record_certified has no tick; bar.sh
   witness rows have no plant-fired counter ([147]). New: `TemplateRegistry` has no unregister, and a snapshot of
   `_by_class`/`_lazy` put back after `register()` loses built-in templates silently (the 21 ids' cause); other test
   files that restore the registry by copy were not searched for.

## FILE:LINE MAP (81e6561e)

- tests/test_witness.py: `_OWN`, `_users`, `_take_users_templates`, `_put_back_users_templates`, `_templates_changed`
  :25-65; fixture `clean_default_registry` :69; `on` :82; test_registered_knowledge_falls_through :333;
  `users_knowledge` :351; the five-case test :361; the new kept test :396; test_on_skips_the_session... :470.
- tests/test_templates.py: the test :656, try :675, finally :687. tests/test_p4_review.py: the test :9, try :31, finally :46.
- satassume/witness.py (unchanged): `_users_knowledge` :134-163. satassume/knowledge/templates/registry.py: `_load` :141,
  `register` :161 (`load_all` before a user's template :179).
- rust-spike/slice/results/tools338/: stage338.sh, go338.sh, job338.sh, order338.sh, order338.py (ORDER338 modes,
  LEAKCHECK338), lost-templates-786410d-ids.txt. Orion copies and outputs: ~/sa-rust-ids-work/sa-port-338/ (tools, plug,
  trees/{786410d,32c167ee,81e6561e,ii-only}, indep, order-wt).
- The rest: HANDOFF-sa-port-337.md's map (bar reading), -336's (bar.sh, tools336), -333's (function source).

## Must stay in every report

Tested SHAs and .so above; SLICE_WITNESS off by default and the unchanged path the default, except Engine.stats' 13th
key witness_certified, 0 with the switch off; no SymPy construction or evaluation at query time; "exact" rests on
325's 14-predicate table (issue 247); bar row wall times (from 337's bar); known base rows by id; S1 is the landing
measure (fuzz -28.2% py, -19.2% rust; dev -2.7% py, +1.1% rust), shares from shared-lease runs are not wall times;
the Rust change (entry.rs KEYS 13, ent_record_certified without a tick); the planted-history test's Python rate with
the switch on (1 of 20 plain on 786410d, keep-alive 20 of 20).
