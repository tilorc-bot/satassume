//! State part 3, sub-part 5 (issue 323): `Session`'s own containers held natively in the session core.
//!
//! `pending`, `pending_c`, `demand`, `literals` and `_groups` are insertion-ordered maps of their own (`SesDict`), keyed as the
//! Python dicts they replace: by the key's `hash()` and `==`, each dict holding the key object first set in it (a present key
//! set again keeps its object and its place; a deleted key set again goes last, with the new object). Their values are the
//! Python objects Python put there (lists, sets, a literal). `frontier` and `deferred` are sequences of nodes, the
//! objects themselves. The owner is the session, so the record (`SesCont`) sits in `SessionCore` beside (iii)'s per-`Relations`
//! records. Rust sites read and write through `Ses`; Python reads `Session.<name>` through `SesDictView`/`SesSeqView`
//! (session_live installs them), whose writes are the record methods. A session with no core (`satassume/ref.py`, a test's
//! stand-in) keeps Python's own containers: `Ses::Py`, counted `sb:attr`.
//!
//! The keys are NOT the session's RelKeys ids. 7a18df2 keyed these dicts by `rk_key`, which made a session dict and a
//! `Relations` dict share one object per equal class: on workload scope `demand` holds the int `1` a custom fact passes
//! (`relation_atom('lt', s, 1)`) and `_xside` holds SymPy's `One`; `1 == One` with equal hashes, so `_xside` gave back the
//! int, `_transfer_terms` no longer saw a `Rational`, and `_number_basis(1)` (one `is_many` session) was lost. Python's dicts
//! are separate, so these are too; nothing here reads or writes RelKeys (but plant 446, which puts the fault back). Each `hash()` and `==` on a key is a call into
//! Python, counted `sc:key_hash` and `sc:key_eq` (an identical object is found without `==`, as a dict finds it).

use std::collections::VecDeque;

use pyo3::intern;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyTuple};

use crate::session::{self, sb_planted, tick, SessionCore};

/// The dicts, by index, as Python named them.
pub(crate) const SD_NAMES: [&str; 5] = ["pending", "pending_c", "demand", "literals", "_groups"];
pub(crate) const SD_PENDING: usize = 0;
pub(crate) const SD_PENDING_C: usize = 1;
pub(crate) const SD_DEMAND: usize = 2;
pub(crate) const SD_LITERALS: usize = 3;
pub(crate) const SD_GROUPS: usize = 4;
/// The sequences: `frontier` (a deque on Python) and `deferred` (a list).
pub(crate) const SQ_NAMES: [&str; 2] = ["frontier", "deferred"];
pub(crate) const SQ_FRONTIER: usize = 0;
pub(crate) const SQ_DEFERRED: usize = 1;

/// The plants (`sb_plant`): `sc-<name>-drop` makes the container's write a no-op on Rust (the view's too). 439-445.
/// `sc-key-shared` (446) also interns a dict's key in the session's RelKeys when it is set, as 7a18df2 did: the fault this
/// file's header describes, which workload scope catches.
const SD_PLANT: [u16; 5] = [440, 441, 442, 444, 445];
const SQ_PLANT: [u16; 2] = [439, 443];
const KEY_SHARED_PLANT: u16 = 446;

struct Entry {
    hash: isize,
    key: Py<PyAny>,
    val: Py<PyAny>,
}

/// One dict: entries in insertion order (a deleted one leaves a hole), and the entries of each hash.
#[derive(Default)]
struct SesDict {
    idx: std::collections::HashMap<isize, Vec<usize>>,
    ent: Vec<Option<Entry>>,
    live: usize,
}

impl SesDict {
    fn unlink(&mut self, i: usize) -> Option<Entry> {
        let e = self.ent.get_mut(i)?.take()?;
        if let Some(b) = self.idx.get_mut(&e.hash) {
            b.retain(|&j| j != i);
            if b.is_empty() {
                self.idx.remove(&e.hash);
            }
        }
        self.live -= 1;
        if self.live == 0 {
            self.ent.clear();
        }
        Some(e)
    }
}

