//! `EUFTheory` for Python: `euf.rs` behind `satassume.theories.euf.euf.EUFTheory`'s public surface, for `euf_adapter`
//! and `transfer`, which stay Python for now, and the solver's hooks.
//!
//! Nothing is borrowed while Python runs. Hashing a head, the `on_merge` listener and a repr can all be SymPy or a
//! test's Python, and the listener reads `rep`, `members` and `explain` from inside a merge, so every borrow of the
//! core below ends before any call out. That is why the class is frozen with a `RefCell`, not `&mut self`.
//!
//! `Handles` is the whole of the term interface: Python's dict decides what is one head, by the objects' own `__hash__`
//! and `__eq__`, exactly as `_keys` does. It's per object, and only looked up.
use crate::euf::{Asserted, Euf, Handle, Key, Label, Op, PopError, Term};
use pyo3::exceptions::{PyIndexError, PyKeyError, PyOverflowError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyInt, PyList, PySlice, PyTuple};
use pyo3::{PyTraverseError, PyVisit};
use std::cell::RefCell;

/// Python's `_keys` key to handle, first seen first. The key is the same tuple `_keys` uses, so what is one head is
/// decided per namespace and arity, as there: `1` as a constant and `1.0` as a value are two keys, each keeping its own
/// object. Component 0's term table replaces this.
struct Handles(Py<PyDict>);

impl Handles {
    fn get(&self, p: Python<'_>, key: Bound<'_, PyTuple>) -> PyResult<Handle> {
        let d = self.0.bind(p);
        if let Some(h) = d.get_item(&key)? {
            return Ok(Handle(h.extract()?));
        }
        let h = d.len() as u32;
        d.set_item(key, h)?;
        Ok(Handle(h))
    }

    fn constant(&self, p: Python<'_>, o: &Bound<'_, PyAny>) -> PyResult<Handle> {
        self.get(p, PyTuple::new(p, [pyo3::intern!(p, "c").as_any(), o])?)
    }

    fn value(&self, p: Python<'_>, o: &Bound<'_, PyAny>) -> PyResult<Handle> {
        self.get(p, PyTuple::new(p, [pyo3::intern!(p, "v").as_any(), o])?)
    }

    fn head(&self, p: Python<'_>, o: &Bound<'_, PyAny>, n: usize) -> PyResult<Handle> {
        self.get(p, PyTuple::new(p, [pyo3::intern!(p, "h").as_any(), o, n.into_pyobject(p)?.as_any()])?)
    }
}

/// `term`'s `args`: left out, or whatever was passed. `None` is passed, not left out, and raises as `tuple(None)` does.
enum Args<'py> {
    Absent,
    Given(Bound<'py, PyAny>),
}

impl<'a, 'py> FromPyObject<'a, 'py> for Args<'py> {
    type Error = PyErr;
    fn extract(o: pyo3::Borrowed<'a, 'py, PyAny>) -> PyResult<Self> {
        Ok(Args::Given(o.to_owned()))
    }
}

fn lit_of(x: &Bound<'_, PyAny>) -> PyResult<i32> {
    i32::try_from(x.extract::<i64>()?).map_err(|_| PyOverflowError::new_err("literal out of range"))
}

/// A list index, as `self.rep[t]` reads one.
fn index(i: isize, n: usize) -> PyResult<usize> {
    let j = if i < 0 { i + n as isize } else { i };
    if j < 0 || j as usize >= n {
        return Err(PyIndexError::new_err("list index out of range"));
    }
    Ok(j as usize)
}

#[pyclass(name = "EUFTheory", module = "sa_solver", unsendable, subclass, dict, weakref, frozen)]
pub struct PyEuf {
    core: RefCell<Euf>,
    handles: Handles,
    on_merge: RefCell<Option<Py<PyAny>>>,
    /// `satassume.theories.euf.euf.EqAtom`: `euf_adapter` stays Python and builds the payload.
    eq_atom: Py<PyAny>,
}

