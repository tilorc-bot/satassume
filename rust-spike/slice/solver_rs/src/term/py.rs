//! The Python face of the term module. Python holds ints; nothing here keeps state across queries.
use super::lra_read::{self, items_py, Constraint, Lra, E as LraErr};
use std::collections::HashMap;
use super::tcore;
use super::tf6;
use super::knowledge::{self, Rules, UnitPattern};
use super::offline;
use super::rat::Rat;
use super::table::{Kind, Read, Reads, Refuse, TermTable, READ_RAISED, V};
use super::TermId;
use crate::constfield::Num;
use num_bigint::BigInt;
use pyo3::create_exception;
use pyo3::exceptions::{PyBaseException, PyException, PyKeyError, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyFrozenSet, PyList, PyTuple};
use pyo3::IntoPyObjectExt;

// A BaseException, so that none of the `except Exception` handlers on the engine's path can turn a refusal into a quiet
// answer: `term_live.py` lists them. Only the top of the run catches it.
create_exception!(sa_solver, TermRefuse, PyBaseException, "Rust refuses this query: it goes back to Python.");

thread_local! {
    /// What a read raised, between the callback and `refuse`: `Refuse` is a plain reason, so it can't carry it.
    static RAISED: std::cell::RefCell<Option<PyErr>> = const { std::cell::RefCell::new(None) };
}

pub(crate) fn refuse(r: Refuse) -> PyErr {
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

fn lra_err(py: Python<'_>, e: LraErr) -> PyErr {
    match e {
        LraErr::Unread => PyValueError::new_err("lra: an unread term reached the top"),
        LraErr::Refuse(r) => refuse(r),
        LraErr::Py(x) => x,
        LraErr::Cf(x) => x.py_err(py).unwrap_or_else(|f| f),
    }
}

#[pyfunction]
fn lra_plant(p: u8) {
    lra_read::PLANT.store(p, std::sync::atomic::Ordering::Relaxed);
}

/// Python reads and construction on this path, process-wide.
#[pyfunction]
fn lra_counts<'py>(py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
    use std::sync::atomic::Ordering::Relaxed;
    let c = &lra_read::COUNTS;
    let d = PyDict::new(py);
    d.set_item("registry", c.registry.load(Relaxed))?;
    d.set_item("generic", c.generic.load(Relaxed))?;
    d.set_item("bounds", c.bounds.load(Relaxed))?;
    d.set_item("closed_mul_direct", c.closed_mul_direct.load(Relaxed))?;
    d.set_item("closed_mul_rust", c.closed_mul_rust.load(Relaxed))?;
    d.set_item("closed_mul_scaffold", c.closed_mul_scaffold.load(Relaxed))?;
    d.set_item("product_terms", c.product_terms.load(Relaxed))?;
    d.set_item("keys", c.keys.load(Relaxed))?;
    d.set_item("num_python", crate::constfield::NUM_PY.load(Relaxed))?;
    for (why, n) in lra_read::SCAFFOLD_WHY.lock().unwrap().iter() {
        d.set_item(format!("closed_mul_scaffold:{why}"), *n)?;
    }
    Ok(d)
}

#[pyclass(name = "TermTable", unsendable)]
pub struct PyTermTable(TermTable, HashMap<(u8, u32, u32, bool), LraMemo>, HashMap<(u64, u32), (Py<PyAny>, u32)>);

/// One `lra_*` result as Rust values (Element._new step): no Python object in the memo.
pub enum LraMemo {
    No,
    Interpret(Constraint, Vec<TermId>),
    Sides((Vec<(TermId, Num)>, i8), (Vec<(TermId, Num)>, i8)),
    Integral(Vec<(TermId, Num)>, Num, Vec<TermId>),
}

/// Plant 118: a memo hit gives a wrong number (one more), never a missing entry.
fn plus1(x: &Num, plant: bool) -> PyResult<Num> {
    if plant { Ok(x.add(&Num::one())?) } else { Ok(x.clone()) }
}

fn items_plant<'py>(py: Python<'py>, items: &[(TermId, Num)], plant: bool) -> PyResult<Bound<'py, PyList>> {
    if !plant || items.is_empty() {
        return items_py(py, items);
    }
    let mut v = items.to_vec();
    v[0].1 = plus1(&v[0].1, true)?;
    items_py(py, &v)
}

