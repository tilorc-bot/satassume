# HANDOFF sa-port-119: 5c5 module functions written in Rust, call sites inside Rust switched, Python wiring not done (issue 323)

Clone /home/tilo/dev/sa-port-7, branch port/5c5 (pushed), on rust-slice 064a1b4 (unchanged at 02:00Z; check again).

## bar-5c5a (f99a2e4, the five methods only): read, clean
pareto1:~/sp19/sa-rust-ids-work/sa-port-118/bar-5c5a/sum.txt. Suite 5958 passed (5957 no firing, 1 with: test_ci_stream_reports_only_what_replays),
126 failed, 23 skipped, 18 xfailed; against base new 0, gone 0, changed 0; handler multiset same as base (34+4 _consistent, 1 _build_context
"Already mutably borrowed"); TermFault 0. dev, fuzz, loop: answers and state MATCH (dev 1985 q, fuzz 3000 q, loop 420 q). Plants: all five
fire and DIFFER on dev and fuzz; all five are 0 on loop. 487 tests passed; direct exit 0. Phase not run: seed1.

## Correction to sa-port-118's finding
`_termwise` IS in Rust: `PyTermTable.termwise` (solver_rs/src/term/relations.rs:110, term/py.rs:324), from a5f4590 (slice B, report b45b72f).
`term_live._termwise` (term_live.py:650) replaces `relations._termwise` and answers on ids. So port-ownership.md:70 is right. `rel:cb_termwise`
counts a hop through that Python wrapper into Rust, not Python's `_termwise`. Say this in the report.

## Done (this commit, unchecked beyond 87 tests)
- solver_rs/src/relations_core.rs, section "step 5c5, second part" (before `pub fn register`): pyfunctions `rel_own_term`, `rel_number_basis`,
  `rel_number_facts`, `rel_sympy_atom`, `rel_zero_args`, `rel_under_of`, `rel_zero_twins`, `rel_glue_atoms`, `rel_guarded_adapters`,
  `rel_terms_of`, `rel_link_objects`, `rel_closed_units`, `rel_with_closed_units` (pyclass `ClosedUnits`), `rel_missing`,
  `rel_default_specs`, `rel_relational_name`; helpers `term_free` (term id with no session, via `term_live.term_id`), `free_is_number`,
  `constant_term` (session link), `closure_mask`/`rule_masks` (masks of `RULE_INSTANTIATED`, kept by identity as `rules._masks` does).
  Memos stay Python's objects (`_SYMPY_ATOMS`, `_CLOSED`, `engine._xbasis`, adapter memo).
- Inside Rust, these callbacks are now direct calls: `sympy_atom` and `_own_term` in `rel_interpret`, `_number_facts` and `_number_basis` in
  the transfer code, `_constant_term` in `rel_share` (so `rel:cb_constant_term` should now read 0).
- Counters session.rs 96-121: rel:own_term .. rel:relational_name, callbacks rel:cb_is_many, cb_sympy_q, cb_under_apps, cb_zero_twin,
  cb_structural_subterms, cb_relation_atom, cb_adapter_read, cb_closed_sign, cb_units, cb_clause_templates, and rel:py_is_number (no-id fallback).
- Plants 75-89 in `rel_plant`: own-term-false, constant-term-never, basis-all, sympy-atom-swap, zero-args-empty, under-of-empty,
  zero-twins-first, glue-no-twins, guarded-none, terms-of-no-order, link-objects-bare, closed-units-none, with-closed-skip, specs-no-euf,
  relname-swap. Each fires only where it changes something.
- orion: build OK; test_relations_core.py + test_query_core.py 87 passed.
- Kept as types, nothing to run: `AdapterSpec` (the spec type callers pass as `relations=`), `Uninterpreted` (exception type).

## Left
1. session_live.py: add the 15 plant names to `_REL_PLANTS`' tail (:448), and in `_install_relations` (:640) patch module attributes, saving
   and restoring them in `undo`: `relations.{zero_args, under_of, zero_twins, glue_atoms, sympy_atom, _own_term, _constant_term (no Rust
   pyfunction: leave Python's, Rust calls its own), _number_basis, _number_facts, _guarded_adapters, _terms_of, link_objects, closed_units,
   with_closed_units, default_specs, _missing, relational_name}`; `engine.{zero_args, under_of, glue_atoms, link_objects}` (engine.py:86-87
   imports them by name); `sympy_api.relational_name` (sympy_api.py:115). Leave ref.py's by-name imports (`glue_atoms`, `_is_number`) Python's;
   ref.py:300 and :544 import `closed_units`/`default_specs` at call time, so they will get Rust's: name that in the report.
   Careful: an Engine built before install keeps Python's `with_closed_units` closure.
2. Python's `link_objects`/`glue_objects` read `_guarded_adapters`, `_terms_of`, `sympy_atom` as globals; term_live's `_glue_objects`
   (term_live.py:677-725) reads them by module attribute, so it picks up Rust's once patched.
3. Tests: add the 15 plants to `test_dropped_clause_is_seen` (test_relations_core.py:883-896) where a case moves; for the rest, a direct
   test comparing Rust against Python's function (`PY` copy) on the fuzz/dev atoms, plus the plant firing. Run 5c4's ten test files on orion.
4. Bar: `PUSH=1 sh rust-spike/slice/p1/bar.sh land TESTED_SHA` style, as sa-port-118 launched it (brief's last map item), PLANTS = the 15
   new ones (the five methods' plants are covered by bar-5c5a; the whole-step bar may add them back if time allows). BASE =
   sa-port-115/bar-5c4/suite. Then results/port-5c5.md in port-5c4.md's form, `agent report`, push.
5. Expect void plants on dev/fuzz for: link-objects-bare, guarded-none, terms-of-no-order (budget cone over-estimate only), specs-no-euf
   (only at Engine construction), possibly basis-all (transfer basis vs all decided facts may give the same closure). Name what catches them.

## Why 5c4 left the five (for the report, one line)
port-ownership.md:76-77 gave them to 5c4 as "called back" rows, not as moves, and 5c4 moved only its "Python" row (:75).

## File:line map (this head)
- relations.py module functions: AdapterSpec :379, _missing :385, closed_units :395, with_closed_units :423, default_specs :435,
  relational_name :542, sympy_atom :550, zero_args :595, under_of :607, zero_twins :630, glue_atoms :659, _termwise :673,
  _constant_term :692, _number_basis :698, _number_facts :752, _own_term :761, _guarded_adapters :1922, _terms_of :1935, link_objects :1970.
- Callers: engine.py :941 :1006 :1195-1196 :1336-1341 :1749 :1753 :1805; ref.py :77 :300 :474 :544; sympy_api.py :115 :324; convert.py :395.
- relations_core.rs: plant consts ~:117-136, `rel_plant` match ~:140-225; 5c5 part two section "step 5c5, second part" before `register`.
- session.rs: NAMES :17 (122), consts :112-164.
- session_live.py: `_REL_METHODS` :421, `_REL_PLANTS` :448, `_install_relations` :640, `from_env` :~722.
- Env for tests on orion: `. ~/sa-rust-ids-work/env.sh; export PYTHONPATH=/home/tilo/dev/sa-port-7:$W/sympy:$W/shim; $PY -m pytest ...`
  (PY is the venv's; `timeout` is /usr/bin/timeout).
