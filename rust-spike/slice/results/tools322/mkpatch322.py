"""mkpatch322.py SRC_DIR [--dry] (sa-port-322, issue 323): edits a SCRATCH copy of solver_rs/src into the None-classes count
build. Every edit is an exact-string replacement with its expected number of matches; a miss stops the script. The package
is never edited: the result is kept as a diff (count322.patch) and applied to a scratch copy only.

The count build appends short tokens to one thread-local string; `sa_solver.nc322_take()` returns and clears it (the driver
nc322.py calls it after every workload query), `sa_solver.nc322_note(s)` adds a token from Python. Tokens (each ends in ';'):
  Q< Q>r      Engine.ask (entry.rs ent_ask); r = T, F, N (None), O (other), X (raised)
  I< I>r      Engine.is_ (entry.rs is_);  M< M>  Engine.is_many
  D< D>r      Engine._decide;  Tge  the session's theory flags when _decide or _ask ends (g gave_up, e exhausted; 0/1)
  B           Engine._over_budget (the discovery budget);  N  a non-commutative refusal;  K  the `_constructing` None
  H           a fact-cache hit in is_
  V< V>x      the set's complete check; x = c (consistent), u (unknown), i (inconsistent), X (raised)
  C           engine.py:1906's catch (ctx:caught);  F  the fallback fresh session (ctx:fallback)
  S< S>b      Solver.solve;  c< c>b  Solver.consistent;  e< e>r  Solver.entails;  a< a>r  Solver.entails_all
  s:n:h:b:k   one solve_int: n assumption literals, h = 1 a ring hit (no search), b = 1 satisfiable, k = ring length before
  w0 w1       witness_satisfies
  xb          LRA: a check ran out of BRANCH_BUDGET;  xs  a split skipped beyond the certificate's bound (also `exhausted`)
  g           LRA: gave up (an undecidable comparison)
"""
import sys, pathlib
D = pathlib.Path(sys.argv[1])
DRY = "--dry" in sys.argv


def edit(name, pairs):
    f = D / name
    s = f.read_text()
    for old, new, n in pairs:
        k = s.count(old)
        if k != n:
            msg = f"{name}: {k} matches, wanted {n}: {old[:90]!r}"
            if DRY:
                print(msg)
                continue
            sys.exit(msg)
        s = s.replace(old, new)
    if not DRY:
        f.write_text(s)


NC = "crate::solver::nc"

# ---- solver.rs: the buffer, and a logging wrapper around each entry (the body keeps its text under NAME_nc) ----
TAIL = r'''
// ---- sa-port-322 count build: a scratch patch, never part of the package (issue 323) ----
thread_local! { static NC322: RefCell<String> = RefCell::new(String::new()); }
pub fn nc(s: &str) {
    NC322.with(|b| {
        let mut b = b.borrow_mut();
        b.push_str(s);
        b.push(';');
    })
}
pub fn nc_take() -> String {
    NC322.with(|b| std::mem::take(&mut *b.borrow_mut()))
}
fn nc_ob(r: &R<Option<bool>>) -> &'static str {
    match r {
        Ok(Some(true)) => "T",
        Ok(Some(false)) => "F",
        Ok(None) => "N",
        Err(_) => "X",
    }
}
fn nc_b(r: &R<bool>) -> &'static str {
    match r {
        Ok(true) => "1",
        Ok(false) => "0",
        Err(_) => "X",
    }
}
'''
SOLVE_INT = "    fn solve_int(&mut self, lits: &[u32], keep: usize) -> bool {"
WITNESS = "    fn witness_satisfies(&self, assumptions: &[u32]) -> bool {"
CONSISTENT = "    pub fn consistent(&mut self, assumptions: &[u32], hold: i32) -> R<bool> {"
ENTAILS = "    pub fn entails(&mut self, lit: i32, assumptions: &[u32], hold: i32) -> R<Option<bool>> {"
ENTAILS_ALL = "    pub fn entails_all(&mut self, lits: &[u32], assumptions: &[u32], hold: i32) -> R<Option<bool>> {"
SOLVE = "    pub fn solve(&mut self, assumptions: &[u32]) -> R<bool> {"
edit("solver.rs", [
    (SOLVE_INT, '''    fn solve_int(&mut self, lits: &[u32], keep: usize) -> bool {
        let h0 = self.n.ring_hits;
        let k0 = self.ring.len();
        let r = self.solve_int_nc(lits, keep);
        nc(&format!("s:{}:{}:{}:{}", lits.len(), (self.n.ring_hits != h0) as u8, r as u8, k0));
        r
    }

    fn solve_int_nc(&mut self, lits: &[u32], keep: usize) -> bool {''', 1),
    (WITNESS, '''    fn witness_satisfies(&self, assumptions: &[u32]) -> bool {
        let r = self.witness_satisfies_nc(assumptions);
        nc(if r { "w1" } else { "w0" });
        r
    }

    fn witness_satisfies_nc(&self, assumptions: &[u32]) -> bool {''', 1),
    (CONSISTENT, '''    pub fn consistent(&mut self, assumptions: &[u32], hold: i32) -> R<bool> {
        nc("c<");
        let r = self.consistent_nc(assumptions, hold);
        nc(&format!("c>{}", nc_b(&r)));
        r
    }

    fn consistent_nc(&mut self, assumptions: &[u32], hold: i32) -> R<bool> {''', 1),
    (ENTAILS, '''    pub fn entails(&mut self, lit: i32, assumptions: &[u32], hold: i32) -> R<Option<bool>> {
        nc("e<");
        let r = self.entails_nc(lit, assumptions, hold);
        nc(&format!("e>{}", nc_ob(&r)));
        r
    }

    fn entails_nc(&mut self, lit: i32, assumptions: &[u32], hold: i32) -> R<Option<bool>> {''', 1),
    (ENTAILS_ALL, '''    pub fn entails_all(&mut self, lits: &[u32], assumptions: &[u32], hold: i32) -> R<Option<bool>> {
        nc("a<");
        let r = self.entails_all_nc(lits, assumptions, hold);
        nc(&format!("a>{}", nc_ob(&r)));
        r
    }

    fn entails_all_nc(&mut self, lits: &[u32], assumptions: &[u32], hold: i32) -> R<Option<bool>> {''', 1),
    (SOLVE, '''    pub fn solve(&mut self, assumptions: &[u32]) -> R<bool> {
        nc("S<");
        let r = self.solve_nc(assumptions);
        nc(&format!("S>{}", nc_b(&r)));
        r
    }

    fn solve_nc(&mut self, assumptions: &[u32]) -> R<bool> {''', 1),
])
if not DRY:
    f = D / "solver.rs"
    f.write_text(f.read_text() + TAIL)

