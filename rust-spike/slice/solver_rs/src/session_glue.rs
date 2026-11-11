//! Step 5c6: the rest of `Session` (`engine.py:305-384`, `936-1153`, `1182-1197`): `__init__`, `assume_formula`, `link_set`,
//! `assumption_lits`, `_set_glue`, `_group_sel`, `_glue_of`. As in 5c1-5c5, the session's containers (`_groups`, `literals`,
//! the solver, `Relations`) stay the Python objects Python reads later, so state is Python's by construction; every read and
//! call Python makes, Rust makes in the same order. Among these seven, and from `query.rs`, the calls are direct Rust calls.
//! Other `Session` methods (`emit`, `_ensure_atoms`, `discover`, `_relations`, `dvar`) are called by name, as Python calls
//! them; under the default Rust backend each is a 5c1/5c3 shell into Rust. Module globals (`atoms_of`, `zero_args`,
//! `under_of`, `glue_atoms`, `theory_scope`, `_affine_pair`, `_is_number`, `compile_formula`, `Solver`, `VarTable`,
//! `Relations`) are read from `satassume.engine` at the call, so whatever is installed there is what runs.
use pyo3::exceptions::PyAssertionError;
use pyo3::intern;
use pyo3::prelude::*;
use crate::relkeys::RDict;
use pyo3::types::{PyBool, PyCFunction, PyDict, PyFrozenSet, PyList, PySet, PyTuple};

use crate::relations_core::{
    planted, AF_DROP_RELATIONS, AL_DROP_DELTA, GLUE_OF_PLAIN, GROUP_SEL_NO_IMPL, INIT_NO_RELATIONS, LINK_SET_SKIP, SET_GLUE_NO_EMIT,
};
use crate::session::{
    tick, SES_ASSUME_FORMULA, SES_ASSUMPTION_LITS, SES_GLUE_OF, SES_GROUP_SEL, SES_INIT, SES_LINK_SET, SES_SET_GLUE,
};

fn engine_mod(p: Python<'_>) -> PyResult<Bound<'_, PyModule>> {
    p.import(intern!(p, "satassume.engine"))
}

fn builtin<'py>(p: Python<'py>, name: &str) -> PyResult<Bound<'py, PyAny>> {
    p.import(intern!(p, "builtins"))?.getattr(name)
}

/// `Session.__init__`.
pub(crate) fn init(s: &Bound<'_, PyAny>, engine: &Bound<'_, PyAny>, scope: &Bound<'_, PyAny>) -> PyResult<()> {
    tick(SES_INIT);
    let p = s.py();
    let em = engine_mod(p)?;
    s.setattr(intern!(p, "engine"), engine)?;
    s.setattr(intern!(p, "scope"), scope)?;
    let solver = em.getattr(intern!(p, "Solver"))?.call0()?;
    s.setattr(intern!(p, "solver"), &solver)?;
    solver.setattr(intern!(p, "track_owners"), false)?;
    solver.call_method1(
        intern!(p, "set_rule_block"),
        (em.getattr(intern!(p, "RULE_INTERNAL"))?, em.getattr(intern!(p, "NPRED"))?),
    )?;
    s.setattr(intern!(p, "table"), em.getattr(intern!(p, "VarTable"))?.call0()?)?;
    s.setattr(intern!(p, "base"), PyDict::new(p))?;
    // `frontier`, `pending`, `pending_c`, `demand`, `deferred`, `literals`, `_groups`: the core's, empty from the start (state
    // part 3, sub-part 5: ses_cont.rs); a session with no core gets Python's own.
    if crate::session::core_of(s).is_err() {
        s.setattr(intern!(p, "frontier"), em.getattr(intern!(p, "deque"))?.call0()?)?;
        s.setattr(intern!(p, "pending"), PyDict::new(p))?;
        s.setattr(intern!(p, "pending_c"), PyDict::new(p))?;
        s.setattr(intern!(p, "demand"), PyDict::new(p))?;
        s.setattr(intern!(p, "deferred"), PyList::empty(p))?;
        s.setattr(intern!(p, "literals"), PyDict::new(p))?;
        s.setattr(intern!(p, "_groups"), PyDict::new(p))?;
    }
    s.setattr(intern!(p, "assumption_formula"), p.None())?;
    s.setattr(intern!(p, "_a_raw"), PyTuple::empty(p))?;
    s.setattr(intern!(p, "_a_zs"), PyTuple::empty(p))?;
    s.setattr(intern!(p, "_a_under"), p.None())?;
    s.setattr(intern!(p, "_a_all"), p.None())?;
    s.setattr(intern!(p, "_a_atoms"), PyFrozenSet::empty(p)?)?;
    s.setattr(intern!(p, "relations"), p.None())?;
    // `verdict`, `sel`, `n_hold`, `_link_pending`, `_neg_shared`, `truncated`: the core's, at `__init__`'s values from the start
    // (state part 3, sub-part 5); `defvars`, `_dv`, `_dv_node` are session.rs `St`'s, and Python's attributes were never read.
    // `s.xfer`: the core's, None from the start (state step, part 2 (ii)); `Session.xfer` is its view.
    if scope.getattr(intern!(p, "glue"))?.is_truthy()? && !planted(INIT_NO_RELATIONS) {
        let specs = engine.getattr(intern!(p, "_relation_specs"))?;
        if specs.is_truthy()? {
            let rel = em.getattr(intern!(p, "Relations"))?.call1((s, engine.getattr(intern!(p, "_relation_specs"))?))?;
            s.setattr(intern!(p, "relations"), rel)?;
        }
    }
    Ok(())
}

