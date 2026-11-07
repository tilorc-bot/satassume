//! Step 5c2: `Session`'s compile loop (`engine.py:539-770`), first part: module `want_of` and `_split`, and
//! `_emit_pattern`, `_flush`, `_compile`, `_compile_pending`. As in 5c1 (`discovery.rs`), the session's containers
//! (`pending`, `pending_c`, `demand`, `frontier`, `deferred`) and the memos `_WANT` and `_SPLIT` stay Python objects that
//! Python reads later, so state is Python's by construction; every read Python makes, Rust makes in the same order.
//! Still Python, called back by name: `_custom`, `compile_formula` (the module global, `session_live`'s under the core) and
//! `Session.emit` (passed to it as Python passes it). The Formula objects of `items` are read as Python reads them
//! (`atom.expr`, `atom.pred`, `!=`), counted callbacks until the formula step after 5c.
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyFrozenSet, PyList, PySet, PyTuple};

use crate::relations_core::{
    planted, DROP_COMPILE_DEMAND, DROP_EMIT_MENT, DROP_FLUSH_CUSTOM, DROP_PEND_COMPILE, DROP_SPLIT_LATER, WANT_EMPTY,
};
use crate::session::{tick, SessionCore, SES_COMPILE, SES_COMPILE_PENDING, SES_EMIT_PATTERN, SES_FLUSH, SES_SPLIT, SES_WANT_OF};

fn engine_mod(p: Python<'_>) -> PyResult<Bound<'_, PyModule>> {
    p.import(intern!(p, "satassume.engine"))
}

fn core_of<'py>(s: &Bound<'py, PyAny>) -> PyResult<Bound<'py, SessionCore>> {
    let p = s.py();
    Ok(s.getattr(intern!(p, "table"))?.getattr(intern!(p, "core"))?.cast_into::<SessionCore>()?)
}

/// Module `want_of`.
pub(crate) fn want_of<'py>(demanded: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    tick(SES_WANT_OF);
    let p = demanded.py();
    let key = PyFrozenSet::new(p, demanded.try_iter()?.collect::<PyResult<Vec<_>>>()?)?.into_any();
    if planted(WANT_EMPTY) {
        return Ok(PyFrozenSet::empty(p)?.into_any());
    }
    let memo = engine_mod(p)?.getattr(intern!(p, "_WANT"))?;
    let w = memo.call_method1(intern!(p, "get"), (&key,))?;
    if !w.is_none() {
        return Ok(w);
    }
    memo.set_item(&key, &key)?;
    Ok(key)
}

/// Module `_split`: `(clauses, now, later, ment)`, memoized in `_SPLIT` per `(id(clauses), want)`.
pub(crate) fn split<'py>(clauses: &Bound<'py, PyAny>, want: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyTuple>> {
    tick(SES_SPLIT);
    let p = clauses.py();
    let memo = engine_mod(p)?.getattr(intern!(p, "_SPLIT"))?.cast_into::<PyDict>()?;
    let key = PyTuple::new(p, [(clauses.as_ptr() as usize).into_pyobject(p)?.into_any(), want.clone()])?;
    if let Some(r) = memo.get_item(&key)? {
        if !r.is_none() && r.get_item(0)?.is(clauses) {
            return Ok(r.cast_into::<PyTuple>()?);
        }
    }
    let none = p.None().into_bound(p);
    let (now, later) = if want.is_none() {
        (clauses.clone(), none.clone())
    } else {
        let (now, later) = (PyList::empty(p), PyList::empty(p));
        for c in clauses.try_iter()? {
            let c = c?;
            if c.get_item(1)?.bitand(want)?.is_truthy()? {
                now.append(&c)?;
            }
        }
        for c in clauses.try_iter()? {
            let c = c?;
            if !c.get_item(1)?.bitand(want)?.is_truthy()? {
                later.append(&c)?;
            }
        }
        if later.is_empty() || planted(DROP_SPLIT_LATER) {
            (if later.is_empty() { clauses.clone() } else { now.into_any() }, none.clone())
        } else {
            (now.into_any(), later.into_any())
        }
    };
    let acc = PyDict::new(p);
    let three = 3i64.into_pyobject(p)?;
    for c in now.try_iter()? {
        let li = c?.get_item(2)?;
        for x in li.try_iter()? {
            let x = x?;
            let (k, off) = (x.get_item(0)?, x.get_item(1)?);
            let m = three.lshift(off.bitand(-2i64)?)?;
            let m = match acc.get_item(&k)? {
                Some(old) => old.bitor(&m)?,
                None => 0i64.into_pyobject(p)?.into_any().bitor(&m)?,
            };
            acc.set_item(&k, m)?;
        }
    }
    let ment = PyTuple::new(p, acc.items().iter())?;
    let r = PyTuple::new(p, [clauses.clone(), now, later, ment.into_any()])?;
    if memo.len() >= 100_000 {
        memo.clear();
    }
    memo.set_item(&key, &r)?;
    Ok(r)
}

