//! Step 5c10d: query entry and counters, the last 5c10 part (inventory part 5, INVENTORY-state.md :293-299; planner's go,
//! 8 Nov 23:50, and its inventory ruling (2), ~06:22).
//!
//! - **Rust-owned state:** `Engine.stats` and `Engine.last_budget_limited` live in one `EngineStats` per engine (twelve
//!   counters in Python's key order, and the flag), held in the instance's `__dict__` under `stats`. `StatsSlot` is the data
//!   descriptor `session_live._install_entry` puts on `Engine` for both names: `Engine.__init__`'s `self.stats = {...}`
//!   converts the dict (`st:slot_set`), its `self.last_budget_limited = False` sets the flag (`st:flag_set`, the one Python
//!   write left, construction only). An engine made before the install converts at its first read. A dict whose keys aren't
//!   Python's twelve, in order, stays a dict (foreign: the Rust writers then go through its own methods, `st:foreign`).
//! - **Readers get a read-only view:** the `EngineStats` mapping methods (`[k]`, `get`, `keys`, `items`, `==`, `dict(...)`)
//!   and the flag's descriptor; each Python call counted `st:py_read`. `[k] = v`, `clear`, `update` raise.
//! - **Writers:** the rows below write natively. sympy_api's writers (public `ask`, `_ask`, `_ask_general`, `_consistent`,
//!   `_engine_ask`) and the two scope-miss sites call the named record methods on `Engine` (engine.py's own bodies on the
//!   dict, Rust's here), each counted `st:rec_*`. `_Mark` (term_live.py) snapshots and restores through `_st_mark` /
//!   `_st_rollback` (`st:mark`; wiring, the state step).
//! - **Rows run here, step for step as engine.py:** `is_` (:1986), `is_many` (:2026), `_decide` (:2091), `_put_result`
//!   (:2119), `_is_custom` (:2152), `ask` (:2172), `_ask` (:2220), `_check_version` (:1556), `_settings_changed` (:1528),
//!   `_drop_set_memos` (:1589), `_fresh_session` (:1412); `_over_budget`/`_note_budget` are budget.rs's (from port/5c7),
//!   writing here. Callbacks left, counted: the module helpers that read SymPy's `is_commutative` (`_noncommutative`,
//!   `_construction_level`, `noncommutative_false`, `_noncommutative_atoms`: `ent:cb_noncomm`), `_gave_up` (Rust since state
//!   part 3, theory_flags.rs; `ent:cb_gave_up` still counts the read), `theory_scope` (scope.py: `ent:cb_scope`), `basis_lits`/`basis_formula`
//!   (the rule tables: `ent:cb_basis`). Session's methods and `s.truncated` are read through the session (the state step).

use std::cell::Cell;

use pyo3::exceptions::{PyKeyError, PyRuntimeError, PyTypeError};
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyDict, PyList, PySet, PyString, PyTuple};

use crate::engmemo;
use crate::formula::{Hand, Nodes};
use crate::relations_core::{
    planted, ENT_ASK_NO_CLEAR_FLAG, ENT_ASK_NO_GAVE_UP, ENT_CHECK_VERSION_NO_SYNC, ENT_DECIDE_NO_ESCALATE,
    ENT_DROP_MEMOS_KEEP_ANSWERS, ENT_FRESH_NO_COUNT, ENT_IS_CUSTOM_NO_HIT, ENT_IS_MANY_QUERIES_SHORT, ENT_IS_NO_HIT_COUNT,
    ENT_PUT_RESULT_NO_PUT, ENT_SETTINGS_NO_CLEAR, ST_CACHE_HIT_DROP, ST_CLEAR_FLAG_SKIP, ST_FLAG_VIEW_STALE, ST_KEEP_FLAG_DROP,
    ST_RELEVANT_DROP, ST_SCOPE_MISS_DOUBLE, ST_VIEW_ORDER,
};
use crate::session::{
    tick, ENT_ASK, ENT_ASK_INNER, ENT_CB_BASIS, ENT_CB_GAVE_UP, ENT_CB_NONCOMM, ENT_CB_SCOPE, ENT_CHECK_VERSION, ENT_DECIDE,
    ENT_DROP_SET_MEMOS, ENT_FRESH_SESSION, ENT_IS, ENT_IS_CUSTOM, ENT_IS_MANY, ENT_PUT_RESULT, ENT_SETTINGS_CHANGED, ST_FLAG_SET,
    ST_FOREIGN, ST_MARK, ST_PY_READ, ST_REC_CACHE_HIT, ST_REC_CLEAR_FLAG, ST_REC_CONSISTENCY_CHECK, ST_REC_KEEP_FLAG,
    ST_REC_RELEVANT, ST_REC_SCOPE_MISS, ST_SLOT_SET,
};

/// Python's keys, in `Engine.__init__`'s order.
pub(crate) const KEYS: [&str; 12] = [
    "queries", "cache_hits", "escalations", "searches", "sessions", "relevant", "consistency_checks", "theory_gave_up",
    "version_clears", "set_checks", "budget_limited", "scope_misses",
];
pub(crate) const QUERIES: usize = 0;
pub(crate) const CACHE_HITS: usize = 1;
pub(crate) const ESCALATIONS: usize = 2;
pub(crate) const SEARCHES: usize = 3;
pub(crate) const SESSIONS: usize = 4;
pub(crate) const RELEVANT: usize = 5;
pub(crate) const CONSISTENCY_CHECKS: usize = 6;
pub(crate) const THEORY_GAVE_UP: usize = 7;
pub(crate) const VERSION_CLEARS: usize = 8;
pub(crate) const SET_CHECKS: usize = 9;
pub(crate) const BUDGET_LIMITED: usize = 10;
pub(crate) const SCOPE_MISSES: usize = 11;

