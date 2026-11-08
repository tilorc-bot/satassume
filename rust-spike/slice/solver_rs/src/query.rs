//! Step 5c3: `Session`'s queries (`engine.py:506-545`, `852-935`, `1155-1220`): `query_lit`, `prepare_query`, `emit`,
//! `query_literal`, `_query_all`, `literal_of`, `_relations`, `_ensure_atoms`, `_ensure_twins`. As in 5c1 and 5c2, the
//! session's containers (`literals`, `relations`, the solver) stay Python objects that Python reads later, so state is
//! Python's by construction; every read and call Python makes, Rust makes in the same order. Methods of the session and its
//! solver are called by name, as Python calls them, so a subclass, a tracing wrapper or an instance patch is honoured.
//! Still Python, called back: `basis_lits`, `atoms_of`, `formula_literal` (the module globals), and the
//! `Relations` object's `note_formula` and `process` (5c4). Formula objects are read as Python reads them (`.pred`,
//! `.expr`, `isinstance(_, P)`, dict keys), counted callbacks until the formula step after 5c. `Session._glue_of` is Rust
//! since 5c6 (`session_glue.rs`), called directly.
use pyo3::exceptions::PyValueError;
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::types::{PyList, PySet, PyTuple};

use crate::relations_core::{
    planted, DROP_EA_ENSURE, DROP_EMIT, DROP_LO_DISCOVER, DROP_LO_MEMO, DROP_PREP_REL, DROP_PREP_TWINS, DROP_QA_MENTION, DROP_QL_MENTION,
    DROP_REL_PROCESS, DROP_TWINS_VAR, QL_SKIP_CONSISTENT, QUERY_LIT_TUPLE,
};
use crate::session::{
    tick, SES_EMIT, SES_ENSURE_ATOMS, SES_ENSURE_TWINS, SES_LITERAL_OF, SES_PREPARE_QUERY, SES_QUERY_ALL, SES_QUERY_LIT, SES_QUERY_LITERAL,
    SES_RELATIONS,
};

fn engine_mod(p: Python<'_>) -> PyResult<Bound<'_, PyModule>> {
    p.import(intern!(p, "satassume.engine"))
}

fn inconsistent(p: Python<'_>, msg: &str) -> PyErr {
    match engine_mod(p).and_then(|e| e.getattr(intern!(p, "InconsistentAssumptions"))).and_then(|c| c.call1((msg,))) {
        Ok(v) => PyErr::from_value(v),
        Err(e) => e,
    }
}

/// `raise InconsistentAssumptions(str(e)) from e` for a ValueError `e`; anything else passes through.
fn wrap_value_error(p: Python<'_>, e: PyErr) -> PyErr {
    if !e.is_instance_of::<PyValueError>(p) {
        return e;
    }
    let msg = match e.value(p).str() {
        Ok(s) => s.to_string(),
        Err(x) => return x,
    };
    let new = inconsistent(p, &msg);
    new.set_cause(p, Some(e));
    new
}

/// `{x}`
fn one_set<'py>(x: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PySet>> {
    PySet::new(x.py(), [x])
}

/// `Session.query_lit`.
pub(crate) fn query_lit<'py>(s: &Bound<'py, PyAny>, pred: &Bound<'py, PyAny>, node: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    tick(SES_QUERY_LIT);
    let p = s.py();
    let eng = engine_mod(p)?;
    let i = eng.getattr(intern!(p, "BASIS_INDEX"))?.call_method1(intern!(p, "get"), (pred,))?;
    if !i.is_none() {
        return s.call_method1(intern!(p, "node"), (node,))?.add(i);
    }
    let b: i64 = s.call_method1(intern!(p, "node"), (node,))?.extract()?;
    let r = eng.getattr(intern!(p, "basis_lits"))?.call1((pred,))?;
    let (op, ls) = (r.get_item(0)?, r.get_item(1)?);
    let mut lits: Vec<i64> = Vec::new();
    for l in ls.try_iter()? {
        let l: i64 = l?.extract()?;
        lits.push(if l > 0 { b + l - 1 } else { -(b - l - 1) });
    }
    let t = PyTuple::new(p, &lits)?;
    if lits.len() == 1 && !planted(QUERY_LIT_TUPLE) {
        return Ok(t.get_item(0)?);
    }
    Ok(PyTuple::new(p, [op, t.into_any()])?.into_any())
}

