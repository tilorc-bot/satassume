//! State step, part 2 (iii)(b), the rest: RelKeys and Relations' containers held natively in the session core (issue 323).
//!
//! The planner's ruling (~04:50 UTC 10 Nov, option B refined): RelKeys lives in `SessionCore` and holds strong refs. A key that
//! already has a term id in the query's table takes it and does no new hash (`relations_core::term_of`, the same resolve link
//! uses); only keys with no id are interned, by one hash and `==` at that point, counted by where the key came from:
//! `rk:intern:input` (an object converted from the user's terms) or `rk:intern:engine` (atoms or terms the engine builds,
//! scaffolding until those are Rust-native; target 0 before any backend PR). A session that outlives its query (it meets a
//! second query table, or a table after interning a term with none) is counted `rk:outlive` and goes dict-only, its term-id
//! keys re-interned by hash (`rk:migrate`), so membership stays Python's `==` membership.
//!
//! The sets of `RS_NAMES` are `HashSet<u32>` per `Relations` (session.rs `RelS`). Rust sites read and write them natively; Python
//! reads them through `RelSetView` (session_live installs the views on `Relations`), whose `add`/`update` are the record methods.
//! A `Relations` over a session with no core (`satassume/ref.py`) keeps Python's own sets: `RSet::Py`.

use pyo3::intern;
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::BoundObject;
use pyo3::types::{PyDict, PyList, PySet, PyType};

use crate::relations_core::{hooks, installed, planted, term_of};
use crate::session::{self, tick, RelKeys, RelS, SessionCore, RD_NAMES, RL_NAMES, RS_NAMES};

static BASIC: PyOnceLock<Py<PyType>> = PyOnceLock::new();

/// Where an interned key of each set came from (the ruling's split): the user's terms and atoms, or the engine's own.
const RS_ORIGIN: [usize; 9] = [
    session::RK_INTERN_INPUT,  // linked: an atom's expr, a side
    session::RK_INTERN_INPUT,  // _bounded: a constant term of an atom
    session::RK_INTERN_INPUT,  // _user_eq: a user's eq atom
    session::RK_INTERN_ENGINE, // _xpairs: head pairs the engine builds
    session::RK_INTERN_ENGINE, // _aux_eq: the engine's eq(e, 0)
    session::RK_INTERN_ENGINE, // _link_eq: the links' eq(e, 0)
    session::RK_INTERN_INPUT,  // _xpart: sides
    session::RK_INTERN_INPUT,  // _xcounted: structural subterms of sides
    session::RK_INTERN_INPUT,  // _xcand: candidate nodes (sides)
];

/// The plants, one per moved set: `rs-<name>-drop` makes the set's add a no-op on Rust (the view's too).
pub(crate) const RS_PLANT0: u16 = 269;

fn is_basic(x: &Bound<'_, PyAny>) -> PyResult<bool> {
    let p = x.py();
    let b = BASIC.get_or_try_init(p, || -> PyResult<Py<PyType>> {
        Ok(p.import(intern!(p, "sympy"))?.getattr(intern!(p, "Basic"))?.cast_into::<PyType>()?.unbind())
    })?;
    x.is_instance(b.bind(p))
}

static JOINABLE: PyOnceLock<Py<PyAny>> = PyOnceLock::new();

/// A Basic that `==` a non-Basic Python object of another class (`Integer(2) == 2`, `Float(2) == 2.0`, `S.true == True`,
/// `Tuple(1, 2) == (1, 2)`), where a Python set joins the two. Such keys go by hash and `==` (the dict), never by term id, so
/// RelKeys joins them as Python's set does (the state rule's exactness; the int/Integer gap of sa-port-221's handoff).
fn is_joinable(x: &Bound<'_, PyAny>) -> PyResult<bool> {
    let p = x.py();
    let t = JOINABLE.get_or_try_init(p, || -> PyResult<Py<PyAny>> {
        let s = p.import(intern!(p, "sympy"))?;
        let b = p.import(intern!(p, "sympy.logic.boolalg"))?;
        Ok(pyo3::types::PyTuple::new(p, [s.getattr("Number")?, b.getattr("BooleanAtom")?, s.getattr("Tuple")?])?.into_any().unbind())
    })?;
    x.is_instance(t.bind(p))
}

fn dict<'py>(p: Python<'py>, k: &mut RelKeys) -> Bound<'py, PyDict> {
    k.dict.get_or_insert_with(|| PyDict::new(p).unbind()).bind(p).clone()
}

/// The session outlives its query: every term-id key goes into the dict (by hash), and the session stays dict-only.
fn go_dict_only(p: Python<'_>, k: &mut RelKeys) -> PyResult<()> {
    tick(session::RK_OUTLIVE);
    let d = dict(p, k);
    for (_, key) in k.by_term.drain() {
        tick(session::RK_MIGRATE);
        d.set_item(k.objs[key as usize].bind(p), key)?;
    }
    k.dict_only = true;
    k.table = None;
    Ok(())
}

