//! Step 5c8: sympy_api's relevance keys, split, relevance and consistency rows (`sympy_api.py` on 17442af: `_const_base`
//! :693, `_const_free` :705, `_closed_keys` :724, `_expr_keys` :745, `_arg_keys` :768, `_keys` :779, `_keys_rel` :784,
//! `_bool_keys` :807, `_sides_keys` :844, `_Split` :864 with `__init__` :869 and `part` :912, `_relevant` :929,
//! `_vocab_blocks` :1009, `_part_consistent` :1076, `_consistent` :1088).
//!
//! What stays Python, by the planner's state ruling and sa-port-147's inventory:
//! - `Engine.splits`: Rust-native since 5c9c (engmemo.rs, an `EngineMemo` with `AnswerMemo`'s bound), read here natively;
//!   Python's `_drop_set_memos` (5c10d) and the harness still reach it through its view (`em:py_splits`). The `_Split` values
//!   in it are this file's `Split`, whose fields are Rust's: nothing in Python reads a split's fields (whole-tree search, 5c8
//!   report).
//! - `Engine.stats`: written by sympy_api's conversion rows and the public `ask`, never moved by a planned step (inventory).
//! - `_KEYS` and `_CONST` (PROCESS tables): no inventory row puts their last reader here (tests and `_Mark` read them), so
//!   they stay, read and written through their own methods (`rv:cb_memo`).
//! - Called back by name, counted: `_formula` (`rv:cb_formula`), `Engine.verdict` (`rv:cb_verdict`), `scope.theory_scope`
//!   (`rv:cb_theory_scope`), `_applied_category`/`_is_matrix_predicate` (`rv:cb_category`), the extensions' class tests
//!   (`rv:cb_ext`), SymPy's `And` (`rv:sympy_and`). Reads of input terms (`args`, `is_Rational`, ...) are conversion.
//! - A Boolean deeper than `DEPTH` levels is keyed by Python's own `_keys_rel` (`rv:py_deep`), whose `RecursionError` guard
//!   depends on the caller's stack and isn't reproduced (as `FORMULA_DEPTH` in session.rs).
//!
//! `_consistent`'s `except Exception` catches exactly Python's: an `Exception` from the same sources (`_formula`,
//! `relation_specs`, `verdict`) becomes `False` and is written to `handler_count`'s rows under the same site; a
//! `BaseException` (`TermFault`, `KnowledgeFault`) goes on up. The plant `consistent-fault` raises one inside the body.
use std::collections::HashMap;

use pyo3::exceptions::{PyException, PyRecursionError};
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{PyBool, PyFrozenSet, PyList, PySet, PyString, PyTuple};

use crate::engmemo;
use crate::formula::Hand;
use crate::relations_core::{
    planted, ARG_KEYS_NO_CLOSED, BOOL_KEYS_OPAQUE_IN, CLOSED_KEYS_NO_UNDEF, CONSISTENT_FAULT, CONSISTENT_IGNORE_VERDICT,
    CONST_BASE_NO_POW, CONST_FREE_NO_MUL, EXPR_KEYS_CLOSED_SKIP, KEYS_EMPTY, KEYS_REL_NO_FLAG, PART_CONSISTENT_TRUE,
    RELEVANT_ASSUME_CONSISTENT, SIDES_KEYS_FIRST_ONLY, SPLIT_NO_MERGE, SPLIT_PART_FIRST, VOCAB_NO_DERIVED, EM_SPLITS_PUT_DROP,
};
use crate::session::{
    tick, RV_BR_GLUE, RV_BR_PARTS, RV_BR_UNSUPPORTED, RV_BR_VERDICT, RV_CB_CATEGORY, RV_CB_EXT, RV_CB_FORMULA, RV_CB_MEMO,
    RV_CB_THEORY_SCOPE, RV_CB_VERDICT, RV_CONSISTENT, RV_CONSISTENT_CAUGHT, RV_CONST_FREE_MISS, RV_KEYS_MISS, RV_KEYS_REL,
    RV_PART_CONSISTENT, RV_PY_DEEP, RV_RELEVANT, RV_SPLIT_NEW, RV_SYMPY_AND, RV_VOCAB_BLOCKS,
};

/// Levels of `_bool_keys`/`_expr_keys` walked in Rust; deeper goes to Python's `_keys_rel` (see the module doc).
const DEPTH: u32 = 150;

static APPLIED_UNDEF: PyOnceLock<Py<PyAny>> = PyOnceLock::new();

