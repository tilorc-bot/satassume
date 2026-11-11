//! Step 5c9b: the process memos Rust works on are Rust-native: engine.py's `_WANT`, `_SPLIT`, `_NEIGH` and relations.py's
//! `_CLOSED`, `_SYMPY_ATOMS` (inventory part 5, INVENTORY-state.md :278-280), plus `neighbourhood`, the one row that moves.
//!
//! - **The maps.** Each is a thread-local Rust map. Keys and values stay the Python objects Python's dicts held (a frozenset of
//!   basis indices, a SymPy node, a `P` atom; compiled patterns, `Q` atoms, the `(clauses, now, later, ment)` tuple), because
//!   their consumers are Python objects still; what moved is the container. A lookup is a Python dict's: the key's hash, then
//!   identity or `==` (`pm:key_eq` counts each `==` that runs, a callback when the key is a SymPy or Formula object).
//! - **Bounds as Python's:** `_SPLIT` 100,000 and `_CLOSED` 4,096 (emptied when full, before the write), `_SYMPY_ATOMS` its
//!   table's 100,000; `_WANT` and `_NEIGH` have none (Python's have none).
//! - **`_SPLIT`** is keyed as Python's is, on `(id(clauses), want)`: a hit needs the stored tuple's `clauses` to be the very list
//!   (`r[0] is clauses`); the entry keeps that list alive, so its address can't be reused while the entry is there.
//! - **Views.** memos.rs lists these five in its `TABLES` with Python's own registry names; `session_live._install_procmemos`
//!   puts each view in `memos.PROCESS` where Python's container was (`_tables` for relations', `_adopted` for engine's), so
//!   `names/sizes/items/clear` read the Rust maps. The modules' own attributes stay Python's containers, used only by
//!   Python's functions (the Python backend, and test_relations_core's side-by-side check).
//! - **`neighbourhood`** reads `RULE_CLAUSES` and `BASIS_OF` from `knowledge.rules` (static rule tables), counted
//!   `pm:cb_rules`, 0 per query: no engine code calls it (test_engine.py does).
use std::cell::RefCell;
use std::collections::HashMap;

use pyo3::exceptions::PyTypeError;
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::types::{PyFrozenSet, PyTuple};

use crate::relations_core::{
    planted, PM_ATOMS_KEY_EXPR, PM_CLOSED_HIT_NONE, PM_NEIGH_MEMO_FIRST, PM_NEIGH_NO_SELF, PM_SPLIT_CLEAR_SKIP, PM_SPLIT_NO_FULL_CLEAR,
    PM_WANT_KEY_LEN,
};
use crate::memos::AddLog;
use crate::session::{tick, PM_CB_RULES, PM_FULL, PM_KEY_EQ, PM_KEY_HASH, PM_NEIGH};

/// A Python dict's lookup over Python keys, held in Rust: buckets by the key's hash, then identity or `==`.
#[derive(Default)]
pub(crate) struct PyKeyMap {
    buckets: HashMap<isize, Vec<(Py<PyAny>, Py<PyAny>)>>,
    len: usize,
    log: AddLog<isize>,
}

impl Default for AddLog<isize> {
    fn default() -> Self {
        AddLog::new()
    }
}
impl Default for AddLog<(usize, Option<isize>)> {
    fn default() -> Self {
        AddLog::new()
    }
}

/// What a rollback took out of a map: dropped by the caller once the map's borrow is released (a key's dealloc can run
/// Python code). `None`: the map was emptied.
type Gone<T> = Option<Vec<T>>;