/// `Session.prepare_query`.
pub(crate) fn prepare_query<'py>(s: &Bound<'py, PyAny>, prop: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    tick(SES_PREPARE_QUERY);
    let p = s.py();
    let eng = engine_mod(p)?;
    if prop.is_instance(&eng.getattr(intern!(p, "P"))?)? {
        let pred = prop.getattr(intern!(p, "pred"))?;
        if eng.getattr(intern!(p, "PRED_INDEX"))?.contains(&pred)? {
            let expr = prop.getattr(intern!(p, "expr"))?;
            s.call_method1(intern!(p, "ensure"), (&expr, one_set(&pred)?))?;
            if !planted(DROP_PREP_TWINS) && s.call_method1(intern!(p, "_ensure_twins"), (PyTuple::new(p, [prop])?,))?.is_truthy()? {
                s.call_method0(intern!(p, "_flush"))?;
            }
            if !s.getattr(intern!(p, "relations"))?.is_none() && !planted(DROP_PREP_REL) {
                s.call_method1(intern!(p, "_relations"), (prop,))?;
            }
            // re-read, as Python's `proposition.pred` and `.expr` are read again here
            let (pred, expr) = (prop.getattr(intern!(p, "pred"))?, prop.getattr(intern!(p, "expr"))?);
            return s.call_method1(intern!(p, "query_lit"), (pred, expr));
        }
    }
    s.call_method1(intern!(p, "literal_of"), (prop,))
}

/// `Session.emit`.
pub(crate) fn emit(s: &Bound<'_, PyAny>, clause: &Bound<'_, PyAny>) -> PyResult<()> {
    tick(SES_EMIT);
    let p = s.py();
    if planted(DROP_EMIT) {
        return Ok(());
    }
    s.getattr(intern!(p, "solver"))?.call_method1(intern!(p, "add_clause"), (clause,))?;
    Ok(())
}

/// The head both `query_literal` and `_query_all` share: transfer sync, root propagation, `mention`.
fn head<'py>(s: &Bound<'py, PyAny>, mention: Bound<'py, PyAny>, plant: u8) -> PyResult<Bound<'py, PyAny>> {
    let p = s.py();
    let solver = s.getattr(intern!(p, "solver"))?;
    let xfer = s.getattr(intern!(p, "xfer"))?;
    if !xfer.is_none() {
        xfer.call_method0(intern!(p, "sync_transfer"))?;
    }
    if !solver.call_method0(intern!(p, "propagate"))?.is_truthy()? {
        return Err(inconsistent(p, "rule base or declared facts (templates) are inconsistent"));
    }
    if !planted(plant) {
        solver.call_method1(intern!(p, "mention"), (mention,))?;
    }
    Ok(solver)
}

/// `Session.query_literal`.
pub(crate) fn query_literal<'py>(
    s: &Bound<'py, PyAny>,
    lit: &Bound<'py, PyAny>,
    assumptions: &Bound<'py, PyAny>,
    search: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    tick(SES_QUERY_LITERAL);
    let p = s.py();
    if lit.get_type().is(p.get_type::<PyTuple>()) {
        let (op, ls) = (lit.get_item(0)?, lit.get_item(1)?);
        if op.eq(intern!(p, "|"))? {
            let neg = PyList::empty(p);
            for l in ls.try_iter()? {
                neg.append(l?.neg()?)?;
            }
            let r = s.call_method1(intern!(p, "_query_all"), (neg, assumptions, search))?;
            return if r.is_none() { Ok(r) } else { Ok((!r.is_truthy()?).into_pyobject(p)?.to_owned().into_any()) };
        }
        return s.call_method1(intern!(p, "_query_all"), (PyList::new(p, ls.try_iter()?.collect::<PyResult<Vec<_>>>()?)?, assumptions, search));
    }
    let solver = head(s, PyTuple::new(p, [lit])?.into_any(), DROP_QL_MENTION)?;
    let assumptions = PyList::new(p, assumptions.try_iter()?.collect::<PyResult<Vec<_>>>()?)?;
    let tf = |b: bool| -> PyResult<Bound<'py, PyAny>> { Ok(b.into_pyobject(p)?.to_owned().into_any()) };
    if !assumptions.is_empty() {
        let implied = solver.call_method1(intern!(p, "implied"), (&assumptions,))?;
        if implied.is_none() {
            return Err(inconsistent(p, "inconsistent assumptions"));
        }
        let set = PySet::new(p, implied.try_iter()?.collect::<PyResult<Vec<_>>>()?)?;
        let r = if set.contains(lit)? {
            Some(true)
        } else if set.contains(lit.neg()?)? {
            Some(false)
        } else {
            None
        };
        if let Some(r) = r {
            if !planted(QL_SKIP_CONSISTENT) && !solver.call_method1(intern!(p, "consistent"), (&assumptions,))?.is_truthy()? {
                return Err(inconsistent(p, "inconsistent assumptions"));
            }
            return tf(r);
        }
    } else {
        let v = solver.call_method1(intern!(p, "value"), (lit,))?;
        if !v.is_none() {
            return Ok(v);
        }
    }
    if !search.is_truthy()? {
        return Ok(p.None().into_bound(p));
    }
    solver.call_method1(intern!(p, "entails"), (lit, &assumptions)).map_err(|e| wrap_value_error(p, e))
}

