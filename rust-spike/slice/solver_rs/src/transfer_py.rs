//! `TransferTheory`, `EqualitySharing` and `transfer_wanted` for Python: `transfer.rs` behind the surface
//! `relations.py` and the solver's hooks use. `PyClasses` is the adapter over EUF until component 2 lands; it reads only
//! `rep`, `members`, `explain`, so it works on Python's `EUFTheory` and on port/2's views. Its crossings are counted.
//!
//! `&mut self` is held across the calls out. They don't come back: `explain` and the two reads only read, and
//! `on_merge` fires from EUF's own hooks, not from these. If one ever did, pyo3 raises instead of aliasing.
use crate::handle::TermId;
use crate::pyset::PySetOrder;
use crate::term::offline::OfflineData;
use crate::transfer::{Classes, Pred, SharingCore, TransferCore};
use pyo3::exceptions::{PyRuntimeError, PyTypeError, PyValueError};
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PySet, PyTuple};
use pyo3::{PyTraverseError, PyVisit};
use std::cell::Cell;
use std::collections::HashMap;
use std::sync::OnceLock;

#[derive(Default)]
struct Crossings {
    rep: Cell<u64>,
    members: Cell<u64>,
    explain: Cell<u64>,
}

struct PyClasses<'a, 'py> {
    euf: &'a Bound<'py, PyAny>,
    counts: &'a Crossings,
}

fn bump(c: &Cell<u64>) {
    c.set(c.get() + 1);
}

impl Classes for PyClasses<'_, '_> {
    type Err = PyErr;

    fn rep(&self, t: TermId) -> PyResult<TermId> {
        bump(&self.counts.rep);
        let p = self.euf.py();
        Ok(TermId(self.euf.getattr(intern!(p, "rep"))?.get_item(t.0)?.extract()?))
    }

    fn members(&self, r: TermId) -> PyResult<Vec<TermId>> {
        bump(&self.counts.members);
        let p = self.euf.py();
        let ms = self.euf.getattr(intern!(p, "members"))?.get_item(r.0)?;
        ms.try_iter()?.map(|m| Ok(TermId(m?.extract()?))).collect()
    }

    fn explain(&self, a: TermId, b: TermId) -> PyResult<Vec<i32>> {
        bump(&self.counts.explain);
        let p = self.euf.py();
        let e = self.euf.call_method1(intern!(p, "explain"), (a.0, b.0))?;
        e.try_iter()?.map(|l| Ok(l?.extract()?)).collect()
    }

    fn initial_multi(&self) -> PyResult<Vec<TermId>> {
        let p = self.euf.py();
        let rep = self.euf.getattr(intern!(p, "rep"))?;
        let mut out = Vec::new();
        for (r, ms) in self.euf.getattr(intern!(p, "members"))?.try_iter()?.enumerate() {
            if ms?.len()? > 1 && rep.get_item(r)?.extract::<usize>()? == r {
                out.push(TermId(r as u32));
            }
        }
        Ok(out)
    }
}

/// Python's subclass in `backend.py` calls `_attach` in its `__init__`, so the listener is the instance's own bound
/// method, which is the only thing a wrapper on the class can see. `register_atom` refuses until it has.
#[pyclass(name = "TransferTheory", module = "sa_solver", unsendable, subclass, dict, weakref)]
pub struct PyTransfer {
    core: TransferCore,
    euf: Option<Py<PyAny>>,
    counts: Crossings,
    attached: bool,
}

fn bound<'a, 'py>(p: Python<'py>, euf: &'a Option<Py<PyAny>>) -> PyResult<&'a Bound<'py, PyAny>> {
    euf.as_ref().map(|e| e.bind(p)).ok_or_else(|| PyRuntimeError::new_err("TransferTheory: EUF was cleared"))
}

/// `BASIS_INDEX["polar"]`: section 9's offline data, read once at load. It never changes after that and holds no term.
static POLAR: OnceLock<Pred> = OnceLock::new();