#[derive(Default)]
pub(crate) struct SesCont {
    d: [SesDict; 5],
    q: [VecDeque<Py<PyAny>>; 2],
}

impl SessionCore {
    /// The entry of the key `x` in dict `k` and `x`'s hash: the dict's rule, the same hash and then the same object or `==`
    /// (the held key on the left). No borrow is held while Python's `__hash__` and `__eq__` run.
    fn sd_find(&self, k: usize, x: &Bound<'_, PyAny>) -> PyResult<(Option<usize>, isize)> {
        let p = x.py();
        tick(session::SC_KEY_HASH);
        let hash = x.hash()?;
        let cand: Vec<(usize, Py<PyAny>)> = match self.sc.borrow().d[k].idx.get(&hash) {
            Some(b) => b.iter().filter_map(|&i| self.sc.borrow().d[k].ent[i].as_ref().map(|e| (i, e.key.clone_ref(p)))).collect(),
            None => return Ok((None, hash)),
        };
        for (i, key) in cand {
            let same = key.is(x) || {
                tick(session::SC_KEY_EQ);
                key.bind(p).eq(x)?
            };
            // `==` ran Python: the entry counts only if it is still this key's
            if same && self.sc.borrow().d[k].ent.get(i).and_then(|e| e.as_ref()).is_some_and(|e| e.key.is(&key)) {
                return Ok((Some(i), hash));
            }
        }
        Ok((None, hash))
    }

    pub(crate) fn sd_get<'py>(&self, k: usize, x: &Bound<'py, PyAny>) -> PyResult<Option<Bound<'py, PyAny>>> {
        tick(session::SC_CORE);
        let p = x.py();
        Ok(match self.sd_find(k, x)?.0 {
            Some(i) => self.sc.borrow().d[k].ent[i].as_ref().map(|e| e.val.bind(p).clone()),
            None => None,
        })
    }

    pub(crate) fn sd_set(&self, k: usize, x: &Bound<'_, PyAny>, v: &Bound<'_, PyAny>) -> PyResult<()> {
        tick(session::SC_CORE);
        let (at, hash) = self.sd_find(k, x)?;
        if sb_planted(SD_PLANT[k]) {
            return Ok(());
        }
        if sb_planted(KEY_SHARED_PLANT) {
            crate::relkeys::rk_key(self, x, Some(session::RK_INTERN_INPUT))?;
        }
        // the old value is dropped after the borrow ends
        let old = {
            let mut sc = self.sc.borrow_mut();
            let d = &mut sc.d[k];
            match at.and_then(|i| d.ent[i].as_mut()) {
                Some(e) => Some(std::mem::replace(&mut e.val, v.clone().unbind())),
                None => {
                    d.idx.entry(hash).or_default().push(d.ent.len());
                    d.ent.push(Some(Entry { hash, key: x.clone().unbind(), val: v.clone().unbind() }));
                    d.live += 1;
                    None
                }
            }
        };
        drop(old);
        Ok(())
    }

    pub(crate) fn sd_del(&self, k: usize, x: &Bound<'_, PyAny>) -> PyResult<Option<Py<PyAny>>> {
        tick(session::SC_CORE);
        Ok(match self.sd_find(k, x)?.0 {
            Some(i) => {
                let e = self.sc.borrow_mut().d[k].unlink(i);
                e.map(|e| e.val)
            }
            None => None,
        })
    }

    /// `d.popitem()`: the last key set, with its value.
    pub(crate) fn sd_popitem<'py>(&self, p: Python<'py>, k: usize) -> Option<(Bound<'py, PyAny>, Bound<'py, PyAny>)> {
        tick(session::SC_CORE);
        let e = {
            let mut sc = self.sc.borrow_mut();
            let d = &mut sc.d[k];
            let i = d.ent.iter().rposition(|e| e.is_some())?;
            let e = d.unlink(i);
            d.ent.truncate(i.min(d.ent.len()));
            e
        }?;
        Some((e.key.into_bound(p), e.val.into_bound(p)))
    }

    pub(crate) fn sd_len(&self, k: usize) -> usize {
        tick(session::SC_CORE);
        self.sc.borrow().d[k].live
    }

    pub(crate) fn sd_clear(&self, k: usize) {
        tick(session::SC_CORE);
        let old = std::mem::take(&mut self.sc.borrow_mut().d[k]);
        drop(old);
    }

    /// The dict's (key object, value) pairs in insertion order.
    pub(crate) fn sd_items<'py>(&self, p: Python<'py>, k: usize) -> Vec<(Bound<'py, PyAny>, Bound<'py, PyAny>)> {
        self.sc.borrow().d[k].ent.iter().flatten().map(|e| (e.key.bind(p).clone(), e.val.bind(p).clone())).collect()
    }

    pub(crate) fn sq_push(&self, k: usize, x: &Bound<'_, PyAny>) {
        tick(session::SC_CORE);
        if sb_planted(SQ_PLANT[k]) {
            return;
        }
        self.sc.borrow_mut().q[k].push_back(x.clone().unbind());
    }

    pub(crate) fn sq_popleft<'py>(&self, p: Python<'py>, k: usize) -> Option<Bound<'py, PyAny>> {
        tick(session::SC_CORE);
        self.sc.borrow_mut().q[k].pop_front().map(|x| x.into_bound(p))
    }

    pub(crate) fn sq_pop<'py>(&self, p: Python<'py>, k: usize) -> Option<Bound<'py, PyAny>> {
        tick(session::SC_CORE);
        self.sc.borrow_mut().q[k].pop_back().map(|x| x.into_bound(p))
    }

    pub(crate) fn sq_len(&self, k: usize) -> usize {
        tick(session::SC_CORE);
        self.sc.borrow().q[k].len()
    }

    pub(crate) fn sq_items<'py>(&self, p: Python<'py>, k: usize) -> Vec<Bound<'py, PyAny>> {
        self.sc.borrow().q[k].iter().map(|x| x.bind(p).clone()).collect()
    }

    /// `s.<name> = deque(items)` (or a list): the old items go, as the old object did on Python.
    pub(crate) fn sq_replace(&self, k: usize, items: Vec<Bound<'_, PyAny>>) {
        tick(session::SC_CORE);
        let new: VecDeque<Py<PyAny>> = if sb_planted(SQ_PLANT[k]) { VecDeque::new() } else { items.into_iter().map(|x| x.unbind()).collect() };
        let old = std::mem::replace(&mut self.sc.borrow_mut().q[k], new);
        drop(old);
    }
}