/// `Session._emit_pattern`.
pub(crate) fn emit_pattern(s: &Bound<'_, PyAny>, clauses: &Bound<'_, PyAny>, bases: &Bound<'_, PyAny>, ment: &Bound<'_, PyAny>) -> PyResult<()> {
    tick(SES_EMIT_PATTERN);
    let p = s.py();
    let ment = if ment.is_none() { split(clauses, &p.None().into_bound(p))?.get_item(3)? } else { ment.clone() };
    let solver = s.getattr(intern!(p, "solver"))?;
    let n = s.getattr(intern!(p, "table"))?.len()?;
    solver.call_method1(intern!(p, "ensure_vars"), (n,))?;
    let cls = PyList::empty(p);
    for c in clauses.try_iter()? {
        let li = c?.get_item(2)?;
        let out = PyList::empty(p);
        for x in li.try_iter()? {
            let x = x?;
            out.append(bases.get_item(x.get_item(0)?)?.add(x.get_item(1)?)?)?;
        }
        cls.append(out)?;
    }
    let ms = PyList::empty(p);
    if !planted(DROP_EMIT_MENT) {
        for x in ment.try_iter()? {
            let x = x?;
            let b = bases.get_item(x.get_item(0)?)?.rshift(1i64)?;
            ms.append(PyTuple::new(p, [b, x.get_item(1)?])?)?;
        }
    }
    solver.call_method1(intern!(p, "add_internal"), (cls, ms))?;
    Ok(())
}

/// `Session._flush`.
pub(crate) fn flush(s: &Bound<'_, PyAny>, node: &Bound<'_, PyAny>) -> PyResult<()> {
    tick(SES_FLUSH);
    let p = s.py();
    let table = s.getattr(intern!(p, "table"))?;
    while table.getattr(intern!(p, "new_custom"))?.is_truthy()? {
        let atoms = table.getattr(intern!(p, "new_custom"))?;
        table.setattr(intern!(p, "new_custom"), PyList::empty(p))?;
        if planted(DROP_FLUSH_CUSTOM) {
            continue;
        }
        for atom in atoms.try_iter()? {
            s.call_method1(intern!(p, "_custom"), (atom?,))?;
        }
    }
    let direct = if node.is_none() { None } else { node.getattr_opt(intern!(p, "args"))?.filter(|d| !d.is_none()) };
    let core = core_of(s)?;
    let c = core.borrow();
    for child in table.getattr(intern!(p, "new_nodes"))?.try_iter()? {
        let child = child?;
        if c.base_get(&child)?.is_some() {
            continue;
        }
        match &direct {
            Some(d) if !d.contains(&child)? => s.getattr(intern!(p, "deferred"))?.call_method1(intern!(p, "append"), (child,))?,
            _ => s.getattr(intern!(p, "frontier"))?.call_method1(intern!(p, "append"), (child,))?,
        };
    }
    table.setattr(intern!(p, "new_nodes"), PyList::empty(p))
}

/// `Session._compile`.
pub(crate) fn compile(s: &Bound<'_, PyAny>, node: &Bound<'_, PyAny>, items: &Bound<'_, PyAny>) -> PyResult<()> {
    tick(SES_COMPILE);
    let p = s.py();
    let eng = engine_mod(p)?;
    let table = s.getattr(intern!(p, "table"))?;
    let emit = s.getattr(intern!(p, "emit"))?;
    let demand = s.getattr(intern!(p, "demand"))?;
    let (pred_index, basis_of) = (eng.getattr(intern!(p, "PRED_INDEX"))?, eng.getattr(intern!(p, "BASIS_OF"))?);
    for item in items.try_iter()? {
        let item = item?;
        let (f, atoms) = (item.get_item(0)?, item.get_item(1)?);
        for atom in atoms.try_iter()? {
            let atom = atom?;
            let e = atom.getattr(intern!(p, "expr"))?;
            if e.ne(node)? {
                let pred = atom.getattr(intern!(p, "pred"))?;
                if pred_index.contains(&pred)? && !planted(DROP_COMPILE_DEMAND) {
                    let mut d = demand.call_method1(intern!(p, "get"), (&e,))?;
                    if d.is_none() {
                        d = PySet::empty(p)?.into_any();
                        demand.set_item(&e, &d)?;
                    }
                    d.call_method1(intern!(p, "update"), (basis_of.get_item(&pred)?,))?;
                }
            }
        }
        eng.getattr(intern!(p, "compile_formula"))?.call1((f, &table, &emit))?;
    }
    flush(s, node)
}

