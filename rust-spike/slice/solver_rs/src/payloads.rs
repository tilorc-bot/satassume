//! Adapters step, part C (issue 323): the theory payloads `Negated`, `Integral` (lra.py:230/:247) and `EqAtom` (euf.py:75) as
//! Rust classes, built by the Rust adapters (adapters.rs) and integer_form's Rust route (lra_live.py) with no Python tuple
//! in between.
//!
//! Python keeps its classes for the pure-Python default and for `lra.constraint()`, which only tests call. The readers accept
//! both: euf_py.rs `register_atom` reads a Rust `EqAtom`'s fields directly, lra_backend.py `_register` takes either class.
//!
//! Each behaves as Python's tuple subclass does wherever something can read it later: length, indexing and slicing,
//! iteration, `==`/ordering/hash as the tuple of its fields (so it equals Python's payload and a plain tuple with the same
//! fields, as Python's do), the named fields, `_fields`, the same `repr`, and pickling. What it doesn't have is
//! `isinstance(x, tuple)`: nothing reads a payload that way (rg `isinstance(.*tuple` over satassume/theories and the slice's
//! readers: only `_pairs`' terms, which stay a Python container).
//!
//! Counted at construction: `ad:negated_new`, `ad:integral_new`, `ad:eqatom_new`. Plants, one in each class: `pay-neg-twice`
//! (Negated wraps its payload in a second Negated, so the negation cancels), `pay-int-offset` (Integral's offset is half a
//! unit off), `pay-eq-flip` (EqAtom stores the opposite polarity).

use pyo3::basic::CompareOp;
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::types::{PyTuple, PyType};

use crate::relations_core::{planted, PAY_EQ_FLIP, PAY_INT_OFFSET, PAY_NEG_TWICE};
use crate::session::{self, tick};

/// The fields of any of the three, or the object itself: what `==` and ordering compare against.
fn fields_of<'py>(other: &Bound<'py, PyAny>) -> Bound<'py, PyAny> {
    if let Ok(o) = other.cast::<Negated>() {
        return o.get().items.bind(other.py()).clone().into_any();
    }
    if let Ok(o) = other.cast::<Integral>() {
        return o.get().items.bind(other.py()).clone().into_any();
    }
    if let Ok(o) = other.cast::<EqAtom>() {
        return o.get().items.bind(other.py()).clone().into_any();
    }
    other.clone()
}

macro_rules! tuple_like {
    ($ty:ident, { $($extra:tt)* }) => {
        #[pymethods]
        impl $ty {
            $($extra)*

            fn __len__(&self, p: Python<'_>) -> usize {
                self.items.bind(p).len()
            }

            fn __getitem__<'py>(&self, p: Python<'py>, i: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
                self.items.bind(p).as_any().get_item(i)
            }

            fn __iter__<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
                Ok(self.items.bind(p).as_any().try_iter()?.into_any())
            }

            fn __contains__(&self, p: Python<'_>, x: &Bound<'_, PyAny>) -> PyResult<bool> {
                self.items.bind(p).contains(x)
            }

            fn __hash__(&self, p: Python<'_>) -> PyResult<isize> {
                self.items.bind(p).as_any().hash()
            }

            fn __richcmp__<'py>(&self, p: Python<'py>, other: &Bound<'py, PyAny>, op: CompareOp) -> PyResult<Bound<'py, PyAny>> {
                let o = fields_of(other);
                if !o.is_instance_of::<PyTuple>() {
                    return Ok(p.NotImplemented().into_bound(p));
                }
                self.items.bind(p).as_any().rich_compare(o, op)
            }

            fn __getnewargs__<'py>(&self, p: Python<'py>) -> Bound<'py, PyTuple> {
                self.items.bind(p).clone()
            }

            fn __reduce__<'py>(slf: &Bound<'py, Self>) -> PyResult<(Bound<'py, PyType>, Bound<'py, PyTuple>)> {
                Ok((slf.get_type(), slf.get().items.bind(slf.py()).clone()))
            }

            fn count(&self, p: Python<'_>, x: &Bound<'_, PyAny>) -> PyResult<usize> {
                self.items.bind(p).as_any().call_method1(intern!(p, "count"), (x,))?.extract()
            }

            fn index(&self, p: Python<'_>, x: &Bound<'_, PyAny>) -> PyResult<usize> {
                self.items.bind(p).index(x)
            }
        }
    };
}

/// lra.py:230: "the registered atom is the negation of `payload`".
#[pyclass(frozen, module = "sa_solver")]
pub(crate) struct Negated {
    items: Py<PyTuple>,
}