/// A session's containers as Rust sites see them: the core's, or Python's own on a session with no core.
pub(crate) enum Ses<'py> {
    Core(Bound<'py, SessionCore>),
    Py(Bound<'py, PyAny>),
}

impl<'py> Ses<'py> {
    pub(crate) fn of(s: &Bound<'py, PyAny>) -> Self {
        match session::core_of(s) {
            Ok(c) => Ses::Core(c),
            Err(_) => {
                tick(session::SB_ATTR);
                Ses::Py(s.clone())
            }
        }
    }

    fn py(&self) -> Python<'py> {
        match self {
            Ses::Core(c) => c.py(),
            Ses::Py(s) => s.py(),
        }
    }

    /// `x in s.<dict>`.
    pub(crate) fn d_contains(&self, k: usize, x: &Bound<'py, PyAny>) -> PyResult<bool> {
        match self {
            Ses::Core(c) => Ok(c.borrow().sd_get(k, x)?.is_some()),
            Ses::Py(s) => s.getattr(SD_NAMES[k])?.contains(x),
        }
    }

    /// `s.<dict>.get(x)`: the value or None.
    pub(crate) fn d_get(&self, k: usize, x: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        let p = self.py();
        match self {
            Ses::Core(c) => Ok(c.borrow().sd_get(k, x)?.unwrap_or_else(|| p.None().into_bound(p))),
            Ses::Py(s) => s.getattr(SD_NAMES[k])?.call_method1(intern!(p, "get"), (x,)),
        }
    }

    /// `s.<dict>[x]`, a KeyError when absent.
    pub(crate) fn d_item(&self, k: usize, x: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        match self {
            Ses::Core(c) => c.borrow().sd_get(k, x)?.ok_or_else(|| pyo3::exceptions::PyKeyError::new_err(x.clone().unbind())),
            Ses::Py(s) => s.getattr(SD_NAMES[k])?.get_item(x),
        }
    }

    pub(crate) fn d_set(&self, k: usize, x: &Bound<'py, PyAny>, v: &Bound<'py, PyAny>) -> PyResult<()> {
        match self {
            Ses::Core(c) => c.borrow().sd_set(k, x, v),
            Ses::Py(s) => s.getattr(SD_NAMES[k])?.set_item(x, v),
        }
    }

    /// `del s.<dict>[x]`.
    pub(crate) fn d_del(&self, k: usize, x: &Bound<'py, PyAny>) -> PyResult<()> {
        match self {
            Ses::Core(c) => match c.borrow().sd_del(k, x)? {
                Some(_) => Ok(()),
                None => Err(pyo3::exceptions::PyKeyError::new_err(x.clone().unbind())),
            },
            Ses::Py(s) => s.getattr(SD_NAMES[k])?.del_item(x),
        }
    }

    /// `s.<dict>.popitem()` on a non-empty dict.
    pub(crate) fn d_popitem(&self, k: usize) -> PyResult<(Bound<'py, PyAny>, Bound<'py, PyAny>)> {
        let p = self.py();
        match self {
            Ses::Core(c) => c.borrow().sd_popitem(p, k)
                .ok_or_else(|| pyo3::exceptions::PyKeyError::new_err("popitem(): dictionary is empty")),
            Ses::Py(s) => {
                let item = s.getattr(SD_NAMES[k])?.call_method0(intern!(p, "popitem"))?;
                Ok((item.get_item(0)?, item.get_item(1)?))
            }
        }
    }

    pub(crate) fn d_truthy(&self, k: usize) -> PyResult<bool> {
        match self {
            Ses::Core(c) => Ok(c.borrow().sd_len(k) > 0),
            Ses::Py(s) => s.getattr(SD_NAMES[k])?.is_truthy(),
        }
    }

    /// `s.<seq>.append(x)`.
    pub(crate) fn q_push(&self, k: usize, x: &Bound<'py, PyAny>) -> PyResult<()> {
        match self {
            Ses::Core(c) => {
                c.borrow().sq_push(k, x);
                Ok(())
            }
            Ses::Py(s) => s.getattr(SQ_NAMES[k])?.call_method1(intern!(self.py(), "append"), (x,)).map(|_| ()),
        }
    }

    /// `s.frontier.popleft()` on a non-empty deque.
    pub(crate) fn q_popleft(&self, k: usize) -> PyResult<Bound<'py, PyAny>> {
        let p = self.py();
        match self {
            Ses::Core(c) => c.borrow().sq_popleft(p, k).ok_or_else(|| pyo3::exceptions::PyIndexError::new_err("pop from an empty deque")),
            Ses::Py(s) => s.getattr(SQ_NAMES[k])?.call_method0(intern!(p, "popleft")),
        }
    }

    /// `s.deferred.pop()`.
    pub(crate) fn q_pop(&self, k: usize) -> PyResult<Bound<'py, PyAny>> {
        let p = self.py();
        match self {
            Ses::Core(c) => c.borrow().sq_pop(p, k).ok_or_else(|| pyo3::exceptions::PyIndexError::new_err("pop from empty list")),
            Ses::Py(s) => s.getattr(SQ_NAMES[k])?.call_method0(intern!(p, "pop")),
        }
    }

    pub(crate) fn q_truthy(&self, k: usize) -> PyResult<bool> {
        match self {
            Ses::Core(c) => Ok(c.borrow().sq_len(k) > 0),
            Ses::Py(s) => s.getattr(SQ_NAMES[k])?.is_truthy(),
        }
    }

    /// The items, as iteration over the sequence gives them.
    pub(crate) fn q_items(&self, k: usize) -> PyResult<Vec<Bound<'py, PyAny>>> {
        match self {
            Ses::Core(c) => Ok(c.borrow().sq_items(self.py(), k)),
            Ses::Py(s) => s.getattr(SQ_NAMES[k])?.try_iter()?.collect(),
        }
    }

    /// `s.frontier = deque()` or `deque([x])`: a new object each time on Python, the content replaced in the core.
    pub(crate) fn frontier_reset(&self, x: Option<&Bound<'py, PyAny>>) -> PyResult<()> {
        let p = self.py();
        match self {
            Ses::Core(c) => {
                c.borrow().sq_replace(SQ_FRONTIER, x.into_iter().cloned().collect());
                Ok(())
            }
            Ses::Py(s) => {
                let d = p.import(intern!(p, "collections"))?.getattr(intern!(p, "deque"))?;
                let v = match x {
                    None => d.call0()?,
                    Some(x) => d.call1((PyList::new(p, [x])?,))?,
                };
                s.setattr(intern!(p, "frontier"), v)
            }
        }
    }
}