/// `Session._query_all`.
pub(crate) fn query_all<'py>(
    s: &Bound<'py, PyAny>,
    ls: &Bound<'py, PyAny>,
    assumptions: &Bound<'py, PyAny>,
    search: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    tick(SES_QUERY_ALL);
    let p = s.py();
    let solver = head(s, ls.clone(), DROP_QA_MENTION)?;
    let assumptions = PyList::new(p, assumptions.try_iter()?.collect::<PyResult<Vec<_>>>()?)?;
    // None, False, True per literal, as Python's `vals`
    let mut vals: Vec<Option<bool>> = Vec::new();
    if !assumptions.is_empty() {
        let implied = solver.call_method1(intern!(p, "implied"), (&assumptions,))?;
        if implied.is_none() {
            return Err(inconsistent(p, "inconsistent assumptions"));
        }
        let set = PySet::new(p, implied.try_iter()?.collect::<PyResult<Vec<_>>>()?)?;
        for l in ls.try_iter()? {
            let l = l?;
            vals.push(if set.contains(&l)? {
                Some(true)
            } else if set.contains(l.neg()?)? {
                Some(false)
            } else {
                None
            });
        }
        let decided = vals.contains(&Some(false)) || vals.iter().all(|v| *v == Some(true));
        if decided && !solver.call_method1(intern!(p, "consistent"), (&assumptions,))?.is_truthy()? {
            return Err(inconsistent(p, "inconsistent assumptions"));
        }
    } else {
        for l in ls.try_iter()? {
            let v = solver.call_method1(intern!(p, "value"), (l?,))?;
            // `False in vals` and `all(vals)` compare by ==/truth: a solver returns None, True or False
            vals.push(if v.is_none() { None } else { Some(v.is_truthy()?) });
        }
    }
    let tf = |b: bool| -> PyResult<Bound<'py, PyAny>> { Ok(b.into_pyobject(p)?.to_owned().into_any()) };
    if vals.contains(&Some(false)) {
        return tf(false);
    }
    if vals.iter().all(|v| *v == Some(true)) {
        return tf(true);
    }
    if !search.is_truthy()? {
        return Ok(p.None().into_bound(p));
    }
    solver.call_method1(intern!(p, "entails_all"), (ls, &assumptions)).map_err(|e| wrap_value_error(p, e))
}

/// `Session.literal_of`.
pub(crate) fn literal_of<'py>(s: &Bound<'py, PyAny>, f: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    tick(SES_LITERAL_OF);
    let p = s.py();
    let lit = s.getattr(intern!(p, "literals"))?.call_method1(intern!(p, "get"), (f,))?;
    if !lit.is_none() {
        return Ok(lit);
    }
    s.call_method1(intern!(p, "_ensure_atoms"), (f,))?;
    let eng = engine_mod(p)?;
    let lit = eng.getattr(intern!(p, "formula_literal"))?.call1((
        f,
        s.getattr(intern!(p, "table"))?,
        s.getattr(intern!(p, "emit"))?,
        s.getattr(intern!(p, "dvar"))?,
    ))?;
    if !planted(DROP_LO_DISCOVER) {
        s.call_method0(intern!(p, "discover"))?;
    }
    if !s.getattr(intern!(p, "relations"))?.is_none() {
        s.call_method1(intern!(p, "_relations"), (f,))?;
    }
    if !planted(DROP_LO_MEMO) {
        s.getattr(intern!(p, "literals"))?.set_item(f, &lit)?;
    }
    Ok(lit)
}

/// `Session._relations`.
pub(crate) fn relations(s: &Bound<'_, PyAny>, f: &Bound<'_, PyAny>) -> PyResult<()> {
    tick(SES_RELATIONS);
    let p = s.py();
    let rel = s.getattr(intern!(p, "relations"))?;
    let atoms = engine_mod(p)?.getattr(intern!(p, "atoms_of"))?.call1((f,))?;
    rel.call_method1(intern!(p, "note_formula"), (&atoms,))?;
    if rel.getattr(intern!(p, "active"))?.is_truthy()? || rel.getattr(intern!(p, "queue"))?.is_truthy()? {
        let g = crate::session_glue::glue_of(s, &atoms)?;
        if !planted(DROP_REL_PROCESS) {
            rel.call_method1(intern!(p, "process"), (g,))?;
        }
    }
    Ok(())
}