/// Reads component D's file, which refuses on any hash mismatch. Only the first successful call in a process reads it.
#[pyfunction]
fn read_offline(path: &str, sources_root: &str, sympy: &str) -> PyResult<()> {
    if POLAR.get().is_some() {
        return Ok(());
    }
    let data = OfflineData::load(path, sources_root, sympy)
        .map_err(|e| PyValueError::new_err(format!("offline data refused: {e}")))?;
    let basis = data.basis().ok_or_else(|| PyValueError::new_err("offline data has no basis"))?;
    let at = basis
        .iter()
        .position(|b| *b == "polar")
        .ok_or_else(|| PyValueError::new_err("offline data's basis has no polar"))?;
    let _ = POLAR.set(at as Pred);
    Ok(())
}

/// For the check against Python's `BASIS_INDEX`. `None` until `read_offline` has run.
#[pyfunction]
fn _polar_index() -> Option<Pred> {
    POLAR.get().copied()
}

#[pymethods]
impl PyTransfer {
    #[new]
    fn new(p: Python<'_>, euf: Py<PyAny>) -> PyResult<Self> {
        let polar = *POLAR.get().ok_or_else(|| {
            PyRuntimeError::new_err("TransferTheory: offline data not read; call sa_solver.read_offline first")
        })?;
        let counts = Crossings::default();
        let core = {
            let view = PyClasses { euf: euf.bind(p), counts: &counts };
            TransferCore::new(&view, polar)?
        };
        Ok(PyTransfer { core, euf: Some(euf), counts, attached: false })
    }

    /// `euf.on_merge = self._merged`.
    fn _attach(mut slf: PyRefMut<'_, Self>) -> PyResult<()> {
        slf.attached = true;
        let p = slf.py();
        let euf = slf.euf.as_ref().map(|e| e.clone_ref(p));
        let merged = slf.into_pyobject(p)?.getattr(intern!(p, "_merged"))?;
        match euf {
            Some(e) => e.bind(p).setattr(intern!(p, "on_merge"), merged),
            None => Err(PyRuntimeError::new_err("TransferTheory: EUF was cleared")),
        }
    }

    fn __traverse__(&self, visit: PyVisit<'_>) -> Result<(), PyTraverseError> {
        if let Some(e) = &self.euf {
            visit.call(e)?;
        }
        Ok(())
    }

    fn __clear__(&mut self) {
        self.euf = None;
    }

    #[getter]
    fn euf(&self, p: Python<'_>) -> Option<Py<PyAny>> {
        self.euf.as_ref().map(|e| e.clone_ref(p))
    }

    #[getter]
    fn sel(&self) -> Option<i32> {
        self.core.sel
    }

    #[getter]
    fn enabled(&self) -> bool {
        self.core.enabled
    }

    fn guard(&mut self, sel: i32) {
        self.core.guard(sel);
    }

    fn switch(&mut self, term: u32, full: i32, polar: i32) -> Vec<i32> {
        self.core.switch(TermId(term), full, polar)
    }

    fn _merged(&mut self, _ra: u32, rb: u32) {
        self.core.merged(TermId(rb));
    }

    fn register_atom(&mut self, literal: i32, payload: &Bound<'_, PyAny>) -> PyResult<()> {
        if !self.attached {
            return Err(PyRuntimeError::new_err("TransferTheory: not attached to EUF's on_merge"));
        }
        if self.core.is_control(literal) {
            return Ok(());
        }
        if self.core.is_bad_atom(literal) {
            return Err(PyValueError::new_err(format!("bad or repeated atom variable {literal}")));
        }
        let term: u32 = payload.get_item(0)?.extract()?;
        let pred: Pred = payload.get_item(1)?.extract()?;
        let partial = payload.len()? > 2 && payload.get_item(2)?.is_truthy()?;
        self.core.register_atom(literal, TermId(term), pred, partial);
        Ok(())
    }

    fn assert_lit(&mut self, p: Python<'_>, literal: i32) -> PyResult<Option<Py<PyAny>>> {
        let view = PyClasses { euf: bound(p, &self.euf)?, counts: &self.counts };
        self.core.assert_lit(&view, literal)?;
        Ok(None)
    }