impl PyKeyMap {
    fn find<'py>(&self, k: &Bound<'py, PyAny>, h: isize) -> PyResult<Option<Bound<'py, PyAny>>> {
        let p = k.py();
        // Candidates are copied out first: `==` may run Python code.
        let cand: Vec<(Py<PyAny>, Py<PyAny>)> = match self.buckets.get(&h) {
            Some(b) => b.iter().map(|(a, v)| (a.clone_ref(p), v.clone_ref(p))).collect(),
            None => return Ok(None),
        };
        for (kk, v) in cand {
            let kk = kk.into_bound(p);
            if kk.is(k) {
                return Ok(Some(v.into_bound(p)));
            }
            tick(PM_KEY_EQ);
            if kk.eq(k)? {
                return Ok(Some(v.into_bound(p)));
            }
        }
        Ok(None)
    }

    /// `self[k] = v`: replaces the value of an equal key (keeping the stored key, as a dict does), else appends.
    fn set(&mut self, k: &Bound<'_, PyAny>, h: isize, v: &Bound<'_, PyAny>) -> PyResult<()> {
        let p = k.py();
        let idx = match self.buckets.get(&h) {
            Some(b) => {
                let mut at = None;
                for (i, (kk, _)) in b.iter().enumerate() {
                    let kk = kk.bind(p);
                    if kk.is(k) || {
                        tick(PM_KEY_EQ);
                        kk.eq(k)?
                    } {
                        at = Some(i);
                        break;
                    }
                }
                at
            }
            None => None,
        };
        let b = self.buckets.entry(h).or_default();
        match idx {
            Some(i) if i < b.len() => b[i].1 = v.clone().unbind(),
            _ => {
                b.push((k.clone().unbind(), v.clone().unbind()));
                self.len += 1;
                self.log.added(h);
            }
        }
        Ok(())
    }

    fn clear(&mut self) {
        self.buckets.clear();
        self.len = 0;
        self.log.cleared();
    }

    /// `_Mark`'s rollback: takes out the entries added after `mark`, newest first (a bucket appends, so a key's newest entry
    /// is its bucket's last); `None` when the map was emptied since the mark, and then it is emptied again.
    fn rollback(&mut self, mark: (usize, u64)) -> Gone<(Py<PyAny>, Py<PyAny>)> {
        let Some(hs) = self.log.since(mark) else {
            let was = self.len;
            self.buckets.clear();
            self.len = 0;
            self.log.cleared();
            return if was > 0 || mark.0 > 0 { None } else { Some(Vec::new()) };
        };
        let mut gone = Vec::with_capacity(hs.len());
        for h in hs {
            if let Some(b) = self.buckets.get_mut(&h) {
                if let Some(e) = b.pop() {
                    gone.push(e);
                    self.len -= 1;
                }
                if b.is_empty() {
                    self.buckets.remove(&h);
                }
            }
        }
        Some(gone)
    }

    fn items(&self, p: Python<'_>) -> Vec<(Py<PyAny>, Py<PyAny>)> {
        self.buckets.values().flat_map(|b| b.iter().map(|(k, v)| (k.clone_ref(p), v.clone_ref(p)))).collect()
    }
}

/// `_SPLIT`'s map: `(id(clauses), hash(want) or None)` -> `[(want, (clauses, now, later, ment))]`.
#[derive(Default)]
struct SplitMap {
    buckets: HashMap<(usize, Option<isize>), Vec<(Option<Py<PyAny>>, Py<PyTuple>)>>,
    len: usize,
    log: AddLog<(usize, Option<isize>)>,
}

thread_local! {
    static WANT: RefCell<PyKeyMap> = RefCell::new(PyKeyMap::default());
    static SPLIT: RefCell<SplitMap> = RefCell::new(SplitMap::default());
    static NEIGH: RefCell<PyKeyMap> = RefCell::new(PyKeyMap::default());
    static CLOSED: RefCell<PyKeyMap> = RefCell::new(PyKeyMap::default());
    static ATOMS: RefCell<PyKeyMap> = RefCell::new(PyKeyMap::default());
}

pub(crate) const SPLIT_SIZE: usize = 100_000;
pub(crate) const CLOSED_SIZE: usize = 4096;
pub(crate) const ATOMS_SIZE: usize = 100_000;