impl LraMemo {
    fn to_py<'py>(&self, py: Python<'py>, plant: bool) -> PyResult<Bound<'py, PyAny>> {
        let ids = |ts: &[TermId]| -> Vec<u32> { ts.iter().map(|x| x.0).collect() };
        match self {
            LraMemo::No => Ok(py.None().into_bound(py)),
            LraMemo::Interpret(c, terms) => {
                let c = match c {
                    Constraint::Value(v) => v.into_bound_py_any(py)?,
                    Constraint::Payload { items, rhs, strict, equality, positive } => {
                        (items_py(py, items)?, plus1(rhs, plant)?.to_py(py)?, *strict, *equality, *positive).into_bound_py_any(py)?
                    }
                };
                (c, ids(terms)).into_bound_py_any(py)
            }
            LraMemo::Sides(x, y) => ((items_plant(py, &x.0, plant)?, x.1), (items_py(py, &y.0)?, y.1)).into_bound_py_any(py),
            LraMemo::Integral(items, c, keys) => (items_py(py, items)?, plus1(c, plant)?.to_py(py)?, ids(keys)).into_bound_py_any(py),
        }
    }
}

/// The link's memo and the row reads made after it (`relations_core.rs`). The memo sits here so it dies with the query.
impl PyTermTable {
    /// The table itself, for Rust callers that hold the query's `TermTable` object (rows_tpl.rs's direct core calls).
    pub(crate) fn tt(&self) -> &TermTable {
        &self.0
    }

    /// 6g(c7): the table for rows_tpl.rs's `_cosh_shift_split`, which adds `r`'s sum as `knowledge_f6_live`'s shell does.
    pub(crate) fn tt_mut(&mut self) -> &mut TermTable {
        &mut self.0
    }

    /// The id for `(session, node)` if the memo holds `x` itself; `Err(())` if it holds another object for that node.
    pub(crate) fn link_get(&self, session: u64, nid: u32, x: &Bound<'_, PyAny>) -> Result<Option<u32>, ()> {
        match self.2.get(&(session, nid)) {
            Some((o, t)) if o.bind(x.py()).is(x) => Ok(Some(*t)),
            Some(_) => Err(()),
            None => Ok(None),
        }
    }

    pub(crate) fn link_put(&mut self, session: u64, nid: u32, x: &Bound<'_, PyAny>, t: u32) {
        self.2.insert((session, nid), (x.clone().unbind(), t));
    }

    pub(crate) fn read_is_rational(&self, t: u32) -> bool {
        self.0.class_of(TermId(t)).flags & super::table::flag::IS_RATIONAL != 0
    }

    pub(crate) fn read_is_number(&self, t: u32) -> bool {
        self.0.is_number_term(TermId(t))
    }

    pub(crate) fn read_is_nan(&self, t: u32) -> bool {
        self.0.class_of(TermId(t)).kind == Kind::NaN
    }

    pub(crate) fn read_structural(&self, t: u32) -> bool {
        self.0.structural(TermId(t))
    }
}

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

/// A plan step for Python: `(ensure, clause)`, one of them set. A literal is `(negated, pred or None, term)`; None is the
/// atom's own var.
type PlanRow = (Option<(u32, Vec<&'static str>)>, Vec<(bool, Option<&'static str>, u32)>);

fn plan_rows(plan: &[super::relations::PlanOp]) -> Vec<PlanRow> {
    use super::relations::PlanOp;
    plan.iter()
        .map(|op| match op {
            PlanOp::Ensure(t, preds) => (Some((t.0, preds.clone())), vec![]),
            PlanOp::Clause(lits) => (
                None,
                lits.iter()
                    .map(|(neg, l)| match l {
                        Some((p, t)) => (*neg, Some(*p), t.0),
                        None => (*neg, None, 0),
                    })
                    .collect(),
            ),
        })
        .collect()
}

fn ids_of(v: Vec<u32>) -> Vec<TermId> {
    v.into_iter().map(TermId).collect()
}

fn raw_ids(v: Vec<TermId>) -> Vec<u32> {
    v.into_iter().map(|t| t.0).collect()
}

