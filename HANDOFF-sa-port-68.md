# Handoff: sa-port-68, component 4 slice D, `lra_adapter.py` (issue 323)

**State: on `port/4d`, rebased on `rust-slice` 089c70d (slice B). Wired into `live.py`, `rust_plugin.py` and `fresh.py --lra`. Nothing is on `rust-slice`. The landing bar has not run: no suite and no pareto run yet.** Handed off on the context note (151k), not on a blocker.

## Done this session

- **Wired.** `SLICE_LRA_TERM=rust|py` is the switch (`SLICE_LRA` already belongs to the LRA backend, with other values; the first version's reuse of it would have exited on `SLICE_LRA=python`).
- **A real bug fixed:** `_closed` tested `flag::PLAIN_OPS` on `Mul`, which is never set on `Mul` because `Mul` overrides `as_coeff_Mul`. Every closed `Mul` refused: 97 of 1,985 dev queries, 597 of 3,000 fuzz. **Answers matched anyway, because a refused run answers on Python**, so check refusal counts beside any MATCH. Now only a subclass refuses.
- **`num` moved:** `sa_solver.cf_num`. `lra_backend` uses it; `lra_live` installs it over `constfield.num` and `lra.num`. Anything but Fraction, Element, float or exact int goes to Python's `Fraction(x)`, counted as `rust:num_python`. `test_lra_live.py`: 27 pass against Python's on 25 values (types, error text, identity).
- **`from_sympy`** now also catches a wrapped `CfErr::Py(_Unread)`. No test reaches that line yet. An `LraErr::Unread` reaching the top is a ValueError, then a `TermFault`: loud, not quiet.
- **B's `term_id` and `scaffold`** replace the copies in `lra_live.py`.

## Evidence so far (orion, aarch64, not the landing source's bar)

**Fresh, before the rebase on B, `--term keys --lra`, check on (`c2`):** dev 1,985 and fuzz 3,000 identical to Python, answers and digests, 0 refused, 0 check differences. Calls: interpret 5,848 and 124,642; order_sides 2,901 and 58,982; integer_form 1,194 and 24,134; closed_sign 264 and 597. **Reach is thin:** `closed_mul_rust` 0 and 0, `generic` 1 and 0, `bounds` 1 and 0, `product_terms` 6 and 0. That is why `lra_wl.py` exists.

**Registry (`c3b`), on this source: MATCH.** `lra_registry.py`, one process, no reset between queries, one engine and then a new engine per query, 435 lines of answers with a registry digest after each. Python against Rust is byte-identical in each order. Control: the two orders' registries differ (`log(2)`, `log(3)` swap indices 2 and 3). 0 refused, 0 fault; `rust:generic` 2,052, `rust:registry` 1,598 on that sequence. Registry stays read live, the planner's accepted first version; those two counts are the Python reads during search. No per-query registry was tried.

**Correction: commit 1859d3c's message says "both orders: 545 lines identical". That run was void for order:** `reset_module_state` doesn't clear `_CONSTANTS`, so its reversed scenario kept `log(2)` first. The script is fixed, and `c3b` is the run to quote. Same fact for anyone reading `fresh.py`: **a constant's index survives reset, so fresh columns share registry history across queries.**

## Running when I stopped

`~/sa-rust-ids-work/sa-port-68/c4` on orion, detached, `scripts/c4.sh`, `DONE` written last, `progress` by line. **Read it first, by summary.** It ran on commit 1859d3c (`tree.txt`); the only later source change is `lra_registry.py`. It holds: `lra` workload Python, Rust and Rust with check (`lra-*.txt`, `lra-rust*.json`: `lra`, `check_bad`, `scaffold_bad`, `refusals`), the four plants on dev and lra (`plant-*`), and units (`units.log`, `units-rust.log`). Compare with `cmp` against `lra-py.txt` and c1-style dev rows. The plants need a py base for dev under `--term terms`: run or reuse. No result of c4 has been read.

## Left, in order

1. **Read c4.** Any check difference or lost answer on `lra` is a finding: smallest case. Which plants were caught, and on which workload. If `bounds` or `closed_sign` still have thin reach there, add to `lra_wl.py`.
2. **`closed_mul_scaffold` is not zero:** 24 on the registry sequence (48 on the void run). So Rust's `mul` refuses some closed product and Python builds it. Find the shape, report the count per workload beside `scaffold:rebuilt`, and tell B's session if the fix is in `algebra.rs`. Must reach 0 before any backend PR, not to land. `scaffold:rebuilt` also fires, 55, all at B's `_eq_links`.
3. **Make the suite report these counts:** `rust_plugin.py` dumps `tl.report()` per worker, and that has no `lra_live.counts()` yet. Needed to say how often the suite reaches this slice.
4. **Landing job on pareto0, `machine run pareto0 --shared --wait 4h`, detached.** Model: `pareto1:~/sp19/job66.sh`. pareto0 has no cargo: build the x86-64 .so on pareto1 under --shared (it may wait behind sa-port-69's quiet lease) and copy it. Bar: suite by id with three numbers and quiet firings; fresh dev and fuzz with `--term terms --lra`, check **off**; live dev and fuzz; a plant caught; units. **Base rows: `pareto1:~/sa-rust-ids-work/sa-port-66/l2/suite`** (port-4b.md's output). Copy them if pareto0 can't read them. Add `transfer_fuzz` on a few seeds, reported either way.
5. **`results/port-4d.md`**, then land by the rebase rule, and report. Check whole-module counts. **My reading, unverified: 0 of 32.** `lra_adapter.py` keeps `LRAAdapter` and `relation`; `constfield.py` keeps the registry, `Element` crossings and `_generic`. Name them as partial.
6. Not measured: `_INTERPRETED`'s cost under the per-table memo (timing, backend list). Whether the convert.py flag bits disturb `test_term_live.py` or a digest: c4's units answer the first part.

## Shared files changed

`convert.py`: flag bits 16-18, `exp` imported. `term/table.rs`: `IS_EXPR`, `IS_MATRIX`, `IS_EXP`. `term_live.py`: none now that B's slots are in. `constfield.rs`: `py_err` pub, `cf_num`, `NUM_PY`. `term/algebra.rs`: `is_rational_kind` `pub(super)`. `lra_backend.py`: `num = sa_solver.cf_num`. `live.py`, `rust_plugin.py`, `fresh.py`: wiring, `lra` workload. 0 lines in `satassume/` or `tests/`.

## Map

    constfield.rs:2107:pub static NUM_PY: AtomicU64 = AtomicU64::new(0);
    constfield.rs:2110:pub fn cf_num<'py>(x: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    lra_read.rs:63:pub const PLANT_COEFF: u8 = 1; // `_lin`'s closed or rational coefficie
    lra_read.rs:189:    pub fn lin(&mut self, e: TermId, scale: &Num, out: &mut Form, c: &
    lra_read.rs:257:    fn closed_product(&mut self, closed: &[TermId]) -> Res<Option<Num>
    lra_read.rs:282:    fn closed(&mut self, e: TermId, scale: &Num, out: &mut Form, c: &m
    lra_read.rs:301:            if self.kind(e) != Kind::Mul {
    lra_read.rs:332:    fn constant_bounds(&mut self, e: TermId) -> Res<Option<(Rat, Rat)>
    lra_read.rs:344:    pub fn from_sympy(&mut self, e: TermId) -> Res<Option<Num>> {
    lra_read.rs:446:    fn sort_terms<T>(&mut self, items: &mut [T], id: impl Fn(&T) -> Te
    lra_read.rs:537:    fn unread<T>(&self, r: Res<T>) -> Res<Option<T>> {
    lra_read.rs:624:    pub fn closed_sign(&mut self, e: TermId) -> Res<(Option<i32>, bool
    lra_live.py:74:def _check(site, ours, theirs, arg):
    lra_live.py:89:def _ids(q, site, *terms):
    lra_live.py:103:def _install():
    lra_live.py:207:def install(check=None, plant=None):
    lra_live.py:229:def from_env():
    lra_live.py:241:def counts():
    wire: live.py:342:        import lra_live     # Slice D. SLICE_LRA_TERM=py keeps it off.
    wire: live.py:343:        lra_live.from_env()
    wire: rust_plugin.py:97:    import lra_live
    wire: rust_plugin.py:98:    lra_live.from_env()
    wire: fresh.py:28:ap.add_argument("--lra", action="store_true", help="lra_adapter's term work from Rust: lra_live.py. Needs --term")
    wire: fresh.py:115:        import lra_live
    wire: fresh.py:116:        lra_live.install()
    wire: fresh.py:167:            out.update(lra=lra_live.counts(), check_bad=lra_live.CHECK_BAD[:50], scaffold_bad=lra_live.SCAFFOLD_BAD[:20])
    term_live.py:633:def report():
    rust_plugin.py:146:            json.dump(tl.report(), f)
    lra_wl.py: the workload, queries(seed=323, n_queries=1500). lra_registry.py: py|rust OUT 01|10. test_lra_live.py: num.
    Python's originals: lra_adapter.py :179 _lin, :225 _closed, :254 closed_sign, :318 _constraint, :337 interpret, :359 _side, :400 integer_form, :439 _memoized, :454 LRAAdapter. constfield.py :827 num, :1375 _from_sympy, :1415 _generic. relations.py:410 imports closed_sign at call time.
    Scripts and output: ~/sa-rust-ids-work/sa-port-68/{scripts,c2,c3b,c4}. scripts/env.sh sets the env for this clone.

Env: `. ~/sa-rust-ids-work/sa-port-68/scripts/env.sh`. `SLICE_LRA_TERM=rust|py`, `SLICE_LRA_CHECK=1`, `SLICE_LRA_PLANT=coeff|sort|pi|eq`.