/// The view Python reads a session dict through (session_live installs it as `Session.<name>`). Its writes are the record
/// methods, for Python's own `Session` methods (SLICE_DISC=py, SLICE_LOOP=py, SLICE_GLUE=py over a core) and tests.
#[pyclass(unsendable, frozen)]
pub struct SesDictView {
    core: Py<SessionCore>,
    k: usize,
}

#[pymethods]
impl SesDictView {
    fn __contains__(&self, py: Python<'_>, x: &Bound<'_, PyAny>) -> PyResult<bool> {
        tick(session::SC_VIEW);
        Ok(self.core.borrow(py).sd_get(self.k, x)?.is_some())
    }

    fn __getitem__<'py>(&self, py: Python<'py>, x: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        tick(session::SC_VIEW);
        self.core.borrow(py).sd_get(self.k, x)?.ok_or_else(|| pyo3::exceptions::PyKeyError::new_err(x.clone().unbind()))
    }

    #[pyo3(signature = (x, default=None))]
    fn get<'py>(&self, py: Python<'py>, x: &Bound<'py, PyAny>, default: Option<Bound<'py, PyAny>>) -> PyResult<Bound<'py, PyAny>> {
        tick(session::SC_VIEW);
        Ok(match self.core.borrow(py).sd_get(self.k, x)? {
            Some(v) => v,
            None => default.unwrap_or_else(|| py.None().into_bound(py)),
        })
    }

    fn __setitem__(&self, py: Python<'_>, x: &Bound<'_, PyAny>, v: &Bound<'_, PyAny>) -> PyResult<()> {
        tick(session::SC_RECORD);
        self.core.borrow(py).sd_set(self.k, x, v)
    }

    #[pyo3(signature = (x, default=None))]
    fn setdefault<'py>(&self, py: Python<'py>, x: &Bound<'py, PyAny>, default: Option<Bound<'py, PyAny>>) -> PyResult<Bound<'py, PyAny>> {
        if let Some(v) = self.core.borrow(py).sd_get(self.k, x)? {
            tick(session::SC_VIEW);
            return Ok(v);
        }
        let v = default.unwrap_or_else(|| py.None().into_bound(py));
        self.__setitem__(py, x, &v)?;
        // what the dict holds: under a `sc-*-drop` plant the write was dropped, as it is for a Rust site
        Ok(self.core.borrow(py).sd_get(self.k, x)?.unwrap_or(v))
    }

    fn __delitem__(&self, py: Python<'_>, x: &Bound<'_, PyAny>) -> PyResult<()> {
        tick(session::SC_RECORD);
        match self.core.borrow(py).sd_del(self.k, x)? {
            Some(_) => Ok(()),
            None => Err(pyo3::exceptions::PyKeyError::new_err(x.clone().unbind())),
        }
    }

    #[pyo3(signature = (x, *default))]
    fn pop<'py>(&self, py: Python<'py>, x: &Bound<'py, PyAny>, default: &Bound<'py, PyTuple>) -> PyResult<Bound<'py, PyAny>> {
        tick(session::SC_RECORD);
        match self.core.borrow(py).sd_del(self.k, x)? {
            Some(v) => Ok(v.into_bound(py)),
            None if !default.is_empty() => default.get_item(0),
            None => Err(pyo3::exceptions::PyKeyError::new_err(x.clone().unbind())),
        }
    }

    fn popitem<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyTuple>> {
        tick(session::SC_RECORD);
        match self.core.borrow(py).sd_popitem(py, self.k) {
            Some((a, b)) => PyTuple::new(py, [a, b]),
            None => Err(pyo3::exceptions::PyKeyError::new_err("popitem(): dictionary is empty")),
        }
    }

    fn update(&self, py: Python<'_>, d: &Bound<'_, PyAny>) -> PyResult<()> {
        for kv in d.call_method0(intern!(py, "items"))?.try_iter()? {
            let (key, v): (Bound<'_, PyAny>, Bound<'_, PyAny>) = kv?.extract()?;
            self.__setitem__(py, &key, &v)?;
        }
        Ok(())
    }

    fn clear(&self, py: Python<'_>) {
        tick(session::SC_RECORD);
        self.core.borrow(py).sd_clear(self.k);
    }

    fn __len__(&self, py: Python<'_>) -> usize {
        tick(session::SC_VIEW);
        self.core.borrow(py).sd_len(self.k)
    }

    fn __bool__(&self, py: Python<'_>) -> bool {
        self.__len__(py) > 0
    }

    fn keys<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        tick(session::SC_VIEW);
        PyList::new(py, self.core.borrow(py).sd_items(py, self.k).into_iter().map(|e| e.0))
    }

    fn values<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        tick(session::SC_VIEW);
        PyList::new(py, self.core.borrow(py).sd_items(py, self.k).into_iter().map(|e| e.1))
    }

    fn items<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        tick(session::SC_VIEW);
        let v: Vec<Bound<'py, PyTuple>> = self.core.borrow(py).sd_items(py, self.k).into_iter()
            .map(|(a, b)| PyTuple::new(py, [a, b])).collect::<PyResult<_>>()?;
        PyList::new(py, v)
    }

    /// Over a copy of the keys, taken when iteration starts.
    fn __iter__<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        self.keys(py)?.into_any().try_iter().map(|i| i.into_any())
    }

    /// A Python dict of the items, for a test or a digest that compares.
    fn copy<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let d = PyDict::new(py);
        for (a, b) in self.core.borrow(py).sd_items(py, self.k) {
            d.set_item(a, b)?;
        }
        Ok(d)
    }

    fn __eq__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<bool> {
        match other.cast::<SesDictView>() {
            Ok(o) => self.copy(py)?.eq(o.get().copy(py)?),
            Err(_) => self.copy(py)?.eq(other),
        }
    }

    fn __repr__(&self, py: Python<'_>) -> PyResult<String> {
        Ok(format!("SesDictView({}, {})", SD_NAMES[self.k], self.copy(py)?.repr()?))
    }
}