/// `Session.assume_formula`.
pub(crate) fn assume_formula<'py>(s: &Bound<'py, PyAny>, f: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    tick(SES_ASSUME_FORMULA);
    let p = s.py();
    let em = engine_mod(p)?;
    s.setattr(intern!(p, "assumption_formula"), f)?;
    s.setattr(intern!(p, "_a_raw"), crate::session::core_of(s)?.borrow().atoms_of(f)?)?;
    let raw = s.getattr(intern!(p, "_a_raw"))?;
    s.setattr(intern!(p, "_a_zs"), em.getattr(intern!(p, "zero_args"))?.call1((&raw,))?)?;
    s.setattr(intern!(p, "_a_under"), p.None())?;
    s.setattr(intern!(p, "_a_all"), p.None())?;
    s.call_method1(intern!(p, "_ensure_atoms"), (f,))?;
    let sv = crate::session::table_of(s)?.call_method0(intern!(p, "aux"))?;
    crate::session::ses_set_int(s, crate::session::SS_SEL, sv.extract()?)?;
    // `sum(1 for a in self._a_raw if len(DEF_LITS.get(a.pred, ((), ()))[1]) > 1) >= _NEG_SHARED`
    let def_lits = em.getattr(intern!(p, "DEF_LITS"))?;
    let empty = PyTuple::new(p, [PyTuple::empty(p), PyTuple::empty(p)])?;
    let raw = s.getattr(intern!(p, "_a_raw"))?;
    let mut n: i64 = 0;
    for a in raw.try_iter()? {
        let a = a?;
        let d = def_lits.call_method1(intern!(p, "get"), (a.getattr(intern!(p, "pred"))?, &empty))?;
        if d.get_item(1)?.len()? > 1 {
            n += 1;
        }
    }
    let ns = n.into_pyobject(p)?.into_any().ge(em.getattr(intern!(p, "_NEG_SHARED"))?)?;
    crate::session::ses_set_flag(s, crate::session::SS_NEG_SHARED, ns)?;
    let neg: Bound<'py, PyAny> = sv.neg()?;
    let tail = PyList::new(p, [&neg])?.unbind();
    let ses = s.clone().unbind();
    // `def emit(clause): self.emit(clause + [-s])`
    let emit = PyCFunction::new_closure(p, None, None, move |args: &Bound<'_, PyTuple>, _kw: Option<&Bound<'_, PyDict>>| -> PyResult<()> {
        let p = args.py();
        let clause = args.get_item(0)?;
        let c = clause.add(tail.bind(p))?;
        ses.bind(p).call_method1(intern!(p, "emit"), (c,))?;
        Ok(())
    })?;
    em.getattr(intern!(p, "compile_formula"))?.call1((f, crate::session::table_of(s)?, emit, s.getattr(intern!(p, "dvar"))?))?;
    s.call_method0(intern!(p, "discover"))?;
    if !s.getattr(intern!(p, "relations"))?.is_none() && !planted(AF_DROP_RELATIONS) {
        let exts = s.getattr(intern!(p, "engine"))?.getattr(intern!(p, "_extensions"))?;
        // the session holds `f`'s node: its core is the holder, so nothing is converted by name here
        let sc = match crate::session::core_of(s) {
            Ok(core) => crate::scope_core::theory_scope_from(em.as_any(), "theory_scope", f, &p.None().into_bound(p), &exts, &*core.borrow())?,
            Err(_) => em.getattr(intern!(p, "theory_scope"))?.call1((f, p.None(), exts))?,
        };
        if sc.getattr(intern!(p, "glue"))?.is_truthy()? {
            s.call_method1(intern!(p, "_relations"), (f,))?;
        } else {
            crate::session::ses_set_flag(s, crate::session::SS_LINK_PENDING, true)?;
        }
    }
    Ok(PyList::new(p, [sv])?.into_any())
}

