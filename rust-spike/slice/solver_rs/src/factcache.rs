//! Step 5c10a: the fact caches are Rust-native: `Engine.cache.store` and `Engine.custom_cache.store` (inventory part 5,
//! INVENTORY-state.md :285-287; container row :197).
//!
//! - **The cache.** `FactCache` is the whole `DictCache`: its store (node -> {pred: value}), `maxsize`, `_epoch` and
//!   `_settings`, with Python's methods `sync`, `facts`, `get`, `put` and their semantics exactly: lookup by the node's hash, then
//!   identity or `==` (`fc:key_eq`), insertion order kept (a `Vec` plus a hash index; no single deletes exist), the store emptied
//!   when a new node finds it at `maxsize` (`fc:full`), `sync` emptying it on another epoch or other settings (`!=`, as Python).
//! - **Where caches come from.** `FactCache` is registered as `sa_solver.DictCache`.
//!   `session_live._install_factcache` binds it over Python's class in every loaded module (`engine`, `satassume`,
//!   `sympy_api`, ...; `ObjectCache` too, so `type(Engine().cache) is DictCache` holds), and gives Python's class a `__new__`
//!   that returns one, for a name bound before the install. So every `DictCache(...)` (the engine's default, a caller's shared
//!   cache, the harness's sized ones) is one, and a cache passed to several engines is one object they all write (`fc:new`).
//! - **Callers left on Python, each a counted crossing:** `Engine.is_`, `is_many`, `_is_custom`, `_put_result` (`facts`, `put`;
//!   5c10c), `_check_version` (`sync`; 5c10d), `_settings_changed` (`store.clear()`; 5c10d). No Rust code calls the caches yet.
//! - **The read-only view.** `store` is a `FactView`: a mapping over the Rust store (len, in, [], get, keys, values, items, iter,
//!   `==` with a dict), each value a fresh dict. It has no writer but `clear`, which the registry (`Engine.memos.clear()`, public)
//!   and `_settings_changed` call (`fc:clear`). Views are `native` and `moved`, so `_Mark` skips them and the registry digest
//!   still counts them.
//! - **Rollback.** `_Mark` (term_live.py) undid a refused query's puts by size plus `_journaled_put`'s journal. Here it takes
//!   `_fc_mark()` (entries, clear generation, put serial) and calls `_fc_rollback(mark)`: preds added after the mark to nodes
//!   below it are removed, nodes past it dropped, and a store emptied since is emptied (`fc:rollback`). `_journaled_put` goes.
//! - **Test-only snapshot export:** `fc_snapshot(cache)` reads the Rust store itself, not through the view.
use std::cell::{Cell, RefCell};
use std::collections::HashMap;

use pyo3::basic::CompareOp;
use pyo3::exceptions::PyKeyError;
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyTuple};

use crate::relations_core::{
    planted, FC_CLEAR_SKIP, FC_CUSTOM_PUT_DROP, FC_FACTS_FIRST, FC_GET_NO_DEFAULT, FC_NEW_NO_MAXSIZE, FC_NO_BOUND,
    FC_PUT_NEW_DROP, FC_ROLLBACK_SKIP, FC_SHARED_SYNC_IS, FC_SYNC_NO_CLEAR, FC_VIEW_DROP_LAST,
};
use crate::session::{
    tick, FC_CLEAR, FC_FULL, FC_KEY_EQ, FC_NEW, FC_PY_FACTS, FC_PY_GET, FC_PY_KEY, FC_PY_PUT, FC_PY_SYNC, FC_ROLLBACK, FC_VIEW,
};

/// One node's facts: (pred, value, serial of the put that added the pred).
type Facts = Vec<(Py<PyAny>, Py<PyAny>, u64)>;

#[derive(Default)]
struct Store {
    entries: Vec<(Py<PyAny>, Facts)>,
    index: HashMap<isize, Vec<usize>>,
}

#[pyclass(module = "sa_solver", name = "DictCache", unsendable, weakref)]
pub struct FactCache {
    #[pyo3(get, set)]
    maxsize: usize,
    epoch: i64,
    settings: Py<PyAny>,
    store: RefCell<Store>,
    serial: Cell<u64>,
    generation: Cell<u64>,
}

fn same(a: &Bound<'_, PyAny>, b: &Bound<'_, PyAny>) -> PyResult<bool> {
    if a.is(b) {
        return Ok(true);
    }
    a.eq(b)
}

