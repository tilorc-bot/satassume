//! Step 5c9c: the engine memos Rust works on are Rust-native: `Engine._kids`, `_qcones`, `_glue_adapters`, `_xbasis` and
//! `splits` (inventory part 5, INVENTORY-state.md :281-284).
//!
//! - **The maps.** Each engine holds one `EngineMemo` per container, in the instance's `__dict__` under Python's name. A map
//!   keeps Python's dict semantics: lookup by the key's hash, then identity or `==` (`em:key_eq` counts each `==` that runs,
//!   a callback when the key is a SymPy or Formula object), and insertion order (entries are never removed one at a time, so
//!   a `Vec` in insertion order plus a hash index is a dict's order exactly). Keys and values stay the Python objects
//!   Python's dicts held (formulas, SymPy numbers, adapters, `Split`s), because their consumers are Python objects still;
//!   what moved is the container.
//! - **Bounds as Python's:** `splits` is an `AnswerMemo(20_000)` (`put` empties it when full); `_qcones` 50,000 and `_kids`
//!   200,000 are tested by their callers (`query_cone` here, Python's `_struct`); `_xbasis` and `_glue_adapters` have none.
//! - **Where the maps come from.** `MemoSlot` is a data descriptor that `session_live._install_engmemos` puts on `Engine` for
//!   each of the five names. `Engine.__init__` (Python until 5c10d) assigns `{}` or `AnswerMemo(n)`; the descriptor turns the
//!   assignment into a fresh `EngineMemo` with the value's entries and `maxsize` (`em:slot_set`). The harness's
//!   `eng.splits = AnswerMemo(n)` (harness/state.py:91) and a test's assignment go the same way. An engine made before the
//!   install has dicts in its `__dict__`: the first read converts them, counted the same.
//! - **Rust readers** (`get`, `set`, `put`, `len`, `clear` below) reach the map directly. A container that isn't an
//!   `EngineMemo` (ref.py's engine, a test's dict passed as `memo`) is read through its own Python methods, counted
//!   `em:foreign`.
//! - **Python readers left, each a counted crossing** (`em:py_<container>` per Python call into a map's methods): Python's
//!   `_struct` reads and fills `_kids` and passes `_glue_adapters` to `glue_objects` (5c10c); `_drop_cones` clears
//!   `_kids`, `_qcones`, `_glue_adapters` (5c10c); `_drop_set_memos` clears `splits` and `_xbasis` (5c10d); the registry
//!   (`Engine.memos`: names, sizes, clear, items) and the tests read them as views. `_Mark` (term_live.py) skips them
//!   (`native`), as it skips 5c9b's.
//! - **Test-only snapshot export:** `em_snapshot(memo)` reads a map's entries from the Rust map itself, not through the view's
//!   methods, so memo_check can show the view and the map agree.
use std::cell::RefCell;
use std::collections::HashMap;

use pyo3::exceptions::{PyAttributeError, PyKeyError};
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyString, PyTuple};

use crate::relations_core::{planted, CTX_FAILED_CLEAR_SKIP, CTX_VERDICT_CLEAR_SKIP, EM_KIDS_SET_DROP, EM_QCONES_CLEAR_SKIP, EM_SLOT_NO_MAXSIZE, EM_SPLITS_NO_BOUND};
use crate::session::{tick, EM_FOREIGN, EM_FULL, EM_KEY_EQ, EM_PY_GLUE, EM_PY_KIDS, EM_PY_QCONES, EM_PY_SPLITS, EM_PY_XBASIS, EM_SLOT_SET, EM_PY_FAILED, EM_PY_VERDICT, EM_PY_CTXS};

/// The containers, by slot: Python's attribute names.
pub(crate) const SLOTS: [&str; 8] = ["_kids", "_qcones", "_glue_adapters", "_xbasis", "splits", "_failed", "_verdict", "_context_sessions"];
pub(crate) const KIDS: u8 = 0;
pub(crate) const QCONES: u8 = 1;
pub(crate) const SPLITS: u8 = 4;
/// Step 5c10b (context.rs).
pub(crate) const FAILED: u8 = 5;
pub(crate) const VERDICT: u8 = 6;
const PY_TICK: [usize; 8] = [EM_PY_KIDS, EM_PY_QCONES, EM_PY_GLUE, EM_PY_XBASIS, EM_PY_SPLITS, EM_PY_FAILED, EM_PY_VERDICT, EM_PY_CTXS];