/// `Session.link_set`.
pub(crate) fn link_set(s: &Bound<'_, PyAny>) -> PyResult<()> {
    tick(SES_LINK_SET);
    let p = s.py();
    if crate::session::ses_flag(s, crate::session::SS_LINK_PENDING)? {
        crate::session::ses_set_flag(s, crate::session::SS_LINK_PENDING, false)?;
        if !planted(LINK_SET_SKIP) {
            s.call_method1(intern!(p, "_relations"), (s.getattr(intern!(p, "assumption_formula"))?,))?;
        }
    }
    Ok(())
}

/// `x.pred in RELATION_ATOMS`.
fn is_rel_atom(x: &Bound<'_, PyAny>, ra: &Bound<'_, PyAny>) -> PyResult<bool> {
    ra.contains(x.getattr(intern!(x.py(), "pred"))?)
}

/// `Session.assumption_lits`.
pub(crate) fn assumption_lits<'py>(s: &Bound<'py, PyAny>, prop: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    tick(SES_ASSUMPTION_LITS);
    let p = s.py();
    let em = engine_mod(p)?;
    let sel = crate::session::ses_int(s, crate::session::SS_SEL)?.into_pyobject(p)?.into_any();
    let lits = if sel.is_truthy()? { PyList::new(p, [&sel])? } else { PyList::empty(p) };
    crate::session::ses_set_int(s, crate::session::SS_N_HOLD, lits.len() as i64)?;
    let rel = s.getattr(intern!(p, "relations"))?;
    if rel.is_none() {
        return Ok(lits.into_any());
    }
    if !prop.is_none() && crate::session::ses_flag(s, crate::session::SS_LINK_PENDING)? {
        return Err(PyAssertionError::new_err("Session.link_set"));
    }
    let ra = em.getattr(intern!(p, "RELATION_ATOMS"))?;
    let mut a_all = s.getattr(intern!(p, "_a_all"))?;
    if a_all.is_none() {
        let g = em.getattr(intern!(p, "glue_atoms"))?.call1((s.getattr(intern!(p, "_a_raw"))?,))?;
        s.setattr(intern!(p, "_a_all"), &g)?;
        a_all = g;
        let mut keep = vec![];
        for x in a_all.try_iter()? {
            let x = x?;
            if is_rel_atom(&x, &ra)? {
                keep.push(x);
            }
        }
        s.setattr(intern!(p, "_a_atoms"), PyFrozenSet::new(p, &keep)?)?;
    }
    let a_atoms = s.getattr(intern!(p, "_a_atoms"))?;
    let a_rel = a_atoms.is_truthy()?;
    let p_all: Bound<'py, PyAny> = if !prop.is_none() {
        let atoms = crate::session::core_of(s)?.borrow().atoms_of(prop)?;
        glue_of(s, &atoms)?
    } else {
        PyTuple::empty(p).into_any()
    };
    let mut p_atoms = vec![];
    for x in p_all.try_iter()? {
        let x = x?;
        if is_rel_atom(&x, &ra)? {
            p_atoms.push(x);
        }
    }
    let p_atoms = PyList::new(p, p_atoms)?;
    let p_rel = !p_atoms.is_empty();
    if !(a_rel || p_rel) {
        let both = a_all.add(builtin(p, "tuple")?.call1((&p_all,))?)?;
        if !em.getattr(intern!(p, "_affine_pair"))?.call1((both,))?.is_truthy()? {
            return Ok(lits.into_any());
        }
    }
    let a_x: Bound<'py, PyAny> = if a_rel {
        rel.call_method1(intern!(p, "wants_transfer"), (&a_atoms,))?
    } else {
        PyBool::new(p, false).to_owned().into_any()
    };
    let seen: Bound<'py, PyAny> = if a_rel {
        set_glue(s, &a_all, &a_x)?.into_any()
    } else {
        let mut seen = PyTuple::empty(p).into_any();
        if a_all.is_truthy()? {
            let ga = group_sel(s, &p.None().into_bound(p), &a_all)?;
            if ga.is_truthy()? {
                lits.append(&ga)?;
                seen = crate::ses_cont::Ses::of(s).d_item(crate::ses_cont::SD_GROUPS, &p.None().into_bound(p))?.get_item(1)?;
            }
        }
        seen
    };
    crate::session::ses_set_int(s, crate::session::SS_N_HOLD, lits.len() as i64)?;
    if p_all.is_truthy()? && !planted(AL_DROP_DELTA) {
        for x in rel.call_method1(intern!(p, "selectors_of"), (&p_all,))?.try_iter()? {
            let x = x?;
            if !seen.contains(&x)? {
                lits.append(x)?;
            }
        }
        let xs = crate::session::core_of(s)?.borrow().xfer_obj(&rel, crate::session::XSEL);
        if !xs.is_none() && p_rel && !a_x.is_truthy()? {
            let u = a_atoms.call_method1(intern!(p, "union"), (&p_atoms,))?;
            if rel.call_method1(intern!(p, "wants_transfer"), (u,))?.is_truthy()? {
                lits.append(xs)?;
            }
        }
    }
    Ok(lits.into_any())
}

