# HANDOFF sa-port-138: adapters step (issue 323), part C1 committed, nothing landed; 6d not landed at 05:15 UTC

## State
- port/adapters (pushed): aba6a66 (part B code), ae6e767, b88a782, 5fa5e14 (docs), **de78d2a** (part C1 code), this file.
- rust-slice was still **1401d1f** at 05:15 UTC 8 Nov: 6d (sa-port-137, port/6d in ~/dev/sa-port-5) had not landed. HOLD still
  applies: no push to rust-slice before 6d lands; then a full bar on the merged tree.
- No bar has run on part B or C1. Proposal (not yet asked): **one landing bar for B + C1 on the merged tree** (tested SHA = the
  C1 commit after the rebase), with the report giving part B and part C1 their own sections. If the architect wants them
  apart, bar aba6a66 rebased first, then C1.

## What part C1 did (de78d2a)
- `solver_rs/src/payloads.rs`: `Negated`, `Integral`, `EqAtom` as frozen pyclasses (`module="sa_solver"`), tuple-like:
  len/getitem/iter/contains, `__richcmp__` against the field tuple (unwraps any of the three, so equal to Python's payload
  and to a plain tuple, as Python's are), hash of the field tuple, `_fields`, named getters, same `repr`, `__reduce__`. Not
  `isinstance(x, tuple)`: no reader checks that (rg over satassume/theories and slice readers).
- Builders: adapters.rs `LraAdapter::register` (Negated), `EufAdapter::register` (EqAtom); lra_live.py:168 `integer_form`'s
  Rust route builds `sa_solver.Integral`.
- Readers: euf_py.rs `register_atom` casts to the Rust `EqAtom` first and reads the fields with no Python call;
  lra_backend.py `Integral`/`Negated` are now tuples of (Rust class, Python class) for `_register`'s isinstance checks.
- Python's own theories can't read Rust payloads (lra.py:652/:656, euf.py:411). So: each Rust adapter decides once at build
  (`rust_payloads`): LRA from `theory._rust_payloads` (lra_backend.LRATheory sets it True), EUF from
  `is_instance_of::<PyEuf>`; otherwise it builds Python's class, counted `ad:cb_py_payload`. `register_integer` converts a
  Rust Integral for a Python theory (same counter). lra_live.py `_install` wraps Python's `LRATheory._register_atom` (found
  by MRO, since lra_backend may already have swapped the module attribute) to convert a Rust Integral that Python's
  LRAAdapter hands to Python's theory, counted `ad:integral_to_py` in term_live COUNTS; undone in `undo`. This was found by
  test_relations_core `test_same_core_python_methods_match` (Python LRAAdapter + Python LRATheory with lra_live installed).
- Plants **108-110** (`pay-neg-twice`, `pay-int-offset`, `pay-eq-flip`, session_live.py `_REL_PLANTS`); counters **151-154**
  (`ad:negated_new`, `ad:integral_new`, `ad:eqatom_new`, `ad:cb_py_payload`), arrays 155. 6d will likely renumber again.

## Local evidence (orion, `~/sa-rust-ids-work/sa-port-138/c1/`, built from de78d2a's tree)
- test_adapters_core + test_relations_core + test_scope_core: **97 passed** (`c1-core.txt`).
- dev rust: answers 31cd0945c07f02a6 = py; ad:eqatom_new 526 (= EUFTheory.register_atom hooks 526), ad:integral_new 554,
  **ad:negated_new 0**, ad:cb_py_payload 0, ad:cb_factory 0. fuzz rust answers 173502b6ef285ad6 = py; eqatom_new 12,733,
  integral_new 18,547, negated_new 0, cb_py_payload 0.
- Plants on dev: pay-eq-flip answer_diff 57 (caught); pay-int-offset answer_diff 60 (caught); **pay-neg-twice 0 diff: void**
  (Negated never built). Fuzz plant rows were still running detached at handoff (`run.sh`, end marker `done.txt`; read
  `plant-fuzz-*.cmp`, `dev.cmp`, `fuzz.cmp` there).
- `live.py pay` (pay_wl.py, 332 queries): MATCH bea4a01e9c2db5b5, but **negated_new 0** there too: `Q.ne` atoms don't reach
  the adapter as `ne`. Negated is built only when `interpret` returns positive=False, i.e. relation name "ne"
  (lra_adapter.py:318-334; names at :133 `Q.ne` and :135 `Unequality`). Next: find where the engine turns `Q.ne`/`Ne` into
  `Not(eq)` before relations (rg `"ne"` in relations.py:373/:513, sympy_api.py:141/:818, _rows.py:563), and either build
  pay_wl from a path that registers an `ne` atom (e.g. `relation_atom('ne', ...)` inside a registered extension fact, or an
  `Unequality` reaching `interpret` directly) or state Negated unreachable on the default path and keep the plant listed void
  with that reason. Not yet run: Python payload constructions on the Rust route traced to 0 (as part B's ad_trace.py,
  `~/sa-rust-ids-work/sa-port-129/b1/ad_trace.py`, patching lra.Negated/Integral and euf.EqAtom `__new__`).

## Next
1. Read c1/ fuzz plant rows. Fix or explain pay-neg-twice (above). Amend pay_wl.py or drop it from the commit if it stays
   useless (it's in live.py too).
2. When 6d lands: rebase port/adapters on origin/rust-slice (expect numbering conflicts in relations_core.rs plant consts /
   `rel_plant` match and session.rs NAMES/consts/array size; keep 6d's numbers, shift ours after them), rebuild, rerun the
   core tests, push the branch, no-PUSH `sh rust-spike/slice/p1/bar.sh land <C1 sha>`, read the incoming diff.
3. Full bar on the merged tree, config as HANDOFF-sa-port-133.md "Bar config" plus: PLANTS += `pay-neg-twice pay-int-offset
   pay-eq-flip`, WLS += `pay` (if it reaches Negated), BASE/KEPT_BASE = 6d's bar rows. Then PUSH=1 if the guard allows.
4. Reports: port-adapters.md (part B and part C1 sections, all MUST-STAY items), port-ownership.md rows :92 (EqAtom: Rust),
   :94, :102 (Negated/Integral: Rust; Python classes stay for the pure-Python default and `constraint()`), :104, the TSV.
5. Part C2, constfield (not started): 6 Python rows (port-ownership.md :99: `Constant`, `Constant.__repr__`,
   `_coerce_foreign`, `Element.to_sympy`, `Element.__repr__`, `_sympy_constant`) and the callback row :124. Python sites:
   constfield.py `_to_dmp` :555, `_from_dmp` :568, `_sympy_inner_gcd` :577, `_short` :637, `Constant` :694 (registry
   `_CONSTANTS`/`_BY_KEY` :731), `constant` :735, `radical` :801, `_coerce_foreign` :885, `Element._new` :914, `to_sympy`
   :1281, `__repr__` :1293, `pi_laurent` :1325, `_generic` :1415, `_sympy_constant` :1439. Rust callers: constfield.rs:108
   (`_short`), :777 (`_sympy_inner_gcd`), :1089 (`_CONSTANTS[i]`), :1176-1232 (enclose/radical code identity, `_cache`),
   :2022 (`Element._new`), lra_cert.rs:87 (`pi_laurent`). The constant registry is process-global and shared with
   Python's Element, so porting `Constant` means a Rust registry that Python's `_CONSTANTS` stays consistent with; `enclose`
   stays a permanent callback (R9).