#[pyclass(module = "sa_solver", name = "EngineStats", unsendable)]
pub struct EngineStats {
    c: [Cell<i64>; 12],
    limited: Cell<bool>,
}

impl EngineStats {
    fn order(&self) -> [usize; 12] {
        let mut o = [0usize; 12];
        for (i, x) in o.iter_mut().enumerate() {
            *x = i;
        }
        if planted(ST_VIEW_ORDER) {
            o.copy_within(0..BUDGET_LIMITED, 1);
            o[0] = BUDGET_LIMITED;
        }
        o
    }
    fn index(k: &Bound<'_, PyAny>) -> Option<usize> {
        let s = k.cast::<PyString>().ok()?;
        let s = s.to_str().ok()?;
        KEYS.iter().position(|x| *x == s)
    }
    fn to_dict<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let d = PyDict::new(p);
        for i in self.order() {
            d.set_item(KEYS[i], self.c[i].get())?;
        }
        Ok(d)
    }
    fn add(&self, i: usize, n: i64) {
        self.c[i].set(self.c[i].get() + n);
    }
    /// From Python's dict, when it has exactly Python's twelve keys in order with int values.
    fn from_dict(d: &Bound<'_, PyAny>) -> PyResult<Option<EngineStats>> {
        let Ok(d) = d.cast::<PyDict>() else { return Ok(None) };
        if d.len() != 12 {
            return Ok(None);
        }
        let s = EngineStats { c: Default::default(), limited: Cell::new(false) };
        for (i, (k, v)) in d.iter().enumerate() {
            if Self::index(&k) != Some(i) {
                return Ok(None);
            }
            let Ok(v) = v.extract::<i64>() else { return Ok(None) };
            s.c[i].set(v);
        }
        Ok(Some(s))
    }
}

#[pymethods]
impl EngineStats {
    fn __getitem__(&self, k: &Bound<'_, PyAny>) -> PyResult<i64> {
        tick(ST_PY_READ);
        match Self::index(k) {
            Some(i) => Ok(self.c[i].get()),
            None => Err(PyKeyError::new_err(k.clone().unbind())),
        }
    }
    #[pyo3(signature = (k, default=None))]
    fn get<'py>(&self, k: &Bound<'py, PyAny>, default: Option<Bound<'py, PyAny>>) -> PyResult<Bound<'py, PyAny>> {
        tick(ST_PY_READ);
        let p = k.py();
        Ok(match Self::index(k) {
            Some(i) => self.c[i].get().into_pyobject(p)?.into_any(),
            None => default.unwrap_or_else(|| p.None().into_bound(p)),
        })
    }
    fn __contains__(&self, k: &Bound<'_, PyAny>) -> bool {
        tick(ST_PY_READ);
        Self::index(k).is_some()
    }
    fn __len__(&self) -> usize {
        12
    }
    fn __iter__<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        tick(ST_PY_READ);
        self.to_dict(p)?.try_iter().map(|i| i.into_any())
    }
    fn keys<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        tick(ST_PY_READ);
        self.to_dict(p)?.call_method0(intern!(p, "keys"))
    }
    fn values<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        tick(ST_PY_READ);
        self.to_dict(p)?.call_method0(intern!(p, "values"))
    }
    fn items<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        tick(ST_PY_READ);
        self.to_dict(p)?.call_method0(intern!(p, "items"))
    }
    fn copy<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        tick(ST_PY_READ);
        self.to_dict(p)
    }
    fn __eq__(&self, other: &Bound<'_, PyAny>) -> PyResult<bool> {
        tick(ST_PY_READ);
        let p = other.py();
        let mine = self.to_dict(p)?;
        if let Ok(o) = other.cast::<EngineStats>() {
            return mine.eq(o.borrow().to_dict(p)?);
        }
        mine.eq(other)
    }
    fn __ne__(&self, other: &Bound<'_, PyAny>) -> PyResult<bool> {
        Ok(!self.__eq__(other)?)
    }
    fn __repr__(&self, p: Python<'_>) -> PyResult<String> {
        Ok(self.to_dict(p)?.repr()?.to_string())
    }
    fn __setitem__(&self, k: &Bound<'_, PyAny>, _v: &Bound<'_, PyAny>) -> PyResult<()> {
        Err(PyTypeError::new_err(format!(
            "Engine.stats is a read-only view of Rust-owned counters (step 5c10d); write {} through the engine's record methods",
            k.repr()?
        )))
    }
    fn __delitem__(&self, k: &Bound<'_, PyAny>) -> PyResult<()> {
        self.__setitem__(k, k)
    }
    /// The flag, read-only (the descriptor on `Engine` reads it).
    #[getter]
    fn limited(&self) -> bool {
        self.limited.get()
    }
    /// `_Mark`'s snapshot (term_live.py, wiring): the counters and the flag.
    fn _st_mark<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyTuple>> {
        tick(ST_MARK);
        let v: Vec<i64> = self.c.iter().map(|c| c.get()).collect();
        PyTuple::new(p, [PyTuple::new(p, v)?.into_any(), PyBool::new(p, self.limited.get()).to_owned().into_any()])
    }
    fn _st_rollback(&self, m: &Bound<'_, PyTuple>) -> PyResult<()> {
        tick(ST_MARK);
        let v: Vec<i64> = m.get_item(0)?.extract()?;
        for (c, x) in self.c.iter().zip(v) {
            c.set(x);
        }
        self.limited.set(m.get_item(1)?.is_truthy()?);
        Ok(())
    }
}

