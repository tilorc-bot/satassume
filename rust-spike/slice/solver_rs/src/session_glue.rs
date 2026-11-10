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
    s.setattr(intern!(p, "frontier"), em.getattr(intern!(p, "deque"))?.call0()?)?;
    s.setattr(intern!(p, "pending"), PyDict::new(p))?;
    s.setattr(intern!(p, "pending_c"), PyDict::new(p))?;
    s.setattr(intern!(p, "demand"), PyDict::new(p))?;
    s.setattr(intern!(p, "deferred"), PyList::empty(p))?;
    s.setattr(intern!(p, "literals"), PyDict::new(p))?;
    s.setattr(intern!(p, "assumption_formula"), p.None())?;
    s.setattr(intern!(p, "_a_raw"), PyTuple::empty(p))?;
    s.setattr(intern!(p, "_a_zs"), PyTuple::empty(p))?;
    s.setattr(intern!(p, "_a_under"), p.None())?;
    s.setattr(intern!(p, "_groups"), PyDict::new(p))?;
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
    s.setattr(intern!(p, "_a_raw"), em.getattr(intern!(p, "atoms_of"))?.call1((f,))?)?;
    let raw = s.getattr(intern!(p, "_a_raw"))?;
    s.setattr(intern!(p, "_a_zs"), em.getattr(intern!(p, "zero_args"))?.call1((&raw,))?)?;
    s.setattr(intern!(p, "_a_under"), p.None())?;
    s.setattr(intern!(p, "_a_all"), p.None())?;
    s.call_method1(intern!(p, "_ensure_atoms"), (f,))?;
    let sv = s.getattr(intern!(p, "table"))?.call_method0(intern!(p, "aux"))?;
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
    em.getattr(intern!(p, "compile_formula"))?.call1((f, s.getattr(intern!(p, "table"))?, emit, s.getattr(intern!(p, "dvar"))?))?;
    s.call_method0(intern!(p, "discover"))?;
    if !s.getattr(intern!(p, "relations"))?.is_none() && !planted(AF_DROP_RELATIONS) {
        let exts = s.getattr(intern!(p, "engine"))?.getattr(intern!(p, "_extensions"))?;
        let sc = em.getattr(intern!(p, "theory_scope"))?.call1((f, p.None(), exts))?;
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
        let atoms = em.getattr(intern!(p, "atoms_of"))?.call1((prop,))?;
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
                seen = s.getattr(intern!(p, "_groups"))?.get_item(p.None())?.get_item(1)?;
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
    let groups = s.getattr(intern!(p, "_groups"))?;
    let t = PyBool::new(p, true).to_owned().into_any();
    let mut g = groups.call_method1(intern!(p, "get"), (&t,))?;
    if g.is_none() {
        let l = PyList::new(p, [PySet::empty(p)?.into_any(), p.None().into_bound(p), t.clone(), t.clone()])?;
        groups.set_item(&t, &l)?;
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
    let groups = s.getattr(intern!(p, "_groups"))?;
    let g = groups.call_method1(intern!(p, "get"), (key,))?;
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
            groups.set_item(key, PyList::new(p, [zero.clone(), PySet::empty(p)?.into_any(), stamp.into_any()])?)?;
            return Ok(zero);
        }
        let v = s.getattr(intern!(p, "table"))?.call_method0(intern!(p, "aux"))?;
        solver.call_method1(intern!(p, "ensure_vars"), (&v,))?;
        let l = PyList::new(p, [v.clone(), PySet::empty(p)?.into_any(), stamp.clone().into_any()])?;
        groups.set_item(key, &l)?;
        crate::session::solver_of(s)?.call_method1(intern!(p, "set_inert"), (&v,))?;
        l.into_any()
    } else if !g.get_item(0)?.is_truthy()? {
        if want.is_empty() {
            g.set_item(2, &stamp)?;
            return Ok(zero);
        }
        g.set_item(0, s.getattr(intern!(p, "table"))?.call_method0(intern!(p, "aux"))?)?;
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
    m.add_function(wrap_pyfunction!(ses_glue_of, m)?)
}
