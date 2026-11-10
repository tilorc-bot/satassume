//! Step "scope" (issue 323): `satassume/scope.py` in Rust. `affine_pair` landed in C1 (63e085d, `PyTermTable.affine_pair`); this
//! file holds the other six port rows: the `Scope` type (`ScopeRs`, a 3-tuple's protocol over the three fields), `linked_terms`,
//! `scope_of_atoms`, `theory_scope`, `_custom_pred` and `extension_atoms`. `session_live.py` `_SCOPE_FUNCS` patches them in.
//!
//! What still runs on Python, called back and counted (`scope:cb_*`), each read from `scope`'s module globals at call time, as
//! Python's code reads them:
//! - `atoms_of(f)`: a Formula is input (planner's formula ruling); the formula step moves `atoms_of` onto Rust nodes;
//! - `affine_pair(atoms)`: C1's wrapper in term_live, over the term table (`PyTermTable.affine_pair`);
//! - `transfer_wanted(atoms)`: `sa_solver.transfer_wanted` on the default backend (backend.py), so Rust behind one Python call;
//! - `extensions.facts_for(a)`: the facts the user's registered extensions generate (input, the user's own callbacks).
//!
//! `_is_number` is relations_core's `free_is_number` (the row, else Python's, counted `rel:py_is_number`), and `glue_atoms` is
//! relations_core's. `PRED_INDEX` and `RELATION_ATOMS` are read as containers (`in`), with no Python code run. Atoms are `P`
//! objects: their `.pred`, `.expr`, `__hash__` and `__eq__` are Formula input reads, as in 5c5's module functions.
use std::sync::{Arc, RwLock};

use pyo3::exceptions::{PyException, PyIndexError};
use pyo3::prelude::*;
use pyo3::types::{PyFrozenSet, PyList, PySet, PySlice, PyTuple};
use pyo3::{intern, IntoPyObjectExt};

use crate::relations_core::{self, planted};
use crate::session::{self, tick};

struct Hooks {
    /// `satassume.scope`: its globals are read at call time.
    scope: Py<PyAny>,
    /// `EMPTY`, made at install.
    empty: Py<ScopeRs>,
}

static HOOKS: RwLock<Option<Arc<Hooks>>> = RwLock::new(None);

fn hooks() -> PyResult<Arc<Hooks>> {
    HOOKS.read().unwrap().clone().ok_or_else(|| PyException::new_err("scope_core: scope_install hasn't run"))
}

/// `Scope(glue, transfer, linked_terms)`: the theory scope of a query. Python's is a `NamedTuple`; this keeps what callers read
/// of it: the three fields by name, by index and by unpacking, `==` and `hash` as a tuple's (so it equals Python's `Scope` and a
/// plain 3-tuple with the same fields), and its repr. Each field is the object it was built with, as a tuple holds it.
#[pyclass(frozen, name = "Scope", module = "satassume.scope")]
pub struct ScopeRs {
    glue: Py<PyAny>,
    transfer: Py<PyAny>,
    linked: Py<PyAny>,
}

impl ScopeRs {
    fn tuple<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyTuple>> {
        PyTuple::new(p, [self.glue.bind(p).clone(), self.transfer.bind(p).clone(), self.linked_terms(p)?])
    }

    fn linked_terms<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let l = self.linked.bind(p);
        if planted(relations_core::SCOPE_LINKED_EMPTY) && l.is_truthy()? {
            return Ok(PyFrozenSet::empty(p)?.into_any());
        }
        Ok(l.clone())
    }
}

#[pymethods]
impl ScopeRs {
    #[new]
    fn new(glue: Py<PyAny>, transfer: Py<PyAny>, linked_terms: Py<PyAny>) -> Self {
        tick(session::SCOPE_NEW);
        ScopeRs { glue, transfer, linked: linked_terms }
    }

    #[getter]
    fn glue(&self, p: Python<'_>) -> Py<PyAny> {
        self.glue.clone_ref(p)
    }

    #[getter]
    fn transfer(&self, p: Python<'_>) -> Py<PyAny> {
        self.transfer.clone_ref(p)
    }

