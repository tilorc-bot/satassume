//! The Python face of the term module. Python holds ints; nothing here keeps state across queries.
use super::offline;
use super::table::{Kind, Refuse, TermTable, V};
use super::TermId;
use pyo3::create_exception;
use pyo3::exceptions::{PyException, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyTuple};

create_exception!(sa_solver, TermRefuse, PyException, "Rust refuses this query: it goes back to Python.");

fn refuse(r: Refuse) -> PyErr {
    TermRefuse::new_err(r.0)
}

#[pyclass(name = "TermTable", frozen)]
pub struct PyTermTable(TermTable);

fn req<'py, T: FromPyObjectOwned<'py>>(d: &Bound<'py, PyDict>, k: &str) -> PyResult<T> {
    d.get_item(k)?
        .ok_or_else(|| PyValueError::new_err(format!("tables: no {k}")))?
        .extract()
        .map_err(Into::into)
}

/// A value as Python: a term is ("T", id), a rational ("Q", p, q), anything opaque ("O", index).
fn value<'py>(py: Python<'py>, t: &TermTable, v: &V) -> PyResult<Bound<'py, PyAny>> {
    Ok(match v {
        V::None => py.None().into_bound(py),
        V::Bool(b) => b.into_pyobject(py)?.to_owned().into_any(),
        V::Int(n) => n.into_pyobject(py)?.into_any(),
        V::Str(s) => t.strings[*s as usize].as_str().into_pyobject(py)?.into_any(),
        V::Tuple(xs) => {
            let items = xs.iter().map(|x| value(py, t, x)).collect::<PyResult<Vec<_>>>()?;
            PyTuple::new(py, items)?.into_any()
        }
        V::Term(id) => ("T", id.0).into_pyobject(py)?.into_any(),
        V::Rat(r) => ("Q", &r.n, &r.d).into_pyobject(py)?.into_any(),
        V::Opaque(i) => ("O", *i).into_pyobject(py)?.into_any(),
    })
}

#[pymethods]
impl PyTermTable {
    #[new]
    fn new(tables: &Bound<'_, PyDict>) -> PyResult<Self> {
        let classes: Vec<i64> = req(tables, "classes")?;
        let terms: Vec<i64> = req(tables, "terms")?;
        let powers: Vec<i64> = req(tables, "powers")?;
        let settings: Vec<i64> = req(tables, "settings")?;
        let formula: Vec<i64> = req(tables, "formula")?;
        TermTable::from_tokens(
            req(tables, "strings")?,
            &classes,
            &terms,
            &powers,
            &settings,
            &formula,
            req(tables, "n_classes")?,
            req(tables, "n_terms")?,
            req(tables, "n_powers")?,
        )
        .map(PyTermTable)
        .map_err(|e| PyValueError::new_err(format!("tables refused: {e}")))
    }

    /// (proposition, assumptions or None), as nested tuples.
    fn formula<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        value(py, &self.0, &self.0.formula)
    }

    fn __len__(&self) -> usize {
        self.0.len()
    }

    /// (class name, kind index, rank or None, flags, class_key, templates, structural) of a term's class.
    fn class_row<'py>(&self, py: Python<'py>, i: u32) -> PyResult<Bound<'py, PyAny>> {
        let c = self.0.class_of(TermId(i));
        (
            self.0.class_name(c),
            c.kind as u8,
            c.rank,
            c.flags,
            value(py, &self.0, &c.class_key)?,
            value(py, &self.0, &c.templates)?,
            c.structural,
        )
            .into_pyobject(py)
            .map(|t| t.into_any())
    }

    /// (args, content, key or None, free, bits, level, closed, power).
    fn row<'py>(&self, py: Python<'py>, i: u32) -> PyResult<Bound<'py, PyAny>> {
        let r = self.0.row(TermId(i));
        let content = r.content.iter().map(|x| value(py, &self.0, x)).collect::<PyResult<Vec<_>>>()?;
        let key = r.key.as_ref().map(|k| value(py, &self.0, k)).transpose()?;
        let closed = r.closed.as_ref().map(|c| (c.is_finite, c.complex));
        let power = r.power.as_ref().map(|(b, e)| (b.map(|b| b.0), e.clone()));
        (
            r.args.iter().map(|a| a.0).collect::<Vec<_>>(),
            PyTuple::new(py, content)?,
            key,
            r.free.iter().map(|a| a.0).collect::<Vec<_>>(),
            r.bits,
            r.level,
            closed,
            power,
        )
            .into_pyobject(py)
            .map(|t| t.into_any())
    }

    /// The id the hash-cons index holds for this term's own class and content.
    fn find(&self, i: u32) -> Option<u32> {
        let r = self.0.row(TermId(i));
        self.0.find(r.class, &r.content).map(|t| t.0)
    }

    /// `Basic.compare`, as -1, 0 or 1. Raises TermRefuse.
    fn compare(&self, a: u32, b: u32) -> PyResult<i8> {
        self.0.compare(TermId(a), TermId(b)).map(|o| o as i8).map_err(refuse)
    }

    /// `default_sort_key` order, as -1, 0 or 1. Raises TermRefuse.
    fn key_cmp(&self, a: u32, b: u32) -> PyResult<i8> {
        self.0.key_cmp(TermId(a), TermId(b)).map(|o| o as i8).map_err(refuse)
    }

    /// The kinds that have a row but that this slice doesn't use yet stay readable through `class_row`.
    fn is_add(&self, i: u32) -> bool {
        self.0.class_of(TermId(i)).kind == Kind::Add
    }
}

#[pyclass(name = "OfflineData", frozen)]
pub struct PyOfflineData(offline::OfflineData);

#[pymethods]
impl PyOfflineData {
    /// Raises ValueError, naming the reason, for a file it refuses.
    #[new]
    fn new(path: &str, sources_root: &str, sympy: &str) -> PyResult<Self> {
        offline::OfflineData::load(path, sources_root, sympy)
            .map(PyOfflineData)
            .map_err(|e| PyValueError::new_err(format!("offline data refused: {e}")))
    }

    fn roundtrip(&self) -> String {
        self.0.roundtrip()
    }

    fn basis(&self) -> Option<Vec<String>> {
        self.0.basis().map(|b| b.into_iter().map(str::to_string).collect())
    }
}

#[pyfunction]
fn sha256_hex(data: &[u8]) -> String {
    offline::sha256(data)
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyOfflineData>()?;
    m.add_class::<PyTermTable>()?;
    m.add("TermRefuse", m.py().get_type::<TermRefuse>())?;
    m.add_function(wrap_pyfunction!(sha256_hex, m)?)?;
    Ok(())
}