impl PyTermTable {
    /// The per-query memo that takes `_INTERPRETED`'s place on this path: it dies with the table.
    /// Element._new step: the memo holds Rust values, and each call builds its Python result from them, so no Python object
    /// is kept for the query and the numbers cross as the Rust `Element` pyclass (constfield.rs `PyElem`).
    fn lra_memo<'py>(
        &mut self,
        py: Python<'py>,
        key: (u8, u32, u32, bool),
        f: impl FnOnce(&mut TermTable) -> PyResult<LraMemo>,
    ) -> PyResult<Bound<'py, PyAny>> {
        if let Some(v) = self.1.get(&key) {
            crate::session::tick(crate::session::LRA_MEMO_HIT);
            return v.to_py(py, crate::relations_core::planted(crate::relations_core::ELEM_MEMO_PLUS1));
        }
        crate::session::tick(crate::session::LRA_MEMO_MISS);
        let v = f(&mut self.0)?;
        let out = v.to_py(py, false);
        self.1.insert(key, v);
        out
    }
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
        .map(|t| PyTermTable(t, HashMap::new(), HashMap::new()))
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

    /// `_is_number` of a term.
    fn is_number_term(&self, t: u32) -> bool {
        self.0.is_number_term(TermId(t))
    }

    /// The sides of `relation_atom`'s eq atom, stripped and in order. Raises TermRefuse.
    fn eq_sides(&mut self, l: u32, r: u32) -> PyResult<(u32, u32)> {
        self.0.eq_sides(TermId(l), TermId(r)).map(|(a, b)| (a.0, b.0)).map_err(refuse)
    }

    /// `_termwise(a, b, d)`. Raises TermRefuse.
    fn termwise(&mut self, a: u32, b: u32, d: u32) -> PyResult<bool> {
        self.0.termwise(TermId(a), TermId(b), TermId(d)).map_err(refuse)
    }

    /// `_eq_links`'s difference `p - q`, or None when it isn't used. Raises TermRefuse.
    fn eq_diff(&mut self, p: u32, q: u32) -> PyResult<Option<u32>> {
        self.0.eq_diff(TermId(p), TermId(q)).map(|d| d.map(|t| t.0)).map_err(refuse)
    }

    /// `relation_atom`'s lt, gt, le, ge: None for a nan side under le or ge, else (first, second, negated, ext), positions
    /// in `(lhs, rhs)`. Raises TermRefuse.
    fn order_relation(&self, name: &str, l: u32, r: u32) -> PyResult<Option<(usize, usize, bool, Vec<usize>)>> {
        self.0
            .order_relation(name, TermId(l), TermId(r))
            .map(|o| o.map(|o| (o.first, o.second, o.negated, o.ext)))
            .map_err(refuse)
    }

    /// `_ext_atoms`' test on one side.
    fn needs_ext(&self, t: u32) -> bool {
        self.0.needs_ext(TermId(t))
    }

    /// `_eq_links`' plan: see `plan_rows`. Raises TermRefuse.
    fn eq_links_plan(&mut self, a: u32, b: u32) -> PyResult<Vec<PlanRow>> {
        self.0.eq_links_plan(TermId(a), TermId(b)).map(|p| plan_rows(&p)).map_err(refuse)
    }

    /// `scope.affine_pair`, given each sign atom's argument.
    fn affine_pair(&self, signs: Vec<u32>) -> bool {
        self.0.affine_pair(&ids_of(signs))
    }

    /// `_under_apps` of the sides, or None when a side's class has its own `atoms`.
    fn under_apps(&self, sides: Vec<u32>) -> Option<Vec<u32>> {
        self.0.under_apps(&ids_of(sides)).map(raw_ids)
    }

    /// `euf_adapter.structural`.
    fn structural(&self, t: u32) -> bool {
        self.0.structural(TermId(t))
    }

    /// `EUFAdapter.interned`, in its order.
    fn interned(&self, exprs: Vec<u32>) -> Vec<u32> {
        raw_ids(self.0.interned(&ids_of(exprs)))
    }

    /// `relations._structural_subterms`, in its order.
    fn structural_subterms(&self, e: u32) -> Vec<u32> {
        raw_ids(self.0.structural_subterms(TermId(e)))
    }

    /// `n_input`: rows from conversion; later ids are derived.
    #[getter]
    fn n_input(&self) -> usize {
        self.0.n_input
    }

    /// `lra_adapter.interpret` after `relation`: None, or `(constraint, term ids)`.
    fn lra_interpret<'py>(
        &mut self,
        py: Python<'py>,
        name: &str,
        a: u32,
        b: u32,
        generic: bool,
        objects: Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let n = ["lt", "le", "gt", "ge", "eq", "ne"].iter().position(|x| *x == name);
        let n = n.ok_or_else(|| PyValueError::new_err("not a relation name"))? as u8;
        self.lra_memo(py, (n, a, b, generic), |t| {
            let mut l = Lra { t, py, objects, generic };
            let Some((c, terms)) = l.interpret(name, TermId(a), TermId(b)).map_err(|e| lra_err(py, e))? else {
                return Ok(LraMemo::No);
            };
            Ok(LraMemo::Interpret(c, terms))
        })
    }

    /// `lra_adapter.order_sides` after `relation`: None, or two `(items, inf)`.
    fn lra_order_sides<'py>(
        &mut self,
        py: Python<'py>,
        a: u32,
        b: u32,
        generic: bool,
        objects: Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyAny>> {
        self.lra_memo(py, (6, a, b, generic), |t| {
            let mut l = Lra { t, py, objects, generic };
            let Some((x, y)) = l.order_sides(TermId(a), TermId(b)).map_err(|e| lra_err(py, e))? else {
                return Ok(LraMemo::No);
            };
            Ok(LraMemo::Sides((x.0.items, x.1), (y.0.items, y.1)))
        })
    }

    /// `lra_adapter.integer_form`: None, or `(items, constant, key ids)`.
    fn lra_integer_form<'py>(
        &mut self,
        py: Python<'py>,
        e: u32,
        generic: bool,
        objects: Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyAny>> {
        self.lra_memo(py, (7, e, 0, generic), |t| {
            let mut l = Lra { t, py, objects, generic };
            let Some((items, c, keys)) = l.integer_form(TermId(e)).map_err(|e| lra_err(py, e))? else {
                return Ok(LraMemo::No);
            };
            Ok(LraMemo::Integral(items, c, keys))
        })
    }

    /// `lra_adapter.closed_sign`: `(sign, real)`.
    fn lra_closed_sign<'py>(
        &mut self,
        py: Python<'py>,
        e: u32,
        generic: bool,
        objects: Bound<'py, PyAny>,
    ) -> PyResult<(Option<i32>, bool)> {
        let mut l = Lra { t: &mut self.0, py, objects, generic };
        l.closed_sign(TermId(e)).map_err(|e| lra_err(py, e))
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
pub struct PyKnowledge(pub(crate) Rules);

pub(crate) fn pattern<'py>(py: Python<'py>, k: &Rules, p: &UnitPattern) -> PyResult<Bound<'py, PyAny>> {
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
    // `used` holds a slot with a literal: an empty clause (units contradicting a kept clause) gives none, as in Python.
    let used = p.clauses.iter().any(|c| !c.is_empty());
    (rules, clauses, used, p.complete).into_bound_py_any(py)
}