fn sorted<'py>(x: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    builtin(x.py(), "sorted")?.call1((x,))
}

/// `Session._set_glue`.
pub(crate) fn set_glue<'py>(s: &Bound<'py, PyAny>, a_all: &Bound<'py, PyAny>, xfer: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    tick(SES_SET_GLUE);
    let p = s.py();
    let em = engine_mod(p)?;
    let rel = s.getattr(intern!(p, "relations"))?;
    let groups = crate::ses_cont::Ses::of(s);
    let t = PyBool::new(p, true).to_owned().into_any();
    let mut g = groups.d_get(crate::ses_cont::SD_GROUPS, &t)?;
    if g.is_none() {
        let l = PyList::new(p, [PySet::empty(p)?.into_any(), p.None().into_bound(p), t.clone(), t.clone()])?;
        groups.d_set(crate::ses_cont::SD_GROUPS, &t, l.as_any())?;
        g = l.into_any();
    }
    let have = g.get_item(0)?;
    let xf = xfer.is_truthy()?;
    let len = |name: &Bound<'py, PyAny>| -> PyResult<usize> { name.len() };
    let link_sel = RDict::of(&rel, crate::session::RD_LINK_SEL)?;
    let num_sel = RDict::of(&rel, crate::session::RD_NUM_SEL)?;
    let atom_sel = RDict::of(&rel, crate::session::RD_ATOM_SEL)?;
    let m1 = (-1i64).into_pyobject(p)?.into_any();
    let s0 = if g.get_item(2)?.is_truthy()? { (link_sel.len()? + num_sel.len()?).into_pyobject(p)?.into_any() } else { m1.clone() };
    let s1 = if g.get_item(3)?.is_truthy()? { atom_sel.len()?.into_pyobject(p)?.into_any() } else { m1.clone() };
    let s2 = if xf { crate::session::core_of(s)?.borrow().xfer_obj(&rel, crate::session::XSEL) } else { p.None().into_bound(p) };
    let stamp = PyTuple::new(p, [s0, s1, s2])?;
    if stamp.as_any().eq(g.get_item(1)?)? {
        return Ok(have);
    }
    let want = PySet::new(p, rel.call_method1(intern!(p, "selectors_of"), (a_all,))?.try_iter()?.collect::<PyResult<Vec<_>>>()?)?;
    if xf {
        let xs = crate::session::core_of(s)?.borrow().xfer_obj(&rel, crate::session::XSEL);
        if !xs.is_none() {
            want.add(xs)?;
        }
    }
    let new = want.as_any().sub(&have)?;
    if new.is_truthy()? {
        for x in sorted(&new)?.try_iter()? {
            let x = x?;
            if !planted(SET_GLUE_NO_EMIT) {
                s.call_method1(intern!(p, "emit"), (PyList::new(p, [x])?,))?;
            }
        }
        have.call_method1(intern!(p, "__ior__"), (&new,))?;
    }
    let (lsel, nsel, asel) = (RDict::of(&rel, crate::session::RD_LINK_SEL)?, RDict::of(&rel, crate::session::RD_NUM_SEL)?, RDict::of(&rel, crate::session::RD_ATOM_SEL)?);
    let status = RDict::of(&rel, crate::session::RD_STATUS)?;
    let pred_index = em.getattr(intern!(p, "PRED_INDEX"))?;
    let ra = em.getattr(intern!(p, "RELATION_ATOMS"))?;
    let is_number = em.getattr(intern!(p, "_is_number"))?;
    let (mut tp, mut ap) = (false, false);
    for x in a_all.try_iter()? {
        let x = x?;
        let pred = x.getattr(intern!(p, "pred"))?;
        if pred_index.contains(&pred)? {
            let e = x.getattr(intern!(p, "expr"))?;
            if !lsel.contains(&e)? && !nsel.contains(&e)? && !is_number.call1((&e,))?.is_truthy()? {
                tp = true;
            }
        } else if ra.contains(&pred)? {
            if !asel.contains(&x)? {
                ap = true;
            }
            let st = status.get(&x)?;
            if !(st.is_instance_of::<PyBool>() && !st.is_truthy()?) {
                for e in x.getattr(intern!(p, "expr"))?.try_iter()? {
                    let e = e?;
                    if !lsel.contains(&e)? && !is_number.call1((&e,))?.is_truthy()? {
                        tp = true;
                        break;
                    }
                }
            }
        }
    }
    g.set_item(2, tp)?;
    g.set_item(3, ap)?;
    let s0 = if tp { (lsel.len()? + nsel.len()?).into_pyobject(p)?.into_any() } else { m1.clone() };
    let s1 = if ap { asel.len()?.into_pyobject(p)?.into_any() } else { m1.clone() };
    let s2 = if xf { crate::session::core_of(s)?.borrow().xfer_obj(&rel, crate::session::XSEL) } else { p.None().into_bound(p) };
    g.set_item(1, PyTuple::new(p, [s0, s1, s2])?)?;
    Ok(have)
}

