//! Step 5c7, part 1: the discovery budget's stateless rows (`engine.py` on 44f4762: `Engine._union` :1759,
//! `_within_budget` :1783, `_over_budget` :1829, `_note_budget` :2246). They hold no container of their own.
//! The cone rows (`_struct`, `_cone_info`, `_query_cone`, `_drop_cones`) work on the engine's memos (`_kids`, `_cones`,
//! `_qcones`, `_glue_adapters`, `_constructing`). `_query_cone` moved with `_qcones` in 5c9c; step 5c10c moves `_struct`,
//! `_cone_info` and `_drop_cones` here with `_cones` and `_constructing` (engmemo.rs slots 8-9), so every container they touch is
//! Rust-native and 5c9c's counted crossing (`em:py_kids`/`em:py_glue`/`em:py_qcones` from Python's `_struct`/`_drop_cones`) is
//! gone; `bud:cb_struct`/`bud:cb_cone_info` no longer fire. `_struct` still calls the knowledge layer's templates
//! (`bud:cb_templates`) and the extensions (`bud:cb_ext`), and reads SymPy's `args`/`is_Add`/`is_Mul`/`is_Atom`/`is_number`
//! of a cone object (conversion-layer reads).
//! `stats` and `last_budget_limited` are Rust-owned since 5c10d (entry.rs `EngineStats`); `_over_budget`/`_note_budget` write them there.
//! Module globals (`atoms_of`, `under_of`, `zero_twin`, `_kid`) are read from `satassume.engine` at the call.
//! A budget that isn't an int (Python accepts any value) runs Python's own methods (`bud:py_fallback`).
use pyo3::exceptions::PyAssertionError;
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyFrozenSet, PyInt, PyList, PySet, PyTuple};

use crate::engmemo;
use crate::relations_core::{planted, CONE_CONES_NO_BOUND, CONE_DROP_SKIP_CONES, CONE_INFO_OVER_FITS, CONE_KIDS_NO_BOUND,
    CONE_STRUCT_WEIGHT_ONE, CONE_STRUCT_WIDE_SKIP, EM_KIDS_SET_DROP, EM_QCONES_CLEAR_SKIP, EM_QCONE_KEY_F, EM_QCONE_NO_SUMS, NOTE_BUDGET_KEEP_FLAG, OVER_BUDGET_NO_FLAG, UNION_SKIP_OVERLAP, WITHIN_NO_LINK};
use crate::session::{
    tick, BUD_CB_EXT, BUD_CB_GLOBAL, BUD_CB_TEMPLATES, BUD_CONES_HIT, BUD_CONE_INFO, BUD_DROP_CONES, BUD_KIDS_HIT, BUD_QUERY_CONE,
    BUD_PY_CONE_INFO, BUD_PY_DROP_CONES, BUD_PY_STRUCT, BUD_STRUCT, BUD_STRUCT_WIDE, EM_FULL, BUD_NOTE_BUDGET, BUD_OVER_BUDGET, BUD_PY_FALLBACK,
    BUD_UNION, BUD_UNION_CONE_NONE, BUD_UNION_OVER, BUD_UNION_PARTIAL, BUD_WITHIN_BUDGET, BUD_WITHIN_FALSE, BUD_WITHIN_PARTIAL,
};

fn engine_mod(p: Python<'_>) -> PyResult<Bound<'_, PyModule>> {
    p.import(intern!(p, "satassume.engine"))
}

/// The budget as an `i64`, or None when it isn't an exact int (then the caller runs Python's method). Step 5c10c: also None
/// past 2**60, so `budget + 1` and the weights' sums stay exact in an `i64` (Python's ints are unbounded).
fn budget_of(eng: &Bound<'_, PyAny>) -> PyResult<Option<i64>> {
    let b = eng.getattr(intern!(eng.py(), "_discovery_budget"))?;
    if !b.is_exact_instance_of::<PyInt>() {
        return Ok(None);
    }
    Ok(b.extract::<i64>().ok().filter(|&b| b.unsigned_abs() < 1 << 60))
}

fn py_method<'py>(eng: &Bound<'py, PyAny>, name: &str) -> PyResult<Bound<'py, PyAny>> {
    tick(BUD_PY_FALLBACK);
    let p = eng.py();
    let saved = p.import(intern!(p, "session_live"))?.getattr(intern!(p, "PY_BUDGET"))?;
    saved.get_item(name)
}

