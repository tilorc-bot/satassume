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
//!
//! The part 3 follow-up, item 2: each dict also remembers, by identity, every object it has met (`SesDict::seen`, holding a
//! strong ref, so an address can't be reused while it's there): its `hash()`, and the entry it resolved to. A later lookup
//! with that same object goes straight to its entry with no `hash()` and no `==` while the entry is the one it resolved to
//! (`Entry::gen`); otherwise (a miss then, or a deleted and re-set key) it takes the remembered hash and the dict's rule from
//! there. Each `hash()` not called is counted `sc:key_id`. Python's dict gives the same answers: it assumes a key's hash
//! and `==` don't change (SymPy's `Basic` caches its hash), and finds an identical object without `==`. The
//! first key object is still the one the dict holds. Per dict, per session, never process-wide; emptied by `clear()`.
//! Plant 615 `sc-key-id-stale` ignores the generation (a deleted key's old object finds a dead or reused entry); 616
//! `sc-key-id-weak` holds no reference (a reused address finds a freed object's row); 617 `sc-key-id-shared` keeps one memo
//! process-wide (a dict finds another dict's entry). test_ses_keys.py catches each against a plain dict.
//! The memo is derived from its dict: it lives in the `SesDict` and goes with it (`clear()`, a replace, the session's end;
//! sessions are built per query, engine.py `_session`), so a discarded run takes it with its session (R5). The digest
//! (`sc_snapshot`) exports the entries, not the memo.
//! Why not the query's term id: a term id is reached through the session's node table (`node_quiet`, a Python dict lookup),
//! so it would move each `hash()` to `link:cross_hash`, not remove it.

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
pub(crate) const KEY_ID_STALE_PLANT: u16 = 615;
/// 616 `sc-key-id-weak`: a memo row keeps no reference to its object, so a freed object's address, reused by another, finds
/// the freed one's hash and entry (condition (a) of the planner's 11 Nov ruling on item 2).
const KEY_ID_WEAK_PLANT: u16 = 616;
/// 617 `sc-key-id-shared`: one memo for every dict of every session, process-wide (condition (c)).
const KEY_ID_SHARED_PLANT: u16 = 617;

thread_local! {
    /// Plant 617's process-wide memo; empty unless the plant is set.
    static SHARED_SEEN: std::cell::RefCell<std::collections::HashMap<usize, Seen>> = Default::default();
    /// Gauge 701 `sc:ses_live`: the sessions' containers alive now (one per `SessionCore`). The planner's ruling (2) on 293's
    /// deviations: the memo keeps what it looked up alive for its session, so no session may outlive its query. Read at a
    /// query boundary (after `gc.collect()`), it is 0 (test_ses_keys.py `test_no_session_outlives_its_query`).
    static LIVE: std::cell::Cell<i64> = const { std::cell::Cell::new(0) };
    /// Gauge 702 `sc:memo_peak`: the most rows one dict's memo has held, process-wide (one process per workload).
    static PEAK: std::cell::Cell<usize> = const { std::cell::Cell::new(0) };
}

/// The two gauges (701 `sc:ses_live`, 702 `sc:memo_peak`), for `session_counts`.
pub(crate) fn gauges() -> (i64, usize) {
    (LIVE.with(|c| c.get()), PEAK.with(|c| c.get()))
}

struct Entry {
    gen: u64,
    hash: isize,
    key: Py<PyAny>,
    val: Py<PyAny>,
}

/// An object a dict has met: held (so its address stays its own), its `hash()`, and the entry it resolved to with that
/// entry's `gen`, if any. The planner's ruling (1) on 293's deviations: the cached `hash()` is keyed by identity on an object
/// this row holds, never by address alone: the row's key is the address of `obj`, which the row keeps alive, so no other
/// object can have that address while the row lives (plant 616 drops the hold; test_ses_keys.py catches it).
struct Seen {
    #[allow(dead_code)]
    obj: Py<PyAny>,
    hash: isize,
    at: Option<(usize, u64)>,
}

/// One dict: entries in insertion order (a deleted one leaves a hole), and the entries of each hash.
#[derive(Default)]
struct SesDict {
    idx: std::collections::HashMap<isize, Vec<usize>>,
    ent: Vec<Option<Entry>>,
    live: usize,
    /// each object already looked up or set here, by address
    seen: std::collections::HashMap<usize, Seen>,
    gen: u64,
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
            // `seen` stays: its rows name entries by `gen`, which only grows, so a row for a cleared entry never matches
            self.ent.clear();
        }
        Some(e)
    }
}