/// `Session._group_sel`.
pub(crate) fn group_sel<'py>(s: &Bound<'py, PyAny>, key: &Bound<'py, PyAny>, atoms: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    tick(SES_GROUP_SEL);
    let p = s.py();
    let rel = s.getattr(intern!(p, "relations"))?;
    let groups = crate::ses_cont::Ses::of(s);
    let g = groups.d_get(crate::ses_cont::SD_GROUPS, key)?;
    let stamp = PyTuple::new(
        p,
        [
            RDict::of(&rel, crate::session::RD_LINK_SEL)?.len()?.into_pyobject(p)?.into_any(),
            RDict::of(&rel, crate::session::RD_ATOM_SEL)?.len()?.into_pyobject(p)?.into_any(),
            RDict::of(&rel, crate::session::RD_NUM_SEL)?.len()?.into_pyobject(p)?.into_any(),
            crate::session::core_of(s)?.borrow().xfer_obj(&rel, crate::session::XSEL),
        ],
    )?;
    if !g.is_none() && g.get_item(2)?.eq(&stamp)? {
        return g.get_item(0);
    }
    let want = PySet::new(p, rel.call_method1(intern!(p, "selectors_of"), (atoms,))?.try_iter()?.collect::<PyResult<Vec<_>>>()?)?;
    let zero = 0i64.into_pyobject(p)?.into_any();
    let solver = crate::session::solver_of(s)?;
    let g = if g.is_none() {
        if want.is_empty() {
            groups.d_set(crate::ses_cont::SD_GROUPS, key, PyList::new(p, [zero.clone(), PySet::empty(p)?.into_any(), stamp.into_any()])?.as_any())?;
            return Ok(zero);
        }
        let v = crate::session::table_of(s)?.call_method0(intern!(p, "aux"))?;
        solver.call_method1(intern!(p, "ensure_vars"), (&v,))?;
        let l = PyList::new(p, [v.clone(), PySet::empty(p)?.into_any(), stamp.clone().into_any()])?;
        groups.d_set(crate::ses_cont::SD_GROUPS, key, l.as_any())?;
        crate::session::solver_of(s)?.call_method1(intern!(p, "set_inert"), (&v,))?;
        l.into_any()
    } else if !g.get_item(0)?.is_truthy()? {
        if want.is_empty() {
            g.set_item(2, &stamp)?;
            return Ok(zero);
        }
        g.set_item(0, crate::session::table_of(s)?.call_method0(intern!(p, "aux"))?)?;
        solver.call_method1(intern!(p, "ensure_vars"), (g.get_item(0)?,))?;
        crate::session::solver_of(s)?.call_method1(intern!(p, "set_inert"), (g.get_item(0)?,))?;
        g
    } else {
        g
    };
    let (v, have) = (g.get_item(0)?, g.get_item(1)?);
    let nv = v.neg()?;
    for x in sorted(&want.as_any().sub(&have)?)?.try_iter()? {
        let x = x?;
        if !planted(GROUP_SEL_NO_IMPL) {
            s.call_method1(intern!(p, "emit"), (PyList::new(p, [nv.clone(), x])?,))?;
        }
    }
    have.call_method1(intern!(p, "__ior__"), (&want,))?;
    g.set_item(2, &stamp)?;
    Ok(v)
}

/// `Session._glue_of`.
pub(crate) fn glue_of<'py>(s: &Bound<'py, PyAny>, atoms: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    tick(SES_GLUE_OF);
    let p = s.py();
    let a_zs = s.getattr(intern!(p, "_a_zs"))?;
    if planted(GLUE_OF_PLAIN) {
        return Ok(atoms.clone());
    }
    if !a_zs.is_truthy()? {
        let mut zero = false;
        for x in atoms.try_iter()? {
            if x?.getattr(intern!(p, "pred"))?.eq("zero")? {
                zero = true;
                break;
            }
        }
        if !zero {
            return Ok(atoms.clone());
        }
    }
    let em = engine_mod(p)?;
    let mut u = s.getattr(intern!(p, "_a_under"))?;
    if u.is_none() {
        let v = em.getattr(intern!(p, "under_of"))?.call1((s.getattr(intern!(p, "_a_raw"))?,))?;
        s.setattr(intern!(p, "_a_under"), &v)?;
        u = v;
    }
    let kw = PyDict::new(p);
    kw.set_item(intern!(p, "cinfo"), PyTuple::new(p, [a_zs, u])?)?;
    em.getattr(intern!(p, "glue_atoms"))?.call((atoms,), Some(&kw))
}