/// `Session._ensure_atoms`.
pub(crate) fn ensure_atoms(s: &Bound<'_, PyAny>, f: &Bound<'_, PyAny>) -> PyResult<()> {
    tick(SES_ENSURE_ATOMS);
    let p = s.py();
    let eng = engine_mod(p)?;
    let atoms = eng.getattr(intern!(p, "atoms_of"))?.call1((f,))?;
    let pred_index = eng.getattr(intern!(p, "PRED_INDEX"))?;
    for atom in atoms.try_iter()? {
        let atom = atom?;
        let pred = atom.getattr(intern!(p, "pred"))?;
        if pred_index.contains(&pred)? && !planted(DROP_EA_ENSURE) {
            let (expr, pred) = (atom.getattr(intern!(p, "expr"))?, atom.getattr(intern!(p, "pred"))?);
            s.call_method1(intern!(p, "ensure"), (expr, one_set(&pred)?))?;
        }
    }
    s.call_method1(intern!(p, "_ensure_twins"), (atoms,))?;
    Ok(())
}

/// `Session._ensure_twins`.
pub(crate) fn ensure_twins(s: &Bound<'_, PyAny>, atoms: &Bound<'_, PyAny>) -> PyResult<bool> {
    tick(SES_ENSURE_TWINS);
    let p = s.py();
    if !s.getattr(intern!(p, "engine"))?.getattr(intern!(p, "_relation_specs"))?.is_truthy()? {
        return Ok(false);
    }
    let g = crate::session_glue::glue_of(s, atoms)?;
    if g.is(atoms) {
        return Ok(false);
    }
    let var = s.getattr(intern!(p, "table"))?.getattr(intern!(p, "var"))?;
    let n = atoms.len()?;
    let tail = g.get_item(pyo3::types::PySlice::new(p, n as isize, isize::MAX, 1))?;
    for atom in tail.try_iter()? {
        let atom = atom?;
        if !planted(DROP_TWINS_VAR) {
            var.call1((atom,))?;
        }
    }
    Ok(true)
}

#[pyfunction]
fn ses_query_lit<'py>(s: &Bound<'py, PyAny>, pred: &Bound<'py, PyAny>, node: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    query_lit(s, pred, node)
}

#[pyfunction]
fn ses_prepare_query<'py>(s: &Bound<'py, PyAny>, prop: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    prepare_query(s, prop)
}

#[pyfunction]
fn ses_emit(s: &Bound<'_, PyAny>, clause: &Bound<'_, PyAny>) -> PyResult<()> {
    emit(s, clause)
}

#[pyfunction]
fn ses_query_literal<'py>(
    s: &Bound<'py, PyAny>,
    lit: &Bound<'py, PyAny>,
    assumptions: &Bound<'py, PyAny>,
    search: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    query_literal(s, lit, assumptions, search)
}

#[pyfunction]
fn ses_query_all<'py>(
    s: &Bound<'py, PyAny>,
    ls: &Bound<'py, PyAny>,
    assumptions: &Bound<'py, PyAny>,
    search: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    query_all(s, ls, assumptions, search)
}

#[pyfunction]
fn ses_literal_of<'py>(s: &Bound<'py, PyAny>, f: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    literal_of(s, f)
}

#[pyfunction]
fn ses_relations(s: &Bound<'_, PyAny>, f: &Bound<'_, PyAny>) -> PyResult<()> {
    relations(s, f)
}

#[pyfunction]
fn ses_ensure_atoms(s: &Bound<'_, PyAny>, f: &Bound<'_, PyAny>) -> PyResult<()> {
    ensure_atoms(s, f)
}

#[pyfunction]
fn ses_ensure_twins(s: &Bound<'_, PyAny>, atoms: &Bound<'_, PyAny>) -> PyResult<bool> {
    ensure_twins(s, atoms)
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(ses_query_lit, m)?)?;
    m.add_function(wrap_pyfunction!(ses_prepare_query, m)?)?;
    m.add_function(wrap_pyfunction!(ses_emit, m)?)?;
    m.add_function(wrap_pyfunction!(ses_query_literal, m)?)?;
    m.add_function(wrap_pyfunction!(ses_query_all, m)?)?;
    m.add_function(wrap_pyfunction!(ses_literal_of, m)?)?;
    m.add_function(wrap_pyfunction!(ses_relations, m)?)?;
    m.add_function(wrap_pyfunction!(ses_ensure_atoms, m)?)?;
    m.add_function(wrap_pyfunction!(ses_ensure_twins, m)?)
}