/// The key of `x`, or None when it has none; with `origin`, interns it (or takes its term id) when it has none.
pub(crate) fn rk_key(c: &SessionCore, x: &Bound<'_, PyAny>, origin: Option<usize>) -> PyResult<Option<u32>> {
    let p = x.py();
    let basic = is_basic(x)? && !is_joinable(x)?;
    // relations on Python (SLICE_REL=py, rel_install hasn't run): no query-table link, keys by hash (Python's `==` membership)
    if basic && installed() && !c.relkeys.borrow().dict_only {
        let h = hooks()?;
        let q = h.term_live().bind(p).call_method0(intern!(p, "current"))?;
        let tableless = q.is_none() || !q.getattr(intern!(p, "kept"))?.is_none();
        if tableless {
            let mut k = c.relkeys.borrow_mut();
            if !k.by_term.is_empty() {
                go_dict_only(p, &mut k)?;
            } else if origin.is_some() {
                k.tableless = true;
            }
        } else if let Some(l) = term_of(c, &h, x)? {
            let t = l.table.as_ptr() as usize;
            let mut k = c.relkeys.borrow_mut();
            if k.tableless || k.table.is_some_and(|u| u != t) {
                go_dict_only(p, &mut k)?;
            } else {
                k.table = Some(t);
                tick(session::RK_TERM);
                if let Some(&key) = k.by_term.get(&l.id) {
                    return Ok(Some(key));
                }
                // the same object may have been interned by hash before it had a row
                if k.basic_dict > 0 {
                    if let Some(v) = dict(p, &mut k).get_item(x)? {
                        tick(session::RK_DICT_HIT);
                        return Ok(Some(v.extract()?));
                    }
                }
                let Some(_) = origin else { return Ok(None) };
                let key = k.objs.len() as u32;
                k.objs.push(x.clone().unbind());
                k.by_term.insert(l.id, key);
                return Ok(Some(key));
            }
        }
    }
    let mut k = c.relkeys.borrow_mut();
    let d = dict(p, &mut k);
    if let Some(v) = d.get_item(x)? {
        tick(session::RK_DICT_HIT);
        return Ok(Some(v.extract()?));
    }
    let Some(o) = origin else { return Ok(None) };
    tick(o);
    let key = k.objs.len() as u32;
    k.objs.push(x.clone().unbind());
    d.set_item(x, key)?;
    if basic && !k.dict_only {
        k.basic_dict += 1;
    }
    Ok(Some(key))
}

fn with_rel<T>(c: &SessionCore, rel: &Bound<'_, PyAny>, f: impl FnOnce(&mut RelS) -> T) -> T {
    let mut v = c.rels.borrow_mut();
    let i = match v.iter().position(|x| x.rel.is(rel)) {
        Some(i) => i,
        None => {
            v.push(RelS { rel: rel.clone().unbind(), s: Default::default(), order: Default::default(), d: Default::default(), l: Default::default() });
            v.len() - 1
        }
    };
    f(&mut v[i])
}

impl SessionCore {
    /// `Relations.__init__`'s empty sets.
    pub(crate) fn rs_init(&self, rel: &Bound<'_, PyAny>) {
        tick(session::RS_CORE);
        with_rel(self, rel, |r| {
            r.s = Default::default();
            r.order = Default::default();
            r.d = Default::default();
            r.l = Default::default();
        });
    }

    /// `x in rel.<RS_NAMES[k]>`.
    pub(crate) fn rs_contains(&self, rel: &Bound<'_, PyAny>, k: usize, x: &Bound<'_, PyAny>) -> PyResult<bool> {
        tick(session::RS_CORE);
        Ok(match rk_key(self, x, None)? {
            Some(key) => self.rels.borrow().iter().find(|r| r.rel.is(rel)).is_some_and(|r| r.s[k].contains(&key)),
            None => false,
        })
    }

    /// `rel.<RS_NAMES[k]>.add(x)`; true when it wasn't there.
    pub(crate) fn rs_add(&self, rel: &Bound<'_, PyAny>, k: usize, x: &Bound<'_, PyAny>) -> PyResult<bool> {
        tick(session::RS_CORE);
        let key = rk_key(self, x, Some(RS_ORIGIN[k]))?.expect("interned");
        if planted(RS_PLANT0 + k as u16) {
            return Ok(false);
        }
        Ok(with_rel(self, rel, |r| {
            let new = r.s[k].insert(key);
            if new {
                r.order[k].push(key);
            }
            new
        }))
    }

    pub(crate) fn rs_len(&self, rel: &Bound<'_, PyAny>, k: usize) -> usize {
        self.rels.borrow().iter().find(|r| r.rel.is(rel)).map_or(0, |r| r.s[k].len())
    }