/// `self._struct(x)[1]` (Rust's since 5c10c).
fn struct_weight(eng: &Bound<'_, PyAny>, x: &Bound<'_, PyAny>, budget: i64) -> PyResult<i64> {
    struct_(eng, x, budget)?.get_item(1)?.extract()
}

/// Calls the module global `f` with one argument (`atoms_of`, `_kid`), counted as `global` does.
fn call_global<'py>(f: &Bound<'py, PyAny>, arg: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    tick(BUD_CB_GLOBAL);
    f.call1((arg,))
}

/// `k.update(_kid(a) for a in atoms_of(f))`.
fn add_kids_of(k: &Bound<'_, PySet>, f: &Bound<'_, PyAny>, atoms_of: &Bound<'_, PyAny>, kid: &Bound<'_, PyAny>) -> PyResult<()> {
    for a in call_global(atoms_of, f)?.try_iter()? {
        k.add(call_global(kid, &a?)?)?;
    }
    Ok(())
}

/// `kids[o] = r`; 5c9c's plant `em-kids-set-drop` (the store lost) now sits on this, Rust's own write.
fn store_kids(kids: &Bound<'_, PyAny>, o: &Bound<'_, PyAny>, r: &Bound<'_, PyAny>) -> PyResult<()> {
    if planted(EM_KIDS_SET_DROP) {
        return Ok(());
    }
    engmemo::set(kids, o, r)
}