pub(crate) struct SesCont {
    d: [SesDict; 5],
    q: [VecDeque<Py<PyAny>>; 2],
}

impl Default for SesCont {
    fn default() -> Self {
        LIVE.with(|c| c.set(c.get() + 1));
        SesCont { d: Default::default(), q: Default::default() }
    }
}

impl Drop for SesCont {
    fn drop(&mut self) {
        LIVE.with(|c| c.set(c.get() - 1));
    }
}

impl SessionCore {
    /// The entry of the key `x` in dict `k` and `x`'s hash: the dict's rule, the same hash and then the same object or `==`
    /// (the held key on the left). No borrow is held while Python's `__hash__` and `__eq__` run.
    fn sd_find(&self, k: usize, x: &Bound<'_, PyAny>) -> PyResult<(Option<usize>, isize)> {
        let row = self.seen_row(k, x.as_ptr() as usize);
        let known = match row {
            Some((h, at)) => {
                if let Some((i, g)) = at {
                    let sc = self.sc.borrow();
                    if let Some(Some(e)) = sc.d[k].ent.get(i) {
                        if e.gen == g || sb_planted(KEY_ID_STALE_PLANT) {
                            tick(session::SC_KEY_ID);
                            return Ok((Some(i), e.hash));
                        }
                    }
                }
                Some(h)
            }
            None => None,
        };
        let hash = match known {
            Some(h) => {
                tick(session::SC_KEY_ID);
                h
            }
            None => {
                tick(session::SC_KEY_HASH);
                x.hash()?
            }
        };
        let r = self.sd_find_hash(k, x, hash)?;
        self.sd_remember(k, x, hash, r.0);
        Ok(r)
    }

    /// `x` (whose hash is `hash`) resolved to entry `at` of dict `k`, or to none.
    fn sd_remember(&self, k: usize, x: &Bound<'_, PyAny>, hash: isize, at: Option<usize>) {
        let at = {
            let sc = self.sc.borrow();
            let d = &sc.d[k];
            at.and_then(|i| d.ent.get(i).and_then(|e| e.as_ref()).map(|e| (i, e.gen)))
        };
        self.seen_put(k, x, hash, at);
    }

    /// The memo row of the object at address `ptr` in dict `k`: its hash and the entry (with that entry's `gen`) it resolved to.
    fn seen_row(&self, k: usize, ptr: usize) -> Option<(isize, Option<(usize, u64)>)> {
        if sb_planted(KEY_ID_SHARED_PLANT) {
            return SHARED_SEEN.with(|m| m.borrow().get(&ptr).map(|r| (r.hash, r.at)));
        }
        self.sc.borrow().d[k].seen.get(&ptr).map(|r| (r.hash, r.at))
    }

    /// Remember `x` in dict `k`'s memo, holding it (so its address stays its own while the row lives). The row it replaces
    /// is dropped after the borrow ends (dropping an object can run Python).
    fn seen_put(&self, k: usize, x: &Bound<'_, PyAny>, hash: isize, at: Option<(usize, u64)>) {
        let obj = if sb_planted(KEY_ID_WEAK_PLANT) { x.py().None() } else { x.clone().unbind() };
        let row = Seen { obj, hash, at };
        let old = if sb_planted(KEY_ID_SHARED_PLANT) {
            SHARED_SEEN.with(|m| m.borrow_mut().insert(x.as_ptr() as usize, row))
        } else {
            let mut sc = self.sc.borrow_mut();
            let old = sc.d[k].seen.insert(x.as_ptr() as usize, row);
            let n = sc.d[k].seen.len();
            PEAK.with(|c| c.set(c.get().max(n)));
            old
        };
        drop(old);
    }

    fn sd_find_hash(&self, k: usize, x: &Bound<'_, PyAny>, hash: isize) -> PyResult<(Option<usize>, isize)> {
        let p = x.py();
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
                    let i = d.ent.len();
                    d.gen += 1;
                    d.idx.entry(hash).or_default().push(i);
                    d.ent.push(Some(Entry { gen: d.gen, hash, key: x.clone().unbind(), val: v.clone().unbind() }));
                    d.live += 1;
                    let at = Some((i, d.gen));
                    drop(sc);
                    self.seen_put(k, x, hash, at);
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