#[pyfunction]
fn ses_init(s: &Bound<'_, PyAny>, engine: &Bound<'_, PyAny>, scope: &Bound<'_, PyAny>) -> PyResult<()> {
    init(s, engine, scope)
}

#[pyfunction]
fn ses_assume_formula<'py>(s: &Bound<'py, PyAny>, f: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    assume_formula(s, f)
}

#[pyfunction]
fn ses_link_set(s: &Bound<'_, PyAny>) -> PyResult<()> {
    link_set(s)
}

#[pyfunction]
#[pyo3(signature = (s, prop=None))]
fn ses_assumption_lits<'py>(s: &Bound<'py, PyAny>, prop: Option<&Bound<'py, PyAny>>) -> PyResult<Bound<'py, PyAny>> {
    let none = s.py().None().into_bound(s.py());
    assumption_lits(s, prop.unwrap_or(&none))
}

#[pyfunction]
fn ses_set_glue<'py>(s: &Bound<'py, PyAny>, a_all: &Bound<'py, PyAny>, xfer: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    set_glue(s, a_all, xfer)
}

#[pyfunction]
fn ses_group_sel<'py>(s: &Bound<'py, PyAny>, key: &Bound<'py, PyAny>, atoms: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    group_sel(s, key, atoms)
}

#[pyfunction]
fn ses_glue_of<'py>(s: &Bound<'py, PyAny>, atoms: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    glue_of(s, atoms)
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(ses_init, m)?)?;
    m.add_function(wrap_pyfunction!(ses_assume_formula, m)?)?;
    m.add_function(wrap_pyfunction!(ses_link_set, m)?)?;
    m.add_function(wrap_pyfunction!(ses_assumption_lits, m)?)?;
    m.add_function(wrap_pyfunction!(ses_set_glue, m)?)?;
    m.add_function(wrap_pyfunction!(ses_group_sel, m)?)?;
    m.add_function(wrap_pyfunction!(ses_glue_of, m)?)?;
    m.add_class::<EntMethod>()?;
    m.add_class::<GuardMethod>()
}

// --------------------------------------------------------------------------------------------------------------------
// The part 3 follow-up, item C7 (group-d-cause.md, "per-ask entry frame"): an Engine method over a Rust entry (`ent_ask`,
// `ent_is`, the record methods; session_live.py `_ENTRY_METHODS`) with no Python frame between the caller and Rust. A
// pyfunction is a builtin, which doesn't bind, so session_live wrapped each in a `def f(self, *a, **k)`: one Python
// frame per entry call. `EntMethod` binds as a function does (`PyMethod_New`, the bound method Python makes for a `def`),
// and the bound method's call is the pyfunction's own vectorcall.

extern "C" {
    /// CPython's `types.MethodType(f, obj)` (Objects/classobject.c, stable since 3.0; not in pyo3-ffi 0.30).
    fn PyMethod_New(f: *mut pyo3::ffi::PyObject, obj: *mut pyo3::ffi::PyObject) -> *mut pyo3::ffi::PyObject;
}

/// Plant 618 `ent-method-first-self`: every entry method binds the first engine it was read from (a wrong-value plant at
/// the binding: a second engine's calls act on the first). Caught by test_entry_frame.py, which reads each engine's stats.
pub(crate) const ENT_FIRST_SELF_PLANT: u16 = 618;

thread_local! {
    static FIRST_SELF: std::cell::RefCell<Option<Py<PyAny>>> = const { std::cell::RefCell::new(None) };
}

/// A method descriptor over a Rust entry `f`: `eng.name` is `f` bound to `eng`, `Engine.name` is the descriptor itself
/// (so the identity checks over the class, `patched` in context.rs, see what was installed), and calling the descriptor
/// calls `f` with the instance first, as `Engine.ask(eng, p)` calls a `def`.
#[pyclass(module = "sa_solver", frozen)]
pub(crate) struct EntMethod {
    f: Py<PyAny>,
    #[pyo3(get, name = "__name__")]
    name: Py<PyAny>,
    #[pyo3(get, name = "__qualname__")]
    qualname: Py<PyAny>,
    /// `__doc__` per object: CPython's PyType_FromSpec writes the type's own doc into its dict after the getsets, so a
    /// getter named `__doc__` is shadowed; session_live `_method_docs` puts this one under `__doc__`.
    #[pyo3(get, name = "_method_doc")]
    doc: Py<PyAny>,
}