/// `Engine._struct` (engine.py:1609 on 4215655): `(kids, weight)` of the cone object `o`, memoized in `_kids` (emptied at
/// 200,000 entries). The kid sets are Python sets filled in Python's order, so `_cone_info`'s walk visits them as Python's does.
pub(crate) fn struct_<'py>(eng: &Bound<'py, PyAny>, o: &Bound<'py, PyAny>, budget: i64) -> PyResult<Bound<'py, PyAny>> {
    tick(BUD_STRUCT);
    let p = eng.py();
    let kids = eng.getattr(intern!(p, "_kids"))?;
    if let Some(r) = engmemo::get(&kids, o)? {
        tick(BUD_KIDS_HIT);
        return Ok(r);
    }
    if engmemo::len(&kids)? >= 200_000 && !planted(CONE_KIDS_NO_BOUND) {
        tick(EM_FULL);
        engmemo::clear(&kids)?;
    }
    let em = engine_mod(p)?;
    let ext = eng.getattr(intern!(p, "_extensions"))?;
    let atoms_of = em.getattr(intern!(p, "atoms_of"))?;
    let kid = em.getattr(intern!(p, "_kid"))?;
    let zero = 0i64.into_pyobject(p)?.into_any();
    if o.is_instance(&em.getattr(intern!(p, "P"))?)? {
        // an object of a cone that is a P is a custom or relation atom (_kid maps vocabulary atoms to their argument)
        let specs = eng.getattr(intern!(p, "_relation_specs"))?;
        if em.getattr(intern!(p, "RELATION_ATOMS"))?.contains(o.getattr(intern!(p, "pred"))?)? && specs.is_truthy()? {
            // a two-sided `eq` keeps term_live's `glue_objects` (its difference on ids); any other relation atom is Rust's
            let two = o.getattr(intern!(p, "expr"))?.try_iter()?.count() == 2;
            // relations on Python (SLICE_REL=py: rel_install hasn't run) keep Python's `glue_objects` for every relation atom
            let g = if !crate::relations_core::installed() || two && o.getattr(intern!(p, "pred"))?.eq(intern!(p, "eq"))? {
                tick(BUD_CB_GLOBAL);
                em.getattr(intern!(p, "glue_objects"))?.call1((o, &specs, eng.getattr(intern!(p, "_glue_adapters"))?))?
            } else {
                crate::relations_core::glue_objects_plain(o, &specs, &eng.getattr(intern!(p, "_glue_adapters"))?)?.into_any()
            };
            let r = PyTuple::new(p, [g, zero])?.into_any();
            store_kids(&kids, o, &r)?;
            return Ok(r);
        }
        let k = PySet::empty(p)?;
        if !ext.is_none() {
            tick(BUD_CB_EXT);
            for f in ext.call_method1(intern!(p, "facts_for"), (o,))?.try_iter()? {
                add_kids_of(&k, &f?, &atoms_of, &kid)?;
            }
            k.discard(o)?;
        }
        let r = PyTuple::new(p, [k.into_any(), zero])?.into_any();
        store_kids(&kids, o, &r)?;
        return Ok(r);
    }
    let args = match o.getattr(intern!(p, "args")) {
        Ok(a) => a,
        Err(e) if e.is_instance_of::<pyo3::exceptions::PyAttributeError>(p) => PyTuple::empty(p).into_any(),
        Err(e) => return Err(e),
    };
    let flag = |n: &Bound<'py, pyo3::types::PyString>| -> PyResult<bool> {
        match o.getattr(n) {
            Ok(v) => v.is_truthy(),
            Err(e) if e.is_instance_of::<pyo3::exceptions::PyAttributeError>(p) => Ok(false),
            Err(e) => Err(e),
        }
    };
    {
        if args.len()? as i64 > budget && (flag(intern!(p, "is_Add"))? || flag(intern!(p, "is_Mul"))?) && !planted(CONE_STRUCT_WIDE_SKIP) {
            // every non-constant term of a sum or product is a kid of weight >= 1: more of them than the budget put every
            // cone holding `o` over it, so its (quadratic) templates are not built (#180 C-WIDEADD)
            let k = PySet::empty(p)?;
            for a in args.try_iter()? {
                let a = a?;
                let constant = a.getattr(intern!(p, "is_Atom"))?.is_truthy()? && a.getattr(intern!(p, "is_number"))?.is_truthy()?;
                if !constant {
                    k.add(a)?;
                }
            }
            if k.len() as i64 > budget {
                tick(BUD_STRUCT_WIDE);
                let r = PyTuple::new(p, [k.into_any(), (budget + 1).into_pyobject(p)?.into_any()])?.into_any();
                store_kids(&kids, o, &r)?;
                return Ok(r);
            }
        }
    }
    let constructing = eng.getattr(intern!(p, "_constructing"))?;
    let mine = !engmemo::contains(&constructing, o)?;
    if mine {
        engmemo::set_add(&constructing, o)?;           // as Session.node does
    }
    let built = (|| -> PyResult<(Bound<'py, PyAny>, Bound<'py, PyAny>)> {
        let ct = eng.getattr(intern!(p, "clause_templates"))?;
        tick(BUD_CB_TEMPLATES);
        let (compiled, mut formulas) = if !ct.is_none() {
            let t: Vec<Bound<'py, PyAny>> = ct.call1((o,))?.try_iter()?.collect::<PyResult<_>>()?;
            let [c, f]: [Bound<'py, PyAny>; 2] = t.try_into().map_err(|t: Vec<_>| {
                pyo3::exceptions::PyValueError::new_err(format!("expected 2 values to unpack, got {}", t.len()))
            })?;
            (c, f)
        } else {
            (PyTuple::empty(p).into_any(), eng.getattr(intern!(p, "templates"))?.call1((o,))?)
        };
        if !ext.is_none() && ext.getattr(intern!(p, "has_node_facts"))?.is_truthy()? {
            tick(BUD_CB_EXT);
            let l = PyList::empty(p);
            for f in formulas.try_iter()? {
                l.append(f?)?;
            }
            formulas = l.into_any().add(ext.call_method1(intern!(p, "node_facts"), (o,))?)?;
        }
        Ok((compiled, formulas))
    })();
    if mine {
        engmemo::set_discard(&constructing, o)?;
    }
    let (compiled, formulas) = built?;
    let k = PySet::empty(p)?;
    let (objs_n, pattern_n, used_n, node_n) = (intern!(p, "objs"), intern!(p, "pattern"), intern!(p, "used"), intern!(p, "node"));
    for comp in compiled.try_iter()? {
        let comp = comp?;
        let (objs, pat) = (comp.getattr(objs_n)?, comp.getattr(pattern_n)?);
        for i in pat.getattr(used_n)?.try_iter()? {
            let i = i?;
            if i.ne(pat.getattr(node_n)?)? {
                k.add(objs.get_item(&i)?)?;
            }
        }
    }
    for f in formulas.try_iter()? {
        add_kids_of(&k, &f?, &atoms_of, &kid)?;
    }
    k.discard(o)?;
    let w: i64 = if compiled.is_truthy()? && formulas.is_truthy()? && !planted(CONE_STRUCT_WEIGHT_ONE) { 2 } else { 1 };
    let r = PyTuple::new(p, [k.into_any(), w.into_pyobject(p)?.into_any()])?.into_any();
    store_kids(&kids, o, &r)?;
    Ok(r)
}