/// The instance's `EngineStats`, converting a dict of Python's twelve keys (and a flag in the `__dict__`) on the way;
/// otherwise whatever is there (foreign), or None.
fn held<'py>(inst: &Bound<'py, PyAny>) -> PyResult<Option<Bound<'py, PyAny>>> {
    let p = inst.py();
    let d = inst.getattr(intern!(p, "__dict__"))?.cast_into::<PyDict>()?;
    let Some(v) = d.get_item(intern!(p, "stats"))? else { return Ok(None) };
    if v.is_instance_of::<EngineStats>() {
        return Ok(Some(v));
    }
    let Some(s) = EngineStats::from_dict(&v)? else { return Ok(Some(v)) };
    tick(ST_SLOT_SET);
    if let Some(f) = d.get_item(intern!(p, "last_budget_limited"))? {
        s.limited.set(f.is_truthy()?);
        d.del_item(intern!(p, "last_budget_limited"))?;
    }
    let b = Bound::new(p, s)?.into_any();
    d.set_item(intern!(p, "stats"), &b)?;
    Ok(Some(b))
}

/// The data descriptor on `Engine` for `stats` (flag false) and `last_budget_limited` (flag true).
#[pyclass(module = "sa_solver", name = "StatsSlot", frozen)]
pub struct StatsSlot {
    flag: bool,
}

#[pymethods]
impl StatsSlot {
    #[new]
    fn py_new(flag: bool) -> Self {
        StatsSlot { flag }
    }
    fn __get__<'py>(slf: &Bound<'py, Self>, inst: Option<&Bound<'py, PyAny>>, _owner: Option<&Bound<'py, PyAny>>) -> PyResult<Bound<'py, PyAny>> {
        let Some(inst) = inst.filter(|i| !i.is_none()) else { return Ok(slf.clone().into_any()) };
        let p = slf.py();
        let name = if slf.get().flag { "last_budget_limited" } else { "stats" };
        let st = held(inst)?;
        if !slf.get().flag {
            return st.ok_or_else(|| pyo3::exceptions::PyAttributeError::new_err(format!("'Engine' object has no attribute '{name}'")));
        }
        if let Some(st) = st.as_ref().and_then(|s| s.cast::<EngineStats>().ok()) {
            tick(ST_PY_READ);
            let v = st.borrow().limited.get() && !planted(ST_FLAG_VIEW_STALE);
            return Ok(PyBool::new(p, v).to_owned().into_any());
        }
        let d = inst.getattr(intern!(p, "__dict__"))?.cast_into::<PyDict>()?;
        d.get_item(name)?.ok_or_else(|| pyo3::exceptions::PyAttributeError::new_err(format!("'Engine' object has no attribute '{name}'")))
    }
    fn __set__(&self, inst: &Bound<'_, PyAny>, value: &Bound<'_, PyAny>) -> PyResult<()> {
        let p = inst.py();
        let d = inst.getattr(intern!(p, "__dict__"))?.cast_into::<PyDict>()?;
        if self.flag {
            tick(ST_FLAG_SET);
            if let Some(st) = held(inst)? {
                if let Ok(st) = st.cast::<EngineStats>() {
                    st.borrow().limited.set(value.is_truthy()?);
                    return Ok(());
                }
            }
            return d.set_item(intern!(p, "last_budget_limited"), value);
        }
        // `self.stats = {...}`: the flag already set stays (an `EngineStats` replaced, or the `__dict__`'s).
        let old = held(inst)?;
        d.set_item(intern!(p, "stats"), value)?;
        if let Some(o) = old.as_ref().and_then(|o| o.cast::<EngineStats>().ok()) {
            if let Some(n) = held(inst)?.as_ref().and_then(|n| n.cast::<EngineStats>().ok()) {
                if !n.is(o) {
                    n.borrow().limited.set(o.borrow().limited.get());
                }
            } else {
                d.set_item(intern!(p, "last_budget_limited"), o.borrow().limited.get())?;
            }
        }
        Ok(())
    }
}

// The Rust writers and readers. A foreign `stats` (a dict that isn't Python's twelve keys) goes through its own methods.

pub(crate) fn bump(eng: &Bound<'_, PyAny>, i: usize, n: i64) -> PyResult<()> {
    let p = eng.py();
    let st = eng.getattr(intern!(p, "stats"))?;
    if let Ok(s) = st.cast::<EngineStats>() {
        s.borrow().add(i, n);
        return Ok(());
    }
    tick(ST_FOREIGN);
    st.set_item(KEYS[i], st.get_item(KEYS[i])?.add(n)?)
}

pub(crate) fn set_flag(eng: &Bound<'_, PyAny>, v: bool) -> PyResult<()> {
    let p = eng.py();
    let st = eng.getattr(intern!(p, "stats"))?;
    if let Ok(s) = st.cast::<EngineStats>() {
        s.borrow().limited.set(v);
        return Ok(());
    }
    tick(ST_FOREIGN);
    eng.setattr(intern!(p, "last_budget_limited"), v)
}

pub(crate) fn flag(eng: &Bound<'_, PyAny>) -> PyResult<bool> {
    let p = eng.py();
    let st = eng.getattr(intern!(p, "stats"))?;
    if let Ok(s) = st.cast::<EngineStats>() {
        return Ok(s.borrow().limited.get());
    }
    tick(ST_FOREIGN);
    eng.getattr(intern!(p, "last_budget_limited"))?.is_truthy()
}

// The record methods (named, counted): sympy_api's writers and the scope-miss sites.

#[pyfunction]
fn ent_record_cache_hit(eng: &Bound<'_, PyAny>) -> PyResult<()> {
    tick(ST_REC_CACHE_HIT);
    if planted(ST_CACHE_HIT_DROP) {
        return Ok(());
    }
    bump(eng, CACHE_HITS, 1)
}

#[pyfunction]
fn ent_record_relevant(eng: &Bound<'_, PyAny>) -> PyResult<()> {
    tick(ST_REC_RELEVANT);
    if planted(ST_RELEVANT_DROP) {
        return Ok(());
    }
    bump(eng, RELEVANT, 1)
}