/// A template's rules, from any iterable of `(premises, conclusions)`.
pub(crate) fn extract_rules(rules: &Bound<'_, PyAny>) -> PyResult<Vec<knowledge::Rule>> {
    rules.try_iter()?.map(|r| r?.extract()).collect()
}

#[pymethods]
impl PyKnowledge {
    #[new]
    fn new(data: &PyOfflineData) -> PyResult<Self> {
        Rules::load(&data.0).map(PyKnowledge).map_err(PyValueError::new_err)
    }

    /// `symbol_units` of input term `t`, reading it now: (rules, clauses, used, complete). An Exception from the read is a
    /// TermRefuse and anything past Exception goes on up as itself; both go past the caller to the top of the run.
    fn symbol_units<'py>(&self, py: Python<'py>, table: &PyTermTable, t: u32) -> PyResult<Bound<'py, PyAny>> {
        let k = &self.0;
        let items = table.0.symbol_facts(TermId(t)).map_err(refuse)?;
        let mut facts: Vec<(&str, bool)> = Vec::with_capacity(items.len());
        for (name, value) in &items {
            if let (true, Some(v)) = (k.in_vocab(name) && &**name != "commutative", value) {
                facts.push((name, *v));
            }
        }
        let p = k.units(&facts).map_err(PyValueError::new_err)?;
        pattern(py, k, &p)
    }

    /// `constant_units` of input term `t`, reading it now. As `symbol_units`.
    fn constant_units<'py>(&self, py: Python<'py>, table: &PyTermTable, t: u32) -> PyResult<Bound<'py, PyAny>> {
        let k = &self.0;
        let values = table.0.constant_facts(TermId(t)).map_err(refuse)?;
        if values.len() != k.const_basis.len() {
            return Err(PyValueError::new_err(format!("constant read {t}: {} values", values.len())));
        }
        let facts: Vec<(&str, bool)> =
            k.const_basis.iter().zip(&values).filter_map(|(name, v)| v.map(|v| (name.as_str(), v))).collect();
        let p = k.units(&facts).map_err(PyValueError::new_err)?;
        pattern(py, k, &p)
    }

    /// The same for facts Python read off a node that isn't an input term: `[(pred, value), ...]`, already filtered.
    fn units<'py>(&self, py: Python<'py>, facts: Vec<(String, bool)>) -> PyResult<Bound<'py, PyAny>> {
        let f: Vec<(&str, bool)> = facts.iter().map(|(p, v)| (p.as_str(), *v)).collect();
        let p = self.0.units(&f).map_err(PyValueError::new_err)?;
        pattern(py, &self.0, &p)
    }

    /// `_common.resolve`: `read(slot, pred)` is called where Python calls `const_value`, and what it raises comes through as
    /// itself. None is "template asserts a contradiction", for the caller to raise. Raises TermRefuse on a read that isn't a
    /// bool or None.
    fn resolve<'py>(
        &self,
        py: Python<'py>,
        rules: &Bound<'py, PyAny>,
        const_slots: Vec<i64>,
        read: &Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let rules = extract_rules(rules)?;
        let r = knowledge::resolve(
            &rules,
            |k| const_slots.contains(&k),
            |k, pred| -> PyResult<Option<bool>> {
                read.call1((k, pred))?.extract().map_err(|e: PyErr| PyTypeError::new_err(format!("const_value of {pred}: {e}")))
            },
        )?;
        match r {
            None => Ok(py.None().into_bound(py)),
            Some(rs) => {
                let out = PyList::empty(py);
                for (ps, cs) in &rs {
                    out.append((PyTuple::new(py, ps)?, PyTuple::new(py, cs)?))?;
                }
                Ok(out.into_any())
            }
        }
    }

    /// `Pattern.__init__`: (clauses, used, child_preds, indices of the wide rules). An unknown predicate is a KeyError, as `cnf_of`'s.
    fn build_pattern<'py>(
        &self,
        py: Python<'py>,
        rules: &Bound<'py, PyAny>,
        node: i64,
        max_expand: u64,
    ) -> PyResult<Bound<'py, PyAny>> {
        let rules = extract_rules(rules)?;
        let p = self.0.build_pattern(&rules, node, max_expand as u128).map_err(PyKeyError::new_err)?;
        let clauses = PyList::empty(py);
        for c in &p.clauses {
            let preds: Vec<usize> = c.iter().filter(|l| l.0 == node).map(|l| l.1).collect();
            let internal: Vec<(i64, usize)> = c.iter().map(|&(k, i, n)| (k, 2 * i + n as usize)).collect();
            clauses.append((PyTuple::new(py, c)?, PyFrozenSet::new(py, preds)?, PyTuple::new(py, internal)?))?;
        }
        let child_preds = PyDict::new(py);
        for (k, v) in &p.child_preds {
            child_preds.set_item(k, PyFrozenSet::new(py, v)?)?;
        }
        (clauses, PyTuple::new(py, &p.used)?, child_preds, p.wide).into_bound_py_any(py)
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