    /// The set's objects in insertion order (views' iteration, the test-only snapshot).
    pub(crate) fn rs_items<'py>(&self, p: Python<'py>, rel: &Bound<'py, PyAny>, k: usize) -> Vec<Bound<'py, PyAny>> {
        let keys = self.relkeys.borrow();
        self.rels.borrow().iter().find(|r| r.rel.is(rel)).map_or(vec![], |r| {
            r.order[k].iter().map(|&i| keys.objs[i as usize].bind(p).clone()).collect()
        })
    }
}

/// A moved set as Rust sites see it: the core's, or Python's own set on a `Relations` whose session has no core.
pub(crate) enum RSet<'a, 'py> {
    Core(Bound<'py, SessionCore>, &'a Bound<'py, PyAny>, usize),
    Py(Bound<'py, PyAny>),
}

impl<'a, 'py> RSet<'a, 'py> {
    pub(crate) fn of(rel: &'a Bound<'py, PyAny>, k: usize) -> PyResult<Self> {
        let p = rel.py();
        match session::core_of(&rel.getattr(intern!(p, "session"))?) {
            Ok(c) => Ok(RSet::Core(c, rel, k)),
            Err(_) => Ok(RSet::Py(rel.getattr(RS_NAMES[k])?)),
        }
    }

    pub(crate) fn contains(&self, x: &Bound<'py, PyAny>) -> PyResult<bool> {
        match self {
            RSet::Core(c, rel, k) => c.borrow().rs_contains(rel, *k, x),
            RSet::Py(s) => s.contains(x),
        }
    }

    pub(crate) fn add(&self, x: &Bound<'py, PyAny>) -> PyResult<()> {
        match self {
            RSet::Core(c, rel, k) => c.borrow().rs_add(rel, *k, x).map(|_| ()),
            RSet::Py(s) => s.call_method1(intern!(s.py(), "add"), (x,)).map(|_| ()),
        }
    }
}

/// The read-only view Python reads a moved set through (session_live installs it as `Relations.<name>`). `add` and `update`
/// are the record methods, for Python's own `Relations` methods (SLICE_REL=py over a core) and tests that seed a set.
#[pyclass(unsendable, frozen)]
pub struct RelSetView {
    core: Py<SessionCore>,
    rel: Py<PyAny>,
    k: usize,
}

#[pymethods]
impl RelSetView {
    fn __contains__(&self, py: Python<'_>, x: &Bound<'_, PyAny>) -> PyResult<bool> {
        tick(session::RS_VIEW);
        self.core.borrow(py).rs_contains(self.rel.bind(py), self.k, x)
    }

    fn __len__(&self, py: Python<'_>) -> usize {
        tick(session::RS_VIEW);
        self.core.borrow(py).rs_len(self.rel.bind(py), self.k)
    }

    fn __bool__(&self, py: Python<'_>) -> bool {
        self.__len__(py) > 0
    }

    fn __iter__<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        tick(session::RS_VIEW);
        let items = self.core.borrow(py).rs_items(py, self.rel.bind(py), self.k);
        PyList::new(py, items)?.into_any().try_iter().map(|i| i.into_any())
    }

    fn add(&self, py: Python<'_>, x: &Bound<'_, PyAny>) -> PyResult<()> {
        tick(session::RS_RECORD);
        self.core.borrow(py).rs_add(self.rel.bind(py), self.k, x).map(|_| ())
    }

    fn update(&self, py: Python<'_>, xs: &Bound<'_, PyAny>) -> PyResult<()> {
        for x in xs.try_iter()? {
            self.add(py, &x?)?;
        }
        Ok(())
    }

    /// A Python set of the members, for a test that compares.
    fn copy<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PySet>> {
        PySet::new(py, self.core.borrow(py).rs_items(py, self.rel.bind(py), self.k))
    }

    fn __repr__(&self, py: Python<'_>) -> PyResult<String> {
        Ok(format!("RelSetView({}, {})", RS_NAMES[self.k], self.copy(py)?.repr()?))
    }
}

pub(crate) fn rs_view(core: &Bound<'_, SessionCore>, rel: &Bound<'_, PyAny>, k: usize) -> RelSetView {
    RelSetView { core: core.clone().unbind(), rel: rel.clone().unbind(), k }
}


// ---- the dicts (RD_NAMES): IndexMap<u32, V> semantics in `OrdMap`, V a Python object (the values stay as they are) ----

/// Where an interned key of each dict came from (the ruling's split).
const RD_ORIGIN: [usize; 15] = [
    session::RK_INTERN_ENGINE, // adapters: spec names
    session::RK_INTERN_INPUT,  // status: atoms
    session::RK_INTERN_ENGINE, // _guards: (adapter, terms) the engine builds
    session::RK_INTERN_ENGINE, // _link_lt: the link atoms the engine builds
    session::RK_INTERN_INPUT,  // top: vocabulary-atom arguments of user formulas
    session::RK_INTERN_INPUT,  // link_sel: linked terms
    session::RK_INTERN_INPUT,  // atom_sel: atoms
    session::RK_INTERN_INPUT,  // num_sel: number nodes
    session::RK_INTERN_INPUT,  // _roles: atoms
    session::RK_INTERN_INPUT,  // _info: atoms
    session::RK_INTERN_ENGINE, // _link_of: the link atoms
    session::RK_INTERN_INPUT,  // _tv: terms
    session::RK_INTERN_ENGINE, // _tsrc: transfer sources
    session::RK_INTERN_INPUT,  // _xside: sides
    session::RK_INTERN_ENGINE, // _xheads: (func, nargs)
];

/// The plants, one per moved dict: `rd-<name>-drop` makes the dict's set a no-op on Rust (the view's too), 390-404.
pub(crate) const RD_PLANT0: u16 = 390;

/// An insertion-ordered map with Python dict order: setting a present key keeps its place; a deleted key set again goes last.
#[derive(Default)]
pub(crate) struct OrdMap {
    idx: std::collections::HashMap<u32, usize>,
    ent: Vec<Option<(u32, Py<PyAny>)>>,
}

impl OrdMap {
    pub(crate) fn get(&self, k: u32) -> Option<&Py<PyAny>> {
        self.idx.get(&k).and_then(|&i| self.ent[i].as_ref().map(|e| &e.1))
    }
    pub(crate) fn insert(&mut self, k: u32, v: Py<PyAny>) {
        match self.idx.get(&k) {
            Some(&i) => self.ent[i] = Some((k, v)),
            None => {
                self.idx.insert(k, self.ent.len());
                self.ent.push(Some((k, v)));
            }
        }
    }
    pub(crate) fn remove(&mut self, k: u32) -> Option<Py<PyAny>> {
        let i = self.idx.remove(&k)?;
        let v = self.ent[i].take().map(|e| e.1);
        if self.idx.is_empty() {
            self.ent.clear();
        }
        v
    }
    pub(crate) fn len(&self) -> usize {
        self.idx.len()
    }
    pub(crate) fn clear(&mut self) {
        self.idx.clear();
        self.ent.clear();
    }
    pub(crate) fn iter(&self) -> impl Iterator<Item = (u32, &Py<PyAny>)> {
        self.ent.iter().flatten().map(|(k, v)| (*k, v))
    }
    pub(crate) fn values(&self) -> impl Iterator<Item = &Py<PyAny>> {
        self.iter().map(|e| e.1)
    }
}

impl SessionCore {
    fn rd_with<T>(&self, rel: &Bound<'_, PyAny>, k: usize, f: impl FnOnce(&OrdMap) -> T) -> Option<T> {
        self.rels.borrow().iter().find(|r| r.rel.is(rel)).map(|r| f(&r.d[k]))
    }

