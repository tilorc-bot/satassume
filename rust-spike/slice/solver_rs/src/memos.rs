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

/// One Rust-native memo: its registry name, what it is keyed on besides its key (memos.py's `KEYS`), its bound, and its
/// accessors.
struct Native {
    name: &'static str,
    key: &'static str,
    size: usize,
    len: fn() -> usize,
    clear: fn(),
    items: fn(Python<'_>) -> PyResult<Vec<(Py<PyAny>, Py<PyAny>)>>,
}

const TABLES: [Native; 2] = [
    Native {
        name: "sa_solver.relations_core.SPEC_ROWS",
        key: "pure",
        size: crate::relations_core::SPEC_ROWS_SIZE,
        len: crate::relations_core::spec_rows_len,
        clear: crate::relations_core::spec_rows_clear,
        items: crate::relations_core::spec_rows_items,
    },
    Native {
        name: "sa_solver.constfield.ENCLOSURES",
        key: "pure",
        size: crate::constfield::ENCLOSURES_SIZE,
        len: crate::constfield::enclosures_len,
        clear: crate::constfield::enclosures_clear,
        items: crate::constfield::enclosures_items,
    },
];

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
    #[getter]
    fn size(&self) -> usize {
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
        format!("<NativeTable {} key={} {}/{}>", t.name, t.key, (t.len)(), t.size)
    }
}

/// Attaches every native table's view to `process` (`memos.PROCESS`); returns their names. The registry-view plant leaves
/// `SPEC_ROWS` out.
#[pyfunction]
fn memo_install(p: Python<'_>, process: &Bound<'_, PyAny>) -> PyResult<Vec<&'static str>> {
    let mut out = Vec::new();
    for (i, t) in TABLES.iter().enumerate() {
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
    for t in TABLES.iter() {
        process.call_method1(intern!(p, "detach"), (t.name,))?;
    }
    Ok(())
}

/// Test-only: `[(name, key, size, len)]` of every native table, read from the maps, not the views.
#[pyfunction]
fn memo_snapshot() -> Vec<(&'static str, &'static str, usize, usize)> {
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
    m.add_function(wrap_pyfunction!(memo_snapshot, m)?)
}