// ---- core.py (step 6e): splits over ids, rule builders over small ints and rationals. `knowledge_live.py` builds the keys.

fn core_ct<'py>(py: Python<'py>, ct: &tcore::CoeffTerm) -> PyResult<(Option<u32>, Bound<'py, PyAny>)> {
    let t = match &ct.1 {
        tcore::Rest::One(t) => t.0.into_bound_py_any(py)?,
        tcore::Rest::Product(fs) => fs.iter().map(|f| f.0).collect::<Vec<u32>>().into_bound_py_any(py)?,
    };
    Ok((ct.0.map(|c| c.0), t))
}

fn core_ids(ids: Vec<u32>) -> Vec<TermId> {
    ids.into_iter().map(TermId).collect()
}

fn core_rat(p: BigInt, q: BigInt) -> PyResult<Rat> {
    if q == BigInt::from(0) {
        return Err(PyValueError::new_err("core: zero denominator"));
    }
    Ok(Rat::new(p, q))
}

/// `_half_split`: `(a0, [(a_k % 2, c_k, t_k)])`, `c_k` an id or None for 1, `t_k` an id or a list of factor ids for Python's
/// `kept_product`.
#[pyfunction]
#[allow(clippy::type_complexity)]
fn core_half_split<'py>(
    py: Python<'py>,
    table: &PyTermTable,
    args: Vec<u32>,
) -> PyResult<Option<(u8, Vec<(u8, Option<u32>, Bound<'py, PyAny>)>)>> {
    let Some((a0, terms)) = table.0.core_half_split(&core_ids(args)).map_err(refuse)? else { return Ok(None) };
    let mut out = Vec::with_capacity(terms.len());
    for (a, ct) in &terms {
        let (c, t) = core_ct(py, ct)?;
        out.push((*a, c, t));
    }
    Ok(Some((a0, out)))
}

/// `_bound_split`: `(c0, c, t)` as `core_half_split` gives its terms.
#[pyfunction]
fn core_bound_split<'py>(
    py: Python<'py>,
    table: &PyTermTable,
    args: Vec<u32>,
) -> PyResult<Option<(u32, Option<u32>, Bound<'py, PyAny>)>> {
    let Some((c0, ct)) = table.0.core_bound_split(&core_ids(args)).map_err(refuse)? else { return Ok(None) };
    let (c, t) = core_ct(py, &ct)?;
    Ok(Some((c0.0, c, t)))
}

#[pyfunction]
fn core_recip_base(table: &PyTermTable, u: u32) -> PyResult<Option<u32>> {
    table.0.core_recip_base(TermId(u)).map(|x| x.map(|v| v.0)).map_err(refuse)
}

#[pyfunction]
#[allow(clippy::type_complexity)]
fn core_imag_split(table: &PyTermTable, args: Vec<u32>) -> PyResult<Option<Vec<(Option<u32>, Option<u32>)>>> {
    let r = table.0.core_imag_split(&core_ids(args)).map_err(refuse)?;
    Ok(r.map(|ts| ts.into_iter().map(|(c, x)| (c.map(|v| v.0), x.map(|v| v.0))).collect()))
}

#[pyfunction]
fn core_is_number(table: &PyTermTable, t: u32) -> PyResult<bool> {
    table.0.core_is_number(TermId(t)).map_err(refuse)
}

