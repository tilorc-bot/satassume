//! Step 5c7, part 1: the discovery budget's stateless rows (`engine.py` on 44f4762: `Engine._union` :1759,
//! `_within_budget` :1783, `_over_budget` :1829, `_note_budget` :2246). They hold no container of their own.
//! The cone rows (`_struct`, `_cone_info`, `_query_cone`, `_drop_cones`) work on the engine's memos (`_kids`, `_cones`,
//! `_qcones`, `_glue_adapters`, `_constructing`). Under the planner's state ruling their move waits on sa-port-147's
//! inventory rows, so they stay Python's for now and are called back by name (`bud:cb_*`), as Python calls them.
//! `stats` and `last_budget_limited` are the engine's public attributes and stay Python's.
//! Module globals (`atoms_of`, `under_of`, `zero_twin`, `_kid`) are read from `satassume.engine` at the call.
//! A budget that isn't an int (Python accepts any value) runs Python's own methods (`bud:py_fallback`).
use pyo3::exceptions::PyAssertionError;
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyFrozenSet, PyInt, PyList, PySet, PyTuple};

use crate::relations_core::{planted, NOTE_BUDGET_KEEP_FLAG, OVER_BUDGET_NO_FLAG, UNION_SKIP_OVERLAP, WITHIN_NO_LINK};
use crate::session::{
    tick, BUD_CB_CONE_INFO, BUD_CB_GLOBAL, BUD_CB_QUERY_CONE, BUD_CB_STRUCT, BUD_NOTE_BUDGET, BUD_OVER_BUDGET, BUD_PY_FALLBACK,
    BUD_UNION, BUD_UNION_CONE_NONE, BUD_UNION_OVER, BUD_UNION_PARTIAL, BUD_WITHIN_BUDGET, BUD_WITHIN_FALSE, BUD_WITHIN_PARTIAL,
};

fn engine_mod(p: Python<'_>) -> PyResult<Bound<'_, PyModule>> {
    p.import(intern!(p, "satassume.engine"))
}

/// The budget as an `i64`, or None when it isn't an exact int (then the caller runs Python's method).
fn budget_of(eng: &Bound<'_, PyAny>) -> PyResult<Option<i64>> {
    let b = eng.getattr(intern!(eng.py(), "_discovery_budget"))?;
    if !b.is_exact_instance_of::<PyInt>() {
        return Ok(None);
    }
    Ok(b.extract::<i64>().ok())
}

fn py_method<'py>(eng: &Bound<'py, PyAny>, name: &str) -> PyResult<Bound<'py, PyAny>> {
    tick(BUD_PY_FALLBACK);
    let p = eng.py();
    let saved = p.import(intern!(p, "session_live"))?.getattr(intern!(p, "PY_BUDGET"))?;
    saved.get_item(name)
}

/// `self._struct(x)[1]`, called back by name.
fn struct_weight(eng: &Bound<'_, PyAny>, x: &Bound<'_, PyAny>) -> PyResult<i64> {
    tick(BUD_CB_STRUCT);
    eng.call_method1(intern!(eng.py(), "_struct"), (x,))?.get_item(1)?.extract()
}

/// `Engine._union`: `(cone, weight, rel)` of the union of the cones of `objs`, cone None past the budget.
/// `Ok(None)`: the budget isn't an int, and Python's method answered instead (returned by the caller).
pub(crate) fn union<'py>(eng: &Bound<'py, PyAny>, objs: &Bound<'py, PyAny>, budget: i64) -> PyResult<Bound<'py, PyTuple>> {
    let p = eng.py();
    let mut cone = PyFrozenSet::empty(p)?;
    let mut weight: i64 = 0;
    let mut rel = false;
    for o in objs.try_iter()? {
        let o = o?;
        tick(BUD_CB_CONE_INFO);
        let ci = eng.call_method1(intern!(p, "_cone_info"), (&o,))?;
        let (c, w, r) = (ci.get_item(0)?, ci.get_item(1)?, ci.get_item(2)?);
        if c.is_none() {
            tick(BUD_UNION_CONE_NONE);
            return PyTuple::new(p, [p.None().into_bound(p), w, r]);
        }
        rel = rel || r.is_truthy()?;
        let c = c.cast_into::<PyFrozenSet>()?;
        if cone.is_empty() {
            weight = w.extract()?;
            cone = c;
            continue;
        }
        let new = c.call_method1(intern!(p, "__sub__"), (&cone,))?.cast_into::<PyFrozenSet>()?;
        if !new.is_empty() {
            if new.len() == c.len() || planted(UNION_SKIP_OVERLAP) {
                weight += w.extract::<i64>()?;
            } else {
                tick(BUD_UNION_PARTIAL);
                for x in new.iter() {
                    weight += struct_weight(eng, &x)?;
                }
            }
            if weight > budget {
                tick(BUD_UNION_OVER);
                return PyTuple::new(p, [p.None().into_bound(p), weight.into_pyobject(p)?.into_any(), rel_obj(p, rel)]);
            }
            cone = cone.call_method1(intern!(p, "__or__"), (&new,))?.cast_into::<PyFrozenSet>()?;
        }
    }
    PyTuple::new(p, [cone.into_any(), weight.into_pyobject(p)?.into_any(), rel_obj(p, rel)])
}

