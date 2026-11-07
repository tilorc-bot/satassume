# Handoff: sa-port-67, component 4 slice D, `lra_adapter.py` (issue 323)

**State: a first version runs on `port/4d`. Nothing is on `rust-slice`. No item of the landing bar is met.** Handed off on the context note (165k+), not on a blocker.

## What exists

`solver_rs/src/term/lra_read.rs` ports `_lin`, `_closed`, `_linear`, `_constraint`, `interpret`, `_side`, `order_sides`, `integer_form`, `closed_sign` and `constfield._from_sympy`, line for line, on the table. `lra_live.py` installs them over `lra_adapter`'s names; `relation` stays conversion. Decisions taken, none tested beyond the smoke run:

- **Registry:** Rust reads Python's live (`PI`, `E`, `radical`, `_generic`), the planner's accepted first version. One registry, so history can't split by construction; counted as `rust:registry` and `rust:generic`. No per-query registry tried.
- **`:213` `Mul(*closed)`:** one factor builds nothing; more go through Rust's `mul`; if that refuses, Python builds it, counted as `closed_mul_scaffold`.
- **`_INTERPRETED`:** a per-table memo in `PyTermTable.1`. Cost not measured.
- **Sort sites:** Rust asks `sort_key` for every term even when there's one, because Python does and a key can raise; then a stable sort by `key_cmp`.
- **Callback on a derived term:** refuses. Not counted by reason yet.

## What ran

Only `~/sa-rust-ids-work/sa-port-67/smoke.py`, on orion, aarch64: 10 hand-built queries, Python against Rust on fresh engines. Same answers. `SLICE_LRA_CHECK` compared interpret 191, order_sides 87, integer_form 36: 0 differ. 0 refused, 0 scaffold mismatches. registry 32, generic 7, bounds 0, closed_mul_direct 23, closed_mul_rust 8, closed_mul_scaffold 0, product_terms 8, keys 156. **`closed_sign` and `bounds` did not fire, so they're unexercised.** No suite, dev, fuzz, plant or test has run.

## Left, in order

1. **Wire it:** call `lra_live.from_env()` where `term_live` is installed (the `wire:` lines below). Nothing calls it yet, so a suite run today would test nothing.
2. **`num` hasn't moved.** `lra_backend.py:21` still imports Python's. Add a Rust `cf_num` with Python's semantics (`constfield.py:827`: float raises TypeError, otherwise `Fraction(x)`). `Num::from_py` accepts less, so don't just call it.
3. **Check by reading:** `LraErr::Unread` in `lra_err` should be unreachable. `from_sympy` doesn't match `E::Cf(CfErr::Py(..))` unless `is_undecided` or `is_zero_div` covers it, so check a Python `_Unread` inside one. `closed_mul_scaffold` should also count per step beside `scaffold:rebuilt`, since the ruling counts both.
4. **Rebase on slice B if it has landed:** `_term_id` and `_scaffold` in `lra_live.py` are copies of B's `term_live.term_id` and `scaffold`, and the `derived` and `rev` slots on `_Query` use B's names. Delete the copies and use B's. Crate conflicts: B owns `algebra.rs` and the key; if D needs a change there, tell B's session. D only made `is_rational_kind` `pub(super)`.
5. **Registry item, on the bar:** show Python with history and Rust agree, including a sequence that registers constants in both orders (`log(2)` then `log(3)`, and reversed) in one process. Report the smallest case if not.
6. **Landing bar:** suite by id with three numbers and quiet firings; fresh dev and fuzz MATCH with the check flag off; a plant caught (`SLICE_LRA_PLANT` = coeff, sort, pi, eq), with call counts per workload showing each reaches this code. Add a workload or direct comparison for any that makes 0 calls; `closed_sign` and `bounds` are the first to check.
7. **Report whole-module counts honestly. My reading, unverified: neither candidate is whole yet.** `constfield.py` keeps the registry, `Element` crossings and `_generic`. `lra_adapter.py` keeps `LRAAdapter` (`register`, `_attach`, `register_integer`, `register_bounds`, `shared_terms`, `_shared`), which still handles SymPy objects, and the inventory lists those as port. So expect 0 of 32 unless that's ported; name them as partial.

## Shared files changed

`convert.py`: class flags at bits 16-18, and `exp` imported. `term/table.rs`: `flag::IS_EXPR`, `IS_MATRIX`, `IS_EXP`. `term_live.py`: two `_Query` slots. `constfield.rs`: `py_err` made `pub`. `term/algebra.rs`: `is_rational_kind` `pub(super)`. Whether the new flags disturb `test_term_live.py` or any digest hasn't been checked.

## Done on the clone

The 195 untracked `rust-spike/` files, 0 of them on rust-slice, plus 78 ignored build and cache files under the same directory, moved to `~/sa-rust-ids-work/sa-port-67/old-rust-spike/`. The worktree and `order/325-pyset` are untouched.