/// `Session._compile_pending`.
pub(crate) fn compile_pending(s: &Bound<'_, PyAny>, node: &Bound<'_, PyAny>, demanded: &Bound<'_, PyAny>) -> PyResult<()> {
    tick(SES_COMPILE_PENDING);
    let p = s.py();
    let want = want_of(demanded)?;
    let pending_c = s.getattr(intern!(p, "pending_c"))?;
    let pend_c = pending_c.call_method1(intern!(p, "get"), (node,))?;
    if pend_c.is_truthy()? {
        let keep = PyList::empty(p);
        for x in pend_c.try_iter()? {
            let x = x?;
            let (clauses, bases) = (x.get_item(0)?, x.get_item(1)?);
            let r = split(&clauses, &want)?;
            let (now, later, ment) = (r.get_item(1)?, r.get_item(2)?, r.get_item(3)?);
            if now.is_truthy()? {
                emit_pattern(s, &now, &bases, &ment)?;
                if !later.is_none() {
                    keep.append(PyTuple::new(p, [later, bases])?)?;
                }
            } else {
                keep.append(PyTuple::new(p, [clauses, bases])?)?;
            }
        }
        if !keep.is_empty() {
            pending_c.set_item(node, keep)?;
        } else {
            pending_c.del_item(node)?;
        }
    }
    let pending = s.getattr(intern!(p, "pending"))?;
    let pend = pending.call_method1(intern!(p, "get"), (node,))?;
    if !pend.is_truthy()? {
        return Ok(());
    }
    let eng = engine_mod(p)?;
    let (basis_of, no_basis) = (eng.getattr(intern!(p, "BASIS_OF"))?, eng.getattr(intern!(p, "_NO_BASIS"))?);
    let (now, later) = (PyList::empty(p), PyList::empty(p));
    for item in pend.try_iter()? {
        let item = item?;
        let atoms = item.get_item(1)?;
        let mut hit = false;
        for a in atoms.try_iter()? {
            let a = a?;
            if a.getattr(intern!(p, "expr"))?.eq(node)? {
                let b = basis_of.call_method1(intern!(p, "get"), (a.getattr(intern!(p, "pred"))?, &no_basis))?;
                if !b.call_method1(intern!(p, "isdisjoint"), (&want,))?.is_truthy()? {
                    hit = true;
                    break;
                }
            }
        }
        if hit { now.append(item)? } else { later.append(item)? }
    }
    if !later.is_empty() {
        pending.set_item(node, later)?;
    } else {
        pending.del_item(node)?;
    }
    if !now.is_empty() && !planted(DROP_PEND_COMPILE) {
        compile(s, node, now.as_any())?;
    }
    Ok(())
}

#[pyfunction]
fn ses_want_of<'py>(demanded: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    want_of(demanded)
}

#[pyfunction]
fn ses_split<'py>(clauses: &Bound<'py, PyAny>, want: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyTuple>> {
    split(clauses, want)
}

#[pyfunction]
#[pyo3(signature = (s, clauses, bases, ment=None))]
fn ses_emit_pattern(s: &Bound<'_, PyAny>, clauses: &Bound<'_, PyAny>, bases: &Bound<'_, PyAny>, ment: Option<Bound<'_, PyAny>>) -> PyResult<()> {
    let p = s.py();
    emit_pattern(s, clauses, bases, &ment.unwrap_or_else(|| p.None().into_bound(p)))
}

#[pyfunction]
#[pyo3(signature = (s, node=None))]
fn ses_flush(s: &Bound<'_, PyAny>, node: Option<Bound<'_, PyAny>>) -> PyResult<()> {
    let p = s.py();
    flush(s, &node.unwrap_or_else(|| p.None().into_bound(p)))
}

#[pyfunction]
fn ses_compile(s: &Bound<'_, PyAny>, node: &Bound<'_, PyAny>, items: &Bound<'_, PyAny>) -> PyResult<()> {
    compile(s, node, items)
}

#[pyfunction]
fn ses_compile_pending(s: &Bound<'_, PyAny>, node: &Bound<'_, PyAny>, demanded: &Bound<'_, PyAny>) -> PyResult<()> {
    compile_pending(s, node, demanded)
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(ses_want_of, m)?)?;
    m.add_function(wrap_pyfunction!(ses_split, m)?)?;
    m.add_function(wrap_pyfunction!(ses_emit_pattern, m)?)?;
    m.add_function(wrap_pyfunction!(ses_flush, m)?)?;
    m.add_function(wrap_pyfunction!(ses_compile, m)?)?;
    m.add_function(wrap_pyfunction!(ses_compile_pending, m)?)
}