fn rel_obj(p: Python<'_>, rel: bool) -> Bound<'_, PyAny> {
    pyo3::types::PyBool::new(p, rel).to_owned().into_any()
}

/// `self._query_cone(f, link)`, called back by name.
fn query_cone<'py>(eng: &Bound<'py, PyAny>, f: &Bound<'py, PyAny>, link: bool) -> PyResult<Bound<'py, PyAny>> {
    tick(BUD_CB_QUERY_CONE);
    eng.call_method1(intern!(eng.py(), "_query_cone"), (f, link))
}

fn global<'py>(em: &Bound<'py, PyModule>, name: &Bound<'py, pyo3::types::PyString>, arg: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    tick(BUD_CB_GLOBAL);
    em.getattr(name)?.call1((arg,))
}

/// `Engine._within_budget`.
fn within_budget(eng: &Bound<'_, PyAny>, prop: &Bound<'_, PyAny>, assumptions: Option<&Bound<'_, PyAny>>, budget: i64) -> PyResult<bool> {
    let p = eng.py();
    let r = query_cone(eng, prop, false)?;
    let mut rel = r.get_item(2)?.is_truthy()?;
    let mut sums = r.get_item(3)?;
    let zp = r.get_item(4)?.cast_into::<PyTuple>()?;
    let mut cross: Option<Bound<'_, PyList>> = None;
    let specs = eng.getattr(intern!(p, "_relation_specs"))?.is_truthy()?;
    if let Some(a) = assumptions {
        let ra = query_cone(eng, a, false)?;
        rel = rel || ra.get_item(2)?.is_truthy()?;
        sums = sums.call_method1(intern!(p, "__or__"), (ra.get_item(3)?,))?;
        let za = ra.get_item(4)?.cast_into::<PyTuple>()?;
        if (!zp.is_empty() || !za.is_empty()) && specs {
            let em = engine_mod(p)?;
            let (ao, uo, zt) = (intern!(p, "atoms_of"), intern!(p, "under_of"), intern!(p, "zero_twin"));
            let up = global(&em, uo, &global(&em, ao, prop)?)?;
            let ua = global(&em, uo, &global(&em, ao, a)?)?;
            let keys = PyDict::new(p);
            for e in zp.iter().chain(za.iter()) {
                keys.set_item(e, p.None())?;
            }
            let out = PyList::empty(p);
            for e in keys.keys() {
                let (izp, iup) = (zp.contains(&e)?, up.contains(&e)?);
                if izp && iup {
                    continue;
                }
                let (iza, iua) = (za.contains(&e)?, ua.contains(&e)?);
                if iza && iua {
                    continue;
                }
                if iup || iua {
                    out.append(global(&em, zt, &e)?)?;
                }
            }
            rel = rel || !out.is_empty();
            cross = Some(out);
        }
    }
    let link = specs && (rel || sums.len()? >= 2) && !planted(WITHIN_NO_LINK);
    let rp = query_cone(eng, prop, link)?;
    let cp = rp.get_item(0)?;
    if cp.is_none() {
        return Ok(false);
    }
    let Some(a) = assumptions else { return Ok(true) };
    let wp: i64 = rp.get_item(1)?.extract()?;
    let ra = query_cone(eng, a, link)?;
    let mut ca = ra.get_item(0)?;
    if ca.is_none() {
        return Ok(false);
    }
    let mut wa: i64 = ra.get_item(1)?.extract()?;
    if let Some(cross) = cross.filter(|c| !c.is_empty()) {
        let em = engine_mod(p)?;
        let kid = intern!(p, "_kid");
        let objs = PySet::empty(p)?;
        for x in cross.iter() {
            objs.add(global(&em, kid, &x)?)?;
        }
        let u = union(eng, objs.as_any(), budget)?;
        let cx = u.get_item(0)?;
        if cx.is_none() {
            return Ok(false);
        }
        ca = ca.call_method1(intern!(p, "__or__"), (cx,))?;
        wa += u.get_item(1)?.extract::<i64>()?;
    }
    if wp + wa <= budget {
        return Ok(true);
    }
    tick(BUD_WITHIN_PARTIAL);
    let mut total = wp;
    for x in ca.try_iter()? {
        let x = x?;
        if !cp.contains(&x)? {
            total += struct_weight(eng, &x)?;
        }
    }
    Ok(total <= budget)
}