fn api(p: Python<'_>) -> PyResult<Bound<'_, PyModule>> {
    p.import(intern!(p, "satassume.sympy_api"))
}

fn applied_undef(p: Python<'_>) -> PyResult<&Bound<'_, PyAny>> {
    Ok(APPLIED_UNDEF
        .get_or_try_init(p, || -> PyResult<_> { Ok(p.import("sympy.core.function")?.getattr("AppliedUndef")?.unbind()) })?
        .bind(p))
}

/// The `RELATIONAL` modes.
#[derive(Clone, Copy, PartialEq)]
enum Mode {
    Components,
    Whole,
    Rationals,
    Other,
}

fn mode(api: &Bound<'_, PyModule>) -> PyResult<Mode> {
    let p = api.py();
    let r = api.getattr(intern!(p, "RELATIONAL"))?;
    Ok(match r.extract::<String>().ok().as_deref() {
        Some("components") => Mode::Components,
        Some("whole") => Mode::Whole,
        Some("rationals") => Mode::Rationals,
        _ => Mode::Other,
    })
}

/// sympy_api's globals one key walk reads, read at its start (Python reads them at each use; nothing changes them inside it).
struct Ctx<'py> {
    p: Python<'py>,
    api: Bound<'py, PyModule>,
    mode: Mode,
    k_atoms: Bound<'py, PyAny>,
    s_pi: Bound<'py, PyAny>,
    s_exp1: Bound<'py, PyAny>,
    s_zero: Bound<'py, PyAny>,
    connectives: Bound<'py, PyAny>,
    relational: Bound<'py, PyAny>,
    applied: Bound<'py, PyAny>,
    btrue: Bound<'py, PyAny>,
    bfalse: Bound<'py, PyAny>,
    basic: Bound<'py, PyAny>,
    rational: Bound<'py, PyAny>,
    relation_predicates: Bound<'py, PyAny>,
    pred_index: Bound<'py, PyAny>,
    opaque_categories: Bound<'py, PyAny>,
    marker: Bound<'py, PyAny>,
    undef: Bound<'py, PyAny>,
    depth: u32,
    deep: bool,
}

impl<'py> Ctx<'py> {
    fn new(p: Python<'py>) -> PyResult<Self> {
        let api = api(p)?;
        let g = |n: &Bound<'py, PyString>| api.getattr(n);
        let s = g(intern!(p, "_S"))?;
        Ok(Ctx {
            p,
            mode: mode(&api)?,
            k_atoms: g(intern!(p, "_K_ATOMS"))?,
            s_pi: s.getattr(intern!(p, "Pi"))?,
            s_exp1: s.getattr(intern!(p, "Exp1"))?,
            s_zero: s.getattr(intern!(p, "Zero"))?,
            connectives: g(intern!(p, "_CONNECTIVES"))?,
            relational: g(intern!(p, "_Relational"))?,
            applied: g(intern!(p, "_Applied"))?,
            btrue: g(intern!(p, "_BTrue"))?,
            bfalse: g(intern!(p, "_BFalse"))?,
            basic: g(intern!(p, "_Basic"))?,
            rational: g(intern!(p, "_Rational"))?,
            relation_predicates: g(intern!(p, "RELATION_PREDICATES"))?,
            pred_index: g(intern!(p, "PRED_INDEX"))?,
            opaque_categories: g(intern!(p, "OPAQUE_CATEGORIES"))?,
            marker: g(intern!(p, "_RELATION"))?,
            undef: applied_undef(p)?.clone(),
            api,
            depth: 0,
            deep: false,
        })
    }

    fn attr_true(&self, e: &Bound<'py, PyAny>, name: &Bound<'py, PyString>) -> PyResult<bool> {
        e.getattr(name)?.is_truthy()
    }

    fn is_rational(&self, e: &Bound<'py, PyAny>) -> PyResult<bool> {
        self.attr_true(e, intern!(self.p, "is_Rational"))
    }

    fn args(&self, e: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        e.getattr(intern!(self.p, "args"))
    }

    /// `_const_base`.
    fn const_base(&self, c: &Bound<'py, PyAny>) -> PyResult<bool> {
        if self.k_atoms.contains(c)? {
            return Ok(true);
        }
        if self.attr_true(c, intern!(self.p, "is_Pow"))? {
            if planted(CONST_BASE_NO_POW) {
                return Ok(false);
            }
            let a = self.args(c)?;
            let (b, r) = (a.get_item(0)?, a.get_item(1)?);
            return Ok(self.is_rational(&r)?
                && ((self.is_rational(&b)? && self.attr_true(&b, intern!(self.p, "is_positive"))?)
                    || b.is(&self.s_pi)
                    || b.is(&self.s_exp1)));
        }
        Ok(false)
    }

    /// `_const_free`, memoized in sympy_api's `_CONST`.
    fn const_free(&self, c: &Bound<'py, PyAny>) -> PyResult<bool> {
        let p = self.p;
        let tbl = self.api.getattr(intern!(p, "_CONST"))?;
        tick(RV_CB_MEMO);
        let v = tbl.call_method1(intern!(p, "get"), (c,))?;
        if !v.is_none() {
            return v.is_truthy();
        }
        tick(RV_CONST_FREE_MISS);
        let v = if self.is_rational(c)? || self.const_base(c)? {
            true
        } else if self.attr_true(c, intern!(p, "is_Mul"))? {
            if planted(CONST_FREE_NO_MUL) {
                false
            } else {
                let args = self.args(c)?;
                let mut rest = Vec::new();
                for a in args.try_iter()? {
                    let a = a?;
                    if !self.is_rational(&a)? {
                        rest.push(a);
                    }
                }
                rest.len() == 1 && args.len()? <= 2 && self.const_base(&rest[0])?
            }
        } else {
            false
        };
        let size: usize = self.api.getattr(intern!(p, "KEYS_SIZE"))?.extract()?;
        if tbl.len()? >= size {
            tbl.call_method0(intern!(p, "clear"))?;
        }
        tbl.set_item(c, v)?;
        Ok(v)
    }

    /// `_closed_keys`.
    fn closed_keys(&self, c: &Bound<'py, PyAny>, acc: &Bound<'py, PySet>, force: bool) -> PyResult<()> {
        if self.is_rational(c)? || (!force && self.mode != Mode::Rationals && self.const_free(c)?) {
            return Ok(());
        }
        let mut stack = vec![c.clone()];
        while let Some(e) = stack.pop() {
            if self.is_rational(&e)? {
                continue;
            }
            acc.add(&e)?;
            if e.is_instance(&self.undef)? && !planted(CLOSED_KEYS_NO_UNDEF) {
                acc.add(e.get_type())?;
            }
            for a in self.args(&e)?.try_iter()? {
                stack.push(a?);
            }
        }
        if self.mode == Mode::Rationals {
            for a in c.call_method1(intern!(self.p, "atoms"), (&self.rational,))?.try_iter()? {
                acc.add(a?)?;
            }
        }
        Ok(())
    }

    /// `_expr_keys`: true if `e` is closed (nothing added).
    fn expr_keys(&mut self, e: &Bound<'py, PyAny>, acc: &Bound<'py, PySet>, force: bool) -> PyResult<bool> {
        if self.deep {
            return Ok(false);
        }
        if self.attr_true(e, intern!(self.p, "is_Symbol"))? {
            acc.add(e)?;
            return Ok(false);
        }
        if self.is_rational(e)? {
            return Ok(true);
        }
        self.depth += 1;
        if self.depth > DEPTH {
            self.deep = true;
            return Ok(false);
        }
        let args: Vec<Bound<'py, PyAny>> = self.args(e)?.try_iter()?.collect::<PyResult<_>>()?;
        let mut flags = Vec::with_capacity(args.len());
        for a in &args {
            flags.push(self.expr_keys(a, acc, force)?);
        }
        self.depth -= 1;
        if self.deep {
            return Ok(false);
        }
        if flags.iter().all(|&f| f) {
            return Ok(true);
        }
        if !planted(EXPR_KEYS_CLOSED_SKIP) {
            for (a, &closed) in args.iter().zip(&flags) {
                if closed {
                    self.closed_keys(a, acc, force)?;
                }
            }
        }
        if e.is_instance(&self.undef)? {
            acc.add(e.get_type())?;
        }
        Ok(false)
    }

    /// `_arg_keys`.
    fn arg_keys(&mut self, a: &Bound<'py, PyAny>, acc: &Bound<'py, PySet>, force: bool) -> PyResult<()> {
        if self.expr_keys(a, acc, force)? && !self.deep && !planted(ARG_KEYS_NO_CLOSED) {
            self.closed_keys(a, acc, true)?;
        }
        Ok(())
    }

    /// `_bool_keys`.
    fn bool_keys(&mut self, e: &Bound<'py, PyAny>, acc: &Bound<'py, PySet>) -> PyResult<bool> {
        let p = self.p;
        if self.deep {
            return Ok(false);
        }
        if e.is(PyBool::new(p, true)) || e.is(PyBool::new(p, false)) || e.is_instance(&self.btrue)? || e.is_instance(&self.bfalse)? {
            return Ok(true);
        }
        if e.is_instance(&self.connectives)? {
            self.depth += 1;
            if self.depth > DEPTH {
                self.deep = true;
                return Ok(false);
            }
            let mut ok = true;
            for a in self.args(e)?.try_iter()? {
                if !self.bool_keys(&a?, acc)? {
                    ok = false;
                    break;
                }
            }
            self.depth -= 1;
            return Ok(ok && !self.deep);
        }
        if e.is_instance(&self.relational)? {
            let op = e.getattr(intern!(p, "rel_op"))?;
            let eq = op.eq("==")? || op.eq("!=")?;
            let sides = [e.getattr(intern!(p, "lhs"))?, e.getattr(intern!(p, "rhs"))?];
            return self.sides_keys(&sides, acc, eq);
        }
        if e.is_instance(&self.applied)? {
            let func = e.getattr(intern!(p, "function"))?;
            let name_obj = func.getattr(intern!(p, "name"))?.str()?;
            let name = name_obj.to_cow()?.into_owned();
            let args: Vec<Bound<'py, PyAny>> = e.getattr(intern!(p, "arguments"))?.try_iter()?.collect::<PyResult<_>>()?;
            if self.relation_predicates.contains(&name_obj)? {
                return self.sides_keys(&args, acc, name == "eq" || name == "ne");
            }
            if name == "is_true" && args.len() == 1 && args[0].is_instance(&self.relational)? {
                return self.bool_keys(&args[0], acc);
            }
            let unindexed = !self.pred_index.contains(&name_obj)?;
            if unindexed || {
                tick(RV_CB_CATEGORY);
                self.api.getattr(intern!(p, "_is_matrix_predicate"))?.call1((&func, &name_obj))?.is_truthy()?
            } {
                tick(RV_CB_CATEGORY);
                let cat = self.api.getattr(intern!(p, "_applied_category"))?.call1((e,))?;
                if !self.opaque_categories.contains(&cat)? || planted(BOOL_KEYS_OPAQUE_IN) {
                    return Ok(false);
                }
                for a in &args {
                    if !a.is_instance(&self.basic)? {
                        return Ok(false);
                    }
                    self.arg_keys(a, acc, false)?;
                }
                return Ok(!self.deep);
            }
            if name == "zero" && self.mode == Mode::Rationals {
                acc.add(&self.s_zero)?;
            }
            let polar = name == "polar";
            for a in &args {
                if !a.is_instance(&self.basic)? {
                    return Ok(false);
                }
                if self.is_rational(a)? {
                    acc.add(a)?;
                } else {
                    self.arg_keys(a, acc, polar)?;
                }
            }
            return Ok(!self.deep);
        }
        Ok(false)
    }

    /// `_sides_keys`.
    fn sides_keys(&mut self, args: &[Bound<'py, PyAny>], acc: &Bound<'py, PySet>, eq: bool) -> PyResult<bool> {
        acc.add(&self.marker)?;
        let n = if planted(SIDES_KEYS_FIRST_ONLY) { args.len().min(1) } else { args.len() };
        for a in &args[..n] {
            if !a.is_instance(&self.basic)? {
                return Ok(false);
            }
            if self.mode == Mode::Components {
                if self.expr_keys(a, acc, false)? && !self.deep {
                    self.closed_keys(a, acc, false)?;
                }
            } else if eq && self.mode == Mode::Rationals && self.is_rational(a)? {
                acc.add(a)?;
            } else {
                self.arg_keys(a, acc, true)?;
            }
        }
        Ok(!self.deep)
    }
}

/// `_keys_rel`: `(keys or None, has a relation)`, memoized in `_KEYS` per registry epoch.
fn keys_rel<'py>(p: Python<'py>, e: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyTuple>> {
    tick(RV_KEYS_REL);
    let a = api(p)?;
    let state = a.getattr(intern!(p, "_EPOCH"))?.get_item(0)?;
    let keys = a.getattr(intern!(p, "_KEYS"))?;
    tick(RV_CB_MEMO);
    let stamp = intern!(p, "stamp");
    if keys.getattr(stamp)?.ne(&state)? {
        crate::memos::restamp(&keys, &state)?;
        crate::memos::restamp(&a.getattr(intern!(p, "_CONST"))?, &state)?;
    }
    let k = keys.call_method1(intern!(p, "get"), (e,))?;
    if !k.is_none() {
        return Ok(k.cast_into::<PyTuple>()?);
    }
    tick(RV_KEYS_MISS);
    let mut cx = Ctx::new(p)?;
    let acc = PySet::empty(p)?;
    let ok = match cx.bool_keys(e, &acc) {
        Ok(ok) => ok,
        Err(err) if err.is_instance_of::<PyRecursionError>(p) => false,
        Err(err) => return Err(err),
    };
    if cx.deep {
        tick(RV_PY_DEEP);
        let saved = p.import(intern!(p, "session_live"))?.getattr(intern!(p, "PY_RELEVANCE"))?;
        return Ok(saved.get_item("_keys_rel")?.call1((e,))?.cast_into::<PyTuple>()?);
    }
    let rel = acc.contains(&cx.marker)? && !planted(KEYS_REL_NO_FLAG);
    acc.discard(&cx.marker)?;
    let ks: Bound<'py, PyAny> = if ok { p.get_type::<PyFrozenSet>().call1((&acc,))? } else { a.getattr(intern!(p, "_OPAQUE"))? };
    let out = PyTuple::new(p, [ks, PyBool::new(p, rel).to_owned().into_any()])?;
    let size: usize = a.getattr(intern!(p, "KEYS_SIZE"))?.extract()?;
    if keys.len()? >= size {
        keys.call_method0(intern!(p, "clear"))?;
    }
    keys.set_item(e, &out)?;
    Ok(out)
}

/// `_Split`: the components of one set of assumptions. Lives in `Engine.splits` (Python's `AnswerMemo`).
#[pyclass(name = "Split", module = "sa_solver", unsendable)]
pub struct Split {
    #[pyo3(get)]
    whole: Py<PyAny>,
    #[pyo3(get)]
    conjuncts: Py<PyTuple>,
    #[pyo3(get)]
    opaque: bool,
    #[pyo3(get)]
    relational: bool,
    #[pyo3(get)]
    keyless: bool,
    /// (keys, conjunct indices), disjoint keys.
    comps: Vec<(Py<PySet>, Vec<usize>)>,
    /// (indices of components) -> their conjunction (a SymPy Boolean, True if empty, `whole` if all).
    parts: HashMap<Vec<usize>, Py<PyAny>>,
    /// Whether the whole set is known consistent (None: not checked).
    consistent: Option<bool>,
    /// A term of the set has a vocabulary predicate registered for its class (None: not computed).
    #[pyo3(get)]
    vocab: Option<bool>,
}

impl Split {
    fn build(p: Python<'_>, a: &Bound<'_, PyAny>) -> PyResult<Self> {
        tick(RV_SPLIT_NEW);
        let m = api(p)?;
        let cs: Bound<'_, PyTuple> = if a.is_instance(&m.getattr(intern!(p, "_SAnd"))?)? {
            a.getattr(intern!(p, "args"))?.cast_into::<PyTuple>()?
        } else {
            PyTuple::new(p, [a])?
        };
        let mut sp = Split {
            whole: a.clone().unbind(),
            conjuncts: cs.clone().unbind(),
            opaque: false,
            relational: false,
            keyless: false,
            comps: Vec::new(),
            parts: HashMap::new(),
            consistent: None,
            vocab: None,
        };
        let mut comps: Vec<(Bound<'_, PySet>, Vec<usize>)> = Vec::new();
        for (i, c) in cs.iter().enumerate() {
            let kr = keys_rel(p, &c)?;
            let k = kr.get_item(0)?;
            if k.is_none() {
                sp.opaque = true;
                return Ok(sp);
            }
            if kr.get_item(1)?.is_truthy()? {
                sp.relational = true;
            }
            if !k.is_truthy()? {
                sp.keyless = true;
                continue;
            }
            let ks = p.get_type::<PySet>().call1((&k,))?.cast_into::<PySet>()?;
            let mut idx = vec![i];
            let mut rest = Vec::with_capacity(comps.len() + 1);
            for comp in comps.drain(..) {
                if planted(SPLIT_NO_MERGE) || comp.0.call_method1(intern!(p, "isdisjoint"), (&ks,))?.is_truthy()? {
                    rest.push(comp);
                } else {
                    ks.call_method1(intern!(p, "update"), (&comp.0,))?;
                    idx.extend(comp.1);
                }
            }
            rest.push((ks, idx));
            comps = rest;
        }
        sp.comps = comps.into_iter().map(|(k, i)| (k.unbind(), i)).collect();
        Ok(sp)
    }

    fn part_of<'py>(&mut self, p: Python<'py>, mine: &[usize]) -> PyResult<Bound<'py, PyAny>> {
        if let Some(f) = self.parts.get(mine) {
            return Ok(f.bind(p).clone());
        }
        let mut idx: Vec<usize> = mine.iter().flat_map(|&j| self.comps[j].1.iter().copied()).collect();
        idx.sort_unstable();
        let cs = self.conjuncts.bind(p);
        let f = if idx.len() == cs.len() {
            self.whole.bind(p).clone()
        } else if idx.is_empty() {
            PyBool::new(p, true).to_owned().into_any()
        } else if idx.len() == 1 || planted(SPLIT_PART_FIRST) {
            cs.get_item(idx[0])?
        } else {
            tick(RV_SYMPY_AND);
            let items = idx.iter().map(|&i| cs.get_item(i)).collect::<PyResult<Vec<_>>>()?;
            api(p)?.getattr(intern!(p, "_SAnd"))?.call1(PyTuple::new(p, items)?)?
        };
        self.parts.insert(mine.to_vec(), f.clone().unbind());
        Ok(f)
    }
}