impl FactCache {
    /// The entry index of a node equal to `k`. Candidates are copied out first: `==` may run Python code.
    fn find(&self, k: &Bound<'_, PyAny>, h: isize) -> PyResult<Option<usize>> {
        let p = k.py();
        let cand: Vec<(usize, Py<PyAny>)> = {
            let s = self.store.borrow();
            match s.index.get(&h) {
                Some(b) => b.iter().map(|&i| (i, s.entries[i].0.clone_ref(p))).collect(),
                None => return Ok(None),
            }
        };
        for (i, kk) in cand {
            let kk = kk.into_bound(p);
            if kk.is(k) {
                return Ok(Some(i));
            }
            tick(FC_KEY_EQ);
            if kk.eq(k)? {
                return Ok(Some(i));
            }
        }
        Ok(None)
    }

    fn facts_of<'py>(&self, p: Python<'py>, i: usize) -> Vec<(Py<PyAny>, Py<PyAny>)> {
        let s = self.store.borrow();
        s.entries.get(i).map(|e| e.1.iter().map(|(k, v, _)| (k.clone_ref(p), v.clone_ref(p))).collect()).unwrap_or_default()
    }

    fn dict_of<'py>(&self, p: Python<'py>, i: usize) -> PyResult<Bound<'py, PyDict>> {
        let d = PyDict::new(p);
        for (k, v) in self.facts_of(p, i) {
            d.set_item(k, v)?;
        }
        Ok(d)
    }

    fn lookup(&self, k: &Bound<'_, PyAny>) -> PyResult<Option<usize>> {
        let h = k.hash()?;
        self.find(k, h)
    }

    fn len(&self) -> usize {
        self.store.borrow().entries.len()
    }

    fn wipe(&self) {
        let mut s = self.store.borrow_mut();
        s.entries.clear();
        s.index.clear();
        self.generation.set(self.generation.get() + 1);
    }

    fn keys_of(&self, p: Python<'_>) -> Vec<Py<PyAny>> {
        let s = self.store.borrow();
        let mut ks: Vec<Py<PyAny>> = s.entries.iter().map(|e| e.0.clone_ref(p)).collect();
        if planted(FC_VIEW_DROP_LAST) {
            ks.pop();
        }
        ks
    }

    fn snapshot<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let d = PyDict::new(p);
        for (i, k) in self.keys_of(p).into_iter().enumerate() {
            d.set_item(k, self.dict_of(p, i)?)?;
        }
        Ok(d)
    }

    fn pred_at(&self, p: Python<'_>, i: usize, pred: &Bound<'_, PyAny>) -> PyResult<Option<Py<PyAny>>> {
        for (k, v) in self.facts_of(p, i) {
            if same(k.bind(p), pred)? {
                return Ok(Some(v));
            }
        }
        Ok(None)
    }
}

fn is_custom(p: Python<'_>, pred: &Bound<'_, PyAny>) -> PyResult<bool> {
    let idx = p.import(intern!(p, "satassume.knowledge.rules"))?.getattr(intern!(p, "PRED_INDEX"))?;
    Ok(!idx.contains(pred)?)
}

#[pymethods]
impl FactCache {
    #[new]
    #[pyo3(signature = (maxsize=200_000))]
    fn py_new(p: Python<'_>, maxsize: usize) -> PyResult<Self> {
        tick(FC_NEW);
        let epoch: i64 =
            p.import(intern!(p, "satassume.state.epoch"))?.getattr(intern!(p, "EPOCH"))?.get_item(0)?.extract()?;
        let maxsize = if planted(FC_NEW_NO_MAXSIZE) { 200_000 } else { maxsize };
        Ok(FactCache {
            maxsize,
            epoch,
            settings: p.None(),
            store: RefCell::new(Store::default()),
            serial: Cell::new(0),
            generation: Cell::new(0),
        })
    }

    #[getter]
    fn native(&self) -> bool {
        true
    }

    #[getter(_epoch)]
    fn get_epoch(&self) -> i64 {
        tick(FC_PY_KEY);
        self.epoch
    }

    #[setter(_epoch)]
    fn set_epoch(&mut self, v: i64) {
        tick(FC_PY_KEY);
        self.epoch = v;
    }

    #[getter(_settings)]
    fn get_settings(&self, p: Python<'_>) -> Py<PyAny> {
        tick(FC_PY_KEY);
        self.settings.clone_ref(p)
    }

    #[setter(_settings)]
    fn set_settings(&mut self, v: Py<PyAny>) {
        tick(FC_PY_KEY);
        self.settings = v;
    }