    #[getter(linked_terms)]
    fn get_linked_terms<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        self.linked_terms(p)
    }

    #[classattr]
    fn _fields() -> (&'static str, &'static str, &'static str) {
        ("glue", "transfer", "linked_terms")
    }

    fn __len__(&self) -> usize {
        3
    }

    fn __getitem__<'py>(&self, p: Python<'py>, i: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        let t = self.tuple(p)?;
        if i.is_instance_of::<PySlice>() {
            return t.as_any().get_item(i);
        }
        let k: isize = i.extract()?;
        let k = if k < 0 { k + 3 } else { k };
        if !(0..3).contains(&k) {
            return Err(PyIndexError::new_err("tuple index out of range"));
        }
        t.get_item(k as usize)
    }

    fn __iter__<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        Ok(self.tuple(p)?.as_any().try_iter()?.into_any())
    }

    fn __hash__(&self, p: Python<'_>) -> PyResult<isize> {
        self.tuple(p)?.hash()
    }

    fn __richcmp__<'py>(&self, p: Python<'py>, other: &Bound<'py, PyAny>, op: pyo3::basic::CompareOp) -> PyResult<Bound<'py, PyAny>> {
        let o = match other.cast::<ScopeRs>() {
            Ok(s) => s.get().tuple(p)?.into_any(),
            Err(_) if other.is_instance_of::<PyTuple>() => other.clone(),
            Err(_) => return Ok(p.NotImplemented().into_bound(p)),
        };
        self.tuple(p)?.rich_compare(o, op)
    }

    fn __repr__(&self, p: Python<'_>) -> PyResult<String> {
        Ok(format!("Scope(glue={}, transfer={}, linked_terms={})",
                   self.glue.bind(p).repr()?, self.transfer.bind(p).repr()?, self.linked_terms(p)?.repr()?))
    }

    fn _asdict<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let d = pyo3::types::PyDict::new(p);
        d.set_item("glue", self.glue.bind(p))?;
        d.set_item("transfer", self.transfer.bind(p))?;
        d.set_item("linked_terms", self.linked_terms(p)?)?;
        Ok(d.into_any())
    }
}

fn global<'py>(p: Python<'py>, h: &Hooks, name: &Bound<'py, pyo3::types::PyString>) -> PyResult<Bound<'py, PyAny>> {
    h.scope.bind(p).getattr(name)
}

/// `_custom_pred`: a predicate neither in the vocabulary nor a relation.
fn custom_pred(a: &Bound<'_, PyAny>, index: &Bound<'_, PyAny>, rel: &Bound<'_, PyAny>) -> PyResult<bool> {
    tick(session::SCOPE_CUSTOM_PRED);
    let pred = a.getattr(intern!(a.py(), "pred"))?;
    let r = !index.contains(&pred)? && !rel.contains(&pred)?;
    if r && planted(relations_core::CUSTOM_NEVER) {
        return Ok(false);
    }
    Ok(r)
}

fn tables<'py>(p: Python<'py>, h: &Hooks) -> PyResult<(Bound<'py, PyAny>, Bound<'py, PyAny>)> {
    Ok((global(p, h, intern!(p, "PRED_INDEX"))?, global(p, h, intern!(p, "RELATION_ATOMS"))?))
}

#[pyfunction]
fn scope_custom_pred(a: &Bound<'_, PyAny>) -> PyResult<bool> {
    let p = a.py();
    let h = hooks()?;
    let (index, rel) = tables(p, &h)?;
    custom_pred(a, &index, &rel)
}

/// `linked_terms`: the vocabulary atoms' arguments and the relation atoms' sides, numbers excluded. The set is built as Python
/// builds it and frozen by `frozenset(set)`, so its iteration order is Python's.
fn linked_terms<'py>(p: Python<'py>, h: &Hooks, atoms: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    tick(session::SCOPE_LINKED_TERMS);
    let rh = relations_core::hooks()?;
    let (index, rel) = tables(p, h)?;
    let out = PySet::empty(p)?;
    for a in atoms.try_iter()? {
        let a = a?;
        let pred = a.getattr(intern!(p, "pred"))?;
        if index.contains(&pred)? {
            let e = a.getattr(intern!(p, "expr"))?;
            if !relations_core::free_is_number(&rh, &e)? {
                out.add(e)?;
            }
        } else if rel.contains(&pred)? {
            if planted(relations_core::LINKED_NO_REL) {
                continue;
            }
            for e in a.getattr(intern!(p, "expr"))?.try_iter()? {
                let e = e?;
                if !relations_core::free_is_number(&rh, &e)? {
                    out.add(e)?;
                }
            }
        }
    }
    p.get_type::<PyFrozenSet>().call1((out,))
}

#[pyfunction]
fn scope_linked_terms<'py>(atoms: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    linked_terms(atoms.py(), &*hooks()?, atoms)
}

/// `scope_of_atoms`.
fn scope_of_atoms<'py>(p: Python<'py>, h: &Hooks, atoms: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    tick(session::SCOPE_OF_ATOMS);
    let t = PyTuple::new(p, atoms.try_iter()?.collect::<PyResult<Vec<_>>>()?)?;
    let atoms = relations_core::rel_glue_atoms(t.as_any(), None, None)?;
    let rel_names = global(p, h, intern!(p, "RELATION_ATOMS"))?;
    let mut rel = false;
    for a in atoms.try_iter()? {
        if rel_names.contains(a?.getattr(intern!(p, "pred"))?)? {
            rel = true;
            break;
        }
    }
    let glue = rel || {
        if planted(relations_core::SCOPE_NO_AFFINE) {
            false
        } else {
            tick(session::SCOPE_CB_AFFINE_PAIR);
            global(p, h, intern!(p, "affine_pair"))?.call1((&atoms,))?.is_truthy()?
        }
    };
    if !glue {
        return Ok(h.empty.bind(p).clone().into_any());
    }
    let transfer = if rel {
        tick(session::SCOPE_CB_TRANSFER_WANTED);
        global(p, h, intern!(p, "transfer_wanted"))?.call1((&atoms,))?
    } else {
        false.into_bound_py_any(p)?
    };
    let linked = linked_terms(p, h, &atoms)?;
    Ok(Bound::new(p, ScopeRs::new(true.into_py_any(p)?, transfer.unbind(), linked.unbind()))?.into_any())
}

