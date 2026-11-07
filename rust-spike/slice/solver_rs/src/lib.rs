//! `Solver` for Python: the wrapper around `solver.rs`, and the `Theory` hooks over a Python object.
//!
//! Lifetime: everything is in the `Solver` object. The crate has no process state; a session's solver goes when
//! Python drops it, and `__traverse__` and `__clear__` let the GC break a solver <-> adapter cycle.
//! Not ported: provenance (`owner`, `provenance`, `root_step`). The engine sets `track_owners = False`, so it never
//! asks; those raise NotImplementedError rather than answer wrongly.
mod block;
mod compile;
mod constfield;
mod compile_loop;
mod query;
mod discovery;
mod euf;
mod euf_py;
mod formula_py;
mod handle;
// The rational helper is shared with the replay binary in lra/port, which keeps its frozen rational core.
mod lra;
mod lra_cert;
mod lra_py;
mod map;
#[path = "../../../lra/port/src/rat.rs"]
mod rat;
mod realroots;
mod relations_core;
mod rows;
mod session;
mod solver;
mod term;
mod theory;
mod transfer;
mod transfer_py;

use block::Closure;
use pyo3::exceptions::{PyNotImplementedError, PyOverflowError, PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyDict, PyInt, PyIterator, PyList, PyString};
use pyo3::{PyTraverseError, PyVisit};
use solver::{Fault, Solver, ValueError, F, T};
use std::panic::{catch_unwind, resume_unwind, AssertUnwindSafe};
use std::rc::Rc;
use theory::{Check, Theory};

/// Safe under one invariant: hooks run only inside a `#[pymethods]` entry below, which holds the thread attached and
/// doesn't detach, on the one thread an unsendable class allows.
fn py() -> Python<'static> {
    unsafe { Python::assume_attached() }
}

/// Unwind with a hook's Python exception. `run` below turns it back.
fn ok<X>(r: PyResult<X>) -> X {
    match r {
        Ok(x) => x,
        Err(e) => resume_unwind(Box::new(e)),
    }
}

/// Every entry that can reach a hook: raises what the solver or hook raised, with the solver left as it stood.
fn run<X>(f: impl FnOnce() -> solver::R<X>) -> PyResult<X> {
    match catch_unwind(AssertUnwindSafe(f)) {
        Ok(Ok(x)) => Ok(x),
        Ok(Err(ValueError(m))) => Err(PyValueError::new_err(m)),
        Err(p) => match p.downcast::<PyErr>() {
            Ok(e) => Err(*e),
            Err(p) => match p.downcast::<Fault>() {
                Ok(m) => Err(PyRuntimeError::new_err(m.0)),
                Err(p) => resume_unwind(p),
            },
        },
    }
}

/// `int(x)`: `__index__` first, then whatever `int` accepts.
fn int_of(x: &Bound<'_, PyAny>) -> PyResult<i64> {
    match x.extract::<i64>() {
        Ok(i) => Ok(i),
        Err(_) => x.py().get_type::<PyInt>().call1((x,))?.extract::<i64>(),
    }
}

/// A literal of an API call. Python would go on and allocate; past i32 this raises OverflowError instead.
fn api_lit(x: &Bound<'_, PyAny>) -> PyResult<i32> {
    i32::try_from(int_of(x)?).map_err(|_| PyOverflowError::new_err("literal out of range"))
}

fn api_lits(xs: &Bound<'_, PyAny>) -> PyResult<Vec<u32>> {
    xs.try_iter()?.map(|x| Ok(api_lit(&x?)? as u32)).collect()
}

/// A theory's clause. A value past i32 is past nvars too: the solver then raises its bad-literal RuntimeError.
fn hook_lits(xs: &Bound<'_, PyAny>) -> PyResult<Vec<u32>> {
    xs.try_iter()?.map(|x| Ok(int_of(&x?)?.clamp(-(i32::MAX as i64), i32::MAX as i64) as i32 as u32)).collect()
}

/// A theory's result: `None`, or a tuple whose first item `is False`: then the clause.
fn conflict_of(r: &Bound<'_, PyAny>) -> PyResult<Option<Vec<u32>>> {
    if r.is_none() || !r.get_item(0)?.is(PyBool::new(r.py(), false)) {
        return Ok(None);
    }
    Ok(Some(hook_lits(&r.get_item(1)?)?))
}