    pub(crate) fn rd_get<'py>(&self, rel: &Bound<'py, PyAny>, k: usize, x: &Bound<'py, PyAny>) -> PyResult<Option<Bound<'py, PyAny>>> {
        tick(session::RD_CORE);
        let p = rel.py();
        Ok(match rk_key(self, x, None)? {
            Some(key) => self.rd_with(rel, k, |m| m.get(key).map(|v| v.bind(p).clone())).flatten(),
            None => None,
        })
    }

    pub(crate) fn rd_set(&self, rel: &Bound<'_, PyAny>, k: usize, x: &Bound<'_, PyAny>, v: &Bound<'_, PyAny>) -> PyResult<()> {
        tick(session::RD_CORE);
        let key = rk_key(self, x, Some(RD_ORIGIN[k]))?.expect("interned");
        if planted(RD_PLANT0 + k as u16) {
            return Ok(());
        }
        with_rel(self, rel, |r| r.d[k].insert(key, v.clone().unbind()));
        Ok(())
    }

    pub(crate) fn rd_del(&self, rel: &Bound<'_, PyAny>, k: usize, x: &Bound<'_, PyAny>) -> PyResult<Option<Py<PyAny>>> {
        tick(session::RD_CORE);
        Ok(match rk_key(self, x, None)? {
            Some(key) => with_rel(self, rel, |r| r.d[k].remove(key)),
            None => None,
        })
    }

    pub(crate) fn rd_len(&self, rel: &Bound<'_, PyAny>, k: usize) -> usize {
        self.rd_with(rel, k, |m| m.len()).unwrap_or(0)
    }

    pub(crate) fn rd_clear(&self, rel: &Bound<'_, PyAny>, k: usize) {
        tick(session::RD_CORE);
        with_rel(self, rel, |r| r.d[k].clear());
    }