/// A Python dict over Python keys, held in Rust, in insertion order.
#[derive(Default)]
struct OrdMap {
    entries: Vec<(Py<PyAny>, Py<PyAny>)>,
    index: HashMap<isize, Vec<usize>>,
}

/// One engine memo.
#[pyclass(module = "sa_solver", name = "EngineMemo", unsendable)]
pub struct EngineMemo {
    slot: u8,
    maxsize: Option<usize>,
    map: RefCell<OrdMap>,
}

impl EngineMemo {
    fn new(slot: u8, maxsize: Option<usize>) -> Self {
        EngineMemo { slot, maxsize, map: RefCell::new(OrdMap::default()) }
    }

    /// The entry index and value of a key equal to `k`. Candidates are copied out first: `==` may run Python code.
    fn find<'py>(&self, k: &Bound<'py, PyAny>, h: isize) -> PyResult<Option<(usize, Bound<'py, PyAny>)>> {
        let p = k.py();
        let cand: Vec<(usize, Py<PyAny>, Py<PyAny>)> = {
            let m = self.map.borrow();
            match m.index.get(&h) {
                Some(b) => b.iter().map(|&i| (i, m.entries[i].0.clone_ref(p), m.entries[i].1.clone_ref(p))).collect(),
                None => return Ok(None),
            }
        };
        for (i, kk, v) in cand {
            let kk = kk.into_bound(p);
            if kk.is(k) {
                return Ok(Some((i, v.into_bound(p))));
            }
            tick(EM_KEY_EQ);
            if kk.eq(k)? {
                return Ok(Some((i, v.into_bound(p))));
            }
        }
        Ok(None)
    }

    pub(crate) fn lookup<'py>(&self, k: &Bound<'py, PyAny>) -> PyResult<Option<Bound<'py, PyAny>>> {
        let h = k.hash()?;
        Ok(self.find(k, h)?.map(|(_, v)| v))
    }

    /// `self[k] = v`: an equal key keeps its place and its stored key, as a dict's does.
    pub(crate) fn store(&self, k: &Bound<'_, PyAny>, v: &Bound<'_, PyAny>) -> PyResult<()> {
        let h = k.hash()?;
        let at = self.find(k, h)?.map(|(i, _)| i);
        let mut m = self.map.borrow_mut();
        match at {
            Some(i) if i < m.entries.len() => m.entries[i].1 = v.clone().unbind(),
            _ => {
                let i = m.entries.len();
                m.entries.push((k.clone().unbind(), v.clone().unbind()));
                m.index.entry(h).or_default().push(i);
            }
        }
        Ok(())
    }

    /// `AnswerMemo.put`: empties the map first when it holds `maxsize` entries.
    pub(crate) fn put(&self, k: &Bound<'_, PyAny>, v: &Bound<'_, PyAny>) -> PyResult<()> {
        if let Some(n) = self.maxsize {
            if self.len() >= n && !(self.slot == SPLITS && planted(EM_SPLITS_NO_BOUND)) {
                tick(EM_FULL);
                self.wipe();
            }
        }
        self.store(k, v)
    }

    pub(crate) fn len(&self) -> usize {
        self.map.borrow().entries.len()
    }

    pub(crate) fn wipe(&self) {
        let mut m = self.map.borrow_mut();
        m.entries.clear();
        m.index.clear();
    }

    fn entries(&self, p: Python<'_>) -> Vec<(Py<PyAny>, Py<PyAny>)> {
        self.map.borrow().entries.iter().map(|(k, v)| (k.clone_ref(p), v.clone_ref(p))).collect()
    }

    fn py(&self) {
        tick(PY_TICK[self.slot as usize]);
    }
}