## Map

    lra_read.rs:63:pub const PLANT_COEFF: u8 = 1; // `_lin`'s closed or rational coefficient of a Mul lose
    lra_read.rs:64:pub const PLANT_SORT: u8 = 2; // the sort sites sort backwards.
    lra_read.rs:65:pub const PLANT_PI: u8 = 3; // `_from_sympy` reads pi as E.
    lra_read.rs:66:pub const PLANT_NEGATE_EQ: u8 = 4; // an eq's sign normalisation doesn't run.
    lra_read.rs:181:    fn object(&self, t: TermId) -> Res<Bound<'py, PyAny>> 
    lra_read.rs:189:    pub fn lin(&mut self, e: TermId, scale: &Num, out: &mut Form, c: &mut Num) -> Res<
    lra_read.rs:242:    fn kept_product(&mut self, factors: &[TermId]) -> Res<Option<TermId>> 
    lra_read.rs:257:    fn closed_product(&mut self, closed: &[TermId]) -> Res<Option<Num>> 
    lra_read.rs:282:    fn closed(&mut self, e: TermId, scale: &Num, out: &mut Form, c: &mut Num) -> Res<(
    lra_read.rs:331:    fn constant_bounds(&mut self, e: TermId) -> Res<Option<(Rat, Rat)>> 
    lra_read.rs:343:    pub fn from_sympy(&mut self, e: TermId) -> Res<Option<Num>> 
    lra_read.rs:364:    fn registry(&self, name: &str) -> Res<Num> 
    lra_read.rs:370:    fn from_sympy_(&mut self, e: TermId) -> Res<Num> 
    lra_read.rs:445:    fn sort_terms<T>(&mut self, items: &mut [T], id: impl Fn(&T) -> TermId) -> Res<()>
    lra_read.rs:472:    fn constraint(&mut self, name: &str, form: &Form, k: &Num) -> Res<Constraint> 
    lra_read.rs:516:    pub fn interpret(&mut self, name: &str, lhs: TermId, rhs: TermId) -> Res<Option<(C
    lra_read.rs:536:    fn unread<T>(&self, r: Res<T>) -> Res<Option<T>> 
    lra_read.rs:589:    pub fn order_sides(&mut self, a: TermId, b: TermId) -> Res<Option<((Form, i8), (Fo
    lra_read.rs:595:    pub fn integer_form(&mut self, e: TermId) -> Res<Option<(Vec<(TermId, Num)>, Num, 
    lra_read.rs:623:    pub fn closed_sign(&mut self, e: TermId) -> Res<(Option<i32>, bool)> 
    lra_live.py:39:def _refuse(reason):
    lra_live.py:43:def _term_id(q, e, site):
    lra_live.py:72:def _bad(o, why):
    lra_live.py:79:def _scaffold(q, i, site):
    lra_live.py:118:def _query():
    lra_live.py:124:def _rust(site, f, *a):
    lra_live.py:133:def _same_num(a, b):
    lra_live.py:141:def _same(a, b):
    lra_live.py:154:def _check(site, ours, theirs, arg):
    lra_live.py:161:def _objs(q, ids, site):
    lra_live.py:165:def _pairs(q, items, site):
    lra_live.py:169:def _ids(q, site, *terms):
    lra_live.py:179:def _flag():
    lra_live.py:183:def _install():
    lra_live.py:194:    def interpret(atom):
    lra_live.py:216:    def order_sides(atom):
    lra_live.py:234:    def integer_form(e):
    lra_live.py:250:    def closed_sign(e):
    lra_live.py:261:    def memoized(key, read, arg):
    lra_live.py:283:def install(check=None, plant=None):
    lra_live.py:305:def from_env():
    lra_live.py:316:def counts():
    py.rs:56:fn lra_err(py: Python<'_>, e: LraErr) -> PyErr {
    py.rs:66:fn lra_plant(p: u8) {
    py.rs:72:fn lra_counts<'py>(py: Python<'py>) -> PyResult<Bound<'py
    py.rs:117:    fn lra_memo<'py>(
    py.rs:253:    fn lra_interpret<'py>(
    py.rs:281:    fn lra_order_sides<'py>(
    py.rs:299:    fn lra_integer_form<'py>(
    py.rs:317:    fn lra_closed_sign<'py>(
    solver_rs/src/term/table.rs:76:    pub const IS_EXP: u32 = 1 << 18;
    convert.py:71:_IS_EXPR, _IS_MATRIX, _IS_EXP = 1 << 16, 1 << 17, 1 << 18
    convert.py:238:            flags |= _IS_EXPR
    wire: live.py:338:        term_live.from_env()
    wire: fresh.py:106:    term_live.install(keys=a.term == "keys")
    wire: rust_plugin.py:95:    term_live.from_env()
    wire: knowledge_live.py:302:    undo_term = term_live.install()

Python's originals: `satassume/theories/lra/lra_adapter.py` (:179 `_lin`, :225 `_closed`, :254 `closed_sign`, :318 `_constraint`, :337 `interpret`, :359 `_side`, :400 `integer_form`, :439 `_memoized`, :454 `LRAAdapter`), `constfield.py` (:827 `num`, :1375 `_from_sympy`, :1415 `_generic`). `relations.py:410` imports `closed_sign` at call time, so patching `lra_adapter` reaches it. B's source: `~/dev/sa-port-7`, branch `port/4b`.

Env: source `~/sa-rust-ids-work/env.sh`, then `PYTHONPATH=$PWD:$W/sympy:$W/shim:$PWD/rust-spike/slice`; `SLICE_LRA=rust|py`, `SLICE_LRA_CHECK=1`, `SLICE_LRA_PLANT=<name>`.