#[pyfunction]
fn ent_record_consistency_check(eng: &Bound<'_, PyAny>) -> PyResult<()> {
    tick(ST_REC_CONSISTENCY_CHECK);
    bump(eng, CONSISTENCY_CHECKS, 1)
}

/// A scope miss: from Python's `Session._custom` (engine.py :721) and relations.py :907, and Rust's ports of both.
pub(crate) fn scope_miss(eng: &Bound<'_, PyAny>) -> PyResult<()> {
    bump(eng, SCOPE_MISSES, if planted(ST_SCOPE_MISS_DOUBLE) { 2 } else { 1 })
}

#[pyfunction]
fn ent_record_scope_miss(eng: &Bound<'_, PyAny>) -> PyResult<()> {
    tick(ST_REC_SCOPE_MISS);
    scope_miss(eng)
}

#[pyfunction]
fn ent_clear_budget_flag(eng: &Bound<'_, PyAny>) -> PyResult<()> {
    tick(ST_REC_CLEAR_FLAG);
    if planted(ST_CLEAR_FLAG_SKIP) {
        return Ok(());
    }
    set_flag(eng, false)
}

#[pyfunction]
fn ent_keep_budget_flag(eng: &Bound<'_, PyAny>, limited: bool) -> PyResult<()> {
    tick(ST_REC_KEEP_FLAG);
    let v = flag(eng)? || (limited && !planted(ST_KEEP_FLAG_DROP));
    set_flag(eng, v)
}

// The rows.

fn engine_mod(p: Python<'_>) -> PyResult<Bound<'_, PyModule>> {
    p.import(intern!(p, "satassume.engine"))
}

fn epoch<'py>(p: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
    engine_mod(p)?.getattr(intern!(p, "_EPOCH"))?.get_item(0)
}

/// `self._epoch != _EPOCH[0] or self.<cache>._settings != self._settings_key`
fn stale(eng: &Bound<'_, PyAny>, cache: Option<&Bound<'_, PyString>>) -> PyResult<bool> {
    let p = eng.py();
    if eng.getattr(intern!(p, "_epoch"))?.ne(epoch(p)?)? {
        return Ok(true);
    }
    match cache {
        Some(c) => eng.getattr(c)?.getattr(intern!(p, "_settings"))?.ne(eng.getattr(intern!(p, "_settings_key"))?),
        None => Ok(false),
    }
}

fn check_version(eng: &Bound<'_, PyAny>) -> PyResult<()> {
    tick(ENT_CHECK_VERSION);
    let p = eng.py();
    let e = epoch(p)?;
    let mine = eng.getattr(intern!(p, "_epoch"))?;
    if mine.ne(&e)? {
        crate::budget::drop_cones(eng)?;
        if mine.ge(0)? {
            drop_set_memos(eng)?;
        }
        eng.setattr(intern!(p, "_epoch"), &e)?;
    }
    if planted(ENT_CHECK_VERSION_NO_SYNC) {
        return Ok(());
    }
    let key = eng.getattr(intern!(p, "_settings_key"))?;
    eng.getattr(intern!(p, "cache"))?.call_method1(intern!(p, "sync"), (&e, &key))?;
    eng.getattr(intern!(p, "custom_cache"))?.call_method1(intern!(p, "sync"), (&e, &key))?;
    Ok(())
}

#[pyfunction]
fn ent_check_version(eng: &Bound<'_, PyAny>) -> PyResult<()> {
    check_version(eng)
}

fn drop_set_memos(eng: &Bound<'_, PyAny>) -> PyResult<()> {
    tick(ENT_DROP_SET_MEMOS);
    let p = eng.py();
    bump(eng, VERSION_CLEARS, 1)?;
    if !planted(ENT_DROP_MEMOS_KEEP_ANSWERS) {
        eng.getattr(intern!(p, "answers"))?.call_method0(intern!(p, "clear"))?;
    }
    for n in [intern!(p, "splits"), intern!(p, "_failed"), intern!(p, "_verdict"), intern!(p, "_xbasis")] {
        engmemo::clear(&eng.getattr(n)?)?;
    }
    Ok(())
}

#[pyfunction]
fn ent_drop_set_memos(eng: &Bound<'_, PyAny>) -> PyResult<()> {
    drop_set_memos(eng)
}

#[pyfunction]
fn ent_settings_changed(eng: &Bound<'_, PyAny>) -> PyResult<()> {
    tick(ENT_SETTINGS_CHANGED);
    let p = eng.py();
    let key = PyTuple::new(p, [eng.getattr(intern!(p, "_templates"))?, eng.getattr(intern!(p, "_transfer"))?, eng.getattr(intern!(p, "_uninterpreted"))?])?;
    eng.setattr(intern!(p, "_settings_key"), key)?;
    crate::budget::drop_cones(eng)?;
    if eng.getattr(intern!(p, "_epoch"))?.ge(0)? {
        drop_set_memos(eng)?;
        if !planted(ENT_SETTINGS_NO_CLEAR) {
            eng.getattr(intern!(p, "cache"))?.getattr(intern!(p, "store"))?.call_method0(intern!(p, "clear"))?;
            eng.getattr(intern!(p, "custom_cache"))?.getattr(intern!(p, "store"))?.call_method0(intern!(p, "clear"))?;
        }
    }
    Ok(())
}

fn fresh_session<'py>(eng: &Bound<'py, PyAny>, scope: Option<&Bound<'py, PyAny>>) -> PyResult<Bound<'py, PyAny>> {
    tick(ENT_FRESH_SESSION);
    let p = eng.py();
    if !planted(ENT_FRESH_NO_COUNT) {
        bump(eng, SESSIONS, 1)?;
    }
    let em = engine_mod(p)?;
    let scope = match scope {
        Some(s) => s.clone(),
        None => em.getattr(intern!(p, "_EMPTY_SCOPE"))?,
    };
    em.getattr(intern!(p, "Session"))?.call1((eng, scope))
}