#[pymethods]
impl Split {
    #[new]
    fn py_new(py: Python<'_>, a: &Bound<'_, PyAny>) -> PyResult<Self> {
        Split::build(py, a)
    }

    fn part<'py>(&mut self, py: Python<'py>, mine: Vec<usize>) -> PyResult<Bound<'py, PyAny>> {
        self.part_of(py, &mine)
    }

    /// Python's `_Split.__init__` returns at the first opaque conjunct, before it sets `comps`, `parts` and `consistent`:
    /// those slots are unset on an opaque split and reading one raises AttributeError. The same here (issue 323, state
    /// part 3: the moved digest read `comps` as `[]` and `consistent` as None on Rust, unset on Python, on workload scope).
    fn unset(&self, name: &str) -> PyResult<()> {
        if self.opaque {
            return Err(pyo3::exceptions::PyAttributeError::new_err(format!("'Split' object has no attribute '{name}'")));
        }
        Ok(())
    }

    #[getter]
    fn consistent(&self) -> PyResult<Option<bool>> {
        if self.consistent.is_none() {
            self.unset("consistent")?;
        }
        Ok(self.consistent)
    }

    /// `[(keys, conjunct indices)]`, as Python's `comps` (a copy).
    #[getter]
    fn comps<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        self.unset("comps")?;
        let items = self
            .comps
            .iter()
            .map(|(k, i)| PyTuple::new(py, [k.bind(py).clone().into_any(), PyList::new(py, i)?.into_any()]))
            .collect::<PyResult<Vec<_>>>()?;
        PyList::new(py, items)
    }
}

