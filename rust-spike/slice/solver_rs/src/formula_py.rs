//! `P`, the atom `pred(expr)` of `satassume/sat/formula.py`, as Python's frozen dataclass behaves on CPython 3.12. It holds
//! two Python objects until component 0 lands. `hash` stays `hash((pred, expr))`, because sets of atoms are iterated by
//! it, and `==` stays the class check and the tuple compare, whose element identity shortcut is `tuple`'s own.
//! Not reproduced: `__dict__` and `__dataclass_fields__`; nothing in `satassume` or `tests` reads them. The slot
//! wrappers `__rand__`, `__ror__` and `__rrshift__` exist and answer NotImplemented, so the operators behave the same.
use pyo3::basic::CompareOp;
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::types::{PyString, PyTuple, PyType};

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

    /// `f"{self.pred}({self.expr})"`: an f-string's `format(x, "")`, not `str(x)`.
    fn __repr__(&self, p: Python<'_>) -> PyResult<String> {
        let f = intern!(p, "__format__");
        let (a, b) = (self.pred.bind(p).call_method1(f, ("",))?, self.expr.bind(p).call_method1(f, ("",))?);
        Ok(format!("{}({})", a.extract::<String>()?, b.extract::<String>()?))
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
        let (a, b) = (slf.get(), other.cast::<PyP>()?.get());
        let x = PyTuple::new(p, [a.pred.bind(p), a.expr.bind(p)])?;
        let y = PyTuple::new(p, [b.pred.bind(p), b.expr.bind(p)])?;
        let same = x.eq(y)?;
        Ok((same == matches!(op, CompareOp::Eq)).into_pyobject(p)?.to_owned().into_any().unbind())
    }

    fn __setattr__(&self, p: Python<'_>, name: &Bound<'_, PyAny>, _value: &Bound<'_, PyAny>) -> PyResult<()> {
        Err(frozen(p, "assign to", name)?)
    }

    fn __delattr__(&self, p: Python<'_>, name: &Bound<'_, PyAny>) -> PyResult<()> {
        Err(frozen(p, "delete", name)?)
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
    m.add_class::<PyP>()
}