/// The view of `Session.frontier` (a deque's surface) and `Session.deferred` (a list's).
#[pyclass(unsendable, frozen)]
pub struct SesSeqView {
    core: Py<SessionCore>,
    k: usize,
}

#[pymethods]
impl SesSeqView {
    fn append(&self, py: Python<'_>, x: &Bound<'_, PyAny>) {
        tick(session::SC_RECORD);
        self.core.borrow(py).sq_push(self.k, x);
    }

    fn extend(&self, py: Python<'_>, xs: &Bound<'_, PyAny>) -> PyResult<()> {
        let v: Vec<Bound<'_, PyAny>> = xs.try_iter()?.collect::<PyResult<_>>()?;
        for x in v {
            self.append(py, &x);
        }
        Ok(())
    }

    fn popleft<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        tick(session::SC_RECORD);
        self.core.borrow(py).sq_popleft(py, self.k).ok_or_else(|| pyo3::exceptions::PyIndexError::new_err("pop from an empty deque"))
    }

    /// `xs.pop()`: the last item.
    fn pop<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        tick(session::SC_RECORD);
        self.core.borrow(py).sq_pop(py, self.k).ok_or_else(|| pyo3::exceptions::PyIndexError::new_err("pop from empty list"))
    }

    fn clear(&self, py: Python<'_>) {
        tick(session::SC_RECORD);
        self.core.borrow(py).sq_replace(self.k, vec![]);
    }

    fn __getitem__<'py>(&self, py: Python<'py>, i: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        tick(session::SC_VIEW);
        self.copy(py)?.as_any().get_item(i)
    }

    fn __contains__(&self, py: Python<'_>, x: &Bound<'_, PyAny>) -> PyResult<bool> {
        tick(session::SC_VIEW);
        self.copy(py)?.contains(x)
    }

    fn __len__(&self, py: Python<'_>) -> usize {
        tick(session::SC_VIEW);
        self.core.borrow(py).sq_len(self.k)
    }

    fn __bool__(&self, py: Python<'_>) -> bool {
        self.__len__(py) > 0
    }

    /// Over a copy of the items, taken when iteration starts.
    fn __iter__<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        tick(session::SC_VIEW);
        self.copy(py)?.into_any().try_iter().map(|i| i.into_any())
    }

    /// A Python list of the items, for a test or a digest that compares.
    fn copy<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        PyList::new(py, self.core.borrow(py).sq_items(py, self.k))
    }

    /// Equal to any sequence with the same items in order (a deque or a list on Python).
    fn __eq__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<bool> {
        let Ok(it) = other.try_iter() else { return Ok(false) };
        let o = PyList::new(py, it.collect::<PyResult<Vec<_>>>()?)?;
        self.copy(py)?.eq(o)
    }

    fn __repr__(&self, py: Python<'_>) -> PyResult<String> {
        Ok(format!("SesSeqView({}, {})", SQ_NAMES[self.k], self.copy(py)?.repr()?))
    }
}