/// The planner's ruling (3) on 293's deviations: a bound entry method must look like the Python method it replaces, since
/// P1 honours patched methods by name. A bound method forwards `__name__`, `__qualname__`, `__doc__` and `__module__` to its
/// `__func__`, the pyfunction (`ent_ask`, `sa_solver`). So the method binds a builtin of its own over the same C entry
/// point: named as the method (`ml_name`), with the method's doc (`ml_doc`), the class as its `__self__` (a builtin whose
/// `__self__` is a type has `__qualname__` `<class>.<name>`, Objects/methodobject.c `meth_get__qualname__`) and the
/// method's module. pyo3's pyfunction trampoline ignores `self`, so the call is unchanged. One `PyMethodDef` per installed
/// method, leaked: it must outlive the builtin, and installs are once per process.
fn renamed_entry(p: Python<'_>, f: &Bound<'_, PyAny>, name: &str, doc: Option<&str>, owner: &Bound<'_, PyAny>, module: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
    use pyo3::ffi;
    unsafe {
        if ffi::PyCFunction_CheckExact(f.as_ptr()) == 0 {
            return Ok(f.clone().unbind());
        }
        let src = &*(*(f.as_ptr() as *mut ffi::PyCFunctionObject)).m_ml;
        if src.ml_flags & ffi::METH_METHOD != 0 {
            return Ok(f.clone().unbind());
        }
        let cname = std::ffi::CString::new(name).map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        let cdoc = match doc.map(std::ffi::CString::new) {
            Some(Ok(d)) => d.into_raw() as *const std::ffi::c_char,
            Some(Err(e)) => return Err(pyo3::exceptions::PyValueError::new_err(e.to_string())),
            None => std::ptr::null(),
        };
        let def = Box::leak(Box::new(ffi::PyMethodDef { ml_name: cname.into_raw(), ml_meth: src.ml_meth, ml_flags: src.ml_flags, ml_doc: cdoc }));
        Ok(Bound::from_owned_ptr_or_err(p, ffi::PyCFunction_NewEx(def, owner.as_ptr(), module.as_ptr()))?.unbind())
    }
}

#[pymethods]
impl EntMethod {
    /// `owner` (the class) and `module` (the method's `__module__`) given: the method binds a builtin named as the method
    /// (`renamed_entry`). Without them it binds `f` itself, which a bound method then names `f.__name__` (test_entry_frame.py's
    /// control for the name check).
    #[new]
    #[pyo3(signature = (f, name, qualname, doc=None, owner=None, module=None))]
    fn new(
        p: Python<'_>,
        f: Py<PyAny>,
        name: Py<PyAny>,
        qualname: Py<PyAny>,
        doc: Option<Py<PyAny>>,
        owner: Option<Py<PyAny>>,
        module: Option<Py<PyAny>>,
    ) -> PyResult<Self> {
        let doc = doc.unwrap_or_else(|| p.None());
        let f = match (owner, module) {
            (Some(o), Some(m)) => {
                let n: String = name.bind(p).extract()?;
                let d: Option<String> = doc.bind(p).extract()?;
                renamed_entry(p, f.bind(p), &n, d.as_deref(), o.bind(p), m.bind(p))?
            }
            _ => f,
        };
        Ok(EntMethod { f, name, qualname, doc })
    }

    fn __get__<'py>(slf: &Bound<'py, Self>, obj: Option<&Bound<'py, PyAny>>, _typ: Option<&Bound<'py, PyAny>>) -> PyResult<Bound<'py, PyAny>> {
        let p = slf.py();
        match obj {
            Some(o) if !o.is_none() => {
                let o = if crate::session::sb_planted(ENT_FIRST_SELF_PLANT) {
                    FIRST_SELF.with(|c| c.borrow_mut().get_or_insert_with(|| o.clone().unbind()).bind(p).clone())
                } else {
                    o.clone()
                };
                unsafe { Bound::from_owned_ptr_or_err(p, PyMethod_New(slf.get().f.as_ptr(), o.as_ptr())) }
            }
            _ => Ok(slf.clone().into_any()),
        }
    }

    #[pyo3(signature = (*args, **kwargs))]
    fn __call__<'py>(
        &self,
        p: Python<'py>,
        args: &Bound<'py, pyo3::types::PyTuple>,
        kwargs: Option<&Bound<'py, pyo3::types::PyDict>>,
    ) -> PyResult<Bound<'py, PyAny>> {
        self.f.bind(p).call(args, kwargs)
    }

    /// The Rust entry under the method (session_live's tests, and a tool that wants the function).
    #[getter]
    fn __func__(&self, p: Python<'_>) -> Py<PyAny> {
        self.f.clone_ref(p)
    }
}

// --------------------------------------------------------------------------------------------------------------------
// The part 3 follow-up, item (4): session_live.py's guarded method wrappers with no Python frame. Each was
//     def f(self, *a): if not isinstance(<self or self.session>.__dict__.get('_table_view'), TableView): return PY_X[key](self, *a)
//                      return sa_solver.<entry>(self, *a)
// (a session with no core, `satassume/ref.py`'s or one built while `engine.VarTable` isn't `TableView`, runs Python's
// method). `GuardMethod` makes the same test and the same call in Rust; the Python method is read from `PY_X` at the call,
// as the def read it.