/// Rust's side of `kept_product(factors)`: `mul`'s product, if it is a Mul that keeps exactly these factors. Raises
/// TermRefuse where `mul` refuses.
#[pyfunction]
fn core_kept_product(mut table: PyRefMut<'_, PyTermTable>, factors: Vec<u32>) -> PyResult<Option<u32>> {
    let fs = core_ids(factors);
    let t = table.0.mul(fs.clone()).map_err(refuse)?;
    let row = table.0.row(t);
    if table.0.class_of(t).kind != Kind::Mul || row.args.len() != fs.len() {
        return Ok(None);
    }
    let (mut a, mut b): (Vec<u32>, Vec<u32>) = (row.args.iter().map(|x| x.0).collect(), fs.iter().map(|x| x.0).collect());
    a.sort_unstable();
    b.sort_unstable();
    Ok(if a == b { Some(t.0) } else { None })
}

#[pyfunction]
fn core_half_rules(a0: u8, odd: Vec<bool>, m: usize) -> PyResult<Vec<tcore::Rule>> {
    if odd.len() < m {
        return Err(PyValueError::new_err("core: odd shorter than m"));
    }
    Ok(tcore::half_rules(a0, &odd, m))
}

#[pyfunction]
fn core_bound_rules(p0: BigInt, q0: BigInt, p1: BigInt, q1: BigInt) -> PyResult<Vec<tcore::Rule>> {
    Ok(tcore::bound_rules(&core_rat(p0, q0)?, &core_rat(p1, q1)?))
}

#[pyfunction]
fn core_recip_rules(p0: BigInt, q0: BigInt, p1: BigInt, q1: BigInt) -> PyResult<Vec<tcore::Rule>> {
    Ok(tcore::recip_rules(&core_rat(p0, q0)?, &core_rat(p1, q1)?))
}

#[pyfunction]
fn core_imag_rules(signs: Vec<i8>, c_pos: bool, c_neg: bool) -> Vec<tcore::Rule> {
    tcore::imag_rules(&signs, c_pos, c_neg)
}

#[pyfunction]
fn core_imag_number_rules() -> Vec<tcore::Rule> {
    tcore::imag_number_rules()
}

/// Indices into `_INT_BOUNDS`.
#[pyfunction]
fn core_not_unit_premises(p0: BigInt, q0: BigInt, p1: BigInt, q1: BigInt) -> PyResult<Vec<usize>> {
    Ok(tcore::not_unit_premises(&core_rat(p0, q0)?, &core_rat(p1, q1)?))
}

fn core_rest<'py>(py: Python<'py>, r: &tcore::Rest) -> PyResult<Bound<'py, PyAny>> {
    core_ct(py, &(None, r.clone())).map(|x| x.1)
}

pub(crate) fn core_pq(r: &Rat) -> (BigInt, BigInt) {
    (r.n.clone(), r.d.clone())
}

/// `_pi_split(arg, imag)`: `((p, q), s)`, `s` None, an id, or a list of factor ids for Python's `kept_product`.
#[pyfunction]
#[allow(clippy::type_complexity)]
fn core_pi_split<'py>(
    py: Python<'py>,
    table: &PyTermTable,
    arg: u32,
    imag: bool,
) -> PyResult<Option<((BigInt, BigInt), Option<Bound<'py, PyAny>>)>> {
    let Some((c, s)) = table.0.core_pi_split(TermId(arg), imag).map_err(refuse)? else { return Ok(None) };
    let s = match &s {
        Some(r) => Some(core_rest(py, r)?),
        None => None,
    };
    Ok(Some((core_pq(&c), s)))
}

