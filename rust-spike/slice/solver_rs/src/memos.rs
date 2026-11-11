//! Step 5c9a: the memo registry (`satassume/state/memos.py`) holds Rust-native tables, and the registry rows Rust ran
//! through Python callbacks run here.
//!
//! - **Native tables.** Rust keeps two process-wide memos that Python's registry never saw: relations_core's `SPEC_ROWS`
//!   (an `AdapterSpec`'s fields, keyed by the spec it keeps alive) and constfield's `ENCLOSURES` (a constant's integer
//!   enclosure, keyed by (constant index, prec) and checked against the identity of `Constant._cache`'s tuple). `memo_install`
//!   attaches one read-only `NativeTable` view of each to `memos.PROCESS` (`Memos.attach`), so `PROCESS.names/sizes/items/
//!   clear`, `reset_module_state` and `harness inventory` reach them; `memo_uninstall` detaches them. The tables stay Rust
//!   maps: a view converts entries only for `items()`/`keys()` (tests and the inventory), counted `memo:native_items`.
//! - **`Table.restamp`** for `sympy_api._KEYS`/`_CONST` (relevance.rs's `keys_rel`): `restamp` below empties the dict and
//!   writes the stamp in Rust instead of calling the Python method. The two tables stay Python containers: their readers
//!   (`_Mark`, the tests, Python's `_keys_rel` fallback) remain past 5c9a; 5c9b/5c10 own them.
//! - **The settings properties** (`Engine.extensions`, `relation_specs`, `transfer`, `uninterpreted`): `setting` reads the
//!   field the getter returns (`_extensions`, ...) instead of running the property, when the engine's type is `Engine` itself
//!   (a subclass may override the property: then the property runs, counted `memo:setting_prop`). The fields stay on the
//!   Python `Engine` (5c10's container): one counted crossing, `memo:setting`, removed by 5c10.
//! - **Test-only snapshot export** (`memo_snapshot`): `(name, key, size, len)` of every native table, read from the maps
//!   themselves and not through the views, so the bar can show the view lists every table (the registry-view plant).

use pyo3::exceptions::PyKeyError;
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{PyList, PyString, PyTuple, PyType};

use crate::relations_core::{
    planted, MEMO_CLEAR_SKIP, MEMO_RESTAMP_NO_STAMP, MEMO_SET_EXT, MEMO_SET_RELSPECS, MEMO_SET_TRANSFER, MEMO_SET_UNINTERP,
    MEMO_VIEW_DROP,
};
use crate::session::{tick, MEMO_NATIVE_CLEAR, MEMO_NATIVE_ITEMS, MEMO_RESTAMP, MEMO_SETTING, MEMO_SETTING_PROP};

/// What a run added to a native map, for term_live.py's `_Mark` (the formula step, the planner's ruling on lra's cause: a
/// discarded run leaves nothing in a native table either). The keys added, in order, and how often the map was emptied. A
/// mark is `(keys added so far, empties so far)`; `since` gives the keys added after a mark, newest first, or None when the
/// map was emptied since (then what it holds is all the run's, and the rollback empties it, as `_Mark` does a Python table).
/// A value written over an existing key isn't logged: `_Mark` undoes Python's tables by size too.
pub(crate) struct AddLog<K> {
    keys: Vec<K>,
    emptied: u64,
}

impl<K> AddLog<K> {
    pub(crate) const fn new() -> Self {
        AddLog { keys: Vec::new(), emptied: 0 }
    }
    pub(crate) fn added(&mut self, k: K) {
        self.keys.push(k);
    }
    pub(crate) fn cleared(&mut self) {
        self.keys.clear();
        self.emptied += 1;
    }
    pub(crate) fn mark(&self) -> (usize, u64) {
        (self.keys.len(), self.emptied)
    }
    pub(crate) fn since(&mut self, mark: (usize, u64)) -> Option<Vec<K>> {
        if mark.1 != self.emptied || mark.0 > self.keys.len() {
            return None;
        }
        let mut gone = self.keys.split_off(mark.0);
        gone.reverse();
        Some(gone)
    }
}

