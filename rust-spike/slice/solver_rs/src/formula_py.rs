//! `P`, the atom `pred(expr)` of `satassume/sat/formula.py`, as Python's frozen dataclass behaves on CPython 3.12. It holds
//! two Python objects until component 0 lands. `hash` stays `hash((pred, expr))`, because sets of atoms are iterated by
//! it, and `==` stays the class check and the tuple compare, whose element identity shortcut is `tuple`'s own.
//! Not reproduced, by `transfer_fuzz.py`'s `part_p`: `__dict__` and `__dataclass_fields__`, so `is_dataclass` is False; and
//! reading a pickle written by Python's class, which goes through `__new__` with no arguments; and a subclass overriding a
//! field, which is stored here, not in an instance dict. Nothing in `satassume` or `tests` reads the first two or subclasses
//! `P`, and nothing in `satassume` reads a pickle. The slot wrappers `__rand__`, `__ror__` and
//! `__rrshift__` exist and answer NotImplemented, so the operators behave the same.
use pyo3::basic::CompareOp;
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::types::{PyList, PyString, PyTuple, PyType};
use pyo3::{ffi, PyTraverseError, PyTypeInfo, PyVisit};

/// Atomic proposition ``pred(expr)``.
#[pyclass(name = "P", module = "satassume.sat.formula", frozen, subclass, weakref)]
pub struct PyP {
    #[pyo3(get)]
    pred: Py<PyAny>,
    #[pyo3(get)]
    expr: Py<PyAny>,
}

fn form<'py>(p: Python<'py>, name: &Bound<'py, PyString>) -> PyResult<Bound<'py, PyAny>> {
    p.import(intern!(p, "satassume.sat.formula"))?.getattr(name)
}

fn frozen(p: Python<'_>, verb: &str, name: &Bound<'_, PyAny>) -> PyResult<PyErr> {
    let e = p.import(intern!(p, "dataclasses"))?.getattr(intern!(p, "FrozenInstanceError"))?;
    let msg = format!("cannot {verb} field {}", name.repr()?);
    Ok(PyErr::from_value(e.call1((msg,))?))
}

/// `other.pred` and `other.expr`, once `other.__class__` has said it's the class: not necessarily an instance of it.
fn fields<'py>(x: &Bound<'py, PyAny>) -> PyResult<(Bound<'py, PyAny>, Bound<'py, PyAny>)> {
    let p = x.py();
    match x.cast::<PyP>() {
        Ok(s) => Ok((s.get().pred.bind(p).clone(), s.get().expr.bind(p).clone())),
        Err(_) => Ok((x.getattr(intern!(p, "pred"))?, x.getattr(intern!(p, "expr"))?)),
    }
}

/// `super().__setattr__` on a subclass; `value` null deletes. `object.__setattr__` would refuse a subclass of this class,
/// whose slot isn't object's, so this is the call behind it.
fn generic_set(slf: &Bound<'_, PyP>, name: &Bound<'_, PyAny>, value: *mut ffi::PyObject) -> PyResult<()> {
    if unsafe { ffi::PyObject_GenericSetAttr(slf.as_ptr(), name.as_ptr(), value) } < 0 {
        return Err(PyErr::fetch(slf.py()));
    }
    Ok(())
}

/// The frozen check: `type(self) is cls or name in fields`. A subclass's other attributes go through.
fn is_frozen(slf: &Bound<'_, PyP>, name: &Bound<'_, PyAny>) -> PyResult<bool> {
    let p = slf.py();
    Ok(slf.is_exact_instance_of::<PyP>() || name.eq(intern!(p, "pred"))? || name.eq(intern!(p, "expr"))?)
}

#[pymethods]
impl PyP {
    #[new]
    #[pyo3(signature = (pred, expr))]
    fn new(pred: Py<PyAny>, expr: Py<PyAny>) -> Self {
        PyP { pred, expr }
    }

    #[classattr]
    fn __match_args__(p: Python<'_>) -> PyResult<Py<PyTuple>> {
        Ok(PyTuple::new(p, ["pred", "expr"])?.unbind())
    }