#[pyfunction]
#[pyo3(signature = (eng, scope=None))]
fn ent_fresh_session<'py>(eng: &Bound<'py, PyAny>, scope: Option<Bound<'py, PyAny>>) -> PyResult<Bound<'py, PyAny>> {
    fresh_session(eng, scope.as_ref())
}

fn query_literal<'py>(s: &Bound<'py, PyAny>, lit: &Bound<'py, PyAny>, lits: &Bound<'py, PyAny>, search: bool) -> PyResult<Bound<'py, PyAny>> {
    let p = s.py();
    let kw = PyDict::new(p);
    kw.set_item(intern!(p, "search"), search)?;
    s.call_method(intern!(p, "query_literal"), (lit, lits), Some(&kw))
}

fn decide<'py>(eng: &Bound<'py, PyAny>, s: &Bound<'py, PyAny>, lit: &Bound<'py, PyAny>, lits: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    tick(ENT_DECIDE);
    let p = eng.py();
    let mut r = query_literal(s, lit, lits, false)?;
    if r.is_none() && s.getattr(intern!(p, "incomplete"))?.is_truthy()? && !planted(ENT_DECIDE_NO_ESCALATE) {
        bump(eng, ESCALATIONS, 1)?;
        s.call_method0(intern!(p, "escalate"))?;
        r = query_literal(s, lit, lits, false)?;
    }
    if r.is_none() {
        bump(eng, SEARCHES, 1)?;
        r = query_literal(s, lit, lits, true)?;
    }
    Ok(r)
}

#[pyfunction]
#[pyo3(signature = (eng, s, lit, lits=None))]
fn ent_decide<'py>(eng: &Bound<'py, PyAny>, s: &Bound<'py, PyAny>, lit: &Bound<'py, PyAny>, lits: Option<Bound<'py, PyAny>>) -> PyResult<Bound<'py, PyAny>> {
    let p = eng.py();
    let lits = lits.unwrap_or_else(|| PyTuple::empty(p).into_any());
    decide(eng, s, lit, &lits)
}

fn root_only(eng: &Bound<'_, PyAny>) -> PyResult<bool> {
    let p = eng.py();
    eng.getattr(intern!(p, "_writeback"))?.eq(intern!(p, "root-only"))
}

fn put_result(eng: &Bound<'_, PyAny>, s: &Bound<'_, PyAny>, cache: &Bound<'_, PyAny>, node: &Bound<'_, PyAny>, pred: &Bound<'_, PyAny>, r: &Bound<'_, PyAny>) -> PyResult<()> {
    tick(ENT_PUT_RESULT);
    let p = eng.py();
    if crate::session::ses_flag(s, crate::session::SS_TRUNCATED)? {
        return Err(PyRuntimeError::new_err("a session of a query within the budget was truncated"));
    }
    set_flag(eng, false)?;
    if r.is_none() || !root_only(eng)? || planted(ENT_PUT_RESULT_NO_PUT) {
        return Ok(());
    }
    cache.call_method1(intern!(p, "put"), (node, pred, r))?;
    Ok(())
}

#[pyfunction]
fn ent_put_result(eng: &Bound<'_, PyAny>, s: &Bound<'_, PyAny>, cache: &Bound<'_, PyAny>, node: &Bound<'_, PyAny>, pred: &Bound<'_, PyAny>, r: &Bound<'_, PyAny>) -> PyResult<()> {
    put_result(eng, s, cache, node, pred, r)
}

fn noncommutative(p: Python<'_>, node: &Bound<'_, PyAny>) -> PyResult<bool> {
    noncommutative_term(p, node)
}

/// `engine._noncommutative(term)`: domain.py's `_NONCOMM` memo (a `dict`, read as `dict.get` reads it) answers; only
/// on a miss is domain's `_noncommutative` called (it walks the term and fills the row), counted `ent:cb_noncomm` and
/// `nc:memo_miss`. The walk reads SymPy's classes and stays Python.
pub(crate) fn noncommutative_term(p: Python<'_>, term: &Bound<'_, PyAny>) -> PyResult<bool> {
    let dom = p.import(intern!(p, "satassume.knowledge.domain"))?;
    let memo = dom.getattr(intern!(p, "_NONCOMM"))?;
    if let Some(r) = memo.cast::<PyDict>()?.get_item(term)? {
        if !r.is_none() {
            return Ok(r.is_truthy()? && !crate::formula::planted_nc_memo());
        }
    }
    tick(ENT_CB_NONCOMM);
    crate::formula::tick(crate::formula::NC_MEMO_MISS);
    dom.getattr(intern!(p, "_noncommutative"))?.call1((term,))?.is_truthy()
}

/// `engine._noncommutative_atoms(*formulas)`, native (B's item 2, group-d-cause.md C7's cb_noncomm): whether a
/// vocabulary atom (`pred in PRED_INDEX`) of one of `formulas` (None skipped) has a non-commutative term. The atoms come
/// from `hand`'s node of each formula, so the formula is converted once for the entry, not walked in Python.
pub(crate) fn noncommutative_atoms(p: Python<'_>, formulas: &[&Bound<'_, PyAny>], hand: &Hand) -> PyResult<bool> {
    let index = engine_mod(p)?.getattr(intern!(p, "PRED_INDEX"))?;
    for f in formulas {
        if f.is_none() {
            continue;
        }
        for a in hand.atoms(f)?.iter() {
            if index.contains(a.getattr(intern!(p, "pred"))?)? && noncommutative_term(p, &a.getattr(intern!(p, "expr"))?)? {
                return Ok(true);
            }
        }
    }
    Ok(false)
}

