//! The Python face of the term module. Python holds ints; nothing here keeps state across queries.
use super::knowledge::{Rules, UnitPattern};
use super::offline;
use super::rat::Rat;
use super::table::{AtomRow, Kind, Refuse, TermTable, V};
use super::TermId;
use num_bigint::BigInt;
use pyo3::create_exception;
use pyo3::exceptions::{PyException, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyFrozenSet, PyList, PyTuple};
use pyo3::IntoPyObjectExt;

create_exception!(sa_solver, TermRefuse, PyException, "Rust refuses this query: it goes back to Python.");

fn refuse(r: Refuse) -> PyErr {
    TermRefuse::new_err(r.0)
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
        .and_then(|mut t| {
            // Additive: a table from before the atoms rows simply has none.
            if let Some(a) = tables.get_item("atoms").map_err(|e| e.to_string())? {
                let a: Vec<i64> = a.extract().map_err(|e: PyErr| e.to_string())?;
                let n: usize = req(tables, "n_atoms").map_err(|e: PyErr| e.to_string())?;
                t.read_atoms(&a, n)?;
            }
            Ok(t)
        })
        .map(PyTermTable)
        .map_err(|e: String| PyValueError::new_err(format!("tables refused: {e}")))
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

/// The atoms family of runtime knowledge. Holds offline data only, so it can live as long as the process.
#[pyclass(name = "Knowledge", frozen)]
pub struct PyKnowledge(Rules);

fn pattern<'py>(py: Python<'py>, k: &Rules, p: &UnitPattern) -> PyResult<Bound<'py, PyAny>> {
    // Exactly `Pattern`'s fields, as `Pattern.__init__` and `units` build them.
    let empty = PyTuple::empty(py);
    let rules = PyList::empty(py);
    for r in &p.rules {
        let cs: Vec<(i32, &str, bool)> = r.iter().map(|&(i, pos)| (0, k.basis[i].as_str(), pos)).collect();
        rules.append((empty.clone(), PyTuple::new(py, cs)?))?;
    }
    let clauses = PyList::empty(py);
    for c in &p.clauses {
        let lits: Vec<(i32, usize, bool)> = c.iter().map(|&(i, n)| (0, i, n)).collect();
        let preds: Vec<usize> = c.iter().map(|&(i, _)| i).collect();
        let internal: Vec<(i32, usize)> = c.iter().map(|&(i, n)| (0, 2 * i + n as usize)).collect();
        clauses.append((PyTuple::new(py, lits)?, PyFrozenSet::new(py, preds)?, PyTuple::new(py, internal)?))?;
    }
    (rules, clauses, !p.clauses.is_empty(), p.complete).into_bound_py_any(py)
}

#[pymethods]
impl PyKnowledge {
    #[new]
    fn new(data: &PyOfflineData) -> PyResult<Self> {
        Rules::load(&data.0).map(PyKnowledge).map_err(PyValueError::new_err)
    }

    /// `symbol_units` or `constant_units` of input term `t`, from its row: (rules, clauses, used, complete).
    /// ValueError if the term has no row, which the caller treats as a fault, not as a reason to stay on Python.
    fn atom_units<'py>(&self, py: Python<'py>, table: &PyTermTable, t: u32) -> PyResult<Bound<'py, PyAny>> {
        let k = &self.0;
        let row = table.0.atoms.get(&TermId(t)).ok_or_else(|| PyValueError::new_err(format!("no atom row: {t}")))?;
        let mut facts: Vec<(&str, bool)> = Vec::with_capacity(k.const_basis.len());
        match row {
            AtomRow::Symbol(items) => {
                for &(name, value) in items {
                    let name = table.0.strings[name as usize].as_str();
                    if let (true, Some(v)) = (k.in_vocab(name) && name != "commutative", value) {
                        facts.push((name, v));
                    }
                }
            }
            AtomRow::Constant(values) => {
                if values.len() != k.const_basis.len() {
                    return Err(PyValueError::new_err(format!("atom row {t}: {} values", values.len())));
                }
                for (name, value) in k.const_basis.iter().zip(values) {
                    if let Some(v) = value {
                        facts.push((name.as_str(), *v));
                    }
                }
            }
        }
        let p = k.units(&facts).map_err(PyValueError::new_err)?;
        pattern(py, k, &p)
    }

    /// The same for facts Python read off a node that isn't an input term: `[(pred, value), ...]`, already filtered.
    fn units<'py>(&self, py: Python<'py>, facts: Vec<(String, bool)>) -> PyResult<Bound<'py, PyAny>> {
        let f: Vec<(&str, bool)> = facts.iter().map(|(p, v)| (p.as_str(), *v)).collect();
        let p = self.0.units(&f).map_err(PyValueError::new_err)?;
        pattern(py, &self.0, &p)
    }

    fn const_basis(&self) -> Vec<String> {
        self.0.const_basis.clone()
    }

    fn in_vocab(&self, pred: &str) -> bool {
        self.0.in_vocab(pred)
    }
}

#[pyfunction]
fn sha256_hex(data: &[u8]) -> String {
    offline::sha256(data)
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyOfflineData>()?;
    m.add_class::<PyTermTable>()?;
    m.add_class::<PyKnowledge>()?;
    m.add("TermRefuse", m.py().get_type::<TermRefuse>())?;
    m.add_function(wrap_pyfunction!(sha256_hex, m)?)?;
    Ok(())
}