/// `_mul_factor_sets`' derived sets: `((c, rest factor ids) or None, ((p, q), s) or None)`, `s` as `core_pi_split` gives it.
#[pyfunction]
#[allow(clippy::type_complexity)]
fn core_mul_factor_sets<'py>(
    py: Python<'py>,
    table: &PyTermTable,
    expr: u32,
) -> PyResult<(Option<(u32, Vec<u32>)>, Option<((BigInt, BigInt), Bound<'py, PyAny>)>)> {
    let (ct, ipi) = table.0.core_mul_factor_sets(TermId(expr)).map_err(refuse)?;
    let ct = ct.map(|(c, fs)| (c.0, fs.iter().map(|f| f.0).collect()));
    let ipi = match &ipi {
        Some((c, r)) => Some((core_pq(c), core_rest(py, r)?)),
        None => None,
    };
    Ok((ct, ipi))
}

#[pyfunction]
fn core_quotient_shape(table: &PyTermTable, expr: u32) -> PyResult<Option<(u32, u32, u32)>> {
    let r = table.0.core_quotient_shape(TermId(expr)).map_err(refuse)?;
    Ok(r.map(|(a, v, t)| (a.0, v.0, t.0)))
}

#[pyfunction]
fn core_quotient_rules() -> Vec<tcore::Rule> {
    tcore::quotient_rules()
}

#[pyfunction]
fn core_unit_angle(table: &PyTermTable, b: u32) -> PyResult<Option<(BigInt, BigInt)>> {
    Ok(table.0.core_unit_angle(TermId(b)).map_err(refuse)?.map(|r| core_pq(&r)))
}

#[pyfunction]
fn core_exp_arg(table: &PyTermTable, b: u32) -> PyResult<Option<u32>> {
    Ok(table.0.core_exp_arg(TermId(b)).map_err(refuse)?.map(|u| u.0))
}

#[pyfunction]
fn core_irrational_root(table: &PyTermTable, b: u32, e: u32) -> PyResult<bool> {
    table.0.core_irrational_root(TermId(b), TermId(e)).map_err(refuse)
}

#[pyfunction]
fn core_pow_bound_shape(table: &PyTermTable, expr: u32) -> PyResult<Option<(u32, u32)>> {
    Ok(table.0.core_pow_bound_shape(TermId(expr)).map_err(refuse)?.map(|(b, e)| (b.0, e.0)))
}

/// `_pow_bound_templates`' rules over indices into `_INT_BOUNDS`.
#[pyfunction]
fn core_pow_bound_rules(prems: Vec<usize>) -> PyResult<Vec<tcore::Rule>> {
    if prems.iter().any(|&i| i >= tcore::INT_BOUNDS.len()) {
        return Err(PyValueError::new_err("core: premise index out of range"));
    }
    Ok(tcore::pow_bound_rules(&prems))
}

/// `_unit_power_units` for a Rational exponent: `(predicate, value)` facts, or None for another exponent.
#[pyfunction]
fn core_unit_power_units(
    table: &PyTermTable,
    p: BigInt,
    q: BigInt,
    e: u32,
) -> PyResult<Option<Vec<(&'static str, bool)>>> {
    table.0.core_unit_power_units(&core_rat(p, q)?, TermId(e)).map_err(refuse)
}

#[pyfunction]
#[pyo3(signature = (p, q, s, n))]
fn core_ipi_rules(p: BigInt, q: BigInt, s: Option<usize>, n: usize) -> PyResult<Vec<tcore::Rule>> {
    Ok(tcore::ipi_rules(&core_rat(p, q)?, s, n))
}

// ---- Step 6f: functions, special, rootof, nodes, physics, stats (`tf6.rs`). `knowledge_f6_live.py` builds keys and literals.

fn f6_rest<'py>(py: Python<'py>, s: &Option<tcore::Rest>) -> PyResult<Option<Bound<'py, PyAny>>> {
    match s {
        Some(r) => Some(core_rest(py, r)).transpose(),
        None => Ok(None),
    }
}

#[pyfunction]
fn f6_pi_trig_rules(cos_: bool, p: BigInt, q: BigInt, has_s: bool) -> PyResult<Vec<tcore::Rule>> {
    Ok(tf6::pi_trig_rules(cos_, &core_rat(p, q)?, has_s))
}

#[pyfunction]
fn f6_cosh_shift_rules(p: BigInt, q: BigInt, has_s: bool) -> PyResult<Vec<tcore::Rule>> {
    let c = core_rat(p, q)?;
    if !c.is_int() {
        return Err(PyValueError::new_err("f6: _cosh_shift_rules of a non-integer c"));
    }
    Ok(tf6::cosh_shift_rules(&c, has_s))
}

#[pyfunction]
fn f6_parts_of_round_rules() -> Vec<tcore::Rule> {
    tf6::parts_of_round_rules()
}

#[pyfunction]
fn f6_genocchi_half_rules(h: usize) -> Vec<tcore::Rule> {
    tf6::genocchi_half_rules(h)
}

#[pyfunction]
fn f6_accum_rules() -> Vec<tcore::Rule> {
    tf6::accum_rules()
}

#[pyfunction]
fn f6_multigamma_rules(p: BigInt) -> Vec<tcore::Rule> {
    tf6::multigamma_rules(&p)
}

#[pyfunction]
fn f6_unit_interval_units(acos: bool, p: BigInt, q: BigInt) -> PyResult<Vec<(&'static str, bool)>> {
    Ok(tf6::unit_interval_units(acos, &core_rat(p, q)?))
}

#[pyfunction]
#[pyo3(signature = (coeffs, index))]
fn f6_rootof_facts(coeffs: Option<Vec<BigInt>>, index: BigInt) -> Vec<(&'static str, bool)> {
    tf6::rootof_facts(coeffs.as_deref(), &index)
}

#[pyfunction]
#[pyo3(signature = (positive, integer, real))]
fn f6_randomsymbol_units(positive: Option<bool>, integer: Option<bool>, real: bool) -> Vec<(&'static str, bool)> {
    tf6::randomsymbol_units(positive, integer, real)
}

#[pyfunction]
fn f6_const_units(tag: &str) -> PyResult<Vec<(&'static str, bool)>> {
    tf6::const_units(tag).ok_or_else(|| PyValueError::new_err("f6: unknown constant units tag"))
}