/// `_vocab_blocks`.
fn vocab_blocks(p: Python<'_>, e: &Bound<'_, PyAny>, ext: &Bound<'_, PyAny>) -> PyResult<bool> {
    tick(RV_VOCAB_BLOCKS);
    let m = api(p)?;
    if !planted(VOCAB_NO_DERIVED) {
        for c in m.getattr(intern!(p, "_DERIVED_CLASSES"))?.try_iter()? {
            tick(RV_CB_EXT);
            if ext.call_method1(intern!(p, "is_scalar_class"), (c?,))?.is_truthy()? {
                return Ok(true);
            }
        }
    }
    let basic = m.getattr(intern!(p, "_Basic"))?;
    let mut stack = vec![e.clone()];
    let seen = PySet::empty(p)?;
    while let Some(n) = stack.pop() {
        tick(RV_CB_EXT);
        if ext.call_method1(intern!(p, "is_scalar_like"), (&n,))?.is_truthy()? {
            return Ok(true);
        }
        let args = match n.getattr(intern!(p, "args")) {
            Ok(a) => a,
            Err(err) if err.is_instance_of::<pyo3::exceptions::PyAttributeError>(p) => continue,
            Err(err) => return Err(err),
        };
        for a in args.try_iter()? {
            let a = a?;
            if a.is_instance(&basic)? && !seen.contains(&a)? {
                seen.add(&a)?;
                stack.push(a);
            }
        }
    }
    Ok(false)
}