# ---- lra.rs: the two ways a check sets `exhausted`, and giving up ----
edit("lra.rs", [
    ("            if skipped {\n                self.exhausted = true;",
     f"            if skipped {{\n                {NC}(\"xs\");\n                self.exhausted = true;", 1),
    ("        if *budget <= limit {\n            self.exhausted = true;",
     f"        if *budget <= limit {{\n            {NC}(\"xb\");\n            self.exhausted = true;", 1),
    ("        self.gave_up = true;", f"        {NC}(\"g\");\n        self.gave_up = true;", 1),
])

# ---- entry.rs: Engine.ask, is_, is_many, _decide, _ask's end ----
SIG_ASK = "fn ent_ask<'py>(eng: &Bound<'py, PyAny>, proposition: &Bound<'py, PyAny>, assumptions: Option<Bound<'py, PyAny>>) -> PyResult<Bound<'py, PyAny>> {\n    tick(ENT_ASK);"
SIG_DEC = "fn decide<'py>(eng: &Bound<'py, PyAny>, s: &Bound<'py, PyAny>, lit: &Bound<'py, PyAny>, lits: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {\n    tick(ENT_DECIDE);"
SIG_IS = "fn is_<'py>(eng: &Bound<'py, PyAny>, node: &Bound<'py, PyAny>, pred: &Bound<'py, PyAny>, hand: &Hand) -> PyResult<Bound<'py, PyAny>> {\n    tick(ENT_IS);"
SIG_MANY = "fn ent_is_many<'py>(eng: &Bound<'py, PyAny>, node: &Bound<'py, PyAny>, preds: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyList>> {"
FLAGS = '''    {
        let g = crate::theory_flags::theory_flag(s, crate::theory_flags::Flag::GaveUp).unwrap_or(false);
        let e = crate::theory_flags::theory_flag(s, crate::theory_flags::Flag::Exhausted).unwrap_or(false);
        crate::solver::nc(&format!("T{}{}", g as u8, e as u8));
    }
'''
HELP = r'''
// ---- sa-port-322 count build (scratch) ----
fn nc_res(tag: &str, r: &PyResult<Bound<'_, PyAny>>) {
    let v = match r {
        Ok(v) if v.is_none() => "N",
        Ok(v) if v.is_instance_of::<PyBool>() => {
            if v.is_truthy().unwrap_or(false) {
                "T"
            } else {
                "F"
            }
        }
        Ok(_) => "O",
        Err(_) => "X",
    };
    crate::solver::nc(&format!("{tag}{v}"));
}
'''
edit("entry.rs", [
    (SIG_ASK, '''fn ent_ask<'py>(eng: &Bound<'py, PyAny>, proposition: &Bound<'py, PyAny>, assumptions: Option<Bound<'py, PyAny>>) -> PyResult<Bound<'py, PyAny>> {
    crate::solver::nc("Q<");
    let r = ent_ask_nc(eng, proposition, assumptions);
    nc_res("Q>", &r);
    r
}

fn ent_ask_nc<'py>(eng: &Bound<'py, PyAny>, proposition: &Bound<'py, PyAny>, assumptions: Option<Bound<'py, PyAny>>) -> PyResult<Bound<'py, PyAny>> {
    tick(ENT_ASK);''', 1),
    (SIG_DEC, '''fn decide<'py>(eng: &Bound<'py, PyAny>, s: &Bound<'py, PyAny>, lit: &Bound<'py, PyAny>, lits: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    crate::solver::nc("D<");
    let r = decide_nc(eng, s, lit, lits);
''' + FLAGS + '''    nc_res("D>", &r);
    r
}

fn decide_nc<'py>(eng: &Bound<'py, PyAny>, s: &Bound<'py, PyAny>, lit: &Bound<'py, PyAny>, lits: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    tick(ENT_DECIDE);''', 1),
    (SIG_IS, '''fn is_<'py>(eng: &Bound<'py, PyAny>, node: &Bound<'py, PyAny>, pred: &Bound<'py, PyAny>, hand: &Hand) -> PyResult<Bound<'py, PyAny>> {
    crate::solver::nc("I<");
    let r = is_nc(eng, node, pred, hand);
    nc_res("I>", &r);
    r
}

fn is_nc<'py>(eng: &Bound<'py, PyAny>, node: &Bound<'py, PyAny>, pred: &Bound<'py, PyAny>, hand: &Hand) -> PyResult<Bound<'py, PyAny>> {
    tick(ENT_IS);''', 1),
    (SIG_MANY, '''fn ent_is_many<'py>(eng: &Bound<'py, PyAny>, node: &Bound<'py, PyAny>, preds: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyList>> {
    crate::solver::nc("M<");
    let r = ent_is_many_nc(eng, node, preds);
    crate::solver::nc("M>");
    r
}

fn ent_is_many_nc<'py>(eng: &Bound<'py, PyAny>, node: &Bound<'py, PyAny>, preds: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyList>> {''', 1),
    ("    crate::budget::note_budget(eng, s)?;\n    Ok(r)", FLAGS + "    crate::budget::note_budget(eng, s)?;\n    Ok(r)", 1),
    ("    if noncommutative_atoms(p, &[proposition, &ctx_or_none], &hand)? {\n        return Ok(none);",
     "    if noncommutative_atoms(p, &[proposition, &ctx_or_none], &hand)? {\n        crate::solver::nc(\"N\");\n        return Ok(none);", 1),
    ("    if noncommutative(p, node)? {\n        return noncomm_answer(",
     "    if noncommutative(p, node)? {\n        crate::solver::nc(\"N\");\n        return noncomm_answer(", 1),
    ("    if engmemo::contains(&eng.getattr(intern!(p, \"_constructing\"))?, node)? {\n        return Ok(p.None().into_bound(p));",
     "    if engmemo::contains(&eng.getattr(intern!(p, \"_constructing\"))?, node)? {\n        crate::solver::nc(\"K\");\n        return Ok(p.None().into_bound(p));", 1),
    ("        set_flag(eng, false)?;\n        return facts.get_item(pred);",
     "        set_flag(eng, false)?;\n        crate::solver::nc(\"H\");\n        return facts.get_item(pred);", 2),
])
if not DRY:
    f = D / "entry.rs"
    f.write_text(f.read_text() + HELP)

