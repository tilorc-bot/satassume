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
use pyo3::types::{PyDict, PyList, PySet, PyType};

use crate::relations_core::{hooks, installed, planted, term_of};
use crate::session::{self, tick, RelKeys, RelS, SessionCore, RS_NAMES};

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
            v.push(RelS { rel: rel.clone().unbind(), s: Default::default(), order: Default::default() });
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