    /// The dict's (key object, value) pairs in insertion order.
    pub(crate) fn rd_items<'py>(&self, p: Python<'py>, rel: &Bound<'py, PyAny>, k: usize) -> Vec<(Bound<'py, PyAny>, Bound<'py, PyAny>)> {
        let keys = self.relkeys.borrow();
        self.rd_with(rel, k, |m| m.iter().map(|(i, v)| (keys.objs[i as usize].bind(p).clone(), v.bind(p).clone())).collect())
            .unwrap_or_default()
    }
}

fn obj<'py, K: IntoPyObject<'py>>(p: Python<'py>, x: K) -> PyResult<Bound<'py, PyAny>> {
    x.into_pyobject(p).map(|b| b.into_any().into_bound()).map_err(Into::into)
}

/// A moved dict as Rust sites see it: the core's, or Python's own dict on a `Relations` whose session has no core.
pub(crate) enum RDict<'a, 'py> {
    Core(Bound<'py, SessionCore>, &'a Bound<'py, PyAny>, usize),
    Py(Bound<'py, PyDict>),
}

impl<'a, 'py> RDict<'a, 'py> {
    pub(crate) fn of(rel: &'a Bound<'py, PyAny>, k: usize) -> PyResult<Self> {
        let p = rel.py();
        match session::core_of(&rel.getattr(intern!(p, "session"))?) {
            Ok(c) => Ok(RDict::Core(c, rel, k)),
            Err(_) => Ok(RDict::Py(rel.getattr(RD_NAMES[k])?.cast_into::<PyDict>()?)),
        }
    }

    pub(crate) fn get_item<K: IntoPyObject<'py>>(&self, x: K) -> PyResult<Option<Bound<'py, PyAny>>> {
        let x = &obj(self.py(), x)?;
        match self {
            RDict::Core(c, rel, k) => c.borrow().rd_get(rel, *k, x),
            RDict::Py(d) => d.get_item(x),
        }
    }

    /// `d[x]`, a KeyError when absent.
    fn py(&self) -> Python<'py> {
        match self {
            RDict::Core(c, _, _) => c.py(),
            RDict::Py(d) => d.py(),
        }
    }

    pub(crate) fn item(&self, x: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        self.get_item(x)?.ok_or_else(|| pyo3::exceptions::PyKeyError::new_err(x.clone().unbind()))
    }

    pub(crate) fn set_item<K: IntoPyObject<'py>, V: IntoPyObject<'py>>(&self, x: K, v: V) -> PyResult<()> {
        let (x, v) = (&obj(self.py(), x)?, &obj(self.py(), v)?);
        match self {
            RDict::Core(c, rel, k) => c.borrow().rd_set(rel, *k, x, v),
            RDict::Py(d) => d.set_item(x, v),
        }
    }

    pub(crate) fn contains<K: IntoPyObject<'py>>(&self, x: K) -> PyResult<bool> {
        Ok(self.get_item(x)?.is_some())
    }

    pub(crate) fn is_truthy(&self) -> PyResult<bool> {
        Ok(self.len()? > 0)
    }

    /// Python's `d.get(x)`: the value or None.
    pub(crate) fn get<K: IntoPyObject<'py>>(&self, x: K) -> PyResult<Bound<'py, PyAny>> {
        let p = self.py();
        Ok(self.get_item(x)?.unwrap_or_else(|| p.None().into_bound(p)))
    }

    pub(crate) fn len(&self) -> PyResult<usize> {
        Ok(match self {
            RDict::Core(c, rel, k) => c.borrow().rd_len(rel, *k),
            RDict::Py(d) => d.len(),
        })
    }

    pub(crate) fn clear(&self) {
        match self {
            RDict::Core(c, rel, k) => c.borrow().rd_clear(rel, *k),
            RDict::Py(d) => d.clear(),
        }
    }

    pub(crate) fn items(&self) -> PyResult<Vec<(Bound<'py, PyAny>, Bound<'py, PyAny>)>> {
        match self {
            RDict::Core(c, rel, k) => Ok(c.borrow().rd_items(rel.py(), rel, *k)),
            RDict::Py(d) => Ok(d.iter().collect()),
        }
    }

    pub(crate) fn values(&self) -> PyResult<Vec<Bound<'py, PyAny>>> {
        Ok(self.items()?.into_iter().map(|e| e.1).collect())
    }
}

/// The view Python reads a moved dict through (session_live installs it as `Relations.<name>`). Its writes are the record
/// methods, for Python's own `Relations` methods (SLICE_REL=py over a core) and tests that seed a dict.
#[pyclass(unsendable, frozen)]
pub struct RelDictView {
    core: Py<SessionCore>,
    rel: Py<PyAny>,
    k: usize,
}