/// `Engine._cone_info` (engine.py:1676 on 4215655): `(cone, weight, rel)` of the cone object `d`, memoized in `_cones`
/// (emptied at 100,000 entries).
pub(crate) fn cone_info<'py>(eng: &Bound<'py, PyAny>, d: &Bound<'py, PyAny>, budget: i64) -> PyResult<Bound<'py, PyAny>> {
    tick(BUD_CONE_INFO);
    let p = eng.py();
    let cones = eng.getattr(intern!(p, "_cones"))?;
    if let Some(r) = engmemo::get(&cones, d)? {
        tick(BUD_CONES_HIT);
        return Ok(r);
    }
    let em = engine_mod(p)?;
    let pcls = em.getattr(intern!(p, "P"))?;
    let ratoms = em.getattr(intern!(p, "RELATION_ATOMS"))?;
    let seen = PySet::new(p, [d])?;
    let mut stack = vec![d.clone()];
    let mut total: i64 = 0;
    let mut rel = false;
    let mut over = false;
    while let Some(o) = stack.pop() {
        let s = struct_(eng, &o, budget)?;
        let (k, w) = (s.get_item(0)?, s.get_item(1)?.extract::<i64>()?);
        total += w;
        if o.get_type().is(&pcls) && ratoms.contains(o.getattr(intern!(p, "pred"))?)? {
            rel = true;
        }
        let known = if o.is(d) { None } else { engmemo::get(&cones, &o)? };
        if let Some(known) = known {
            let (kc, krel) = (known.get_item(0)?, known.get_item(2)?);
            if kc.is_none() {
                over = true; // a sub-cone that does not fit
                break;
            }
            rel = rel || krel.is_truthy()?;
            // a known (closed) sub-cone: count its objects, no expansion
            for x in kc.try_iter()? {
                let x = x?;
                if !seen.contains(&x)? {
                    seen.add(&x)?;
                    total += struct_weight(eng, &x, budget)?;
                }
            }
        } else {
            for x in k.try_iter()? {
                let x = x?;
                if !seen.contains(&x)? {
                    seen.add(&x)?;
                    stack.push(x);
                }
            }
        }
        if total > budget {
            over = true;
            break;
        }
    }
    let r = if over && !planted(CONE_INFO_OVER_FITS) {
        PyTuple::new(p, [p.None().into_bound(p), total.max(budget + 1).into_pyobject(p)?.into_any(), rel_obj(p, rel)])?
    } else {
        let fs = p.get_type::<PyFrozenSet>().call1((&seen,))?;
        PyTuple::new(p, [fs, total.into_pyobject(p)?.into_any(), rel_obj(p, rel)])?
    };
    if engmemo::len(&cones)? >= 100_000 && !planted(CONE_CONES_NO_BOUND) {
        tick(EM_FULL);
        engmemo::clear(&cones)?;
    }
    let r = r.into_any();
    engmemo::set(&cones, d, &r)?;
    Ok(r)
}

/// `Engine._drop_cones` (engine.py:1603 on 4215655). 5c9c's plant `em-qcones-clear-skip` sits on this now (Rust clears the maps
/// directly, not through the view's `clear`).
pub(crate) fn drop_cones(eng: &Bound<'_, PyAny>) -> PyResult<()> {
    tick(BUD_DROP_CONES);
    let p = eng.py();
    for n in [intern!(p, "_kids"), intern!(p, "_cones"), intern!(p, "_qcones"), intern!(p, "_glue_adapters")] {
        let name = n.to_str()?;
        if (name == "_cones" && planted(CONE_DROP_SKIP_CONES)) || (name == "_qcones" && planted(EM_QCONES_CLEAR_SKIP)) {
            continue;
        }
        engmemo::clear(&eng.getattr(n)?)?;
    }
    Ok(())
}

#[pyfunction]
fn bud_struct<'py>(eng: &Bound<'py, PyAny>, o: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    tick(BUD_PY_STRUCT);
    match budget_of(eng)? {
        Some(b) => struct_(eng, o, b),
        None => py_method(eng, "_struct")?.call1((eng, o)),
    }
}