fn construction_level(p: Python<'_>, node: &Bound<'_, PyAny>) -> PyResult<i64> {
    tick(ENT_CB_NONCOMM);
    engine_mod(p)?.getattr(intern!(p, "_construction_level"))?.call1((node,))?.extract()
}

/// `_noncommutative_answer`.
fn noncomm_answer<'py>(p: Python<'py>, level: i64, pred: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    if level == 2 {
        tick(ENT_CB_NONCOMM);
        let nf = p.import(intern!(p, "satassume.knowledge.domain"))?.getattr(intern!(p, "noncommutative_false"))?.call0()?;
        return Ok(if nf.contains(pred)? { PyBool::new(p, false).to_owned().into_any() } else { p.None().into_bound(p) });
    }
    Ok(if level != 0 && pred.eq(intern!(p, "commutative"))? { PyBool::new(p, false).to_owned().into_any() } else { p.None().into_bound(p) })
}

/// `basis_lits(pred)[0] == '&'` for a predicate with no basis (true or false by definition); None if it has a basis.
fn by_definition(p: Python<'_>, pred: &Bound<'_, PyAny>) -> PyResult<Option<bool>> {
    let em = engine_mod(p)?;
    if em.getattr(intern!(p, "BASIS_OF"))?.get_item(pred)?.is_truthy()? {
        return Ok(None);
    }
    tick(ENT_CB_BASIS);
    Ok(Some(em.getattr(intern!(p, "basis_lits"))?.call1((pred,))?.get_item(0)?.eq("&")?))
}

fn cone_head<'py>(eng: &Bound<'py, PyAny>, node: &Bound<'py, PyAny>, memo_first: bool, nodes: &dyn Nodes) -> PyResult<Bound<'py, PyAny>> {
    let p = eng.py();
    if memo_first {
        if let Some(c) = engmemo::get(&eng.getattr(intern!(p, "_cones"))?, node)? {
            return c.get_item(0);
        }
    }
    crate::budget::cone_info_any(eng, node, nodes)?.get_item(0)
}

fn is_<'py>(eng: &Bound<'py, PyAny>, node: &Bound<'py, PyAny>, pred: &Bound<'py, PyAny>, hand: &Hand) -> PyResult<Bound<'py, PyAny>> {
    tick(ENT_IS);
    let p = eng.py();
    if stale(eng, Some(intern!(p, "cache")))? {
        check_version(eng)?;
    }
    let em = engine_mod(p)?;
    if !em.getattr(intern!(p, "PRED_INDEX"))?.contains(pred)? {
        return is_custom(eng, node, pred, hand);
    }
    if noncommutative(p, node)? {
        return noncomm_answer(p, construction_level(p, node)?, pred);
    }
    if engmemo::contains(&eng.getattr(intern!(p, "_constructing"))?, node)? {
        return Ok(p.None().into_bound(p));
    }
    if cone_head(eng, node, true, hand)?.is_none() {
        return crate::budget::over_budget(eng);
    }
    let cache = eng.getattr(intern!(p, "cache"))?;
    let facts = cache.call_method1(intern!(p, "facts"), (node,))?;
    if !facts.is_none() && facts.contains(pred)? {
        if !planted(ENT_IS_NO_HIT_COUNT) {
            bump(eng, CACHE_HITS, 1)?;
        }
        set_flag(eng, false)?;
        return facts.get_item(pred);
    }
    if let Some(r) = by_definition(p, pred)? {
        set_flag(eng, false)?;
        if root_only(eng)? {
            cache.call_method1(intern!(p, "put"), (node, pred, r))?;
        }
        return Ok(PyBool::new(p, r).to_owned().into_any());
    }
    bump(eng, QUERIES, 1)?;
    let s = fresh_session(eng, None)?;
    hand.give(&s, &[])?;    // the cone's facts, converted by `cone_head`: the session's discovery reads the same objects
    let want = PySet::new(p, [pred])?;
    s.call_method1(intern!(p, "ensure"), (node, want))?;
    let lit = s.call_method1(intern!(p, "query_lit"), (pred, node))?;
    let r = decide(eng, &s, &lit, &PyTuple::empty(p).into_any())?;
    put_result(eng, &s, &cache, node, pred, &r)?;
    Ok(r)
}

#[pyfunction]
fn ent_is<'py>(eng: &Bound<'py, PyAny>, node: &Bound<'py, PyAny>, pred: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    is_(eng, node, pred, &Hand::enter())
}