impl RelDictView {
    fn items_of<'py>(&self, py: Python<'py>) -> Vec<(Bound<'py, PyAny>, Bound<'py, PyAny>)> {
        self.core.borrow(py).rd_items(py, self.rel.bind(py), self.k)
    }
}

#[pymethods]
impl RelDictView {
    fn __contains__(&self, py: Python<'_>, x: &Bound<'_, PyAny>) -> PyResult<bool> {
        tick(session::RD_VIEW);
        Ok(self.core.borrow(py).rd_get(self.rel.bind(py), self.k, x)?.is_some())
    }

    fn __getitem__<'py>(&self, py: Python<'py>, x: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        tick(session::RD_VIEW);
        self.core.borrow(py).rd_get(self.rel.bind(py), self.k, x)?
            .ok_or_else(|| pyo3::exceptions::PyKeyError::new_err(x.clone().unbind()))
    }

    #[pyo3(signature = (x, default=None))]
    fn get<'py>(&self, py: Python<'py>, x: &Bound<'py, PyAny>, default: Option<Bound<'py, PyAny>>) -> PyResult<Bound<'py, PyAny>> {
        tick(session::RD_VIEW);
        Ok(match self.core.borrow(py).rd_get(self.rel.bind(py), self.k, x)? {
            Some(v) => v,
            None => default.unwrap_or_else(|| py.None().into_bound(py)),
        })
    }

    fn __setitem__(&self, py: Python<'_>, x: &Bound<'_, PyAny>, v: &Bound<'_, PyAny>) -> PyResult<()> {
        tick(session::RD_RECORD);
        self.core.borrow(py).rd_set(self.rel.bind(py), self.k, x, v)
    }

    #[pyo3(signature = (x, default=None))]
    fn setdefault<'py>(&self, py: Python<'py>, x: &Bound<'py, PyAny>, default: Option<Bound<'py, PyAny>>) -> PyResult<Bound<'py, PyAny>> {
        if let Some(v) = self.core.borrow(py).rd_get(self.rel.bind(py), self.k, x)? {
            tick(session::RD_VIEW);
            return Ok(v);
        }
        let v = default.unwrap_or_else(|| py.None().into_bound(py));
        self.__setitem__(py, x, &v)?;
        Ok(v)
    }

    fn __delitem__(&self, py: Python<'_>, x: &Bound<'_, PyAny>) -> PyResult<()> {
        tick(session::RD_RECORD);
        match self.core.borrow(py).rd_del(self.rel.bind(py), self.k, x)? {
            Some(_) => Ok(()),
            None => Err(pyo3::exceptions::PyKeyError::new_err(x.clone().unbind())),
        }
    }

    #[pyo3(signature = (x, *default))]
    fn pop<'py>(&self, py: Python<'py>, x: &Bound<'py, PyAny>, default: &Bound<'py, pyo3::types::PyTuple>) -> PyResult<Bound<'py, PyAny>> {
        tick(session::RD_RECORD);
        match self.core.borrow(py).rd_del(self.rel.bind(py), self.k, x)? {
            Some(v) => Ok(v.into_bound(py)),
            None if !default.is_empty() => default.get_item(0),
            None => Err(pyo3::exceptions::PyKeyError::new_err(x.clone().unbind())),
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
        tick(session::RD_RECORD);
        self.core.borrow(py).rd_clear(self.rel.bind(py), self.k);
    }

    fn __len__(&self, py: Python<'_>) -> usize {
        tick(session::RD_VIEW);
        self.core.borrow(py).rd_len(self.rel.bind(py), self.k)
    }

    fn __bool__(&self, py: Python<'_>) -> bool {
        self.__len__(py) > 0
    }

    fn keys<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        tick(session::RD_VIEW);
        PyList::new(py, self.items_of(py).into_iter().map(|e| e.0))
    }

    fn values<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        tick(session::RD_VIEW);
        PyList::new(py, self.items_of(py).into_iter().map(|e| e.1))
    }

    fn items<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        tick(session::RD_VIEW);
        let v: Vec<Bound<'py, pyo3::types::PyTuple>> = self.items_of(py).into_iter()
            .map(|(a, b)| pyo3::types::PyTuple::new(py, [a, b])).collect::<PyResult<_>>()?;
        PyList::new(py, v)
    }

    fn __iter__<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        self.keys(py)?.into_any().try_iter().map(|i| i.into_any())
    }

    /// A Python dict of the items, for a test that compares.
    fn copy<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let d = PyDict::new(py);
        for (a, b) in self.items_of(py) {
            d.set_item(a, b)?;
        }
        Ok(d)
    }

    fn __eq__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<bool> {
        self.copy(py)?.eq(other)
    }

    fn __repr__(&self, py: Python<'_>) -> PyResult<String> {
        Ok(format!("RelDictView({}, {})", RD_NAMES[self.k], self.copy(py)?.repr()?))
    }
}