/// `_cosh_shift_split(arg)`: `(r, (p, q), s)`, `s` None, an id, or a list of factor ids for Python's `kept_product`.
#[pyfunction]
#[allow(clippy::type_complexity)]
fn f6_cosh_shift_split<'py>(
    py: Python<'py>,
    mut table: PyRefMut<'_, PyTermTable>,
    arg: u32,
) -> PyResult<Option<(u32, (BigInt, BigInt), Option<Bound<'py, PyAny>>)>> {
    let Some((r, c, s)) = table.0.f6_cosh_shift_split(TermId(arg)).map_err(refuse)? else { return Ok(None) };
    Ok(Some((r.0, core_pq(&c), f6_rest(py, &s)?)))
}

#[pyfunction]
fn f6_shifted(mut table: PyRefMut<'_, PyTermTable>, x: u32, p: BigInt, q: BigInt) -> PyResult<u32> {
    let c = core_rat(p, q)?;
    Ok(table.0.f6_shifted(TermId(x), &c).map_err(refuse)?.0)
}

#[pyfunction]
fn f6_doubled(mut table: PyRefMut<'_, PyTermTable>, x: u32) -> PyResult<u32> {
    Ok(table.0.f6_doubled(TermId(x)).map_err(refuse)?.0)
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyOfflineData>()?;
    m.add_class::<PyTermTable>()?;
    m.add_class::<PyKnowledge>()?;
    m.add("TermRefuse", m.py().get_type::<TermRefuse>())?;
    m.add_function(wrap_pyfunction!(sha256_hex, m)?)?;
    m.add_function(wrap_pyfunction!(lra_plant, m)?)?;
    m.add_function(wrap_pyfunction!(lra_counts, m)?)?;
    m.add_function(wrap_pyfunction!(core_half_split, m)?)?;
    m.add_function(wrap_pyfunction!(core_bound_split, m)?)?;
    m.add_function(wrap_pyfunction!(core_recip_base, m)?)?;
    m.add_function(wrap_pyfunction!(core_imag_split, m)?)?;
    m.add_function(wrap_pyfunction!(core_is_number, m)?)?;
    m.add_function(wrap_pyfunction!(core_kept_product, m)?)?;
    m.add_function(wrap_pyfunction!(core_half_rules, m)?)?;
    m.add_function(wrap_pyfunction!(core_bound_rules, m)?)?;
    m.add_function(wrap_pyfunction!(core_recip_rules, m)?)?;
    m.add_function(wrap_pyfunction!(core_imag_rules, m)?)?;
    m.add_function(wrap_pyfunction!(core_imag_number_rules, m)?)?;
    m.add_function(wrap_pyfunction!(core_not_unit_premises, m)?)?;
    m.add_function(wrap_pyfunction!(core_pi_split, m)?)?;
    m.add_function(wrap_pyfunction!(core_mul_factor_sets, m)?)?;
    m.add_function(wrap_pyfunction!(core_quotient_shape, m)?)?;
    m.add_function(wrap_pyfunction!(core_quotient_rules, m)?)?;
    m.add_function(wrap_pyfunction!(core_unit_angle, m)?)?;
    m.add_function(wrap_pyfunction!(core_exp_arg, m)?)?;
    m.add_function(wrap_pyfunction!(core_irrational_root, m)?)?;
    m.add_function(wrap_pyfunction!(core_pow_bound_shape, m)?)?;
    m.add_function(wrap_pyfunction!(core_pow_bound_rules, m)?)?;
    m.add_function(wrap_pyfunction!(core_unit_power_units, m)?)?;
    m.add_function(wrap_pyfunction!(core_ipi_rules, m)?)?;
    m.add_function(wrap_pyfunction!(f6_pi_trig_rules, m)?)?;
    m.add_function(wrap_pyfunction!(f6_cosh_shift_rules, m)?)?;
    m.add_function(wrap_pyfunction!(f6_parts_of_round_rules, m)?)?;
    m.add_function(wrap_pyfunction!(f6_genocchi_half_rules, m)?)?;
    m.add_function(wrap_pyfunction!(f6_accum_rules, m)?)?;
    m.add_function(wrap_pyfunction!(f6_multigamma_rules, m)?)?;
    m.add_function(wrap_pyfunction!(f6_unit_interval_units, m)?)?;
    m.add_function(wrap_pyfunction!(f6_rootof_facts, m)?)?;
    m.add_function(wrap_pyfunction!(f6_randomsymbol_units, m)?)?;
    m.add_function(wrap_pyfunction!(f6_const_units, m)?)?;
    m.add_function(wrap_pyfunction!(f6_cosh_shift_split, m)?)?;
    m.add_function(wrap_pyfunction!(f6_shifted, m)?)?;
    m.add_function(wrap_pyfunction!(f6_doubled, m)?)?;
    Ok(())
}