struct PyObj(Py<PyAny>);

impl Clone for PyObj {
    fn clone(&self) -> PyObj {
        PyObj(self.0.clone_ref(py()))
    }
}

struct PyProps(Bound<'static, PyIterator>);

impl Iterator for PyProps {
    type Item = (i32, Vec<u32>);

    fn next(&mut self) -> Option<Self::Item> {
        let item = ok(self.0.next()?);
        let parts: Vec<Bound<'_, PyAny>> = ok(item.try_iter().and_then(|i| i.collect::<PyResult<Vec<_>>>()));
        if parts.len() != 2 {
            ok::<()>(Err(PyValueError::new_err("theory propagate: expected (literal, reason) pairs")));
        }
        let x = ok(int_of(&parts[0])).clamp(-(i32::MAX as i64), i32::MAX as i64) as i32;
        Some((x, ok(hook_lits(&parts[1]))))
    }
}

/// `assert_lit`, `check`, `push_level` and `pop_level` are looked up per call and `propagate` and `decide` once at
/// attach, exactly as the Python solver does, so a test that wraps a method sees the same calls.
struct PyTheory {
    obj: Py<PyAny>,
    prop: Option<Py<PyAny>>,
    dec: Option<Py<PyAny>>,
    n_register: Py<PyString>,
    n_assert: Py<PyString>,
    n_check: Py<PyString>,
    n_push: Py<PyString>,
    n_pop: Py<PyString>,
}

impl PyTheory {
    fn new(t: &Bound<'_, PyAny>) -> PyResult<PyTheory> {
        let p = t.py();
        let opt = |name: &str| -> PyResult<Option<Py<PyAny>>> {
            Ok(t.getattr_opt(name)?.filter(|v| !v.is_none()).map(Bound::unbind))
        };
        let name = |s: &str| PyString::intern(p, s).unbind();
        Ok(PyTheory {
            obj: t.clone().unbind(),
            prop: opt("propagate")?,
            dec: opt("decide")?,
            n_register: name("register_atom"),
            n_assert: name("assert_lit"),
            n_check: name("check"),
            n_push: name("push_level"),
            n_pop: name("pop_level"),
        })
    }
}

impl Theory for PyTheory {
    type Payload = Py<PyAny>;
    type Model = PyObj;
    type Props = PyProps;

    fn register_atom(&mut self, var: i32, payload: Py<PyAny>) {
        let p = py();
        ok(self.obj.bind(p).call_method1(self.n_register.bind(p), (var, payload)));
    }

    fn assert_lit(&mut self, x: i32) -> Option<Vec<u32>> {
        let p = py();
        let r = ok(self.obj.bind(p).call_method1(self.n_assert.bind(p), (x,)));
        ok(conflict_of(&r))
    }

    fn check(&mut self) -> Check<PyObj> {
        let p = py();
        let r = ok(self.obj.bind(p).call_method0(self.n_check.bind(p)));
        if r.is_none() {
            return Check::Nothing;
        }
        match ok(conflict_of(&r)) {
            Some(c) => Check::Conflict(c),
            None => Check::Model(PyObj(ok(r.get_item(1)).unbind())),
        }
    }

    fn push_level(&mut self) {
        let p = py();
        ok(self.obj.bind(p).call_method0(self.n_push.bind(p)));
    }

    fn pop_level(&mut self) {
        let p = py();
        ok(self.obj.bind(p).call_method0(self.n_pop.bind(p)));
    }

    fn has_propagate(&self) -> bool {
        self.prop.is_some()
    }

    fn propagate(&mut self) -> PyProps {
        let r = ok(self.prop.as_ref().unwrap().bind(py()).call0());
        PyProps(ok(r.try_iter()))
    }

    fn has_decide(&self) -> bool {
        self.dec.is_some()
    }

    fn decide(&mut self) -> Option<i64> {
        let r = ok(self.dec.as_ref().unwrap().bind(py()).call0());
        if r.is_none() {
            None
        } else {
            Some(ok(int_of(&r)))
        }
    }
}

fn bottom(p: Python<'_>) -> PyResult<Bound<'_, PyAny>> {
    p.import("satassume.sat.solver")?.getattr("BOTTOM")
}

fn opt_hold(hold: Option<i32>) -> i32 {
    hold.unwrap_or(-1)
}

#[pyclass(name = "Solver", module = "sa_solver", unsendable, subclass, dict, weakref)]
struct PySolver {
    s: Solver<PyTheory>,
    #[pyo3(get, set)]
    track_owners: bool,
}

#[pymethods]
impl PySolver {
    #[new]
    fn new() -> PySolver {
        PySolver { s: Solver::new(), track_owners: true }
    }

    fn __traverse__(&self, visit: PyVisit<'_>) -> Result<(), PyTraverseError> {
        for t in &self.s.theories {
            visit.call(&t.obj)?;
            if let Some(x) = &t.prop {
                visit.call(x)?;
            }
            if let Some(x) = &t.dec {
                visit.call(x)?;
            }
        }
        for m in self.s.stored_models() {
            visit.call(&m.0)?;
        }
        Ok(())
    }

    fn __clear__(&mut self) {
        self.s.clear_hooks();
    }

    #[getter]
    fn owner<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        bottom(p)
    }

    #[setter]
    fn set_owner(&mut self, v: &Bound<'_, PyAny>) -> PyResult<()> {
        if v.is(&bottom(v.py())?) {
            return Ok(());
        }
        Err(PyNotImplementedError::new_err("the Rust solver has no provenance"))
    }

    fn provenance(&self, _v: i64, _memo: &Bound<'_, PyAny>) -> PyResult<()> {
        Err(PyNotImplementedError::new_err("the Rust solver has no provenance"))
    }

    fn root_step(&self, _v: i64) -> PyResult<()> {
        Err(PyNotImplementedError::new_err("the Rust solver has no provenance"))
    }

    fn new_var(&mut self) -> usize {
        self.s.new_var()
    }

    fn nvars(&self) -> usize {
        self.s.nvars()
    }

    fn ensure_vars(&mut self, v: i64) {
        if v > 0 {
            self.s.ensure_vars(v as usize);
        }
    }

    fn add_clause(&mut self, lits: &Bound<'_, PyAny>) -> PyResult<bool> {
        let lits = api_lits(lits)?;
        run(|| self.s.add_clause(&lits))
    }

    fn add_clauses(&mut self, clauses: &Bound<'_, PyAny>) -> PyResult<bool> {
        let c = clauses
            .try_iter()?
            .map(|c| c?.try_iter()?.map(|x| api_lit(&x?)).collect::<PyResult<Vec<i32>>>())
            .collect::<PyResult<Vec<_>>>()?;
        run(|| Ok(self.s.add_clauses(&c)))
    }

    #[pyo3(signature = (clauses, mentions=None))]
    fn add_internal(&mut self, clauses: &Bound<'_, PyAny>, mentions: Option<Vec<(u32, u128)>>) -> PyResult<bool> {
        let c = clauses
            .try_iter()?
            .map(|c| c?.try_iter()?.map(|l| l?.extract::<u32>().map_err(Into::into)).collect::<PyResult<Vec<u32>>>())
            .collect::<PyResult<Vec<_>>>()?;
        run(|| self.s.add_internal(&c, mentions.as_deref()))
    }

    fn add_pattern(&mut self, pattern: Vec<Vec<u32>>, base: usize, nvars: usize) -> PyResult<bool> {
        run(|| Ok(self.s.add_pattern(&pattern, base, nvars)))
    }

    #[pyo3(signature = (block, nvars=None))]
    fn set_rule_block(&mut self, block: &Bound<'_, PyAny>, nvars: Option<&Bound<'_, PyAny>>) -> PyResult<()> {
        let p = block.py();
        // Python's own check and memo, unchanged; only the finished models cross.
        let f = p.import("satassume.sat.solver")?.getattr("_rule_tables")?;
        let r = f.call1((block, nvars))?;
        let tables = r.get_item(0)?;
        let n = r.get_item(1)?.extract::<usize>()?;
        let clauses = tables.get_item(0)?.extract::<Vec<Vec<u32>>>()?;
        let models = tables.get_item(1)?.getattr("models")?.extract::<Vec<u128>>()?;
        let c = Rc::new(Closure::from_models(clauses, n, models));
        run(|| self.s.set_rule_block(&c))
    }

    #[pyo3(signature = (base, mentions=None))]
    fn register_block(&mut self, base: i32, mentions: Option<&Bound<'_, PyAny>>) -> PyResult<bool> {
        let m = match mentions {
            None => 0,
            Some(x) => x
                .extract::<u128>()
                .map_err(|_| PyValueError::new_err("register_block: mentions beyond the block size"))?,
        };
        run(|| self.s.register_block(base, m))
    }

    fn mention_blocks(&mut self, pairs: Vec<(u32, u128)>) -> PyResult<()> {
        run(|| self.s.mention_blocks(&pairs))
    }

    fn mention(&mut self, lits: &Bound<'_, PyAny>) -> PyResult<()> {
        let lits = api_lits(lits)?;
        run(|| self.s.mention(&lits))
    }

    fn propagate(&mut self) -> PyResult<bool> {
        run(|| Ok(self.s.propagate()))
    }

    fn value(&self, lit: i32) -> Option<bool> {
        self.s.value(lit)
    }

    fn root_trail(&self) -> Vec<i32> {
        self.s.root_trail()
    }

    #[pyo3(signature = (assumptions=None, hold=None))]
    fn implied(&mut self, assumptions: Option<&Bound<'_, PyAny>>, hold: Option<i32>) -> PyResult<Option<Vec<i32>>> {
        let a = lits_opt(assumptions)?;
        run(|| self.s.implied(&a, opt_hold(hold)))
    }

    fn release(&mut self, k: usize) -> PyResult<()> {
        run(|| Ok(self.s.release(k)))
    }

    fn attach_theory(&mut self, theory: &Bound<'_, PyAny>) -> PyResult<()> {
        if self.s.theories.iter().any(|t| t.obj.is(theory)) {
            return Err(PyValueError::new_err("theory already attached"));
        }
        let t = PyTheory::new(theory)?;
        run(|| Ok(self.s.attach_theory(t)))
    }

    fn theories<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        PyList::new(p, self.s.theories.iter().map(|t| t.obj.clone_ref(p)))
    }

    #[pyo3(signature = (theory, var, payload, mention=true))]
    fn register_atom(
        &mut self,
        theory: &Bound<'_, PyAny>,
        var: &Bound<'_, PyAny>,
        payload: Py<PyAny>,
        mention: bool,
    ) -> PyResult<bool> {
        let ti = match self.s.theories.iter().position(|t| t.obj.is(theory)) {
            Some(i) => i,
            None => return Err(PyValueError::new_err("theory not attached")),
        };
        let v = api_lit(var)?;
        run(|| self.s.register_atom(ti, v, payload, mention))
    }

    fn theory_models<'py>(&self, p: Python<'py>) -> PyResult<Option<Bound<'py, PyList>>> {
        match self.s.theory_models() {
            None => Ok(None),
            Some(ms) => {
                let items = ms.iter().map(|m| m.as_ref().map(|x| x.0.clone_ref(p)));
                Ok(Some(PyList::new(p, items)?))
            }
        }
    }

    fn set_inert(&mut self, v: usize) -> PyResult<()> {
        run(|| self.s.set_inert(v))
    }

    #[pyo3(signature = (assumptions=None))]
    fn solve(&mut self, assumptions: Option<&Bound<'_, PyAny>>) -> PyResult<bool> {
        let a = lits_opt(assumptions)?;
        run(|| self.s.solve(&a))
    }

    fn model<'py>(&mut self, p: Python<'py>) -> PyResult<Option<Bound<'py, PyDict>>> {
        let mv = match self.s.model_vals() {
            None => return Ok(None),
            Some(mv) => mv,
        };
        let d = PyDict::new(p);
        for (i, &x) in mv.iter().enumerate() {
            let val = match x {
                T => Some(true),
                F => Some(false),
                _ => None,
            };
            d.set_item(i + 1, val)?;
        }
        Ok(Some(d))
    }

    fn conflict(&self) -> Vec<i32> {
        self.s.conflict_lits()
    }

    #[pyo3(signature = (assumptions=None, hold=None))]
    fn consistent(&mut self, assumptions: Option<&Bound<'_, PyAny>>, hold: Option<i32>) -> PyResult<bool> {
        let a = lits_opt(assumptions)?;
        run(|| self.s.consistent(&a, opt_hold(hold)))
    }

    #[pyo3(signature = (lit, assumptions=None, hold=None))]
    fn entails(&mut self, lit: i32, assumptions: Option<&Bound<'_, PyAny>>, hold: Option<i32>) -> PyResult<Option<bool>> {
        let a = lits_opt(assumptions)?;
        run(|| self.s.entails(lit, &a, opt_hold(hold)))
    }

    #[pyo3(signature = (lits, assumptions=None, hold=None))]
    fn entails_all(
        &mut self,
        lits: &Bound<'_, PyAny>,
        assumptions: Option<&Bound<'_, PyAny>>,
        hold: Option<i32>,
    ) -> PyResult<Option<bool>> {
        let l = api_lits(lits)?;
        let a = lits_opt(assumptions)?;
        run(|| self.s.entails_all(&l, &a, opt_hold(hold)))
    }

    /// The compare tool's dump: field name to canonical string, as `state.py` builds it from the Python solver.
    fn dump<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let d = PyDict::new(p);
        for (k, v) in self.s.dump() {
            d.set_item(k, v)?;
        }
        let list = |ms: Option<&Vec<Option<PyObj>>>| -> PyResult<String> {
            match ms {
                None => Ok("N".to_string()),
                Some(ms) => {
                    let mut o = Vec::new();
                    for m in ms {
                        o.push(match m {
                            None => "None".to_string(),
                            Some(x) => x.0.bind(p).repr()?.to_string(),
                        });
                    }
                    Ok(o.join(" ; "))
                }
            }
        };
        d.set_item("tmodels", list(self.s.theory_models())?)?;
        let mut r = Vec::new();
        for ms in self.s.ring_models() {
            r.push(list(ms)?);
        }
        d.set_item("ring_tm", r.join(" // "))?;
        Ok(d)
    }

    #[getter(_restart_first)]
    fn get_restart_first(&self) -> f64 {
        self.s.restart_first
    }

    #[setter(_restart_first)]
    fn set_restart_first(&mut self, x: f64) {
        self.s.restart_first = x;
    }

    #[getter(_learnt_size_min)]
    fn get_learnt_size_min(&self) -> f64 {
        self.s.learnt_size_min
    }

    #[setter(_learnt_size_min)]
    fn set_learnt_size_min(&mut self, x: f64) {
        self.s.learnt_size_min = x;
    }

    #[getter(_var_inc)]
    fn get_var_inc(&self) -> f64 {
        self.s.var_inc
    }

    #[setter(_var_inc)]
    fn set_var_inc(&mut self, x: f64) {
        self.s.var_inc = x;
    }

    #[getter(_cla_inc)]
    fn get_cla_inc(&self) -> f64 {
        self.s.cla_inc
    }

    #[setter(_cla_inc)]
    fn set_cla_inc(&mut self, x: f64) {
        self.s.cla_inc = x;
    }

    fn stats<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        const KEYS: [&str; 11] = [
            "propagations", "conflicts", "decisions", "learned", "restarts", "vars", "clauses", "learnts",
            "rule_blocks", "witness_hits", "theory_decisions",
        ];
        let d = PyDict::new(p);
        for (k, v) in KEYS.iter().zip(self.s.stats()) {
            d.set_item(*k, v)?;
        }
        Ok(d)
    }
}

fn lits_opt(a: Option<&Bound<'_, PyAny>>) -> PyResult<Vec<u32>> {
    match a {
        None => Ok(Vec::new()),
        Some(a) => api_lits(a),
    }
}

#[pymodule]
fn sa_solver(m: &Bound<'_, PyModule>) -> PyResult<()> {
    term::py::register(m)?;
    m.add_class::<PySolver>()?;
    m.add_class::<lra_py::LraCore>()?;
    constfield::register(m)?;
    lra_cert::register(m)?;
    euf_py::add_to(m)?;
    formula_py::register(m)?;
    realroots::register(m)?;
    rows::register(m)?;
    session::register(m)?;
    relations_core::register(m)?;
    discovery::register(m)?;
    compile_loop::register(m)?;
    query::register(m)?;
    transfer_py::register(m)
}