pub(crate) fn rd_view(core: &Bound<'_, SessionCore>, rel: &Bound<'_, PyAny>, k: usize) -> RelDictView {
    RelDictView { core: core.clone().unbind(), rel: rel.clone().unbind(), k }
}

// ---- the lists (RL_NAMES): `Vec<Py<PyAny>>`, the items stay Python objects (atoms, terms, `(node, base)` pairs) ----

/// The plants, one per moved list: `rl-<name>-drop` makes the list's push a no-op on Rust (the view's too), 405-408.
pub(crate) const RL_PLANT0: u16 = 405;

impl SessionCore {
    fn rl_with<T>(&self, rel: &Bound<'_, PyAny>, k: usize, f: impl FnOnce(&Vec<Py<PyAny>>) -> T) -> Option<T> {
        self.rels.borrow().iter().find(|r| r.rel.is(rel)).map(|r| f(&r.l[k]))
    }

    pub(crate) fn rl_push(&self, rel: &Bound<'_, PyAny>, k: usize, x: &Bound<'_, PyAny>) {
        tick(session::RL_CORE);
        if planted(RL_PLANT0 + k as u16) {
            return;
        }
        with_rel(self, rel, |r| r.l[k].push(x.clone().unbind()));
    }

    pub(crate) fn rl_pop<'py>(&self, rel: &Bound<'py, PyAny>, k: usize) -> Option<Bound<'py, PyAny>> {
        tick(session::RL_CORE);
        let p = rel.py();
        with_rel(self, rel, |r| r.l[k].pop()).map(|v| v.into_bound(p))
    }

    pub(crate) fn rl_len(&self, rel: &Bound<'_, PyAny>, k: usize) -> usize {
        self.rl_with(rel, k, |v| v.len()).unwrap_or(0)
    }

    pub(crate) fn rl_clear(&self, rel: &Bound<'_, PyAny>, k: usize) {
        tick(session::RL_CORE);
        with_rel(self, rel, |r| r.l[k].clear());
    }

    /// The items, in order.
    pub(crate) fn rl_items<'py>(&self, p: Python<'py>, rel: &Bound<'py, PyAny>, k: usize) -> Vec<Bound<'py, PyAny>> {
        self.rl_with(rel, k, |v| v.iter().map(|x| x.bind(p).clone()).collect()).unwrap_or_default()
    }

    /// `xs[:] = items` (a whole replacement, no plant: it is not a push).
    pub(crate) fn rl_replace(&self, rel: &Bound<'_, PyAny>, k: usize, items: Vec<Bound<'_, PyAny>>) {
        tick(session::RL_CORE);
        with_rel(self, rel, |r| r.l[k] = items.into_iter().map(|x| x.unbind()).collect());
    }
}

/// A moved list as Rust sites see it: the core's, or Python's own list on a `Relations` whose session has no core.
pub(crate) enum RList<'a, 'py> {
    Core(Bound<'py, SessionCore>, &'a Bound<'py, PyAny>, usize),
    Py(Bound<'py, PyList>),
}

impl<'a, 'py> RList<'a, 'py> {
    pub(crate) fn of(rel: &'a Bound<'py, PyAny>, k: usize) -> PyResult<Self> {
        let p = rel.py();
        match session::core_of(&rel.getattr(intern!(p, "session"))?) {
            Ok(c) => Ok(RList::Core(c, rel, k)),
            Err(_) => Ok(RList::Py(rel.getattr(RL_NAMES[k])?.cast_into::<PyList>()?)),
        }
    }

    pub(crate) fn push(&self, x: &Bound<'py, PyAny>) -> PyResult<()> {
        match self {
            RList::Core(c, rel, k) => {
                c.borrow().rl_push(rel, *k, x);
                Ok(())
            }
            RList::Py(l) => l.append(x),
        }
    }

    /// `xs.pop()`, None when empty (callers test truth first, as Python's do).
    pub(crate) fn pop(&self) -> PyResult<Option<Bound<'py, PyAny>>> {
        match self {
            RList::Core(c, rel, k) => Ok(c.borrow().rl_pop(rel, *k)),
            RList::Py(l) => if l.is_empty() { Ok(None) } else { l.call_method0(intern!(l.py(), "pop")).map(Some) },
        }
    }

    pub(crate) fn len(&self) -> usize {
        match self {
            RList::Core(c, rel, k) => c.borrow().rl_len(rel, *k),
            RList::Py(l) => l.len(),
        }
    }

    pub(crate) fn is_truthy(&self) -> bool {
        self.len() > 0
    }

    pub(crate) fn items(&self) -> Vec<Bound<'py, PyAny>> {
        match self {
            RList::Core(c, rel, k) => c.borrow().rl_items(rel.py(), rel, *k),
            RList::Py(l) => l.iter().collect(),
        }
    }