#[pyfunction]
fn ent_is_many<'py>(eng: &Bound<'py, PyAny>, node: &Bound<'py, PyAny>, preds: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyList>> {
    let hand = &Hand::enter();
    tick(ENT_IS_MANY);
    let p = eng.py();
    if stale(eng, Some(intern!(p, "cache")))? {
        check_version(eng)?;
    }
    let preds: Vec<Bound<'py, PyAny>> = preds.try_iter()?.collect::<PyResult<_>>()?;
    let none = p.None().into_bound(p);
    let mut out: Vec<Bound<'py, PyAny>> = vec![none.clone(); preds.len()];
    let mut todo: Vec<usize> = Vec::new();
    let noncomm = noncommutative(p, node)?;
    let mut level: Option<i64> = None;
    let index = engine_mod(p)?.getattr(intern!(p, "PRED_INDEX"))?;
    for (k, pred) in preds.iter().enumerate() {
        if !index.contains(pred)? {
            out[k] = is_custom(eng, node, pred, hand)?;
        } else if noncomm {
            if level.is_none() {
                level = Some(construction_level(p, node)?);
            }
            out[k] = noncomm_answer(p, level.unwrap(), pred)?;
        } else {
            todo.push(k);
        }
    }
    let done = |out: Vec<Bound<'py, PyAny>>| PyList::new(p, out);
    if todo.is_empty() || engmemo::contains(&eng.getattr(intern!(p, "_constructing"))?, node)? {
        return done(out);
    }
    if cone_head(eng, node, true, hand)?.is_none() {
        for _ in &todo {
            crate::budget::over_budget(eng)?;
        }
        return done(out);
    }
    let cache = eng.getattr(intern!(p, "cache"))?;
    let facts = cache.call_method1(intern!(p, "facts"), (node,))?;
    if !facts.is_none() {
        let mut left = Vec::new();
        for &k in &todo {
            if facts.contains(&preds[k])? {
                bump(eng, CACHE_HITS, 1)?;
                set_flag(eng, false)?;
                out[k] = facts.get_item(&preds[k])?;
            } else {
                left.push(k);
            }
        }
        todo = left;
    }
    let mut left = Vec::new();
    for &k in &todo {
        match by_definition(p, &preds[k])? {
            None => left.push(k),
            Some(r) => {
                set_flag(eng, false)?;
                out[k] = PyBool::new(p, r).to_owned().into_any();
                if root_only(eng)? {
                    cache.call_method1(intern!(p, "put"), (node, &preds[k], r))?;
                }
            }
        }
    }
    todo = left;
    if todo.is_empty() {
        return done(out);
    }
    let n = todo.len() as i64 - i64::from(planted(ENT_IS_MANY_QUERIES_SHORT));
    bump(eng, QUERIES, n)?;
    let s = fresh_session(eng, None)?;
    hand.give(&s, &[])?;
    let want = PySet::empty(p)?;
    for &k in &todo {
        want.add(&preds[k])?;
    }
    s.call_method1(intern!(p, "ensure"), (node, want))?;
    let empty = PyTuple::empty(p).into_any();
    for &k in &todo {
        let lit = s.call_method1(intern!(p, "query_lit"), (&preds[k], node))?;
        let r = decide(eng, &s, &lit, &empty)?;
        put_result(eng, &s, &cache, node, &preds[k], &r)?;
        out[k] = r;
    }
    done(out)
}

fn theory_scope<'py>(eng: &Bound<'py, PyAny>, f: &Bound<'py, PyAny>, hand: &Hand) -> PyResult<Bound<'py, PyAny>> {
    tick(ENT_CB_SCOPE);
    let p = eng.py();
    crate::scope_core::theory_scope_from(engine_mod(p)?.as_any(), "theory_scope", &p.None().into_bound(p), f, &eng.getattr(intern!(p, "_extensions"))?, hand)
}

fn is_custom<'py>(eng: &Bound<'py, PyAny>, node: &Bound<'py, PyAny>, pred: &Bound<'py, PyAny>, hand: &Hand) -> PyResult<Bound<'py, PyAny>> {
    tick(ENT_IS_CUSTOM);
    let p = eng.py();
    if stale(eng, Some(intern!(p, "custom_cache")))? {
        check_version(eng)?;
    }
    let atom = engine_mod(p)?.getattr(intern!(p, "P"))?.call1((pred, node))?;
    if cone_head(eng, &atom, false, hand)?.is_none() {
        return crate::budget::over_budget(eng);
    }
    let cache = eng.getattr(intern!(p, "custom_cache"))?;
    let facts = cache.call_method1(intern!(p, "facts"), (node,))?;
    if !facts.is_none() && facts.contains(pred)? && !planted(ENT_IS_CUSTOM_NO_HIT) {
        bump(eng, CACHE_HITS, 1)?;
        set_flag(eng, false)?;
        return facts.get_item(pred);
    }
    bump(eng, QUERIES, 1)?;
    let scope = theory_scope(eng, &atom, hand)?;
    let s = fresh_session(eng, Some(&scope))?;
    hand.give(&s, &[&atom])?;
    let lit = s.call_method1(intern!(p, "literal_of"), (&atom,))?;
    let lits = s.call_method1(intern!(p, "assumption_lits"), (&atom,))?;
    let r = decide(eng, &s, &lit, &lits)?;
    put_result(eng, &s, &cache, node, pred, &r)?;
    Ok(r)
}

#[pyfunction]
fn ent_is_custom<'py>(eng: &Bound<'py, PyAny>, node: &Bound<'py, PyAny>, pred: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    is_custom(eng, node, pred, &Hand::enter())
}

#[pyfunction]
#[pyo3(signature = (eng, proposition, assumptions=None))]
fn ent_ask<'py>(eng: &Bound<'py, PyAny>, proposition: &Bound<'py, PyAny>, assumptions: Option<Bound<'py, PyAny>>) -> PyResult<Bound<'py, PyAny>> {
    tick(ENT_ASK);
    let p = eng.py();
    if stale(eng, None)? {
        check_version(eng)?;
    }
    bump(eng, QUERIES, 1)?;
    if !planted(ENT_ASK_NO_CLEAR_FLAG) {
        set_flag(eng, false)?;
    }
    let none = p.None().into_bound(p);
    let assumptions = assumptions.unwrap_or_else(|| none.clone());
    let contextual = !assumptions.is_none() && !assumptions.is(PyBool::new(p, true));
    let em = engine_mod(p)?;
    let ctx_or_none = if contextual { assumptions.clone() } else { none.clone() };
    let hand = Hand::enter();
    if noncommutative_atoms(p, &[proposition, &ctx_or_none], &hand)? {
        return Ok(none);
    }
    let within = |f: &Bound<'py, PyAny>, a: &Bound<'py, PyAny>| -> PyResult<bool> {
        crate::budget::within_from(eng, f, Some(a), &hand)
    };
    if !within(proposition, &ctx_or_none)? {
        if contextual && within(&assumptions, &none)? {
            let v = crate::context::verdict_from(eng, &assumptions, &hand)?;
            if v.is(&em.getattr(intern!(p, "INCONSISTENT"))?) {
                let e = em.getattr(intern!(p, "InconsistentAssumptions"))?.call1(("inconsistent assumptions",))?;
                return Err(PyErr::from_value(e));
            }
        }
        return crate::budget::over_budget(eng);
    }
    if !contextual {
        let not = em.getattr(intern!(p, "Not"))?;
        let negated = proposition.is_instance(&not)?;
        let a = if negated { proposition.getattr(intern!(p, "args"))?.get_item(0)? } else { proposition.clone() };
        if a.is_instance(&em.getattr(intern!(p, "P"))?)? {
            tick(ENT_CB_BASIS);
            let c = em.getattr(intern!(p, "basis_formula"))?.call1((&a,))?;
            let t = em.getattr(intern!(p, "TRUE"))?;
            if c.is(&t) || c.is(&em.getattr(intern!(p, "FALSE"))?) {
                return Ok(PyBool::new(p, c.is(&t) != negated).to_owned().into_any());
            }
        }
    }
    let (s, lits) = if contextual {
        let sl = crate::context::context_session_from(eng, &assumptions, proposition, &hand)?;
        (sl.get_item(0)?, sl.get_item(1)?)
    } else {
        let scope = theory_scope(eng, proposition, &hand)?;
        (fresh_session(eng, Some(&scope))?, PyList::empty(p).into_any())
    };
    hand.give(&s, &[proposition])?;
    ask_inner(eng, &s, &lits, proposition, contextual)
}