pub(crate) fn dict_view(core: &Bound<'_, SessionCore>, k: usize) -> PyResult<SesDictView> {
    if k >= SD_NAMES.len() {
        return Err(pyo3::exceptions::PyValueError::new_err("no such session dict"));
    }
    Ok(SesDictView { core: core.clone().unbind(), k })
}

pub(crate) fn seq_view(core: &Bound<'_, SessionCore>, k: usize) -> PyResult<SesSeqView> {
    if k >= SQ_NAMES.len() {
        return Err(pyo3::exceptions::PyValueError::new_err("no such session sequence"));
    }
    Ok(SesSeqView { core: core.clone().unbind(), k })
}

/// The record method behind `s.<dict> = {...}`: the content replaced.
pub(crate) fn dict_replace(core: &Bound<'_, SessionCore>, k: usize, d: &Bound<'_, PyAny>) -> PyResult<()> {
    tick(session::SC_RECORD);
    let v = dict_view(core, k)?;
    let items: Vec<(Bound<'_, PyAny>, Bound<'_, PyAny>)> =
        d.call_method0(intern!(d.py(), "items"))?.try_iter()?.map(|kv| kv?.extract()).collect::<PyResult<_>>()?;
    let c = core.borrow();
    c.sd_clear(k);
    for (a, b) in items {
        c.sd_set(v.k, &a, &b)?;
    }
    Ok(())
}

/// ... `s.frontier = deque(...)`, `s.deferred = [...]`.
pub(crate) fn seq_replace(core: &Bound<'_, SessionCore>, k: usize, xs: &Bound<'_, PyAny>) -> PyResult<()> {
    tick(session::SC_RECORD);
    seq_view(core, k)?;
    let items: Vec<Bound<'_, PyAny>> = xs.try_iter()?.collect::<PyResult<_>>()?;
    core.borrow().sq_replace(k, items);
    Ok(())
}

/// Every container's content, by Python's name: dicts as dicts, sequences as lists (a test's and the digest's export).
pub(crate) fn snapshot<'py>(core: &Bound<'py, SessionCore>) -> PyResult<Bound<'py, PyDict>> {
    let p = core.py();
    let out = PyDict::new(p);
    for (k, n) in SQ_NAMES.iter().enumerate() {
        out.set_item(n, seq_view(core, k)?.copy(p)?)?;
    }
    for (k, n) in SD_NAMES.iter().enumerate() {
        out.set_item(n, dict_view(core, k)?.copy(p)?)?;
    }
    Ok(out)
}