/// `handler_count`'s row for a catch in Rust, under Python's site name; nothing if it isn't loaded.
fn handler_row(p: Python<'_>, site: &str, err: &PyErr) -> PyResult<()> {
    let mods = p.import(intern!(p, "sys"))?.getattr(intern!(p, "modules"))?;
    if let Some(h) = mods.call_method1(intern!(p, "get"), ("handler_count",))?.extract::<Option<Bound<'_, PyAny>>>()? {
        if h.hasattr("rust_handled")? {
            h.call_method1("rust_handled", (site, err.value(p)))?;
        }
    }
    Ok(())
}

/// Tells `catch_count`'s wrappers who calls them: Python's caller frame is `_consistent`, which Rust replaces.
fn caller_hint(p: Python<'_>, name: Option<&str>) -> PyResult<()> {
    let mods = p.import(intern!(p, "sys"))?.getattr(intern!(p, "modules"))?;
    if let Some(c) = mods.call_method1(intern!(p, "get"), ("catch_count",))?.extract::<Option<Bound<'_, PyAny>>>()? {
        c.setattr("NEXT_CALLER", name)?;
    }
    Ok(())
}

fn consistent_body(p: Python<'_>, a: &Bound<'_, PyAny>, eng: &Bound<'_, PyAny>, hand: &Hand) -> PyResult<bool> {
    let m = api(p)?;
    let rel = crate::memos::setting(eng, intern!(p, "_relation_specs"), intern!(p, "relation_specs"))?.is_truthy()?;
    tick(RV_CB_FORMULA);
    caller_hint(p, Some("_consistent"))?;
    let g = m.getattr(intern!(p, "_formula"))?.call1((a, rel, true));
    caller_hint(p, None)?;
    let g = g?;
    if planted(CONSISTENT_FAULT) {
        let f = p.import(intern!(p, "session_live"))?.getattr(intern!(p, "_fault"))?;
        return Err(PyErr::from_value(f.call1(("relevance", "plant consistent-fault"))?));
    }
    if g.is(&m.getattr(intern!(p, "TRUE"))?) {
        return Ok(true);
    }
    if g.is(&m.getattr(intern!(p, "FALSE"))?) {
        return Ok(false);
    }
    tick(RV_CB_VERDICT);
    caller_hint(p, Some("_consistent"))?;
    let v = crate::context::verdict_from(eng, &g, hand);
    caller_hint(p, None)?;
    let v = v?;
    if planted(CONSISTENT_IGNORE_VERDICT) {
        return Ok(true);
    }
    Ok(!v.is(&m.getattr(intern!(p, "_INCONSISTENT"))?))
}