fn ask_inner<'py>(eng: &Bound<'py, PyAny>, s: &Bound<'py, PyAny>, _lits: &Bound<'py, PyAny>, proposition: &Bound<'py, PyAny>, contextual: bool) -> PyResult<Bound<'py, PyAny>> {
    tick(ENT_ASK_INNER);
    let p = eng.py();
    let release = |s: &Bound<'py, PyAny>| -> PyResult<()> {
        crate::session::solver_of(s)?.call_method1(intern!(p, "release"), (crate::session::ses_int(s, crate::session::SS_N_HOLD)?,))?;
        Ok(())
    };
    release(s)?;
    let q = s.call_method1(intern!(p, "prepare_query"), (proposition,))?;
    let lits = s.call_method1(intern!(p, "assumption_lits"), (proposition,))?;
    let mut r = query_literal(s, &q, &lits, false)?;
    if r.is_none() && s.getattr(intern!(p, "incomplete"))?.is_truthy()? {
        bump(eng, ESCALATIONS, 1)?;
        release(s)?;
        s.call_method0(intern!(p, "escalate"))?;
        r = query_literal(s, &q, &lits, false)?;
    }
    if r.is_none() {
        bump(eng, SEARCHES, 1)?;
        r = query_literal(s, &q, &lits, true)?;
    }
    if contextual {
        tick(ENT_CB_GAVE_UP);
        if crate::theory_flags::theory_flag(s, crate::theory_flags::Flag::GaveUp)? && !planted(ENT_ASK_NO_GAVE_UP) {
            bump(eng, THEORY_GAVE_UP, 1)?;
        }
    }
    crate::budget::note_budget(eng, s)?;
    Ok(r)
}

#[pyfunction]
fn ent_ask_inner<'py>(eng: &Bound<'py, PyAny>, s: &Bound<'py, PyAny>, lits: &Bound<'py, PyAny>, proposition: &Bound<'py, PyAny>, contextual: bool) -> PyResult<Bound<'py, PyAny>> {
    ask_inner(eng, s, lits, proposition, contextual)
}

/// Test-only: the twelve counters and the flag of an engine's `EngineStats` read in Rust (not through the view).
#[pyfunction]
fn st_snapshot<'py>(eng: &Bound<'py, PyAny>) -> PyResult<Option<Bound<'py, PyTuple>>> {
    let p = eng.py();
    let st = eng.getattr(intern!(p, "stats"))?;
    let Ok(s) = st.cast::<EngineStats>() else { return Ok(None) };
    let s = s.borrow();
    let d = PyDict::new(p);
    for (i, k) in KEYS.iter().enumerate() {
        d.set_item(*k, s.c[i].get())?;
    }
    Ok(Some(PyTuple::new(p, [d.into_any(), PyBool::new(p, s.limited.get()).to_owned().into_any()])?))
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<EngineStats>()?;
    m.add_class::<StatsSlot>()?;
    m.add_function(wrap_pyfunction!(ent_record_cache_hit, m)?)?;
    m.add_function(wrap_pyfunction!(ent_record_relevant, m)?)?;
    m.add_function(wrap_pyfunction!(ent_record_consistency_check, m)?)?;
    m.add_function(wrap_pyfunction!(ent_record_scope_miss, m)?)?;
    m.add_function(wrap_pyfunction!(ent_clear_budget_flag, m)?)?;
    m.add_function(wrap_pyfunction!(ent_keep_budget_flag, m)?)?;
    m.add_function(wrap_pyfunction!(ent_check_version, m)?)?;
    m.add_function(wrap_pyfunction!(ent_drop_set_memos, m)?)?;
    m.add_function(wrap_pyfunction!(ent_settings_changed, m)?)?;
    m.add_function(wrap_pyfunction!(ent_fresh_session, m)?)?;
    m.add_function(wrap_pyfunction!(ent_decide, m)?)?;
    m.add_function(wrap_pyfunction!(ent_put_result, m)?)?;
    m.add_function(wrap_pyfunction!(ent_is, m)?)?;
    m.add_function(wrap_pyfunction!(ent_is_many, m)?)?;
    m.add_function(wrap_pyfunction!(ent_is_custom, m)?)?;
    m.add_function(wrap_pyfunction!(ent_ask, m)?)?;
    m.add_function(wrap_pyfunction!(ent_ask_inner, m)?)?;
    m.add_function(wrap_pyfunction!(st_snapshot, m)?)
}
