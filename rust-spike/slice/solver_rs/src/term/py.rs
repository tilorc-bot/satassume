//! The Python face of the term module. Python holds ints; nothing here keeps state across queries.
use super::offline;
use super::rat::Rat;
use super::table::{Kind, Read, Reads, Refuse, TermTable, READ_RAISED, V};
use super::TermId;
use num_bigint::BigInt;
use pyo3::create_exception;
use pyo3::exceptions::{PyException, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyTuple};

create_exception!(sa_solver, TermRefuse, PyException, "Rust refuses this query: it goes back to Python.");

thread_local! {
    /// What a read raised, between the callback and `refuse`: `Refuse` is a plain reason, so it can't carry it.
    static RAISED: std::cell::RefCell<Option<PyErr>> = const { std::cell::RefCell::new(None) };
}

fn refuse(r: Refuse) -> PyErr {
    if r.0 == READ_RAISED {
        if let Some(e) = RAISED.with(|x| x.borrow_mut().take()) {
            return e;
        }
    }
    TermRefuse::new_err(r.0)
}

/// `tables['reads']`: `convert.py`'s `_Walk.read`, `(kind, id) -> (tokens, strings) or None`. It catches `Exception`
/// itself, so what reaches `Err` here is a `BaseException`, or a bug, and goes on up to the caller as it is.
struct PyReads(Py<PyAny>);

impl Reads for PyReads {
    fn read(&self, kind: Read, t: TermId) -> Result<Option<(Vec<i64>, Vec<String>)>, Refuse> {
        Python::attach(|py| {
            let got = self.0.bind(py).call1((kind as u8, t.0)).and_then(|x| {
                if x.is_none() {
                    Ok(None)
                } else {
                    x.extract().map(Some).map_err(Into::into)
                }
            });
            got.map_err(|e| {
                RAISED.with(|x| *x.borrow_mut() = Some(e));
                Refuse(READ_RAISED)
            })
        })
    }
}

#[pyclass(name = "TermTable")]
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
        V::Text(s) => s.as_ref().into_pyobject(py)?.into_any(),
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
        let reads: Py<PyAny> = req(tables, "reads")?;
        TermTable::from_tokens(
            req(tables, "strings")?,
            &classes,
            &terms,
            &powers,
            &settings,
            &formula,
            req(tables, "n_classes")?,
            req(tables, "n_terms")?,
            Box::new(PyReads(reads)),
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

    /// (args, content, key, free, bits, level, closed, power). Key, closed and power are what's been read so far, None
    /// if nothing has: this forces no read. `sort_key`, `closed`, `power` and `commutative` read.
    fn row<'py>(&self, py: Python<'py>, i: u32) -> PyResult<Bound<'py, PyAny>> {
        let r = self.0.row(TermId(i));
        let content = r.content.iter().map(|x| value(py, &self.0, x)).collect::<PyResult<Vec<_>>>()?;
        let id = TermId(i);
        let key = self.0.peek(Read::Key, id).flatten().map(|k| value(py, &self.0, &k)).transpose()?;
        let closed = self.0.peek_closed(id);
        let power = self.0.peek_power(id).map(|(b, e)| (b.map(|b| b.0), e));
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

    /// `is_finite` of a closed input term, reading it if it hasn't been. None if the term has no read. Raises TermRefuse.
    fn finite(&self, i: u32) -> PyResult<Option<bool>> {
        self.0.finite_of(TermId(i)).map_err(refuse)
    }

    /// `complex()` of a closed input term as (re, im), reading it if it hasn't been. None if it raised or has no read.
    fn complex(&self, i: u32) -> PyResult<Option<(f64, f64)>> {
        self.0.complex_of(TermId(i)).map_err(refuse)
    }

    /// (base id or None, exponent) from `decompose_power`, reading it if it hasn't been. None if the term has no split.
    fn power(&self, i: u32) -> PyResult<Option<(Option<u32>, BigInt)>> {
        Ok(self.0.power_of(TermId(i)).map_err(refuse)?.map(|(b, e)| (b.map(|b| b.0), e)))
    }

    /// `is_commutative is True`, reading it for an input term if it hasn't been.
    fn commutative(&self, i: u32) -> PyResult<bool> {
        self.0.commutative_of(TermId(i)).map_err(refuse)
    }

    /// How many lazy reads this table's memo holds. It dies with the table.
    fn reads_held(&self) -> usize {
        self.0.reads_held()
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

    /// `n_input`: rows from conversion; later ids are derived.
    #[getter]
    fn n_input(&self) -> usize {
        self.0.n_input
    }

    /// The term of a rational, by value.
    fn number(&mut self, p: BigInt, q: BigInt) -> u32 {
        self.0.number(&Rat::new(p, q)).0
    }

    /// `-t`. Raises TermRefuse, as do the rest.
    fn neg(&mut self, t: u32) -> PyResult<u32> {
        self.0.neg(TermId(t)).map(|x| x.0).map_err(refuse)
    }

    fn add(&mut self, args: Vec<u32>) -> PyResult<u32> {
        self.0.add(args.into_iter().map(TermId).collect()).map(|x| x.0).map_err(refuse)
    }

    fn mul(&mut self, args: Vec<u32>) -> PyResult<u32> {
        self.0.mul(args.into_iter().map(TermId).collect()).map(|x| x.0).map_err(refuse)
    }

    fn sub(&mut self, a: u32, b: u32) -> PyResult<u32> {
        self.0.sub(TermId(a), TermId(b)).map(|x| x.0).map_err(refuse)
    }

    fn raw_add(&mut self, args: Vec<u32>) -> u32 {
        self.0.raw_add(args.into_iter().map(TermId).collect()).0
    }

    fn raw_mul(&mut self, args: Vec<u32>) -> u32 {
        self.0.raw_mul(args.into_iter().map(TermId).collect()).0
    }

    fn coeff_add(&mut self, t: u32) -> PyResult<(u32, u32)> {
        self.0.coeff_add(TermId(t)).map(|(a, b)| (a.0, b.0)).map_err(refuse)
    }

    fn coeff_mul(&mut self, t: u32) -> PyResult<(u32, u32)> {
        self.0.coeff_mul(TermId(t)).map(|(a, b)| (a.0, b.0)).map_err(refuse)
    }

    /// `default_sort_key(t)`, as `row` gives keys.
    fn sort_key<'py>(&self, py: Python<'py>, t: u32) -> PyResult<Bound<'py, PyAny>> {
        let k = self.0.sort_key(TermId(t)).map_err(refuse)?;
        value(py, &self.0, &k)
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