/// One Rust-native memo: its registry name, what it is keyed on besides its key (memos.py's `KEYS`), its bound, and its
/// accessors.
struct Native {
    name: &'static str,
    key: &'static str,
    size: Option<usize>,
    len: fn() -> usize,
    clear: fn(),
    items: fn(Python<'_>) -> PyResult<Vec<(Py<PyAny>, Py<PyAny>)>>,
    /// `_Mark`'s mark and rollback (`AddLog`); the rollback answers whether it had to empty the table.
    mark: fn() -> (usize, u64),
    rollback: fn((usize, u64)) -> bool,
}

const TABLES: [Native; 7] = [
    Native {
        name: "sa_solver.relations_core.SPEC_ROWS",
        key: "pure",
        size: Some(crate::relations_core::SPEC_ROWS_SIZE),
        len: crate::relations_core::spec_rows_len,
        clear: crate::relations_core::spec_rows_clear,
        items: crate::relations_core::spec_rows_items,
        mark: crate::relations_core::spec_rows_mark,
        rollback: crate::relations_core::spec_rows_rollback,
    },
    Native {
        name: "sa_solver.constfield.ENCLOSURES",
        key: "pure",
        size: Some(crate::constfield::ENCLOSURES_SIZE),
        len: crate::constfield::enclosures_len,
        clear: crate::constfield::enclosures_clear,
        items: crate::constfield::enclosures_items,
        mark: crate::constfield::enclosures_mark,
        rollback: crate::constfield::enclosures_rollback,
    },
    // Step 5c9b (procmemo.rs): Python's own process memos, moved; their views take Python's names and places in the registry.
    Native { name: "satassume.engine._WANT", key: "pure", size: None, len: crate::procmemo::want_len, clear: crate::procmemo::want_clear, items: crate::procmemo::want_items, mark: crate::procmemo::want_mark, rollback: crate::procmemo::want_rollback },
    Native { name: "satassume.engine._SPLIT", key: "pure", size: Some(crate::procmemo::SPLIT_SIZE), len: crate::procmemo::split_len, clear: crate::procmemo::split_clear, items: crate::procmemo::split_items, mark: crate::procmemo::split_mark, rollback: crate::procmemo::split_rollback },
    Native { name: "satassume.engine._NEIGH", key: "pure", size: None, len: crate::procmemo::neigh_len, clear: crate::procmemo::neigh_clear, items: crate::procmemo::neigh_items, mark: crate::procmemo::neigh_mark, rollback: crate::procmemo::neigh_rollback },
    Native { name: "satassume.relations._CLOSED", key: "pure", size: Some(crate::procmemo::CLOSED_SIZE), len: crate::procmemo::closed_len, clear: crate::procmemo::closed_clear, items: crate::procmemo::closed_items, mark: crate::procmemo::closed_mark, rollback: crate::procmemo::closed_rollback },
    Native { name: "satassume.relations._SYMPY_ATOMS", key: "pure", size: Some(crate::procmemo::ATOMS_SIZE), len: crate::procmemo::atoms_len, clear: crate::procmemo::atoms_clear, items: crate::procmemo::atoms_items, mark: crate::procmemo::atoms_mark, rollback: crate::procmemo::atoms_rollback },
];
/// The native tables `memo_install` attaches; the rest (5c9b's) replace Python's containers in place (`procmemo_views`).
const ATTACHED: usize = 2;

/// The read-only Python view of one native table: no `__setitem__`; `clear()`/`reset()` empty the Rust map (a native table
/// keeps no stamp, so `stamp` is None and `reset` is `clear`).
#[pyclass(module = "sa_solver", name = "NativeTable", frozen)]
pub struct NativeTable {
    i: usize,
}

#[pymethods]
impl NativeTable {
    #[getter]
    fn name(&self) -> &'static str {
        TABLES[self.i].name
    }
    #[getter]
    fn key(&self) -> &'static str {
        TABLES[self.i].key
    }
    /// A 5c9b table: it replaces a container Python's registry had, so the switch digest counts it (memo_check.py).
    #[getter]
    fn moved(&self) -> bool {
        self.i >= ATTACHED
    }
    #[getter]
    fn size(&self) -> Option<usize> {
        TABLES[self.i].size
    }
    #[getter]
    fn stamp(&self) -> Option<i64> {
        None
    }
    /// Marks the view for `_Mark` (term_live.py), which leaves native tables to Rust.
    #[getter]
    fn native(&self) -> bool {
        true
    }
    fn __len__(&self) -> usize {
        (TABLES[self.i].len)()
    }
    fn __contains__(&self, p: Python<'_>, k: &Bound<'_, PyAny>) -> PyResult<bool> {
        Ok(self.__getitem__(p, k).is_ok())
    }
    #[pyo3(signature = (k, default=None))]
    fn get(&self, p: Python<'_>, k: &Bound<'_, PyAny>, default: Option<Py<PyAny>>) -> Py<PyAny> {
        self.__getitem__(p, k).unwrap_or_else(|_| default.unwrap_or_else(|| p.None()))
    }
    fn __bool__(&self) -> bool {
        (TABLES[self.i].len)() > 0
    }
    fn clear(&self) {
        tick(MEMO_NATIVE_CLEAR);
        if !(planted(MEMO_CLEAR_SKIP) && self.i == 1) {
            (TABLES[self.i].clear)();
        }
    }
    fn reset(&self) {
        self.clear()
    }
    /// `_Mark`'s mark of this table (term_live.py): what a run adds after it, `_nt_rollback` removes.
    fn _nt_mark(&self) -> (usize, u64) {
        (TABLES[self.i].mark)()
    }
    /// Removes what was added after `mark`; True when the table had to be emptied for it (Python's `rollback:cleared`).
    fn _nt_rollback(&self, mark: (usize, u64)) -> bool {
        (TABLES[self.i].rollback)(mark)
    }
    /// `[(key, value)]`, converted now (tests and the inventory only).
    fn items<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        tick(MEMO_NATIVE_ITEMS);
        let v = (TABLES[self.i].items)(p)?;
        PyList::new(p, v.into_iter().map(|(k, x)| PyTuple::new(p, [k, x]).map(|t| t.into_any())).collect::<PyResult<Vec<_>>>()?)
    }
    fn keys<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        tick(MEMO_NATIVE_ITEMS);
        let v = (TABLES[self.i].items)(p)?;
        PyList::new(p, v.into_iter().map(|(k, _)| k))
    }
    fn __iter__<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        Ok(self.keys(p)?.try_iter()?.into_any())
    }
    fn __getitem__<'py>(&self, p: Python<'py>, k: &Bound<'py, PyAny>) -> PyResult<Py<PyAny>> {
        tick(MEMO_NATIVE_ITEMS);
        for (kk, v) in (TABLES[self.i].items)(p)? {
            if kk.bind(p).eq(k)? {
                return Ok(v);
            }
        }
        Err(PyKeyError::new_err(k.clone().unbind()))
    }
    fn __repr__(&self) -> String {
        let t = &TABLES[self.i];
        format!("<NativeTable {} key={} {}/{}>", t.name, t.key, (t.len)(), t.size.map_or("-".to_string(), |n| n.to_string()))
    }
}