impl PyEuf {
    fn a_term(&self, a: &Bound<'_, PyAny>) -> Option<Term> {
        if !a.is_instance_of::<PyInt>() {
            return None;
        }
        let n = self.core.borrow().len() as i64;
        match a.extract::<i64>() {
            Ok(i) if 0 <= i && i < n => Some(i as Term),
            _ => None,
        }
    }

    /// `_process`. `i` is local here as it is there, so a listener that re-enters behaves the same.
    fn process(&self, p: Python<'_>) -> PyResult<()> {
        let mut i = 0;
        loop {
            let merged = {
                let mut c = self.core.borrow_mut();
                if !(i < c.pending.len() && c.conflict.is_none()) {
                    c.pending.clear();
                    return Ok(());
                }
                let (a, b, label) = c.pending[i];
                i += 1;
                c.union(a, b, label)
            };
            if let Some((ra, rb)) = merged {
                let listener = self.on_merge.borrow().as_ref().map(|f| f.clone_ref(p));
                if let Some(f) = listener {
                    f.bind(p).call1((ra, rb))?;
                }
            }
        }
    }

    fn conflict_obj<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        match &self.core.borrow().conflict {
            None => Ok(p.None().into_bound(p)),
            Some(c) => Ok((false, PyList::new(p, c)?).into_pyobject(p)?.into_any()),
        }
    }
}

#[pymethods]
impl PyEuf {
    #[new]
    fn new(p: Python<'_>) -> PyResult<PyEuf> {
        Ok(PyEuf {
            core: RefCell::new(Euf::new()),
            handles: Handles(PyDict::new(p).unbind()),
            on_merge: RefCell::new(None),
            eq_atom: p.import("satassume.theories.euf.euf")?.getattr("EqAtom")?.unbind(),
        })
    }

    fn __traverse__(&self, visit: PyVisit<'_>) -> Result<(), PyTraverseError> {
        visit.call(&self.handles.0)?;
        visit.call(&self.eq_atom)?;
        if let Ok(f) = self.on_merge.try_borrow() {
            if let Some(f) = f.as_ref() {
                visit.call(f)?;
            }
        }
        Ok(())
    }

    fn __clear__(&self) {
        let f = self.on_merge.borrow_mut().take();
        drop(f);
    }

    /// `on_merge(retired_rep, new_rep)` after each union, or None.
    #[getter]
    fn get_on_merge(&self, p: Python<'_>) -> Option<Py<PyAny>> {
        self.on_merge.borrow().as_ref().map(|f| f.clone_ref(p))
    }

    #[setter]
    fn set_on_merge(&self, f: Option<Py<PyAny>>) {
        let old = std::mem::replace(&mut *self.on_merge.borrow_mut(), f);
        drop(old);
    }

    /// term -> its class representative. A live, read-only view.
    #[getter]
    fn rep(slf: Py<Self>) -> RepView {
        RepView { th: slf }
    }

    /// representative -> the members of its class. A live, read-only view; each item is a new list, in Python's order.
    #[getter]
    fn members(slf: Py<Self>) -> MembersView {
        MembersView { th: slf }
    }