#[pyfunction]
fn scope_scope_of_atoms<'py>(atoms: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    scope_of_atoms(atoms.py(), &*hooks()?, atoms)
}

/// `extension_atoms`: the atoms of the facts `extensions` generates for the custom atoms, transitively, in Python's order.
fn extension_atoms<'py>(p: Python<'py>, h: &Hooks, atoms: &Bound<'py, PyAny>, extensions: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyList>> {
    tick(session::SCOPE_EXTENSION_ATOMS);
    let (index, rel) = tables(p, h)?;
    let out = PyList::empty(p);
    let seen = PySet::empty(p)?;
    let mut stack: Vec<Bound<'py, PyAny>> = Vec::new();
    for a in atoms.try_iter()? {
        let a = a?;
        if custom_pred(&a, &index, &rel)? {
            stack.push(a);
        }
    }
    while let Some(a) = stack.pop() {
        if seen.contains(&a)? {
            continue;
        }
        seen.add(&a)?;
        tick(session::SCOPE_CB_FACTS_FOR);
        for f in extensions.call_method1(intern!(p, "facts_for"), (&a,))?.try_iter()? {
            for b in crate::formula::atoms_nosession(&f?)?.iter() {
                out.append(&b)?;
                if custom_pred(&b, &index, &rel)? && !planted(relations_core::EXT_SHALLOW) {
                    stack.push(b);
                }
            }
        }
    }
    Ok(out)
}

#[pyfunction]
fn scope_extension_atoms<'py>(atoms: &Bound<'py, PyAny>, extensions: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyList>> {
    extension_atoms(atoms.py(), &*hooks()?, atoms, extensions)
}

/// `theory_scope`: the atoms of the two formulas (None and True have none), the extensions' atoms, then `scope_of_atoms`.
#[pyfunction]
#[pyo3(signature = (assumptions, proposition, extensions=None))]
fn scope_theory_scope<'py>(assumptions: &Bound<'py, PyAny>, proposition: &Bound<'py, PyAny>, extensions: Option<&Bound<'py, PyAny>>) -> PyResult<Bound<'py, PyAny>> {
    let p = assumptions.py();
    let h = hooks()?;
    tick(session::SCOPE_THEORY_SCOPE);
    let atoms = PyList::empty(p);
    let pt = pyo3::types::PyBool::new(p, true);
    for (k, f) in [assumptions, proposition].into_iter().enumerate() {
        if f.is_none() || f.is(&*pt) {
            continue;
        }
        if k == 0 && planted(relations_core::THEORY_NO_ASSUME) {
            continue;
        }
        for a in crate::formula::atoms_nosession(f)?.iter() {
            atoms.append(a)?;
        }
    }
    if let Some(ext) = extensions.filter(|e| !e.is_none()) {
        let more = extension_atoms(p, &h, atoms.as_any(), ext)?;
        for b in more.iter() {
            atoms.append(b)?;
        }
    }
    scope_of_atoms(p, &h, atoms.as_any())
}

/// Install: `scope` is the module; returns `EMPTY`, which session_live sets in place of Python's.
#[pyfunction]
fn scope_install<'py>(p: Python<'py>, scope: Py<PyAny>) -> PyResult<Bound<'py, ScopeRs>> {
    let empty = Bound::new(p, ScopeRs { glue: false.into_py_any(p)?, transfer: false.into_py_any(p)?,
                                        linked: PyFrozenSet::empty(p)?.into_any().unbind() })?;
    *HOOKS.write().unwrap() = Some(Arc::new(Hooks { scope, empty: empty.clone().unbind() }));
    Ok(empty)
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<ScopeRs>()?;
    m.add_function(wrap_pyfunction!(scope_install, m)?)?;
    m.add_function(wrap_pyfunction!(scope_custom_pred, m)?)?;
    m.add_function(wrap_pyfunction!(scope_linked_terms, m)?)?;
    m.add_function(wrap_pyfunction!(scope_scope_of_atoms, m)?)?;
    m.add_function(wrap_pyfunction!(scope_extension_atoms, m)?)?;
    m.add_function(wrap_pyfunction!(scope_theory_scope, m)?)?;
    Ok(())
}