    pub(crate) fn clear(&self) -> PyResult<()> {
        match self {
            RList::Core(c, rel, k) => {
                c.borrow().rl_clear(rel, *k);
                Ok(())
            }
            RList::Py(l) => l.call_method0(intern!(l.py(), "clear")).map(|_| ()),
        }
    }

    /// `xs[:] = items`.
    pub(crate) fn replace(&self, items: Vec<Bound<'py, PyAny>>) -> PyResult<()> {
        match self {
            RList::Core(c, rel, k) => {
                c.borrow().rl_replace(rel, *k, items);
                Ok(())
            }
            RList::Py(l) => l.set_slice(0, l.len(), PyList::new(l.py(), items)?.as_any()),
        }
    }
}

/// The view Python reads a moved list through (session_live installs it as `Relations.<name>`). Its writes are the record
/// methods, for Python's own `Relations` methods (SLICE_REL=py over a core) and tests that seed a list.
#[pyclass(unsendable, frozen)]
pub struct RelListView {
    core: Py<SessionCore>,
    rel: Py<PyAny>,
    k: usize,
}

impl RelListView {
    fn items_of<'py>(&self, py: Python<'py>) -> Vec<Bound<'py, PyAny>> {
        self.core.borrow(py).rl_items(py, self.rel.bind(py), self.k)
    }
}

#[pymethods]
impl RelListView {
    fn append(&self, py: Python<'_>, x: &Bound<'_, PyAny>) {
        tick(session::RL_RECORD);
        self.core.borrow(py).rl_push(self.rel.bind(py), self.k, x);
    }

    fn extend(&self, py: Python<'_>, xs: &Bound<'_, PyAny>) -> PyResult<()> {
        let v: Vec<Bound<'_, PyAny>> = xs.try_iter()?.collect::<PyResult<_>>()?;
        for x in v {
            self.append(py, &x);
        }
        Ok(())
    }

    /// `xs.pop()`: the last item only (the only form `Relations` uses).
    fn pop<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        tick(session::RL_RECORD);
        self.core.borrow(py).rl_pop(self.rel.bind(py), self.k)
            .ok_or_else(|| pyo3::exceptions::PyIndexError::new_err("pop from empty list"))
    }

    fn clear(&self, py: Python<'_>) {
        tick(session::RL_RECORD);
        self.core.borrow(py).rl_clear(self.rel.bind(py), self.k);
    }

    /// `xs[:] = items`: only the whole slice (the only form `Relations` uses).
    fn __setitem__(&self, py: Python<'_>, i: &Bound<'_, PyAny>, items: &Bound<'_, PyAny>) -> PyResult<()> {
        let whole = i.cast::<pyo3::types::PySlice>().ok()
            .map(|s| s.getattr("start").ok().is_some_and(|x| x.is_none()) && s.getattr("stop").ok().is_some_and(|x| x.is_none())
                && s.getattr("step").ok().is_some_and(|x| x.is_none()))
            .unwrap_or(false);
        if !whole {
            return Err(pyo3::exceptions::PyTypeError::new_err("RelListView: only xs[:] = items"));
        }
        tick(session::RL_RECORD);
        let v: Vec<Bound<'_, PyAny>> = items.try_iter()?.collect::<PyResult<_>>()?;
        self.core.borrow(py).rl_replace(self.rel.bind(py), self.k, v);
        Ok(())
    }

    fn __getitem__<'py>(&self, py: Python<'py>, i: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        tick(session::RL_VIEW);
        PyList::new(py, self.items_of(py))?.as_any().get_item(i)
    }

    fn __len__(&self, py: Python<'_>) -> usize {
        tick(session::RL_VIEW);
        self.core.borrow(py).rl_len(self.rel.bind(py), self.k)
    }

    fn __bool__(&self, py: Python<'_>) -> bool {
        self.__len__(py) > 0
    }

    /// Over a copy of the items, taken when iteration starts.
    fn __iter__<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        tick(session::RL_VIEW);
        PyList::new(py, self.items_of(py))?.into_any().try_iter().map(|i| i.into_any())
    }

    /// A Python list of the items, for a test that compares.
    fn copy<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        PyList::new(py, self.items_of(py))
    }

    fn __eq__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<bool> {
        self.copy(py)?.eq(other)
    }

    fn __repr__(&self, py: Python<'_>) -> PyResult<String> {
        Ok(format!("RelListView({}, {})", RL_NAMES[self.k], self.copy(py)?.repr()?))
    }
}

pub(crate) fn rl_view(core: &Bound<'_, SessionCore>, rel: &Bound<'_, PyAny>, k: usize) -> RelListView {
    RelListView { core: core.clone().unbind(), rel: rel.clone().unbind(), k }
}