macro_rules! accessors {
    ($m:ident, $len:ident, $clear:ident, $items:ident, $mark:ident, $rollback:ident) => {
        pub(crate) fn $len() -> usize {
            $m.with(|m| m.borrow().len)
        }
        pub(crate) fn $clear() {
            $m.with(|m| m.borrow_mut().clear());
        }
        pub(crate) fn $items(p: Python<'_>) -> PyResult<Vec<(Py<PyAny>, Py<PyAny>)>> {
            Ok($m.with(|m| m.borrow().items(p)))
        }
        pub(crate) fn $mark() -> (usize, u64) {
            $m.with(|m| m.borrow().log.mark())
        }
        pub(crate) fn $rollback(mark: (usize, u64)) -> bool {
            let gone = $m.with(|m| m.borrow_mut().rollback(mark));
            gone.is_none()
        }
    };
}
accessors!(WANT, want_len, want_clear, want_items, want_mark, want_rollback);
accessors!(NEIGH, neigh_len, neigh_clear, neigh_items, neigh_mark, neigh_rollback);
accessors!(CLOSED, closed_len, closed_clear, closed_items, closed_mark, closed_rollback);
accessors!(ATOMS, atoms_len, atoms_clear, atoms_items, atoms_mark, atoms_rollback);

pub(crate) fn split_len() -> usize {
    SPLIT.with(|m| m.borrow().len)
}
/// The `_SPLIT` view's `clear()`; the clear plant leaves the map as it is.
pub(crate) fn split_clear() {
    if !planted(PM_SPLIT_CLEAR_SKIP) {
        SPLIT.with(|m| {
            let mut m = m.borrow_mut();
            m.buckets.clear();
            m.len = 0;
            m.log.cleared();
        });
    }
}
pub(crate) fn split_mark() -> (usize, u64) {
    SPLIT.with(|m| m.borrow().log.mark())
}
/// `_Mark`'s rollback of `_SPLIT`, as `PyKeyMap::rollback`.
pub(crate) fn split_rollback(mark: (usize, u64)) -> bool {
    let gone: Gone<(Option<Py<PyAny>>, Py<PyTuple>)> = SPLIT.with(|m| {
        let mut m = m.borrow_mut();
        let Some(ks) = m.log.since(mark) else {
            let was = m.len;
            m.buckets.clear();
            m.len = 0;
            m.log.cleared();
            return if was > 0 || mark.0 > 0 { None } else { Some(Vec::new()) };
        };
        let mut gone = Vec::with_capacity(ks.len());
        for k in ks {
            if let Some(b) = m.buckets.get_mut(&k) {
                let e = b.pop();
                if b.is_empty() {
                    m.buckets.remove(&k);
                }
                if let Some(e) = e {
                    gone.push(e);
                    m.len -= 1;
                }
            }
        }
        Some(gone)
    });
    gone.is_none()
}
/// `[((id(clauses), want), r)]`, as Python's keys read.
pub(crate) fn split_items(p: Python<'_>) -> PyResult<Vec<(Py<PyAny>, Py<PyAny>)>> {
    let rows: Vec<(usize, Option<Py<PyAny>>, Py<PyTuple>)> = SPLIT.with(|m| {
        m.borrow()
            .buckets
            .iter()
            .flat_map(|((id, _), b)| b.iter().map(move |(w, r)| (*id, w.as_ref().map(|w| w.clone_ref(p)), r.clone_ref(p))))
            .collect()
    });
    rows.into_iter()
        .map(|(id, w, r)| {
            let w = w.map(|w| w.into_bound(p)).unwrap_or_else(|| p.None().into_bound(p));
            Ok((PyTuple::new(p, [id.into_pyobject(p)?.into_any(), w])?.into_any().unbind(), r.into_any()))
        })
        .collect()
}

fn hash(k: &Bound<'_, PyAny>) -> PyResult<isize> {
    k.hash()
}