    /// `f"{self.pred}({self.expr})"`: an f-string's `format(x, "")`, which looks on the type and checks it got a `str`. Joined
    /// as Python strings, because a lone surrogate has no UTF-8.
    fn __repr__<'py>(slf: &Bound<'py, Self>) -> PyResult<Bound<'py, PyAny>> {
        let p = slf.py();
        let s = slf.get();
        let (a, b) = (s.pred.bind(p), s.expr.bind(p));
        let format = p.import(intern!(p, "builtins"))?.getattr(intern!(p, "format"))?;
        let parts = [format.call1((a,))?, intern!(p, "(").clone().into_any(), format.call1((b,))?, intern!(p, ")").clone().into_any()];
        intern!(p, "").call_method1(intern!(p, "join"), (PyList::new(p, parts)?,))
    }

    fn __hash__(&self, p: Python<'_>) -> PyResult<isize> {
        PyTuple::new(p, [self.pred.bind(p), self.expr.bind(p)])?.hash()
    }

    fn __richcmp__(slf: &Bound<'_, Self>, other: &Bound<'_, PyAny>, op: CompareOp) -> PyResult<Py<PyAny>> {
        let p = slf.py();
        let not_impl = || p.NotImplemented();
        if !matches!(op, CompareOp::Eq | CompareOp::Ne) {
            return Ok(not_impl());
        }
        let cls: Bound<'_, PyType> = slf.get_type();
        if !other.getattr(intern!(p, "__class__"))?.is(&cls) {
            return Ok(not_impl());
        }
        let (a, b) = (slf.get(), fields(other)?);
        let x = PyTuple::new(p, [a.pred.bind(p), a.expr.bind(p)])?;
        let y = PyTuple::new(p, [b.0, b.1])?;
        let same = x.eq(y)?;
        Ok((same == matches!(op, CompareOp::Eq)).into_pyobject(p)?.to_owned().into_any().unbind())
    }

    fn __setattr__(slf: &Bound<'_, Self>, name: &Bound<'_, PyAny>, value: &Bound<'_, PyAny>) -> PyResult<()> {
        let p = slf.py();
        if is_frozen(slf, name)? {
            return Err(frozen(p, "assign to", name)?);
        }
        generic_set(slf, name, value.as_ptr())
    }

    fn __delattr__(slf: &Bound<'_, Self>, name: &Bound<'_, PyAny>) -> PyResult<()> {
        let p = slf.py();
        if is_frozen(slf, name)? {
            return Err(frozen(p, "delete", name)?);
        }
        generic_set(slf, name, std::ptr::null_mut())
    }

    /// Python's instance is collected through its `__dict__`; without this, a cycle through an atom never is. No `__clear__`:
    /// the atom is frozen, and whatever else is in the cycle can be cleared.
    fn __traverse__(&self, visit: PyVisit<'_>) -> Result<(), PyTraverseError> {
        visit.call(&self.pred)?;
        visit.call(&self.expr)
    }

    fn __invert__<'py>(slf: &Bound<'py, Self>) -> PyResult<Bound<'py, PyAny>> {
        form(slf.py(), intern!(slf.py(), "Not"))?.call1((slf,))
    }

    fn __and__<'py>(slf: &Bound<'py, Self>, other: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        form(slf.py(), intern!(slf.py(), "And"))?.call1((slf, other))
    }

    fn __or__<'py>(slf: &Bound<'py, Self>, other: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        form(slf.py(), intern!(slf.py(), "Or"))?.call1((slf, other))
    }

    fn __rshift__<'py>(slf: &Bound<'py, Self>, other: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        form(slf.py(), intern!(slf.py(), "Implies"))?.call1((slf, other))
    }

    /// What pickle and `copy` go through; Python's dataclass gets there by its `__dict__`.
    fn __reduce__<'py>(slf: &Bound<'py, Self>) -> PyResult<(Bound<'py, PyType>, (Py<PyAny>, Py<PyAny>))> {
        let p = slf.py();
        let s = slf.get();
        Ok((slf.get_type(), (s.pred.clone_ref(p), s.expr.clone_ref(p))))
    }
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyP>()?;
    // Error text reads `tp_name`, which is the dotted name here and plain `P` on Python's class. `__name__` and `__module__`
    // don't read it. The string is static.
    let t = PyP::type_object(m.py());
    unsafe { (*t.as_ptr().cast::<ffi::PyTypeObject>()).tp_name = c"P".as_ptr() };
    Ok(())
}
