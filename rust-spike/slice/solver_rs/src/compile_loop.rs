//! Step 5c2: `Session`'s compile loop (`engine.py:539-770`), first part: module `want_of` and `_split`, and
//! `_emit_pattern`, `_flush`, `_compile`, `_compile_pending`, `_compile_patterns`. As in 5c1 (`discovery.rs`), the session's containers
//! (`pending`, `pending_c`, `demand`, `frontier`, `deferred`) and the memos `_WANT` and `_SPLIT` stay Python objects that
//! Python reads later, so state is Python's by construction; every read Python makes, Rust makes in the same order.
//! 5c2's second part adds `_custom`, `_visit` and the core's visit callback (`core_visit`); `Session._link` is `session.rs`'s
//! `link`. Still Python, called back by name: `compile_formula` (the module global, `session_live`'s under the core) and
//! `Session.emit` (passed to it as Python passes it). The Formula objects of `items` are read as Python reads them
//! (`atom.expr`, `atom.pred`, `!=`), counted callbacks until the formula step after 5c.
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyFrozenSet, PyList, PySet, PyTuple};

use crate::ses_cont::{Ses, SD_DEMAND, SD_PENDING, SD_PENDING_C, SQ_DEFERRED, SQ_FRONTIER};

use crate::relations_core::{
    planted, DROP_COMPILE_DEMAND, DROP_CUSTOM_FACTS, DROP_CUSTOM_REL, DROP_EMIT_MENT, DROP_FLUSH_CUSTOM, DROP_PEND_COMPILE, DROP_PAT_DEMAND,
    DROP_SPLIT_LATER, DROP_VISIT_ITEMS, WANT_EMPTY,
};
use crate::session::{
    tick, SES_COMPILE, SES_COMPILE_PATTERNS, SES_COMPILE_PENDING, SES_CORE_VISIT, SES_CUSTOM, SES_EMIT_PATTERN, SES_FLUSH,
    SES_SPLIT, SES_VISIT, SES_WANT_OF,
};

fn engine_mod(p: Python<'_>) -> PyResult<Bound<'_, PyModule>> {
    p.import(intern!(p, "satassume.engine"))
}

use crate::session::core_of;

/// Module `want_of`.
pub(crate) fn want_of<'py>(demanded: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    tick(SES_WANT_OF);
    let p = demanded.py();
    let key = PyFrozenSet::new(p, demanded.try_iter()?.collect::<PyResult<Vec<_>>>()?)?.into_any();
    if planted(WANT_EMPTY) {
        return Ok(PyFrozenSet::empty(p)?.into_any());
    }
    crate::procmemo::want_get_or_put(key)
}

/// Module `_split`: `(clauses, now, later, ment)`, memoized in `_SPLIT` per `(id(clauses), want)`.
pub(crate) fn split<'py>(clauses: &Bound<'py, PyAny>, want: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyTuple>> {
    tick(SES_SPLIT);
    let p = clauses.py();
    if let Some(r) = crate::procmemo::split_get(clauses, want)? {
        return Ok(r);
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
    crate::procmemo::split_put(clauses, want, &r)?;
    Ok(r)
}

/// `Session._emit_pattern`.
pub(crate) fn emit_pattern(s: &Bound<'_, PyAny>, clauses: &Bound<'_, PyAny>, bases: &Bound<'_, PyAny>, ment: &Bound<'_, PyAny>) -> PyResult<()> {
    tick(SES_EMIT_PATTERN);
    let p = s.py();
    let ment = if ment.is_none() { split(clauses, &p.None().into_bound(p))?.get_item(3)? } else { ment.clone() };
    let solver = crate::session::solver_of(s)?;
    let n = crate::session::table_of(s)?.len()?;
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
    let table = crate::session::table_of(s)?;
    while table.getattr(intern!(p, "new_custom"))?.is_truthy()? {
        let atoms = table.getattr(intern!(p, "new_custom"))?;
        table.setattr(intern!(p, "new_custom"), PyList::empty(p))?;
        if planted(DROP_FLUSH_CUSTOM) {
            continue;
        }
        for atom in atoms.try_iter()? {
            // by name, as Python's `self._custom`: the class's is Rust's (`ses_custom`), and an override is honoured
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
            Some(d) if !d.contains(&child)? => c.sq_push(SQ_DEFERRED, &child),
            _ => c.sq_push(SQ_FRONTIER, &child),
        };
    }
    table.setattr(intern!(p, "new_nodes"), PyList::empty(p))
}

/// `Session._compile`.
pub(crate) fn compile(s: &Bound<'_, PyAny>, node: &Bound<'_, PyAny>, items: &Bound<'_, PyAny>) -> PyResult<()> {
    tick(SES_COMPILE);
    let p = s.py();
    let eng = engine_mod(p)?;
    let table = crate::session::table_of(s)?;
    let emit = s.getattr(intern!(p, "emit"))?;
    let ses = Ses::of(s);
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
                    let mut d = ses.d_get(SD_DEMAND, &e)?;
                    if d.is_none() {
                        d = PySet::empty(p)?.into_any();
                        ses.d_set(SD_DEMAND, &e, &d)?;
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
    let ses = Ses::of(s);
    let pend_c = ses.d_get(SD_PENDING_C, node)?;
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
            ses.d_set(SD_PENDING_C, node, keep.as_any())?;
        } else {
            ses.d_del(SD_PENDING_C, node)?;
        }
    }
    let pend = ses.d_get(SD_PENDING, node)?;
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
        ses.d_set(SD_PENDING, node, later.as_any())?;
    } else {
        ses.d_del(SD_PENDING, node)?;
    }
    if !now.is_empty() && !planted(DROP_PEND_COMPILE) {
        compile(s, node, now.as_any())?;
    }
    Ok(())
}