/// `_WANT`: the memoized `frozenset(demanded)` (one object per value). The key-length plant answers from any entry of the
/// same size.
pub(crate) fn want_get_or_put<'py>(key: Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    let h = hash(&key)?;
    if planted(PM_WANT_KEY_LEN) {
        let n = key.len()?;
        let p = key.py();
        let hit = WANT.with(|m| -> PyResult<Option<Py<PyAny>>> {
            for (_, v) in m.borrow().items(p) {
                if v.bind(p).len()? == n {
                    return Ok(Some(v));
                }
            }
            Ok(None)
        })?;
        if let Some(v) = hit {
            return Ok(v.into_bound(p));
        }
    }
    let found = WANT.with(|m| m.borrow().find(&key, h))?;
    if let Some(w) = found {
        return Ok(w);
    }
    WANT.with(|m| m.borrow_mut().set(&key, h, &key))?;
    Ok(key)
}

/// `_SPLIT`'s lookup: the stored tuple when its `clauses` is this very list.
pub(crate) fn split_get<'py>(clauses: &Bound<'py, PyAny>, want: &Bound<'py, PyAny>) -> PyResult<Option<Bound<'py, PyTuple>>> {
    let p = clauses.py();
    let wh = if want.is_none() { None } else { Some(hash(want)?) };
    let key = (clauses.as_ptr() as usize, wh);
    let cand: Vec<(Option<Py<PyAny>>, Py<PyTuple>)> = SPLIT.with(|m| {
        m.borrow().buckets.get(&key).map(|b| b.iter().map(|(w, r)| (w.as_ref().map(|w| w.clone_ref(p)), r.clone_ref(p))).collect())
    })
    .unwrap_or_default();
    for (w, r) in cand {
        let same = match (&w, want.is_none()) {
            (None, true) => true,
            (Some(w), false) => {
                let w = w.bind(p);
                w.is(want) || {
                    tick(PM_KEY_EQ);
                    w.eq(want)?
                }
            }
            _ => false,
        };
        if same {
            let r = r.into_bound(p);
            return Ok(if r.get_item(0)?.is(clauses) { Some(r) } else { None });
        }
    }
    Ok(None)
}

/// `_SPLIT[key] = r`, emptied first when full (Python tests the size before every write, a replacement too).
pub(crate) fn split_put(clauses: &Bound<'_, PyAny>, want: &Bound<'_, PyAny>, r: &Bound<'_, PyTuple>) -> PyResult<()> {
    let p = clauses.py();
    let wh = if want.is_none() { None } else { Some(hash(want)?) };
    let key = (clauses.as_ptr() as usize, wh);
    if split_len() >= SPLIT_SIZE {
        tick(PM_FULL);
        if !planted(PM_SPLIT_NO_FULL_CLEAR) {
            SPLIT.with(|m| {
                let mut m = m.borrow_mut();
                m.buckets.clear();
                m.len = 0;
                m.log.cleared();
            });
        }
    }
    let ws: Vec<Option<Py<PyAny>>> =
        SPLIT.with(|m| m.borrow().buckets.get(&key).map(|b| b.iter().map(|(w, _)| w.as_ref().map(|w| w.clone_ref(p))).collect()))
            .unwrap_or_default();
    let mut at = None;
    for (i, w) in ws.iter().enumerate() {
        let same = match (w, want.is_none()) {
            (None, true) => true,
            (Some(w), false) => {
                let w = w.bind(p);
                w.is(want) || {
                    tick(PM_KEY_EQ);
                    w.eq(want)?
                }
            }
            _ => false,
        };
        if same {
            at = Some(i);
            break;
        }
    }
    SPLIT.with(|m| {
        let mut m = m.borrow_mut();
        let b = m.buckets.entry(key).or_default();
        match at {
            Some(i) if i < b.len() => b[i].1 = r.clone().unbind(),
            _ => {
                b.push(((!want.is_none()).then(|| want.clone().unbind()), r.clone().unbind()));
                m.len += 1;
                m.log.added(key);
            }
        }
    });
    Ok(())
}

/// `_CLOSED[node]`: `Ok(None)` on a miss; `Err` a `TypeError` for an unhashable node (the caller answers None, as Python's does).
pub(crate) fn closed_get<'py>(node: &Bound<'py, PyAny>) -> PyResult<Option<Bound<'py, PyAny>>> {
    tick(PM_KEY_HASH);
    let h = hash(node)?;
    let r = CLOSED.with(|m| m.borrow().find(node, h))?;
    if r.is_some() && planted(PM_CLOSED_HIT_NONE) {
        return Ok(Some(node.py().None().into_bound(node.py())));
    }
    Ok(r)
}