/// `_consistent`: the set's verdict is consistent or unknown; False also when it can't be checked.
fn consistent(p: Python<'_>, a: &Bound<'_, PyAny>, eng: &Bound<'_, PyAny>, hand: &Hand) -> PyResult<bool> {
    tick(RV_CONSISTENT);
    if !planted(crate::relations_core::ST_CONSISTENCY_DROP) {
        crate::entry::bump(eng, crate::entry::CONSISTENCY_CHECKS, 1)?;
    }
    match consistent_body(p, a, eng, hand) {
        Ok(v) => Ok(v),
        Err(err) if err.is_instance_of::<PyException>(p) => {
            tick(RV_CONSISTENT_CAUGHT);
            handler_row(p, "_consistent", &err)?;
            Ok(false)
        }
        Err(err) => Err(err),
    }
}

/// `_part_consistent`: `_consistent` of one component, memoized in `Engine.splits` under `(_OK, f)`.
fn part_consistent(p: Python<'_>, f: &Bound<'_, PyAny>, eng: &Bound<'_, PyAny>, hand: &Hand) -> PyResult<bool> {
    tick(RV_PART_CONSISTENT);
    if planted(PART_CONSISTENT_TRUE) {
        return Ok(true);
    }
    let key = PyTuple::new(p, [api(p)?.getattr(intern!(p, "_OK"))?, f.clone()])?;
    let splits = eng.getattr(intern!(p, "splits"))?;
    if let Some(ok) = engmemo::get(&splits, key.as_any())? {
        return ok.is_truthy();
    }
    let ok = consistent(p, f, eng, hand)?;
    engmemo::put(&splits, key.as_any(), PyBool::new(p, ok).as_any())?;
    Ok(ok)
}