/// Plant 619 `gm-guard-skip`: the guard is skipped, so a session with no core is given the Rust entry (a wrong-value plant
/// at the guard). Caught by test_guard_method.py, which asks on sessions with no core and compares the answers.
pub(crate) const GM_GUARD_SKIP_PLANT: u16 = 619;

#[pyclass(module = "sa_solver", frozen)]
pub(crate) struct GuardMethod {
    f: Py<PyAny>,
    py_methods: Py<PyAny>,
    key: Py<PyAny>,
    via_session: bool,
    positional: bool,
    view: Py<PyAny>,
    /// The def it stands for (session_live's wrapper): session.rs `named` compares it, as it compared the def.
    pub(crate) origin: Py<PyAny>,
    #[pyo3(get, name = "__name__")]
    name: Py<PyAny>,
    #[pyo3(get, name = "__qualname__")]
    qualname: Py<PyAny>,
    /// `__doc__` per object: CPython's PyType_FromSpec writes the type's own doc into its dict after the getsets, so a
    /// getter named `__doc__` is shadowed; session_live `_method_docs` puts this one under `__doc__`.
    #[pyo3(get, name = "_method_doc")]
    doc: Py<PyAny>,
}

#[pymethods]
impl GuardMethod {
    /// `f` the Rust entry; `py_methods[key]` Python's method; `via_session`: the test reads `self.session` (a
    /// `Relations`); `positional`: keyword arguments are refused, as `def f(self, *a)` refuses them; `view` the class
    /// `TableView`.
    #[new]
    #[pyo3(signature = (f, py_methods, key, via_session, positional, view, origin, name, qualname, doc=None))]
    #[allow(clippy::too_many_arguments)]
    fn new(
        p: Python<'_>,
        f: Py<PyAny>,
        py_methods: Py<PyAny>,
        key: Py<PyAny>,
        via_session: bool,
        positional: bool,
        view: Py<PyAny>,
        origin: Py<PyAny>,
        name: Py<PyAny>,
        qualname: Py<PyAny>,
        doc: Option<Py<PyAny>>,
    ) -> Self {
        GuardMethod { f, py_methods, key, via_session, positional, view, origin, name, qualname, doc: doc.unwrap_or_else(|| p.None()) }
    }

    fn __get__<'py>(slf: &Bound<'py, Self>, obj: Option<&Bound<'py, PyAny>>, _typ: Option<&Bound<'py, PyAny>>) -> PyResult<Bound<'py, PyAny>> {
        match obj {
            Some(o) if !o.is_none() => unsafe { Bound::from_owned_ptr_or_err(slf.py(), PyMethod_New(slf.as_ptr(), o.as_ptr())) },
            _ => Ok(slf.clone().into_any()),
        }
    }

    #[pyo3(signature = (*args, **kwargs))]
    fn __call__<'py>(
        &self,
        p: Python<'py>,
        args: &Bound<'py, pyo3::types::PyTuple>,
        kwargs: Option<&Bound<'py, pyo3::types::PyDict>>,
    ) -> PyResult<Bound<'py, PyAny>> {
        if self.positional && kwargs.is_some_and(|k| !k.is_empty()) {
            return Err(pyo3::exceptions::PyTypeError::new_err(format!(
                "{}() got an unexpected keyword argument",
                self.name.bind(p)
            )));
        }
        let me = args.get_item(0)?;
        if crate::session::sb_planted(GM_GUARD_SKIP_PLANT) || self.has_core(&me)? {
            return self.f.bind(p).call(args, kwargs);
        }
        self.py_methods.bind(p).get_item(self.key.bind(p))?.call(args, kwargs)
    }

    #[getter]
    fn __func__(&self, p: Python<'_>) -> Py<PyAny> {
        self.f.clone_ref(p)
    }
}

impl GuardMethod {
    /// `isinstance(<me or me.session>.__dict__.get('_table_view'), TableView)`.
    fn has_core(&self, me: &Bound<'_, PyAny>) -> PyResult<bool> {
        let p = me.py();
        let holder = if self.via_session { me.getattr(intern!(p, "session"))? } else { me.clone() };
        let d = holder.getattr(intern!(p, "__dict__"))?;
        let tv = match d.cast::<pyo3::types::PyDict>() {
            Ok(d) => d.get_item(intern!(p, "_table_view"))?,
            Err(_) => d.call_method1(intern!(p, "get"), (intern!(p, "_table_view"),)).ok().filter(|x| !x.is_none()),
        };
        match tv {
            Some(tv) => tv.is_instance(self.view.bind(p)),
            None => Ok(false),
        }
    }
}