    /// `DictCache.sync`.
    fn sync(&mut self, epoch: i64, settings: &Bound<'_, PyAny>) -> PyResult<()> {
        tick(FC_PY_SYNC);
        let p = settings.py();
        let old = self.settings.bind(p);
        let other = !old.is_none()
            && if planted(FC_SHARED_SYNC_IS) { !old.is(settings) } else { old.ne(settings)? };
        if (self.epoch != epoch && !planted(FC_SYNC_NO_CLEAR)) || other {
            self.wipe();
        }
        self.epoch = epoch;
        self.settings = settings.clone().unbind();
        Ok(())
    }

    /// `DictCache.facts`: a fresh dict of the node's facts, or None.
    fn facts<'py>(&self, k: &Bound<'py, PyAny>) -> PyResult<Option<Bound<'py, PyDict>>> {
        tick(FC_PY_FACTS);
        let p = k.py();
        match self.lookup(k)? {
            None => Ok(None),
            Some(i) => {
                let d = self.dict_of(p, i)?;
                if planted(FC_FACTS_FIRST) && d.len() > 1 {
                    let first = d.items().get_item(0)?;
                    let one = PyDict::new(p);
                    one.set_item(first.get_item(0)?, first.get_item(1)?)?;
                    return Ok(Some(one));
                }
                Ok(Some(d))
            }
        }
    }

    /// `DictCache.get`.
    #[pyo3(signature = (k, pred, default=None))]
    fn get<'py>(&self, k: &Bound<'py, PyAny>, pred: &Bound<'py, PyAny>, default: Option<Bound<'py, PyAny>>) -> PyResult<Bound<'py, PyAny>> {
        tick(FC_PY_GET);
        let p = k.py();
        let dflt = if planted(FC_GET_NO_DEFAULT) { p.None().into_bound(p) } else { default.unwrap_or_else(|| p.None().into_bound(p)) };
        Ok(match self.lookup(k)? {
            None => dflt,
            Some(i) => self.pred_at(p, i, pred)?.map(|v| v.into_bound(p)).unwrap_or(dflt),
        })
    }

    /// `DictCache.put`.
    fn put(&self, k: &Bound<'_, PyAny>, pred: &Bound<'_, PyAny>, value: &Bound<'_, PyAny>) -> PyResult<()> {
        tick(FC_PY_PUT);
        let p = k.py();
        if planted(FC_CUSTOM_PUT_DROP) && is_custom(p, pred)? {
            return Ok(());
        }
        let h = k.hash()?;
        let at = self.find(k, h)?;
        let serial = self.serial.get() + 1;
        self.serial.set(serial);
        match at {
            None => {
                if planted(FC_PUT_NEW_DROP) {
                    return Ok(());
                }
                if self.len() >= self.maxsize && !planted(FC_NO_BOUND) {
                    tick(FC_FULL);
                    self.wipe();
                }
                let mut s = self.store.borrow_mut();
                let i = s.entries.len();
                s.entries.push((k.clone().unbind(), vec![(pred.clone().unbind(), value.clone().unbind(), serial)]));
                s.index.entry(h).or_default().push(i);
            }
            Some(i) => {
                let mut pos = None;
                for (j, (kk, _)) in self.facts_of(p, i).into_iter().enumerate() {
                    if same(kk.bind(p), pred)? {
                        pos = Some(j);
                        break;
                    }
                }
                let mut s = self.store.borrow_mut();
                if let Some(e) = s.entries.get_mut(i) {
                    match pos {
                        Some(j) => e.1[j].1 = value.clone().unbind(),
                        None => e.1.push((pred.clone().unbind(), value.clone().unbind(), serial)),
                    }
                }
            }
        }
        Ok(())
    }

    /// Empties the store (what `store.clear()` does).
    fn clear(&self) {
        tick(FC_CLEAR);
        if !planted(FC_CLEAR_SKIP) {
            self.wipe();
        }
    }

    /// The read-only view of the store.
    #[getter]
    fn store(slf: &Bound<'_, Self>) -> FactView {
        FactView { cache: slf.clone().unbind() }
    }

    /// `_Mark`'s mark: (entries, clear generation, put serial).
    fn _fc_mark(&self) -> (usize, u64, u64) {
        (self.len(), self.generation.get(), self.serial.get())
    }

    /// Undoes what was written after `mark`; True when the store was emptied for it (Python's `rollback:cleared`).
    fn _fc_rollback(&self, mark: (usize, u64, u64)) -> bool {
        tick(FC_ROLLBACK);
        let (n, generation, serial) = mark;
        if generation != self.generation.get() {
            let changed = self.len() > 0 || n > 0;
            self.wipe();
            return changed;
        }
        if planted(FC_ROLLBACK_SKIP) {
            return false;
        }
        let mut s = self.store.borrow_mut();
        for e in s.entries.iter_mut().take(n) {
            e.1.retain(|(_, _, at)| *at <= serial);
        }
        if s.entries.len() > n {
            s.entries.truncate(n);
            s.index.retain(|_, b| {
                b.retain(|&i| i < n);
                !b.is_empty()
            });
        }
        false
    }

    fn __repr__(&self) -> String {
        format!("<DictCache (Rust) {} nodes, maxsize {}>", self.len(), self.maxsize)
    }
}