/// `_relevant`: `a` itself, or the part of `a` connected to `prop` if smaller and `a` isn't found inconsistent.
fn relevant<'py>(p: Python<'py>, prop: &Bound<'py, PyAny>, a: &Bound<'py, PyAny>, eng: &Bound<'py, PyAny>, hand: &Hand) -> PyResult<Bound<'py, PyAny>> {
    tick(RV_RELEVANT);
    let splits = eng.getattr(intern!(p, "splits"))?;
    let sp: Bound<'py, Split> = match engmemo::get(&splits, a)? {
        None => {
            let sp = Bound::new(p, Split::build(p, a)?)?;
            if !planted(EM_SPLITS_PUT_DROP) {
                engmemo::put(&splits, a, sp.as_any())?;
            }
            sp
        }
        Some(got) => got.cast_into::<Split>()?,
    };
    if sp.borrow().opaque {
        return Ok(a.clone());
    }
    let ext = crate::memos::setting(eng, intern!(p, "_extensions"), intern!(p, "extensions"))?;
    if !ext.is_none() && ext.getattr(intern!(p, "has_node_facts"))?.is_truthy()? {
        let v0 = sp.borrow().vocab;
        let v = match v0 {
            Some(v) => v,
            None => {
                let v = vocab_blocks(p, a, &ext)?;
                sp.borrow_mut().vocab = Some(v);
                v
            }
        };
        if v || vocab_blocks(p, prop, &ext)? {
            return Ok(a.clone());
        }
    }
    let pkr = keys_rel(p, prop)?;
    let pk = pkr.get_item(0)?;
    if !pk.is_truthy()? {
        return Ok(a.clone());
    }
    let m = api(p)?;
    if mode(&m)? == Mode::Whole && (pkr.get_item(1)?.is_truthy()? || sp.borrow().relational || sp.borrow().keyless) {
        return Ok(a.clone());
    }
    let mine: Vec<usize> = {
        let b = sp.borrow();
        let mut v = Vec::new();
        for (j, (k, _)) in b.comps.iter().enumerate() {
            if !k.bind(p).call_method1(intern!(p, "isdisjoint"), (&pk,))?.is_truthy()? {
                v.push(j);
            }
        }
        v
    };
    let f = sp.borrow_mut().part_of(p, &mine)?;
    if f.is(a) {
        return Ok(a.clone());
    }
    let known = sp.borrow().consistent;
    let ok = match known {
        Some(ok) => ok,
        None => {
            let (relational, keyless, n) = {
                let b = sp.borrow();
                (b.relational, b.keyless, b.comps.len())
            };
            let ok = if planted(RELEVANT_ASSUME_CONSISTENT) {
                true
            } else if relational || keyless {
                tick(RV_BR_VERDICT);
                consistent(p, a, eng, hand)?
            } else {
                let rel = crate::memos::setting(eng, intern!(p, "_relation_specs"), intern!(p, "relation_specs"))?.is_truthy()?;
                tick(RV_CB_FORMULA);
                match m.getattr(intern!(p, "_formula"))?.call1((a, rel, true)) {
                    Err(err) if err.is_instance(p, &m.getattr(intern!(p, "Unsupported"))?) => {
                        tick(RV_BR_UNSUPPORTED);
                        false
                    }
                    Err(err) => return Err(err),
                    Ok(g) => {
                        let glue = rel && {
                            tick(RV_CB_THEORY_SCOPE);
                            crate::scope_core::theory_scope_from(m.as_any(), "_theory_scope", &g, &p.None().into_bound(p), &ext, hand)?
                                .getattr(intern!(p, "glue"))?
                                .is_truthy()?
                        };
                        if glue {
                            tick(RV_BR_GLUE);
                            consistent(p, a, eng, hand)?
                        } else {
                            tick(RV_BR_PARTS);
                            let mut all = true;
                            for j in 0..n {
                                let part = sp.borrow_mut().part_of(p, &[j])?;
                                if !part_consistent(p, &part, eng, hand)? {
                                    all = false;
                                    break;
                                }
                            }
                            all
                        }
                    }
                }
            };
            sp.borrow_mut().consistent = Some(ok);
            ok
        }
    };
    Ok(if ok { f } else { a.clone() })
}