    #[pyo3(signature = (head, args=Args::Absent))]
    fn term<'py>(&self, p: Python<'py>, head: &Bound<'py, PyAny>, args: Args<'py>) -> PyResult<Term> {
        let args: Vec<Bound<'_, PyAny>> = match args {
            Args::Absent => Vec::new(),
            Args::Given(a) => a.try_iter()?.collect::<PyResult<_>>()?,
        };
        if args.is_empty() {
            let h = self.handles.constant(p, head)?;
            return Ok(self.core.borrow_mut().constant(h));
        }
        let mut ids = Vec::with_capacity(args.len());
        for a in &args {
            match self.a_term(a) {
                Some(t) => ids.push(t),
                None => return Err(PyValueError::new_err(format!("not a term id: {}", a.repr()?))),
            }
        }
        let h = self.handles.head(p, head, ids.len())?;
        let mut t = self.core.borrow_mut().head(h, ids.len() as u32);
        for a in ids {
            let (nt, new) = self.core.borrow_mut().apply(t, a);
            t = nt;
            if new {
                self.process(p)?;
            }
        }
        Ok(t)
    }

    fn value(&self, p: Python<'_>, key: &Bound<'_, PyAny>) -> PyResult<Term> {
        let h = self.handles.value(p, key)?;
        Ok(self.core.borrow_mut().value(h))
    }

    fn find(&self, t: isize) -> PyResult<Term> {
        let c = self.core.borrow();
        Ok(c.rep[index(t, c.len())?])
    }

    fn equal(&self, a: isize, b: isize) -> PyResult<bool> {
        let c = self.core.borrow();
        Ok(c.rep[index(a, c.len())?] == c.rep[index(b, c.len())?])
    }

    fn explain(&self, a: isize, b: isize) -> PyResult<Vec<i32>> {
        let c = self.core.borrow();
        let (a, b) = (index(a, c.len())?, index(b, c.len())?);
        if c.rep[a] != c.rep[b] {
            return Err(PyValueError::new_err("explain: terms are not equal"));
        }
        Ok(c.explain(a as Term, b as Term))
    }

    fn register_atom(&self, literal: &Bound<'_, PyAny>, payload: &Bound<'_, PyAny>) -> PyResult<()> {
        let v = lit_of(literal)?;
        if v <= 0 || self.core.borrow().atoms.contains_key(&v) {
            return Err(PyValueError::new_err(format!("bad or repeated atom variable {v}")));
        }
        let parts: Vec<Bound<'_, PyAny>> = payload.try_iter()?.collect::<PyResult<_>>()?;
        let (s, t, pos) = if payload.is_instance(self.eq_atom.bind(payload.py()))? {
            (&parts[0], &parts[1], parts[2].is_truthy()?)
        } else {
            match parts.len() {
                2 => (&parts[0], &parts[1], true),
                n if n < 2 => {
                    return Err(PyValueError::new_err(format!("not enough values to unpack (expected 2, got {n})")))
                }
                _ => return Err(PyValueError::new_err("too many values to unpack (expected 2)")),
            }
        };
        match (self.a_term(s), self.a_term(t)) {
            (Some(s), Some(t)) => {
                self.core.borrow_mut().register_atom(v, s, t, pos);
                Ok(())
            }
            _ => Err(PyValueError::new_err(format!("EUF atom over unknown terms: {}", payload.repr()?))),
        }
    }

    fn assert_lit<'py>(&self, p: Python<'py>, literal: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        let step = self.core.borrow_mut().assert_begin(lit_of(literal)?);
        match step {
            Asserted::NotAtom => Ok(p.None().into_bound(p)),
            Asserted::Done => self.conflict_obj(p),
            Asserted::Merge => {
                self.process(p)?;
                self.conflict_obj(p)
            }
        }
    }

    fn check<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let c = self.core.borrow();
        if let Some(cl) = &c.conflict {
            return Ok((false, PyList::new(p, cl)?).into_pyobject(p)?.into_any());
        }
        let d = PyDict::new(p);
        for (i, r) in c.rep.iter().enumerate() {
            d.set_item(i, *r)?;
        }
        Ok((true, d).into_pyobject(p)?.into_any())
    }

    fn propagate<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        let out = self.core.borrow_mut().propagate();
        let items = out.into_iter().map(|(l, why)| Ok((l, PyList::new(p, why)?).into_pyobject(p)?)).collect::<PyResult<Vec<_>>>()?;
        PyList::new(p, items)
    }

    fn push_level(&self) {
        self.core.borrow_mut().push_level();
    }

    fn pop_level(&self, p: Python<'_>) -> PyResult<()> {
        let begun = self.core.borrow_mut().pop_begin();
        let atoms = begun.map_err(|e| match e {
            PopError::NoLevel => PyIndexError::new_err("pop from empty list"),
            PopError::NoAssign(v) => PyKeyError::new_err(v),
            PopError::NoLookup(x, y) => PyKeyError::new_err((x, y)),
        })?;
        self.process(p)?;
        self.core.borrow_mut().pop_end(atoms);
        Ok(())
    }

    fn __repr__(&self) -> String {
        let c = self.core.borrow();
        format!("<EUFTheory {} terms, {} atoms, level {}>", c.len(), c.atoms.len(), c.lims.len())
    }

    /// The compare tool's state, field -> string, the same as `state.dump_euf_py` on the Python class. `show` turns a
    /// head into text, so the two sides can't differ in how they print one. Reads only.
    fn dump<'py>(&self, p: Python<'py>, show: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyDict>> {
        // Python first, with no borrow held: `show` can be anything
        let shown: Vec<String> =
            self.handles.0.bind(p).keys().iter().map(|k| show.call1((k.get_item(1)?,))?.extract()).collect::<PyResult<_>>()?;
        let c = self.core.borrow();
        let mut keys: Vec<(Term, Key)> = c.keys.iter().map(|(k, t)| (*t, *k)).collect();
        keys.sort_unstable_by_key(|x| x.0);
        let key_text = keys.iter().map(|(t, k)| match k {
            Key::Const(h) => format!("{t}=c:{}", shown[h.0 as usize]),
            Key::Head(h, n) => format!("{t}=h:{}:{n}", shown[h.0 as usize]),
            Key::Value(h) => format!("{t}=v:{}", shown[h.0 as usize]),
            Key::App(f, a) => format!("{t}=a:{f}:{a}"),
        });
        let lab = |l: &Label| match l {
            Label::None => "N".to_string(),
            Label::Lit(x) => x.to_string(),
            Label::Pair(a, b) => format!("{a},{b}"),
        };
        let forest = |t: &Term| if *t == u32::MAX { -1 } else { *t as i64 };
        let d = PyDict::new(p);
        let put = |k: &str, v: String| d.set_item(format!("euf.{k}"), v);
        put("keys", key_text.collect::<Vec<_>>().join(";"))?;
        put("app", join(c.app.iter().map(|a| a.map_or("N".to_string(), |(f, x)| format!("{f},{x}")))))?;
        put("rep", join(c.rep.iter()))?;
        put("members", joins(&c.members))?;
        put("use", joins(&c.uses))?;
        let mut lookup: Vec<_> = c.lookup.iter().map(|(k, t)| (k.0, k.1, *t)).collect();
        lookup.sort_unstable();
        put("lookup", join(lookup.iter().map(|(a, b, t)| format!("{a},{b}:{t}"))))?;
        put("pfp", join(c.pfp.iter().map(forest)))?;
        put("pfl", join(c.pfl.iter().map(lab)))?;
        put("val", join(c.val.iter()))?;
        put("diseq", c.diseq.iter().map(|l| join(l.iter().map(|x| format!("{},{},{}", x.lit, x.s, x.t)))).collect::<Vec<_>>().join(";"))?;
        put("atoms_of", joins(&c.atoms_of))?;
        let mut atoms: Vec<_> = c.atoms.iter().map(|(v, a)| (*v, a.s, a.t, a.pos as i32)).collect();
        atoms.sort_unstable();
        put("atoms", join(atoms.iter().map(|(v, s, t, x)| format!("{v}:{s},{t},{x}"))))?;
        let mut assigned: Vec<_> = c.assigned.iter().map(|(v, l)| (*v, *l)).collect();
        assigned.sort_unstable();
        put("assigned", join(assigned.iter().map(|(v, l)| format!("{v}:{l}"))))?;
        put("pending", join(c.pending.iter().map(|(a, b, l)| format!("{a},{b},{}", lab(l)))))?;
        put("propq", join(c.propq.iter()))?;
        put("conflict", c.conflict.as_ref().map_or("N".to_string(), |x| join(x.iter())))?;
        put("trail", join(c.trail.iter().map(op_text)))?;
        put("lims", join(c.lims.iter()))?;
        Ok(d)
    }
}