/// The read-only view of a cache's store: what the tests, the registry and Python's readers see.
#[pyclass(module = "sa_solver", name = "FactView", unsendable)]
pub struct FactView {
    cache: Py<FactCache>,
}

#[pymethods]
impl FactView {
    #[getter]
    fn native(&self) -> bool {
        true
    }

    /// Counted in the registry digest, as 5c9b's moved memos are.
    #[getter]
    fn moved(&self) -> bool {
        true
    }

    fn __len__(&self, p: Python<'_>) -> usize {
        tick(FC_VIEW);
        let n = self.cache.borrow(p).len();
        if planted(FC_VIEW_DROP_LAST) { n.saturating_sub(1) } else { n }
    }

    fn __bool__(&self, p: Python<'_>) -> bool {
        self.__len__(p) > 0
    }

    fn __contains__(&self, k: &Bound<'_, PyAny>) -> PyResult<bool> {
        tick(FC_VIEW);
        Ok(self.cache.borrow(k.py()).lookup(k)?.is_some())
    }

    fn __getitem__<'py>(&self, k: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyDict>> {
        tick(FC_VIEW);
        let c = self.cache.borrow(k.py());
        match c.lookup(k)? {
            Some(i) => c.dict_of(k.py(), i),
            None => Err(PyKeyError::new_err(k.clone().unbind())),
        }
    }

    #[pyo3(signature = (k, default=None))]
    fn get<'py>(&self, k: &Bound<'py, PyAny>, default: Option<Bound<'py, PyAny>>) -> PyResult<Bound<'py, PyAny>> {
        tick(FC_VIEW);
        let p = k.py();
        let c = self.cache.borrow(p);
        Ok(match c.lookup(k)? {
            Some(i) => c.dict_of(p, i)?.into_any(),
            None => default.unwrap_or_else(|| p.None().into_bound(p)),
        })
    }

    fn keys<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        tick(FC_VIEW);
        PyList::new(p, self.cache.borrow(p).keys_of(p))
    }

    fn values<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        tick(FC_VIEW);
        let d = self.cache.borrow(p).snapshot(p)?;
        Ok(d.values())
    }

    fn items<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        tick(FC_VIEW);
        let d = self.cache.borrow(p).snapshot(p)?;
        Ok(d.items())
    }

    fn __iter__<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        self.keys(p)?.try_iter().map(|i| i.into_any())
    }

    fn __richcmp__<'py>(&self, other: &Bound<'py, PyAny>, op: CompareOp) -> PyResult<Py<PyAny>> {
        let p = other.py();
        tick(FC_VIEW);
        let d = self.cache.borrow(p).snapshot(p)?;
        let other = if let Ok(v) = other.cast::<FactView>() { v.borrow().cache.borrow(p).snapshot(p)?.into_any() } else { other.clone() };
        Ok(d.as_any().rich_compare(&other, op)?.unbind())
    }

    fn clear(&self, p: Python<'_>) {
        self.cache.borrow(p).clear();
    }

    fn __repr__(&self, p: Python<'_>) -> PyResult<String> {
        Ok(self.cache.borrow(p).snapshot(p)?.repr()?.to_string())
    }
}

/// Test-only: (maxsize, epoch, settings, [(node, [(pred, value)])]) read from the Rust store itself.
#[pyfunction]
fn fc_snapshot<'py>(p: Python<'py>, cache: &Bound<'py, FactCache>) -> PyResult<Bound<'py, PyTuple>> {
    let c = cache.borrow();
    let rows = PyList::empty(p);
    for (k, f) in c.store.borrow().entries.iter() {
        let fs = PyList::empty(p);
        for (pr, v, _) in f.iter() {
            fs.append((pr.clone_ref(p), v.clone_ref(p)))?;
        }
        rows.append((k.clone_ref(p), fs))?;
    }
    PyTuple::new(p, [c.maxsize.into_pyobject(p)?.into_any(), c.epoch.into_pyobject(p)?.into_any(), c.settings.bind(p).clone(), rows.into_any()])
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<FactCache>()?;
    m.add_class::<FactView>()?;
    m.add_function(wrap_pyfunction!(fc_snapshot, m)?)?;
    Ok(())
}