#[pyfunction]
fn rv_relevant<'py>(p: Python<'py>, prop: &Bound<'py, PyAny>, a: &Bound<'py, PyAny>, eng: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    relevant(p, prop, a, eng, &Hand::enter())
}

#[pyfunction]
fn rv_keys_rel<'py>(p: Python<'py>, e: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyTuple>> {
    keys_rel(p, e)
}

/// `_keys` (test-only caller).
#[pyfunction]
fn rv_keys<'py>(p: Python<'py>, e: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    let k = keys_rel(p, e)?.get_item(0)?;
    if planted(KEYS_EMPTY) {
        return Ok(PyFrozenSet::empty(p)?.into_any());
    }
    Ok(k)
}

#[pyfunction]
fn rv_const_free(p: Python<'_>, c: &Bound<'_, PyAny>) -> PyResult<bool> {
    let cx = Ctx::new(p)?;
    cx.const_free(c)
}

#[pyfunction]
fn rv_vocab_blocks(p: Python<'_>, e: &Bound<'_, PyAny>, ext: &Bound<'_, PyAny>) -> PyResult<bool> {
    vocab_blocks(p, e, ext)
}

#[pyfunction]
fn rv_part_consistent(p: Python<'_>, f: &Bound<'_, PyAny>, eng: &Bound<'_, PyAny>) -> PyResult<bool> {
    part_consistent(p, f, eng, &Hand::enter())
}

#[pyfunction]
fn rv_consistent(p: Python<'_>, a: &Bound<'_, PyAny>, eng: &Bound<'_, PyAny>) -> PyResult<bool> {
    consistent(p, a, eng, &Hand::enter())
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Split>()?;
    m.add_function(wrap_pyfunction!(rv_relevant, m)?)?;
    m.add_function(wrap_pyfunction!(rv_keys_rel, m)?)?;
    m.add_function(wrap_pyfunction!(rv_keys, m)?)?;
    m.add_function(wrap_pyfunction!(rv_const_free, m)?)?;
    m.add_function(wrap_pyfunction!(rv_vocab_blocks, m)?)?;
    m.add_function(wrap_pyfunction!(rv_part_consistent, m)?)?;
    m.add_function(wrap_pyfunction!(rv_consistent, m)?)
}