/// `Session._compile_patterns`.
pub(crate) fn compile_patterns(s: &Bound<'_, PyAny>, node: &Bound<'_, PyAny>, compiled: &Bound<'_, PyAny>, demanded: &Bound<'_, PyAny>) -> PyResult<()> {
    tick(SES_COMPILE_PATTERNS);
    let p = s.py();
    let table = crate::session::table_of(s)?;
    let base_of = table.getattr(intern!(p, "base_of"))?;
    let ses = Ses::of(s);
    let want = if demanded.is_none() { p.None().into_bound(p) } else { want_of(demanded)? };
    for comp in compiled.try_iter()? {
        let comp = comp?;
        let (objs, pat) = (comp.getattr(intern!(p, "objs"))?, comp.getattr(intern!(p, "pattern"))?);
        let bases = PyList::new(p, vec![0i64; objs.len()?])?;
        let mut new = Vec::new();
        for k in pat.getattr(intern!(p, "used"))?.try_iter()? {
            let k = k?;
            let o = objs.get_item(&k)?;
            let mut bb = base_of.call_method1(intern!(p, "get"), (&o,))?;
            if bb.is_none() {
                bb = table.call_method1(intern!(p, "node_base"), (&o,))?;
                new.push(k.clone());
            }
            bases.set_item(k.extract::<usize>()?, 2i64.into_pyobject(p)?.mul(&bb)?)?;
        }
        let r = split(&pat.getattr(intern!(p, "clauses"))?, &want)?;
        let (now, later, ment) = (r.get_item(1)?, r.get_item(2)?, r.get_item(3)?);
        if !later.is_none() {
            let mut l = ses.d_get(SD_PENDING_C, node)?;
            if l.is_none() {
                l = PyList::empty(p).into_any();
                ses.d_set(SD_PENDING_C, node, &l)?;
            }
            l.call_method1(intern!(p, "append"), (PyTuple::new(p, [later, bases.clone().into_any()])?,))?;
        }
        if now.is_truthy()? {
            emit_pattern(s, &now, bases.as_any(), &ment)?;
        }
        for kv in pat.getattr(intern!(p, "child_preds"))?.call_method0(intern!(p, "items"))?.try_iter()? {
            let kv = kv?;
            let (k, preds) = (kv.get_item(0)?, kv.get_item(1)?);
            if planted(DROP_PAT_DEMAND) {
                continue;
            }
            let o = objs.get_item(&k)?;
            let d = ses.d_get(SD_DEMAND, &o)?;
            if d.is_none() {
                ses.d_set(SD_DEMAND, &objs.get_item(&k)?, PySet::new(p, preds.try_iter()?.collect::<PyResult<Vec<_>>>()?)?.as_any())?;
            } else {
                d.call_method1(intern!(p, "update"), (preds,))?;
            }
        }
        let pn = pat.getattr(intern!(p, "node"))?;
        for k in new {
            if k.lt(&pn)? {
                ses.q_push(SQ_FRONTIER, &objs.get_item(&k)?)?;
            } else if k.gt(&pn)? {
                ses.q_push(SQ_DEFERRED, &objs.get_item(&k)?)?;
            }
        }
    }
    table.setattr(intern!(p, "new_nodes"), PyList::empty(p))
}