    fn set_fixed(&mut self, p: Python<'_>, term: u32, facts: &Bound<'_, PyAny>) -> PyResult<()> {
        let term = TermId(term);
        if self.core.has_fixed(term) {
            return Ok(());
        }
        // `dict(facts)`, by Python itself: a repeated predicate keeps its first place and its last value.
        let d = p.get_type::<PyDict>().call1((facts,))?;
        let mut out = Vec::new();
        for kv in d.cast::<PyDict>()?.iter() {
            out.push((kv.0.extract::<Pred>()?, kv.1.extract::<bool>()?));
        }
        self.core.set_fixed(term, out);
        Ok(())
    }

    fn propagate(&mut self, p: Python<'_>) -> PyResult<Vec<(i32, Vec<i32>)>> {
        let view = PyClasses { euf: bound(p, &self.euf)?, counts: &self.counts };
        self.core.propagate(&view)
    }

    fn check(&mut self, p: Python<'_>) -> PyResult<Option<(bool, Vec<i32>)>> {
        let view = PyClasses { euf: bound(p, &self.euf)?, counts: &self.counts };
        Ok(self.core.check(&view)?.map(|why| (false, why)))
    }

    fn decide(&mut self, p: Python<'_>) -> PyResult<Option<i32>> {
        let view = PyClasses { euf: bound(p, &self.euf)?, counts: &self.counts };
        self.core.decide(&view)
    }

    fn push_level(&mut self) {
        self.core.push_level();
    }

    fn pop_level(&mut self) {
        self.core.pop_level();
    }

    fn __repr__(&self) -> String {
        self.core.repr()
    }

    /// Field -> string, for the shadow and the session digests.
    fn _dump(&self) -> HashMap<&'static str, String> {
        self.core.dump().into_iter().collect()
    }

    /// How often each EUF read crossed into Python, for the report.
    fn _crossings(&self) -> HashMap<&'static str, u64> {
        HashMap::from([
            ("rep", self.counts.rep.get()),
            ("members", self.counts.members.get()),
            ("explain", self.counts.explain.get()),
        ])
    }
}

/// `SharingCore` over Python's objects. Python's own dict says what is one term, by the objects' `__hash__` and
/// `__eq__`, as `count` and `_seen` do. The numbers are this instance's. Pairs hand back the object Python would: for a
/// term new this update, its first occurrence in this update, which need not be the object first numbered.
#[pyclass(name = "EqualitySharing", module = "sa_solver", unsendable, subclass, weakref)]
pub struct PySharing {
    core: SharingCore,
    ids: Py<PyDict>,
    shared_objs: HashMap<TermId, Py<PyAny>>,
}

#[pymethods]
impl PySharing {
    #[new]
    fn new(p: Python<'_>) -> Self {
        PySharing { core: SharingCore::default(), ids: PyDict::new(p).unbind(), shared_objs: HashMap::new() }
    }

    #[getter]
    fn shared(&self, p: Python<'_>) -> Vec<Py<PyAny>> {
        self.core.shared.iter().map(|t| self.shared_objs[t].clone_ref(p)).collect()
    }

    fn update(&mut self, p: Python<'_>, term_sets: &Bound<'_, PyAny>) -> PyResult<Vec<(Py<PyAny>, Py<PyAny>)>> {
        let ids = self.ids.bind(p);
        let mut sets = Vec::new();
        let mut first: HashMap<TermId, Py<PyAny>> = HashMap::new();
        for ts in term_sets.try_iter()? {
            let mut set = Vec::new();
            for t in ts?.try_iter()? {
                let t = t?;
                let id = match ids.get_item(&t)? {
                    Some(n) => TermId(n.extract()?),
                    None => {
                        let n = ids.len() as u32;
                        ids.set_item(&t, n)?;
                        TermId(n)
                    }
                };
                first.entry(id).or_insert_with(|| t.clone().unbind());
                set.push(id);
            }
            sets.push(set);
        }
        let (new, pairs) = self.core.update(&sets);
        for t in new {
            self.shared_objs.insert(t, first.remove(&t).expect("a new term was seen in this update"));
        }
        Ok(pairs
            .into_iter()
            .map(|(u, t)| (self.shared_objs[&u].clone_ref(p), self.shared_objs[&t].clone_ref(p)))
            .collect())
    }
}