/// The Python methods: the views the registry, the tests and the Python rows still on Python (named above) call. Each call is
/// a crossing, counted per container.
#[pymethods]
impl EngineMemo {
    #[getter]
    fn name(&self) -> &'static str {
        SLOTS[self.slot as usize]
    }
    #[getter]
    fn maxsize(&self) -> Option<usize> {
        self.maxsize
    }
    /// Marks the view for `_Mark` (term_live.py), which leaves Rust-native tables to Rust.
    #[getter]
    fn native(&self) -> bool {
        true
    }
    /// A container Python's registry had, now Rust's: the switch digest counts it (memo_check.py).
    #[getter]
    fn moved(&self) -> bool {
        true
    }
    fn __len__(&self) -> usize {
        self.py();
        self.len()
    }
    fn __bool__(&self) -> bool {
        self.py();
        self.len() > 0
    }
    fn __contains__(&self, k: &Bound<'_, PyAny>) -> PyResult<bool> {
        self.py();
        Ok(self.lookup(k)?.is_some())
    }
    #[pyo3(signature = (k, default=None))]
    fn get<'py>(&self, k: &Bound<'py, PyAny>, default: Option<Bound<'py, PyAny>>) -> PyResult<Bound<'py, PyAny>> {
        self.py();
        Ok(match self.lookup(k)? {
            Some(v) => v,
            None => default.unwrap_or_else(|| k.py().None().into_bound(k.py())),
        })
    }
    fn __getitem__<'py>(&self, k: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        self.py();
        self.lookup(k)?.ok_or_else(|| PyKeyError::new_err(k.clone().unbind()))
    }
    fn __setitem__(&self, k: &Bound<'_, PyAny>, v: &Bound<'_, PyAny>) -> PyResult<()> {
        self.py();
        if self.slot == KIDS && planted(EM_KIDS_SET_DROP) {
            return Ok(());
        }
        self.store(k, v)
    }
    #[pyo3(name = "put")]
    fn py_put(&self, k: &Bound<'_, PyAny>, v: &Bound<'_, PyAny>) -> PyResult<()> {
        self.py();
        self.put(k, v)
    }
    /// The planted bug the inventory names: `_drop_cones` (and the registry) leaving `_qcones` as it is.
    fn clear(&self) {
        self.py();
        if self.slot == QCONES && planted(EM_QCONES_CLEAR_SKIP) {
            return;
        }
        // 5c10b: the planted bug the inventory names, `_verdict` kept across a settings change (`_drop_set_memos`).
        if (self.slot == VERDICT && planted(CTX_VERDICT_CLEAR_SKIP)) || (self.slot == FAILED && planted(CTX_FAILED_CLEAR_SKIP)) {
            return;
        }
        self.wipe();
    }
    fn items<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        self.py();
        PyList::new(p, self.entries(p).into_iter().map(|(k, v)| PyTuple::new(p, [k, v])).collect::<PyResult<Vec<_>>>()?)
    }
    fn keys<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        self.py();
        PyList::new(p, self.entries(p).into_iter().map(|(k, _)| k))
    }
    fn values<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        self.py();
        PyList::new(p, self.entries(p).into_iter().map(|(_, v)| v))
    }
    fn __iter__<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        Ok(self.keys(p)?.try_iter()?.into_any())
    }
    fn __repr__(&self) -> String {
        format!("<EngineMemo {} {}/{}>", SLOTS[self.slot as usize], self.len(), self.maxsize.map_or("-".to_string(), |n| n.to_string()))
    }
}

/// A new map for slot `slot` holding `value`'s entries and `maxsize` (a dict or an `AnswerMemo`, as Python's `__init__` and the
/// harness assign).
fn convert<'py>(p: Python<'py>, slot: u8, value: &Bound<'py, PyAny>) -> PyResult<Bound<'py, EngineMemo>> {
    tick(EM_SLOT_SET);
    if let Ok(m) = value.cast::<EngineMemo>() {
        return Ok(m.clone());
    }
    let maxsize = if planted(EM_SLOT_NO_MAXSIZE) {
        None
    } else {
        match value.getattr(intern!(p, "maxsize")) {
            Ok(n) => Some(n.extract::<usize>()?),
            Err(_) => None,
        }
    };
    let m = EngineMemo::new(slot, maxsize);
    if let Ok(d) = value.cast::<PyDict>() {
        for (k, v) in d.iter() {
            m.store(&k, &v)?;
        }
    }
    Bound::new(p, m)
}

/// The data descriptor on `Engine` for one of the five names: the instance's map lives in its `__dict__` under the name.
#[pyclass(module = "sa_solver", name = "MemoSlot", frozen)]
pub struct MemoSlot {
    slot: u8,
}