tuple_like!(Negated, {
    #[new]
    pub(crate) fn new(p: Python<'_>, payload: &Bound<'_, PyAny>) -> PyResult<Negated> {
        tick(session::AD_NEGATED_NEW);
        let payload = if planted(PAY_NEG_TWICE) {
            Bound::new(p, Negated { items: PyTuple::new(p, [payload])?.unbind() })?.into_any()
        } else {
            payload.clone()
        };
        Ok(Negated { items: PyTuple::new(p, [payload])?.unbind() })
    }

    #[classattr]
    fn _fields(p: Python<'_>) -> PyResult<Py<PyTuple>> {
        Ok(PyTuple::new(p, ["payload"])?.unbind())
    }

    #[getter]
    fn payload<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        self.items.bind(p).get_item(0)
    }

    fn __repr__(&self, p: Python<'_>) -> PyResult<String> {
        Ok(format!("Negated(payload={})", self.items.bind(p).get_item(0)?.repr()?))
    }
});

/// lra.py:247: "`sum(c*t for t, c in terms) + offset` is an integer".
#[pyclass(frozen, module = "sa_solver")]
pub(crate) struct Integral {
    items: Py<PyTuple>,
}

tuple_like!(Integral, {
    #[new]
    #[pyo3(signature = (terms, offset=None))]
    pub(crate) fn new(p: Python<'_>, terms: &Bound<'_, PyAny>, offset: Option<&Bound<'_, PyAny>>) -> PyResult<Integral> {
        tick(session::AD_INTEGRAL_NEW);
        let mut offset = match offset {
            Some(o) => o.clone(),
            None => 0i64.into_pyobject(p)?.into_any(),
        };
        if planted(PAY_INT_OFFSET) {
            let half = p.import(intern!(p, "fractions"))?.getattr(intern!(p, "Fraction"))?.call1((1, 2))?;
            offset = offset.add(half)?;
        }
        Ok(Integral { items: PyTuple::new(p, [terms.clone(), offset])?.unbind() })
    }

    #[classattr]
    fn _fields(p: Python<'_>) -> PyResult<Py<PyTuple>> {
        Ok(PyTuple::new(p, ["terms", "offset"])?.unbind())
    }

    #[getter]
    fn terms<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        self.items.bind(p).get_item(0)
    }

    #[getter]
    fn offset<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        self.items.bind(p).get_item(1)
    }

    fn __repr__(&self, p: Python<'_>) -> PyResult<String> {
        let t = self.items.bind(p);
        Ok(format!("Integral(terms={}, offset={})", t.get_item(0)?.repr()?, t.get_item(1)?.repr()?))
    }
});

impl Integral {
    /// (terms, offset), for adapters.rs' conversion to Python's class.
    pub(crate) fn pair<'py>(&self, p: Python<'py>) -> PyResult<(Bound<'py, PyAny>, Bound<'py, PyAny>)> {
        let t = self.items.bind(p);
        Ok((t.get_item(0)?, t.get_item(1)?))
    }
}

/// euf.py:75: "`lhs == rhs` between term ids; with `positive=False` the variable stands for `lhs != rhs`".
#[pyclass(frozen, module = "sa_solver")]
pub(crate) struct EqAtom {
    items: Py<PyTuple>,
}

impl EqAtom {
    /// euf_py.rs reads the fields with no Python call: (lhs, rhs, positive's object).
    pub(crate) fn parts<'py>(&self, p: Python<'py>) -> PyResult<(Bound<'py, PyAny>, Bound<'py, PyAny>, Bound<'py, PyAny>)> {
        let t = self.items.bind(p);
        Ok((t.get_item(0)?, t.get_item(1)?, t.get_item(2)?))
    }
}

tuple_like!(EqAtom, {
    #[new]
    #[pyo3(signature = (lhs, rhs, positive=None))]
    pub(crate) fn new(p: Python<'_>, lhs: &Bound<'_, PyAny>, rhs: &Bound<'_, PyAny>, positive: Option<&Bound<'_, PyAny>>) -> PyResult<EqAtom> {
        tick(session::AD_EQATOM_NEW);
        let mut positive = match positive {
            Some(x) => x.clone(),
            None => true.into_pyobject(p)?.to_owned().into_any(),
        };
        if planted(PAY_EQ_FLIP) {
            let flip = !positive.is_truthy()?;
            positive = flip.into_pyobject(p)?.to_owned().into_any();
        }
        Ok(EqAtom { items: PyTuple::new(p, [lhs.clone(), rhs.clone(), positive])?.unbind() })
    }

    #[classattr]
    fn _fields(p: Python<'_>) -> PyResult<Py<PyTuple>> {
        Ok(PyTuple::new(p, ["lhs", "rhs", "positive"])?.unbind())
    }

    #[getter]
    fn lhs<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        self.items.bind(p).get_item(0)
    }

    #[getter]
    fn rhs<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        self.items.bind(p).get_item(1)
    }

    #[getter]
    fn positive<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        self.items.bind(p).get_item(2)
    }

    fn __repr__(&self, p: Python<'_>) -> PyResult<String> {
        let t = self.items.bind(p);
        Ok(format!("EqAtom(lhs={}, rhs={}, positive={})", t.get_item(0)?.repr()?, t.get_item(1)?.repr()?, t.get_item(2)?.repr()?))
    }
});

pub(crate) fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Negated>()?;
    m.add_class::<Integral>()?;
    m.add_class::<EqAtom>()?;
    Ok(())
}