#[pyfunction]
fn bud_cone_info<'py>(eng: &Bound<'py, PyAny>, d: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    tick(BUD_PY_CONE_INFO);
    match budget_of(eng)? {
        Some(b) => cone_info(eng, d, b),
        None => py_method(eng, "_cone_info")?.call1((eng, d)),
    }
}

#[pyfunction]
fn bud_drop_cones(eng: &Bound<'_, PyAny>) -> PyResult<()> {
    tick(BUD_PY_DROP_CONES);
    drop_cones(eng)
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
        let ci = cone_info(eng, &o, budget)?;
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
                    weight += struct_weight(eng, &x, budget)?;
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

/// `Engine._query_cone` (engine.py:1726 on 2b98ab4): `(cone, weight, rel, sums, zs)` for `f`, memoized per engine in
/// `_qcones` (Rust-native since 5c9c, engmemo.rs), keyed `(f, link)`, emptied at 50,000 entries as Python's.
pub(crate) fn query_cone<'py>(eng: &Bound<'py, PyAny>, f: &Bound<'py, PyAny>, link: bool, budget: i64) -> PyResult<Bound<'py, PyAny>> {
    tick(BUD_QUERY_CONE);
    let p = eng.py();
    let key = if planted(EM_QCONE_KEY_F) { f.clone() } else { PyTuple::new(p, [f.clone(), rel_obj(p, link)])?.into_any() };
    let qc = eng.getattr(intern!(p, "_qcones"))?;
    if let Some(r) = engmemo::get(&qc, &key)? {
        return Ok(r);
    }
    let em = engine_mod(p)?;
    let atoms = global(&em, intern!(p, "atoms_of"), f)?;
    let specs = eng.getattr(intern!(p, "_relation_specs"))?;
    let src = if specs.is_truthy()? { global(&em, intern!(p, "glue_atoms"), &atoms)? } else { atoms.clone() };
    let kid = em.getattr(intern!(p, "_kid"))?;
    let objs = PySet::empty(p)?;
    for a in src.try_iter()? {
        tick(BUD_CB_GLOBAL);
        objs.add(kid.call1((a?,))?)?;
    }
    let pred = intern!(p, "pred");
    let expr = intern!(p, "expr");
    if link {
        let index = em.getattr(intern!(p, "PRED_INDEX"))?;
        let lo = em.getattr(intern!(p, "link_objects"))?;
        let memo = eng.getattr(intern!(p, "_glue_adapters"))?;
        for a in atoms.try_iter()? {
            let a = a?;
            if index.contains(a.getattr(pred)?)? {
                tick(BUD_CB_GLOBAL);
                let more = lo.call1((a.getattr(expr)?, &specs, &memo))?;
                objs.call_method1(intern!(p, "__ior__"), (more,))?;
            }
        }
    }
    let sign = em.getattr(intern!(p, "_SIGN_PREDS"))?;
    let sums = PySet::empty(p)?;
    if !planted(EM_QCONE_NO_SUMS) {
        for a in atoms.try_iter()? {
            let a = a?;
            if !sign.contains(a.getattr(pred)?)? {
                continue;
            }
            let e = a.getattr(expr)?;
            let is_add = match e.getattr(intern!(p, "is_Add")) {
                Ok(v) => v.is_truthy()?,
                Err(_) => false,
            };
            if !is_add {
                continue;
            }
            let fs = match e.getattr(intern!(p, "free_symbols")) {
                Ok(v) => v.is_truthy()?,
                Err(_) => false,
            };
            if fs {
                sums.add(e)?;
            }
        }
    }
    let sums = PyFrozenSet::new(p, sums.iter())?;
    let u = union(eng, objs.as_any(), budget)?;
    let zs = global(&em, intern!(p, "zero_args"), &atoms)?;
    let r = PyTuple::new(p, [u.get_item(0)?, u.get_item(1)?, u.get_item(2)?, sums.into_any(), zs])?.into_any();
    if engmemo::len(&qc)? >= 50_000 {
        tick(EM_FULL);
        engmemo::clear(&qc)?;
    }
    engmemo::set(&qc, &key, &r)?;
    Ok(r)
}

/// `Engine._query_cone` as a method: Python's own when the budget isn't an int.
#[pyfunction]
fn bud_query_cone<'py>(eng: &Bound<'py, PyAny>, f: &Bound<'py, PyAny>, link: bool) -> PyResult<Bound<'py, PyAny>> {
    match budget_of(eng)? {
        Some(b) => query_cone(eng, f, link, b),
        None => py_method(eng, "_query_cone")?.call1((eng, f, link)),
    }
}

fn global<'py>(em: &Bound<'py, PyModule>, name: &Bound<'py, pyo3::types::PyString>, arg: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    tick(BUD_CB_GLOBAL);
    em.getattr(name)?.call1((arg,))
}