#[pyfunction]
fn bud_union<'py>(eng: &Bound<'py, PyAny>, objs: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    tick(BUD_UNION);
    match budget_of(eng)? {
        Some(b) => Ok(union(eng, objs, b)?.into_any()),
        None => py_method(eng, "_union")?.call1((eng, objs)),
    }
}

#[pyfunction]
#[pyo3(signature = (eng, proposition, assumptions=None))]
fn bud_within_budget<'py>(eng: &Bound<'py, PyAny>, proposition: &Bound<'py, PyAny>, assumptions: Option<&Bound<'py, PyAny>>) -> PyResult<Bound<'py, PyAny>> {
    tick(BUD_WITHIN_BUDGET);
    let p = eng.py();
    match budget_of(eng)? {
        Some(b) => {
            let ok = within_budget(eng, proposition, assumptions.filter(|a| !a.is_none()), b)?;
            if !ok {
                tick(BUD_WITHIN_FALSE);
            }
            Ok(pyo3::types::PyBool::new(p, ok).to_owned().into_any())
        }
        None => py_method(eng, "_within_budget")?.call1((eng, proposition, assumptions)),
    }
}

/// `Engine._over_budget`: a query over the discovery budget, None, no session touched.
#[pyfunction]
fn bud_over_budget<'py>(eng: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    tick(BUD_OVER_BUDGET);
    let p = eng.py();
    if !planted(OVER_BUDGET_NO_FLAG) {
        eng.setattr(intern!(p, "last_budget_limited"), true)?;
    }
    bump_limited(eng)?;
    Ok(p.None().into_bound(p))
}

fn bump_limited(eng: &Bound<'_, PyAny>) -> PyResult<()> {
    let p = eng.py();
    let stats = eng.getattr(intern!(p, "stats"))?;
    let k = intern!(p, "budget_limited");
    let v = stats.get_item(k)?;
    stats.set_item(k, v.add(1)?)
}

/// `Engine._note_budget`: the query passed `_within_budget`, so its session ran uncapped.
#[pyfunction]
fn bud_note_budget(eng: &Bound<'_, PyAny>, s: &Bound<'_, PyAny>) -> PyResult<()> {
    tick(BUD_NOTE_BUDGET);
    let p = eng.py();
    let tr = intern!(p, "truncated");
    if s.getattr(tr)?.is_truthy()? {
        return Err(PyAssertionError::new_err("a session of a query within the budget was truncated"));
    }
    if !planted(NOTE_BUDGET_KEEP_FLAG) {
        eng.setattr(intern!(p, "last_budget_limited"), s.getattr(tr)?)?;
    }
    if s.getattr(tr)?.is_truthy()? {
        bump_limited(eng)?;
    }
    Ok(())
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(bud_union, m)?)?;
    m.add_function(wrap_pyfunction!(bud_within_budget, m)?)?;
    m.add_function(wrap_pyfunction!(bud_over_budget, m)?)?;
    m.add_function(wrap_pyfunction!(bud_note_budget, m)?)
}