# ---- budget.rs: the discovery budget ----
edit("budget.rs", [("    tick(BUD_OVER_BUDGET);", "    tick(BUD_OVER_BUDGET);\n    crate::solver::nc(\"B\");", 1)])

# ---- context.rs: the set's complete check, the catch and the fallback ----
SIG_CC = "fn complete_check<'py>(s: &Bound<'py, PyAny>, lits: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {\n    tick(CTX_COMPLETE_CHECK);"
edit("context.rs", [
    (SIG_CC, '''fn complete_check<'py>(s: &Bound<'py, PyAny>, lits: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    crate::solver::nc("V<");
    let r = complete_check_nc(s, lits);
    let v = match &r {
        Ok(v) => v.str().ok().and_then(|x| x.to_string().chars().next()).unwrap_or('?'),
        Err(_) => 'X',
    };
    crate::solver::nc(&format!("V>{v}"));
    r
}

fn complete_check_nc<'py>(s: &Bound<'py, PyAny>, lits: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    tick(CTX_COMPLETE_CHECK);''', 1),
    ("tick(CTX_FALLBACK);", "tick(CTX_FALLBACK);\n            crate::solver::nc(\"F\");", 1),
    ("tick(CTX_CAUGHT);", "tick(CTX_CAUGHT);\n            crate::solver::nc(\"C\");", 1),
])

# ---- lib.rs: the two module functions ----
REG = "    m.add_function(wrap_pyfunction!(rule_block_tables, m)?)?;"
edit("lib.rs", [(REG, REG + "\n    m.add_function(wrap_pyfunction!(nc322_take, m)?)?;\n    m.add_function(wrap_pyfunction!(nc322_note, m)?)?;", 1)])
if not DRY:
    f = D / "lib.rs"
    f.write_text(f.read_text() + r'''
// ---- sa-port-322 count build (scratch) ----
#[pyfunction]
fn nc322_take() -> String {
    crate::solver::nc_take()
}
#[pyfunction]
fn nc322_note(s: &str) {
    crate::solver::nc(s)
}
''')
print("dry run done" if DRY else "patched")