/// `Engine._within_budget`.
fn within_budget(eng: &Bound<'_, PyAny>, prop: &Bound<'_, PyAny>, assumptions: Option<&Bound<'_, PyAny>>, budget: i64) -> PyResult<bool> {
    let p = eng.py();
    let r = query_cone(eng, prop, false, budget)?;
    let mut rel = r.get_item(2)?.is_truthy()?;
    let mut sums = r.get_item(3)?;
    let zp = r.get_item(4)?.cast_into::<PyTuple>()?;
    let mut cross: Option<Bound<'_, PyList>> = None;
    let specs = eng.getattr(intern!(p, "_relation_specs"))?.is_truthy()?;
    if let Some(a) = assumptions {
        let ra = query_cone(eng, a, false, budget)?;
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
    let rp = query_cone(eng, prop, link, budget)?;
    let cp = rp.get_item(0)?;
    if cp.is_none() {
        return Ok(false);
    }
    let Some(a) = assumptions else { return Ok(true) };
    let wp: i64 = rp.get_item(1)?.extract()?;
    let ra = query_cone(eng, a, link, budget)?;
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
            total += struct_weight(eng, &x, budget)?;
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

/// `Engine._over_budget`: a query over the discovery budget, None, no session touched. Step 5c10d: writes the Rust-owned
/// flag and counter (entry.rs).
pub(crate) fn over_budget<'py>(eng: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    tick(BUD_OVER_BUDGET);
    let p = eng.py();
    if !planted(OVER_BUDGET_NO_FLAG) {
        crate::entry::set_flag(eng, true)?;
    }
    crate::entry::bump(eng, crate::entry::BUDGET_LIMITED, 1)?;
    Ok(p.None().into_bound(p))
}

#[pyfunction]
fn bud_over_budget<'py>(eng: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    over_budget(eng)
}

/// `Engine._note_budget`: the query passed `_within_budget`, so its session ran uncapped.
pub(crate) fn note_budget(eng: &Bound<'_, PyAny>, s: &Bound<'_, PyAny>) -> PyResult<()> {
    tick(BUD_NOTE_BUDGET);
    let p = eng.py();
    let truncated = crate::session::ses_flag(s, crate::session::SS_TRUNCATED)?;
    if truncated {
        return Err(PyAssertionError::new_err("a session of a query within the budget was truncated"));
    }
    if !planted(NOTE_BUDGET_KEEP_FLAG) {
        crate::entry::set_flag(eng, truncated)?;
    }
    if truncated || planted(crate::relations_core::NOTE_BUDGET_COUNT) {
        crate::entry::bump(eng, crate::entry::BUDGET_LIMITED, 1)?;
    }
    Ok(())
}

#[pyfunction]
fn bud_note_budget(eng: &Bound<'_, PyAny>, s: &Bound<'_, PyAny>) -> PyResult<()> {
    note_budget(eng, s)
}

/// `self._cone_info(d)` from Rust (entry.rs): Python's for a budget that isn't an int, as `bud_cone_info`.
pub(crate) fn cone_info_any<'py>(eng: &Bound<'py, PyAny>, d: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    match budget_of(eng)? {
        Some(b) => cone_info(eng, d, b),
        None => py_method(eng, "_cone_info")?.call1((eng, d)),
    }
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(bud_union, m)?)?;
    m.add_function(wrap_pyfunction!(bud_struct, m)?)?;
    m.add_function(wrap_pyfunction!(bud_cone_info, m)?)?;
    m.add_function(wrap_pyfunction!(bud_drop_cones, m)?)?;
    m.add_function(wrap_pyfunction!(bud_query_cone, m)?)?;
    m.add_function(wrap_pyfunction!(bud_within_budget, m)?)?;
    m.add_function(wrap_pyfunction!(bud_over_budget, m)?)?;
    m.add_function(wrap_pyfunction!(bud_note_budget, m)?)
}