/// Attaches every native table's view to `process` (`memos.PROCESS`); returns their names. The registry-view plant leaves
/// `SPEC_ROWS` out.
#[pyfunction]
fn memo_install(p: Python<'_>, process: &Bound<'_, PyAny>) -> PyResult<Vec<&'static str>> {
    let mut out = Vec::new();
    for (i, t) in TABLES.iter().enumerate().take(ATTACHED) {
        if i == 0 && planted(MEMO_VIEW_DROP) {
            continue;
        }
        process.call_method1(intern!(p, "attach"), (t.name, Bound::new(p, NativeTable { i })?))?;
        out.push(t.name);
    }
    Ok(out)
}

#[pyfunction]
fn memo_uninstall(p: Python<'_>, process: &Bound<'_, PyAny>) -> PyResult<()> {
    for t in TABLES.iter().take(ATTACHED) {
        process.call_method1(intern!(p, "detach"), (t.name,))?;
    }
    Ok(())
}

/// Step 5c9b: `{name: view}` of the moved process memos, for `session_live._install_procmemos` to put where Python's
/// containers sit in `memos.PROCESS`. The view plant leaves `_SPLIT` out.
#[pyfunction]
fn procmemo_views<'py>(p: Python<'py>) -> PyResult<Bound<'py, pyo3::types::PyDict>> {
    let d = pyo3::types::PyDict::new(p);
    for (i, t) in TABLES.iter().enumerate().skip(ATTACHED) {
        if t.name == "satassume.engine._SPLIT" && planted(crate::relations_core::PM_VIEW_DROP) {
            continue;
        }
        d.set_item(t.name, Bound::new(p, NativeTable { i })?)?;
    }
    Ok(d)
}