/// `transfer_wanted`. Python's dict numbers the sides, so `(y, x) in lts` is decided by the terms' own `==`, and the
/// loop is any-style, so the order of `lts` can't matter. A side count other than two raises, as `for x, y in lts`
/// does, though Python would raise only on reaching it; `lt` atoms always have two.
#[pyfunction]
fn transfer_wanted(p: Python<'_>, atoms: &Bound<'_, PyAny>) -> PyResult<bool> {
    let atoms: Vec<Bound<'_, PyAny>> = atoms.try_iter()?.collect::<PyResult<_>>()?;
    let pred = intern!(p, "pred");
    for a in &atoms {
        if a.getattr(pred)?.eq(intern!(p, "eq"))? {
            return Ok(true);
        }
    }
    // A real `set`, of the atoms' own `expr`, as Python builds. Which atom is met first is visible when one isn't a pair
    // (sa-port-25: `lt(1,2), lt(2,1), lt(1,2,3)` is True or ValueError by hash order), and a pair's reverse is found by
    // `tuple` hash and `==` against whatever `expr` is, so `"ab"` isn't `("a", "b")`.
    let lts = PySet::empty(p)?;
    for a in &atoms {
        if a.getattr(pred)?.eq(intern!(p, "lt"))? {
            lts.add(a.getattr(intern!(p, "expr"))?)?;
        }
    }
    for e in lts.iter() {
        let (x, y) = unpack2(&e)?;
        if lts.contains(PyTuple::new(p, [y, x])?)? {
            return Ok(true);
        }
    }
    Ok(false)
}

/// `x, y = v`: CPython 3.12's `UNPACK_SEQUENCE`, with its text.
fn unpack2<'py>(v: &Bound<'py, PyAny>) -> PyResult<(Bound<'py, PyAny>, Bound<'py, PyAny>)> {
    let p = v.py();
    let mut it = v.try_iter().map_err(|e| {
        let plain = e.is_instance_of::<PyTypeError>(p)
            && !v.get_type().hasattr(intern!(p, "__iter__")).unwrap_or(true)
            && !v.get_type().hasattr(intern!(p, "__getitem__")).unwrap_or(true);
        match (plain, v.get_type().name()) {
            (true, Ok(n)) => PyTypeError::new_err(format!("cannot unpack non-iterable {n} object")),
            _ => e,
        }
    })?;
    let short = |n: usize| PyValueError::new_err(format!("not enough values to unpack (expected 2, got {n})"));
    let x = it.next().ok_or_else(|| short(0))??;
    let y = it.next().ok_or_else(|| short(1))??;
    if it.next().transpose()?.is_some() {
        return Err(PyValueError::new_err("too many values to unpack (expected 2)"));
    }
    Ok((x, y))
}

/// For `transfer_fuzz.py`: builds each group by `add`, folds them with `|`, and returns the result's iteration order.
#[pyfunction]
fn _pyset_replay(groups: Vec<Vec<u32>>) -> Vec<u32> {
    let mut acc: Option<PySetOrder> = None;
    for g in &groups {
        let mut s = PySetOrder::new();
        for &k in g {
            s.add(k);
        }
        acc = Some(match acc {
            None => s,
            Some(a) => a.union(&s),
        });
    }
    acc.map_or_else(Vec::new, |s| s.iter().collect())
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyTransfer>()?;
    m.add_class::<PySharing>()?;
    m.add_function(wrap_pyfunction!(transfer_wanted, m)?)?;
    m.add_function(wrap_pyfunction!(_pyset_replay, m)?)?;
    m.add_function(wrap_pyfunction!(read_offline, m)?)?;
    m.add_function(wrap_pyfunction!(_polar_index, m)?)?;
    Ok(())
}