/// `Session._custom`: a custom-predicate atom was allocated. A relation atom goes to the session's `Relations` (made here, and
/// counted in `engine.stats["scope_misses"]`, when the session has none); otherwise the extensions' facts for it compile.
pub(crate) fn custom(s: &Bound<'_, PyAny>, atom: &Bound<'_, PyAny>) -> PyResult<()> {
    tick(SES_CUSTOM);
    let p = s.py();
    let eng = engine_mod(p)?;
    let engine = s.getattr(intern!(p, "engine"))?;
    if eng.getattr(intern!(p, "RELATION_ATOMS"))?.contains(atom.getattr(intern!(p, "pred"))?)?
        && engine.getattr(intern!(p, "_relation_specs"))?.is_truthy()?
    {
        let mut rel = s.getattr(intern!(p, "relations"))?;
        if rel.is_none() {
            crate::entry::scope_miss(&engine)?;
            rel = eng.getattr(intern!(p, "Relations"))?.call1((s, engine.getattr(intern!(p, "_relation_specs"))?))?;
            s.setattr(intern!(p, "relations"), &rel)?;
            let af = s.getattr(intern!(p, "assumption_formula"))?;
            if !af.is_none() {
                rel.call_method1(intern!(p, "note_formula"), (core_of(s)?.borrow().atoms_of(&af)?,))?;
            }
        }
        if !planted(DROP_CUSTOM_REL) {
            rel.call_method1(intern!(p, "enqueue"), (atom,))?;
        }
        return Ok(());
    }
    let ext = engine.getattr(intern!(p, "_extensions"))?;
    if ext.is_none() {
        return Ok(());
    }
    for f in ext.call_method1(intern!(p, "facts_for"), (atom,))?.try_iter()? {
        let f = f?;
        if planted(DROP_CUSTOM_FACTS) {
            continue;
        }
        eng.getattr(intern!(p, "compile_formula"))?.call1((f, crate::session::table_of(s)?, s.getattr(intern!(p, "emit"))?))?;
    }
    Ok(())
}