/// Test-only: `[(name, key, size, len)]` of every native table, read from the maps, not the views.
#[pyfunction]
fn memo_snapshot() -> Vec<(&'static str, &'static str, Option<usize>, usize)> {
    TABLES.iter().map(|t| (t.name, t.key, t.size, (t.len)())).collect()
}

/// `Table.restamp(stamp)` on a Python `Table`: `dict.clear` and the stamp, in Rust. The restamp plant leaves the stamp, so
/// every later lookup restamps again (the memo never fills: caught by the state digest's sizes).
pub(crate) fn restamp(t: &Bound<'_, PyAny>, stamp: &Bound<'_, PyAny>) -> PyResult<()> {
    tick(MEMO_RESTAMP);
    let p = t.py();
    t.cast::<pyo3::types::PyDict>()?.clear();
    if !planted(MEMO_RESTAMP_NO_STAMP) {
        t.setattr(intern!(p, "stamp"), stamp)?;
    }
    Ok(())
}

static ENGINE: PyOnceLock<Py<PyType>> = PyOnceLock::new();

/// An `Engine` setting read by Rust: the field its property returns (`field`), or the property (`prop`) on a subclass.
pub(crate) fn setting<'py>(eng: &Bound<'py, PyAny>, field: &Bound<'py, PyString>, prop: &Bound<'py, PyString>) -> PyResult<Bound<'py, PyAny>> {
    let p = eng.py();
    let cls = ENGINE.get_or_try_init(p, || -> PyResult<_> {
        Ok(p.import(intern!(p, "satassume.engine"))?.getattr(intern!(p, "Engine"))?.cast_into::<PyType>()?.unbind())
    })?;
    if eng.get_type().is(cls.bind(p)) {
        tick(MEMO_SETTING);
        let v = eng.getattr(field)?;
        // One plant a moved getter, each giving a wrong value for its own setting only.
        if planted(MEMO_SET_TRANSFER) && prop.to_str()? == "transfer" {
            return Ok(pyo3::types::PyBool::new(p, !v.is_truthy()?).to_owned().into_any());
        }
        if planted(MEMO_SET_UNINTERP) && prop.to_str()? == "uninterpreted" {
            let flip = if v.eq(intern!(p, "free"))? { "none" } else { "free" };
            return Ok(PyString::new(p, flip).into_any());
        }
        if planted(MEMO_SET_RELSPECS) && prop.to_str()? == "relation_specs" {
            return Ok(PyTuple::empty(p).into_any());
        }
        if planted(MEMO_SET_EXT) && prop.to_str()? == "extensions" {
            return Ok(p.None().into_bound(p));
        }
        return Ok(v);
    }
    tick(MEMO_SETTING_PROP);
    eng.getattr(prop)
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<NativeTable>()?;
    m.add_function(wrap_pyfunction!(memo_install, m)?)?;
    m.add_function(wrap_pyfunction!(memo_uninstall, m)?)?;
    m.add_function(wrap_pyfunction!(procmemo_views, m)?)?;
    m.add_function(wrap_pyfunction!(memo_snapshot, m)?)
}
