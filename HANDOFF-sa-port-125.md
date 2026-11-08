# HANDOFF sa-port-125: adapters step (issue 323), part B onward

## Done
- Step 0, reported as progress (journal 3a8fc61). On 2ee0c8c Rust read AdapterSpec's fields per query and called
  `spec.factory()` once per spec for each Relations object. Trace script and rows are in
  `~/sa-rust-ids-work/sa-port-125/step0/` (spec_trace.py: swaps `relations.AdapterSpec` after `p_install.install()`
  for a counting tuple subclass).
- Part A, f2e70ba on port/adapters: `spec_row` (relations_core.rs, above `RULE_MASKS`) reads each spec once, keyed by the
  spec object. Counter `rel:cb_spec_read` (session.rs index 122). Plant `spec-row-flip`. Dev: 6 spec reads (were about
  7,600), answers 31cd0945c07f02a6, plant caught. Bar and report: see results/port-adapters.md.

## Left (part B, then C)
B. **The adapters**: LRAAdapter (lra_adapter.py:454-549) and EUFAdapter (euf_adapter.py:98-254) become Rust classes, with
   their module rows: `constant_bounds` :275, `constant_enclosure` :283, `to_constraint` :302, `terms` :351,
   `_memoized` :439, and `_inherits_from_basic` (euf_adapter.py:66). Then `rel_default_specs`
   (relations_core.rs `fn rel_default_specs`) marks the two default specs, and `rel_adapter` and `guarded_adapters` build
   the Rust adapters with no `factory()` call. A user factory stays a callback, named and counted. This closes step 0:
   with it, relations.py counts whole (planner ruling (1)).
C. **Payload classes and constfield**: `EqAtom` (euf.py:75, built at euf_adapter.py:152), `Negated`/`Integral`
   (lra.py:230/:247, built at lra_adapter.py:484/:422; ownership :101 also says "adapters (after 5c4)", although the
   brief names only EqAtom). Also constfield's 6 Python rows (ownership :97: `Constant` :694, `_coerce_foreign` :885,
   `Element.to_sympy` :1281, `_sympy_constant` :1439) and its callback rows at :122 (`enclose` stays, permanent by ruling).

## File:line map (port/adapters f2e70ba)
- Where Rust calls the adapters (relations_core.rs): register_integer :608/:615; register_bounds :655; register / node_term
  / interned in rel_interpret :793-830; integer_form in rel_link :913; engage_transfer node_term :1253-1262; shared_terms /
  term_of / terms_since around :1209, :1293, :1309, :1425, :1451, :1761; terms / order_sides / integer_form in terms_of
  and link_objects :2499-2545. Get exact lines with rg `"register"|"node_term"|...`, since part A moved them by about 45.
- Existing Rust for the adapters' term work: term/lra_read.rs (interpret, order_sides, integer_form, closed_sign, slice D),
  installed by lra_live.py:107-130, which wraps `lra_adapter.interpret` etc. and `_memoized`. `structural`/`interned`:
  relations_core.rs `fn structural` (around :1022) and euf_adapter's landed C1 rows.
- Theories: lra_backend.py:261-266 swaps `lra_adapter.LRATheory`; backend.py:88-97 `install_euf` swaps
  `adapter.EUFTheory`. lra_py.rs (363 lines) and euf_py.rs (482) are the Rust theory classes. lra.rs:192 and lra_py.rs:136
  read Negated/Integral. euf_py.rs:2/:77 read EqAtom.
- Wiring model: session_live.py `_REL_FUNCS`/`_REL_METHODS` (:440-480), `_REL_PLANTS` (:448-463), install at :665-680.
- Tests: tests/test_lra_adapter.py, tests/test_euf_adapter.py, tests/test_constfield.py; rust-spike/slice/test_relations_core.py.
- Ownership: port-ownership.md :90 (EqAtom), :92 (EUFAdapter 12), :97 (constfield 6), :101 (Negated/Integral 8),
  :102 (LRAAdapter 17), :122 (constfield callbacks).