#[pymethods]
impl MemoSlot {
    #[new]
    fn py_new(slot: u8) -> Self {
        MemoSlot { slot }
    }
    fn __get__<'py>(slf: &Bound<'py, Self>, inst: Option<&Bound<'py, PyAny>>, _owner: Option<&Bound<'py, PyAny>>) -> PyResult<Bound<'py, PyAny>> {
        let Some(inst) = inst.filter(|i| !i.is_none()) else { return Ok(slf.clone().into_any()) };
        let p = slf.py();
        let slot = slf.get().slot;
        let name = PyString::new(p, SLOTS[slot as usize]);
        let d = inst.getattr(intern!(p, "__dict__"))?.cast_into::<PyDict>()?;
        let Some(v) = d.get_item(&name)? else {
            return Err(PyAttributeError::new_err(format!("'Engine' object has no attribute '{}'", SLOTS[slot as usize])));
        };
        if v.is_instance_of::<EngineMemo>() {
            return Ok(v);
        }
        let m = convert(p, slot, &v)?;
        d.set_item(&name, &m)?;
        Ok(m.into_any())
    }
    fn __set__(&self, inst: &Bound<'_, PyAny>, value: &Bound<'_, PyAny>) -> PyResult<()> {
        let p = inst.py();
        let m = convert(p, self.slot, value)?;
        inst.getattr(intern!(p, "__dict__"))?.cast_into::<PyDict>()?.set_item(SLOTS[self.slot as usize], m)
    }
    #[getter]
    fn name(&self) -> &'static str {
        SLOTS[self.slot as usize]
    }
}

// The Rust readers. A foreign container (not an `EngineMemo`) goes through its own Python methods, counted.

pub(crate) fn get<'py>(c: &Bound<'py, PyAny>, k: &Bound<'py, PyAny>) -> PyResult<Option<Bound<'py, PyAny>>> {
    if let Ok(m) = c.cast::<EngineMemo>() {
        return m.borrow().lookup(k);
    }
    tick(EM_FOREIGN);
    let r = c.call_method1(intern!(c.py(), "get"), (k,))?;
    Ok(if r.is_none() { None } else { Some(r) })
}

pub(crate) fn set(c: &Bound<'_, PyAny>, k: &Bound<'_, PyAny>, v: &Bound<'_, PyAny>) -> PyResult<()> {
    if let Ok(m) = c.cast::<EngineMemo>() {
        return m.borrow().store(k, v);
    }
    tick(EM_FOREIGN);
    c.set_item(k, v)
}

/// `AnswerMemo.put`.
pub(crate) fn put(c: &Bound<'_, PyAny>, k: &Bound<'_, PyAny>, v: &Bound<'_, PyAny>) -> PyResult<()> {
    if let Ok(m) = c.cast::<EngineMemo>() {
        return m.borrow().put(k, v);
    }
    tick(EM_FOREIGN);
    c.call_method1(intern!(c.py(), "put"), (k, v)).map(|_| ())
}

/// The first entry's value (plant `em-xbasis-first` only).
pub(crate) fn first<'py>(c: &Bound<'py, PyAny>) -> PyResult<Option<Bound<'py, PyAny>>> {
    let p = c.py();
    if let Ok(m) = c.cast::<EngineMemo>() {
        return Ok(m.borrow().map.borrow().entries.first().map(|(_, v)| v.clone_ref(p).into_bound(p)));
    }
    Ok(None)
}

pub(crate) fn len(c: &Bound<'_, PyAny>) -> PyResult<usize> {
    if let Ok(m) = c.cast::<EngineMemo>() {
        return Ok(m.borrow().len());
    }
    tick(EM_FOREIGN);
    c.len()
}

pub(crate) fn clear(c: &Bound<'_, PyAny>) -> PyResult<()> {
    if let Ok(m) = c.cast::<EngineMemo>() {
        m.borrow().wipe();
        return Ok(());
    }
    tick(EM_FOREIGN);
    c.call_method0(intern!(c.py(), "clear")).map(|_| ())
}

/// Test-only: `(name, maxsize, [(key, value)])` read from the map itself, in its order, not through the view's methods.
#[pyfunction]
fn em_snapshot<'py>(p: Python<'py>, memo: &Bound<'py, EngineMemo>) -> PyResult<(&'static str, Option<usize>, Bound<'py, PyList>)> {
    let m = memo.borrow();
    let rows = PyList::new(p, m.entries(p).into_iter().map(|(k, v)| PyTuple::new(p, [k, v])).collect::<PyResult<Vec<_>>>()?)?;
    Ok((SLOTS[m.slot as usize], m.maxsize, rows))
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<EngineMemo>()?;
    m.add_class::<MemoSlot>()?;
    m.add_function(wrap_pyfunction!(em_snapshot, m)?)
}