/// `Session._visit`, the body of `Session.node`: the node's templates and node facts, its rule-base block, then its patterns
/// and formulas (parked under a demand).
pub(crate) fn visit(s: &Bound<'_, PyAny>, node: &Bound<'_, PyAny>, b: i32, demanded: &Bound<'_, PyAny>) -> PyResult<()> {
    tick(SES_VISIT);
    let p = s.py();
    let eng = engine_mod(p)?;
    let engine = s.getattr(intern!(p, "engine"))?;
    let ct = engine.getattr(intern!(p, "clause_templates"))?;
    let (compiled, mut formulas) = if !ct.is_none() {
        let two: Vec<Bound<'_, PyAny>> = ct.call1((node,))?.try_iter()?.collect::<PyResult<_>>()?;
        let [c, f]: [Bound<'_, PyAny>; 2] =
            two.try_into().map_err(|v: Vec<_>| pyo3::exceptions::PyValueError::new_err(format!("expected 2 values to unpack, got {}", v.len())))?;
        (c, f)
    } else {
        (PyTuple::empty(p).into_any(), engine.call_method1(intern!(p, "_templates"), (node,))?)
    };
    let ext = engine.getattr(intern!(p, "_extensions"))?;
    if !ext.is_none() && ext.getattr(intern!(p, "has_node_facts"))?.is_truthy()? {
        let l = PyList::new(p, formulas.try_iter()?.collect::<PyResult<Vec<_>>>()?)?.into_any();
        formulas = l.add(ext.call_method1(intern!(p, "node_facts"), (node,))?)?;
    }
    let has_formulas = formulas.is_truthy()?;
    let items = if has_formulas {
        let core = core_of(s)?;
        let mut v = Vec::new();
        for f in formulas.try_iter()? {
            let f = f?;
            let a = core.borrow().atoms_of(&f)?.into_any();
            v.push(PyTuple::new(p, [f, a])?);
        }
        Some(PyList::new(p, v)?)
    } else {
        None
    };
    let solver = crate::session::solver_of(s)?;
    let complete_constant = compiled.len()? == 1
        && compiled.get_item(0)?.getattr(intern!(p, "pattern"))?.getattr(intern!(p, "complete"))?.is_truthy()?
        && !has_formulas;
    if !complete_constant {
        let mut own = 0i64.into_pyobject(p)?.into_any();
        if compiled.is_truthy()? {
            let want = if demanded.is_none() { p.None().into_bound(p) } else { want_of(demanded)? };
            for comp in compiled.try_iter()? {
                let pat = comp?.getattr(intern!(p, "pattern"))?;
                let k0 = pat.getattr(intern!(p, "node"))?;
                for km in split(&pat.getattr(intern!(p, "clauses"))?, &want)?.get_item(3)?.try_iter()? {
                    let km = km?;
                    let (k, m) = (km.get_item(0)?, km.get_item(1)?);
                    if k.eq(&k0)? {
                        own = own.bitor(m)?;
                    }
                }
            }
        }
        solver.call_method1(intern!(p, "register_block"), (b, own))?;
    } else {
        let npred = eng.getattr(intern!(p, "NPRED"))?;
        solver.call_method1(intern!(p, "ensure_vars"), (npred.add(b)?.sub(1)?,))?;
    }
    if compiled.is_truthy()? {
        compile_patterns(s, node, &compiled, demanded)?;
    }
    if let Some(items) = items {
        if items.is_truthy()? && !planted(DROP_VISIT_ITEMS) {
            if demanded.is_none() {
                compile(s, node, items.as_any())?;
            } else {
                Ses::of(s).d_set(SD_PENDING, node, items.as_any())?;
                compile_pending(s, node, demanded)?;
            }
        }
    }
    Ok(())
}

/// What the core calls to visit a node (`session_live._core_visit` until 5c2): the census when on, and the node marked in
/// `engine._constructing` while its visit runs.
pub(crate) fn core_visit(s: &Bound<'_, PyAny>, node: &Bound<'_, PyAny>, b: i32, demanded: &Bound<'_, PyAny>) -> PyResult<()> {
    tick(SES_CORE_VISIT);
    let p = s.py();
    let sl = p.import(intern!(p, "session_live"))?;
    if !sl.getattr(intern!(p, "CENSUS"))?.is_none() {
        sl.getattr(intern!(p, "_census"))?.call1((node,))?;
    }
    // step 5c10c: `_constructing` is Rust-native (engmemo.rs slot 9), reached directly
    let constructing = s.getattr(intern!(p, "engine"))?.getattr(intern!(p, "_constructing"))?;
    crate::engmemo::set_add(&constructing, node)?;
    // by name, as Python's `Session.node` calls `self._visit`: the class's is Rust's (`ses_visit`); a test's instance override
    // (test_session_limits.py `_object_case`) is honoured
    // state part 3, sub-part 5: `visit` directly while the class's is still session_live's frame (session.rs `named`)
    static FW_VISIT: pyo3::sync::PyOnceLock<Py<PyAny>> = pyo3::sync::PyOnceLock::new();
    let r = match crate::session::named(s, intern!(p, "_visit"), &FW_VISIT, "_ses_visit") {
        Ok(None) => visit(s, node, b, demanded),
        Ok(Some(m)) => m.call1((node, b, demanded)).map(|_| ()),
        Err(e) => Err(e),
    };
    crate::engmemo::set_discard(&constructing, node)?;
    r
}

#[pyfunction]
fn ses_custom(s: &Bound<'_, PyAny>, atom: &Bound<'_, PyAny>) -> PyResult<()> {
    custom(s, atom)
}

#[pyfunction]
fn ses_visit(s: &Bound<'_, PyAny>, node: &Bound<'_, PyAny>, b: i32, demanded: &Bound<'_, PyAny>) -> PyResult<()> {
    visit(s, node, b, demanded)
}

#[pyfunction]
fn ses_compile_patterns(s: &Bound<'_, PyAny>, node: &Bound<'_, PyAny>, compiled: &Bound<'_, PyAny>, demanded: &Bound<'_, PyAny>) -> PyResult<()> {
    compile_patterns(s, node, compiled, demanded)
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
    m.add_function(wrap_pyfunction!(ses_compile_pending, m)?)?;
    m.add_function(wrap_pyfunction!(ses_custom, m)?)?;
    m.add_function(wrap_pyfunction!(ses_visit, m)?)?;
    m.add_function(wrap_pyfunction!(ses_compile_patterns, m)?)
}