fn join<T: std::fmt::Display>(xs: impl Iterator<Item = T>) -> String {
    xs.map(|x| x.to_string()).collect::<Vec<_>>().join(" ")
}

fn joins<T: std::fmt::Display>(xs: &[Vec<T>]) -> String {
    xs.iter().map(|l| join(l.iter())).collect::<Vec<_>>().join(";")
}

fn op_text(o: &Op) -> String {
    match *o {
        Op::Union { ra, rb, a, old_root, nuse, ndiseq, natoms, set_val } => {
            format!("U{ra},{rb},{a},{old_root},{nuse},{ndiseq},{natoms},{}", set_val as i32)
        }
        Op::Lookup(x, y) => format!("L{x},{y}"),
        Op::Assign(v) => format!("A{v}"),
        Op::Diseq { rs, ns, rt, nt } => format!("D{rs},{ns},{rt},{nt}"),
        Op::RegApp(t) => format!("P{t}"),
        Op::RegAtom { v, rs, rt } => format!("T{v},{rs},{rt}"),
        Op::Use(r) => format!("S{r}"),
    }
}

/// `euf.rep`, for `transfer`'s reads until component 3 lands. Live, and each read crosses.
#[pyclass(name = "RepView", module = "sa_solver", unsendable, frozen)]
pub struct RepView {
    th: Py<PyEuf>,
}