pub(crate) fn closed_put(node: &Bound<'_, PyAny>, r: &Bound<'_, PyAny>) -> PyResult<()> {
    let h = hash(node)?;
    if closed_len() >= CLOSED_SIZE {
        tick(PM_FULL);
        closed_clear();
    }
    CLOSED.with(|m| m.borrow_mut().set(node, h, r))
}

/// `_SYMPY_ATOMS.get(atom)`. The key plant answers from an entry with the same `expr` and any `pred`.
pub(crate) fn atoms_get<'py>(atom: &Bound<'py, PyAny>) -> PyResult<Option<Bound<'py, PyAny>>> {
    tick(PM_KEY_HASH);
    let h = hash(atom)?;
    let r = ATOMS.with(|m| m.borrow().find(atom, h))?;
    if r.is_none() && planted(PM_ATOMS_KEY_EXPR) {
        let p = atom.py();
        let e = atom.getattr(intern!(p, "expr"))?;
        for (k, v) in ATOMS.with(|m| m.borrow().items(p)) {
            if k.bind(p).getattr(intern!(p, "expr"))?.eq(&e)? {
                return Ok(Some(v.into_bound(p)));
            }
        }
    }
    Ok(r)
}

pub(crate) fn atoms_put(atom: &Bound<'_, PyAny>, r: &Bound<'_, PyAny>) -> PyResult<()> {
    let h = hash(atom)?;
    if atoms_len() >= ATOMS_SIZE {
        tick(PM_FULL);
        atoms_clear();
    }
    ATOMS.with(|m| m.borrow_mut().set(atom, h, r))
}

/// `neighbourhood(pred)`: `pred` (a name or index) plus every predicate sharing a rule clause with it, as indices; memoized
/// per index in `_NEIGH`.
#[pyfunction]
fn pm_neighbourhood<'py>(pred: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    tick(PM_NEIGH);
    let p = pred.py();
    let rules = p.import(intern!(p, "satassume.knowledge.rules"))?;
    if let Ok(name) = pred.cast::<pyo3::types::PyString>() {
        tick(PM_CB_RULES);
        let basis = rules.getattr(intern!(p, "BASIS_OF"))?.get_item(name)?;
        let mut acc: Vec<Bound<'py, PyAny>> = Vec::new();
        for i in basis.try_iter()? {
            for x in pm_neighbourhood(&i?)?.try_iter()? {
                acc.push(x?);
            }
        }
        return Ok(PyFrozenSet::new(p, acc)?.into_any());
    }
    let i: i64 = pred.extract().map_err(|_| PyTypeError::new_err("neighbourhood: a predicate name or an int index"))?;
    let h = hash(pred)?;
    if planted(PM_NEIGH_MEMO_FIRST) {
        if let Some((_, v)) = NEIGH.with(|m| m.borrow().items(p)).into_iter().next() {
            return Ok(v.into_bound(p));
        }
    }
    if let Some(n) = NEIGH.with(|m| m.borrow().find(pred, h))? {
        return Ok(n);
    }
    tick(PM_CB_RULES);
    let clauses: Vec<Vec<i64>> = rules.getattr(intern!(p, "RULE_CLAUSES"))?.try_iter()?.map(|c| c?.extract()).collect::<PyResult<_>>()?;
    let mut acc: Vec<i64> = if planted(PM_NEIGH_NO_SELF) { vec![] } else { vec![i] };
    for c in &clauses {
        let idx: Vec<i64> = c.iter().map(|l| l.abs() - 1).collect();
        if idx.contains(&i) {
            acc.extend(idx);
        }
    }
    let n = PyFrozenSet::new(p, acc)?.into_any();
    NEIGH.with(|m| m.borrow_mut().set(pred, h, &n))?;
    Ok(n)
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(pm_neighbourhood, m)?)
}