impl RepView {
    fn list<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        PyList::new(p, &self.th.bind(p).borrow().core.borrow().rep)
    }
}

#[pymethods]
impl RepView {
    fn __traverse__(&self, visit: PyVisit<'_>) -> Result<(), PyTraverseError> {
        visit.call(&self.th)
    }

    fn __len__(&self, p: Python<'_>) -> usize {
        self.th.bind(p).borrow().core.borrow().rep.len()
    }

    fn __getitem__<'py>(&self, p: Python<'py>, i: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        if i.is_instance_of::<PySlice>() {
            return self.list(p)?.as_any().get_item(i);
        }
        let th = self.th.bind(p).borrow();
        let c = th.core.borrow();
        Ok(c.rep[index(i.extract()?, c.rep.len())?].into_pyobject(p)?.into_any())
    }

    fn __iter__<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        Ok(self.list(p)?.as_any().try_iter()?.into_any())
    }

    fn __eq__(&self, p: Python<'_>, o: &Bound<'_, PyAny>) -> PyResult<bool> {
        self.list(p)?.as_any().eq(o)
    }

    fn __repr__(&self, p: Python<'_>) -> PyResult<String> {
        Ok(self.list(p)?.repr()?.to_string())
    }
}

/// `euf.members`, for `transfer`'s reads until component 3 lands. `transfer` keeps an item only within one hook, in
/// which nothing merges, so a copy reads what Python's alias reads.
#[pyclass(name = "MembersView", module = "sa_solver", unsendable, frozen)]
pub struct MembersView {
    th: Py<PyEuf>,
}

impl MembersView {
    fn list<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        let th = self.th.bind(p).borrow();
        let c = th.core.borrow();
        let items = c.members.iter().map(|m| PyList::new(p, m)).collect::<PyResult<Vec<_>>>()?;
        PyList::new(p, items)
    }
}

#[pymethods]
impl MembersView {
    fn __traverse__(&self, visit: PyVisit<'_>) -> Result<(), PyTraverseError> {
        visit.call(&self.th)
    }

    fn __len__(&self, p: Python<'_>) -> usize {
        self.th.bind(p).borrow().core.borrow().members.len()
    }

    fn __getitem__<'py>(&self, p: Python<'py>, i: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        if i.is_instance_of::<PySlice>() {
            return self.list(p)?.as_any().get_item(i);
        }
        let th = self.th.bind(p).borrow();
        let c = th.core.borrow();
        Ok(PyList::new(p, &c.members[index(i.extract()?, c.members.len())?])?.into_any())
    }

    fn __iter__<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        Ok(self.list(p)?.as_any().try_iter()?.into_any())
    }

    fn __eq__(&self, p: Python<'_>, o: &Bound<'_, PyAny>) -> PyResult<bool> {
        self.list(p)?.as_any().eq(o)
    }

    fn __repr__(&self, p: Python<'_>) -> PyResult<String> {
        Ok(self.list(p)?.repr()?.to_string())
    }
}

/// The solver reaches this class through `lib.rs`'s `PyTheory`, the Python methods, like any other theory for now.
pub fn add_to(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyEuf>()?;
    m.add_class::<RepView>()?;
    m.add_class::<MembersView>()
}
