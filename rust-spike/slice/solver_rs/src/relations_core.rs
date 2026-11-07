//! Component 5, step 5b: the id-to-term link, and C2a's `Relations` methods over the Rust session.
//!
//! **The link** answers "which of this query's term ids is this object", for a session's node. Nodes live for a session and
//! term ids for a query, and queries nest, so it can't be a column. It resolves the object passed, never the object a node's
//! slot holds, so a join's second object gets its own answer. It creates no node. It reads no row, so rows can fill later than
//! conversion; only positive answers are kept, since a later row could turn None into an id. None is an ordinary answer: that
//! read goes to Python's own function.
//!
//! **The methods** follow `satassume/relations.py` line for line, in its order of effects. What hasn't moved is a callback to
//! `rel`, and module attributes are read at each call because `term_live` and `lra_live` replace them. No table or session
//! borrow is held across a callback, since `Session.ensure` and discovery stay Python and come back in. A callback's exception
//! goes on up unchanged (`Uninterpreted`, the budget's); only this file's own failures become `TermFault`, which no handler on
//! the engine's path can turn into a quiet unknown.
use std::sync::atomic::{AtomicU8, Ordering::Relaxed};
use std::sync::{Arc, RwLock};

use pyo3::exceptions::{PyException, PyKeyError, PyValueError};
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyDict, PyList, PySet, PyTuple};

use crate::session::{self, tick, SessionCore};
use crate::term::py::PyTermTable;

struct Hooks {
    term_live: Py<PyAny>,
    relations: Py<PyAny>,
    euf_adapter: Py<PyAny>,
    /// `session_live._fault(site, text)`: counts it and returns a `TermFault` to raise.
    fault: Py<PyAny>,
}

static HOOKS: RwLock<Option<Arc<Hooks>>> = RwLock::new(None);

/// Test plants: 1 `link-none`, every resolve answers None; 2, 3, 4 drop one clause each in `_order_sides`, `_order_infinite`,
/// `_trichotomy`. From 5 on, C2b's: one effect dropped in each moved method, and `fresh-skew` shifts numbering.
static PLANT: AtomicU8 = AtomicU8::new(0);
const LINK_NONE: u8 = 1;
const DROP_SIDES: u8 = 2;
const DROP_INFINITE: u8 = 3;
const DROP_TRICHOTOMY: u8 = 4;
const DROP_INTERPRET: u8 = 5;
const DROP_GUARD: u8 = 6;
const DROP_BOUND: u8 = 7;
const DROP_LINK: u8 = 8;
const DROP_SELECTOR: u8 = 9;
const DROP_EQ_INFINITY: u8 = 10;
const FRESH_NOT_INERT: u8 = 11;
const FRESH_SKEW: u8 = 12;
/// All of `_trichotomy` off, as a test patching Python's method does. `DROP_TRICHOTOMY` keeps its `ensure`s, vars and roles.
const SKIP_TRICHOTOMY: u8 = 13;
/// From here, C2c's: one effect dropped in each moved method.
const DROP_ADD_ROLE: u8 = 14;
const DROP_APPLY_ROLE: u8 = 15;
const DROP_CANDIDACY: u8 = 16;
const DROP_TSOURCE: u8 = 17;
const DROP_TVAR: u8 = 18;
const DROP_TVAR_MC: u8 = 19;
const DROP_ENGAGE: u8 = 20;
const DROP_TERMS: u8 = 21;
const DROP_TERMS_SIDE: u8 = 22;
const DROP_FIXED: u8 = 23;
const DROP_SYNC: u8 = 24;
const DROP_SYNC_POLAR: u8 = 25;
const DROP_XSWITCH: u8 = 26;
const DROP_CONGRUENCE: u8 = 27;
const CONGRUENT_NEVER: u8 = 28;
const SHARE_GUARD_ONE: u8 = 29;

#[pyfunction]
fn rel_install(term_live: Py<PyAny>, relations: Py<PyAny>, euf_adapter: Py<PyAny>, fault: Py<PyAny>) {
    *HOOKS.write().unwrap() = Some(Arc::new(Hooks { term_live, relations, euf_adapter, fault }));
}

#[pyfunction]
fn rel_plant(name: Option<&str>) -> PyResult<()> {
    let v = match name {
        None => 0,
        Some("link-none") => LINK_NONE,
        Some("drop-order-sides") => DROP_SIDES,
        Some("drop-order-infinite") => DROP_INFINITE,
        Some("drop-trichotomy") => DROP_TRICHOTOMY,
        Some("drop-interpret") => DROP_INTERPRET,
        Some("drop-guard") => DROP_GUARD,
        Some("drop-bound") => DROP_BOUND,
        Some("drop-link") => DROP_LINK,
        Some("drop-selector") => DROP_SELECTOR,
        Some("drop-eq-infinity") => DROP_EQ_INFINITY,
        Some("fresh-not-inert") => FRESH_NOT_INERT,
        Some("fresh-skew") => FRESH_SKEW,
        Some("skip-trichotomy") => SKIP_TRICHOTOMY,
        Some("drop-add-role") => DROP_ADD_ROLE,
        Some("drop-apply-role") => DROP_APPLY_ROLE,
        Some("drop-candidacy") => DROP_CANDIDACY,
        Some("drop-tsource") => DROP_TSOURCE,
        Some("drop-tvar") => DROP_TVAR,
        Some("drop-tvar-mc") => DROP_TVAR_MC,
        Some("drop-engage") => DROP_ENGAGE,
        Some("drop-terms") => DROP_TERMS,
        Some("drop-terms-side") => DROP_TERMS_SIDE,
        Some("drop-fixed") => DROP_FIXED,
        Some("drop-sync") => DROP_SYNC,
        Some("drop-sync-polar") => DROP_SYNC_POLAR,
        Some("drop-xswitch") => DROP_XSWITCH,
        Some("drop-congruence") => DROP_CONGRUENCE,
        Some("congruent-never") => CONGRUENT_NEVER,
        Some("share-guard-one") => SHARE_GUARD_ONE,
        Some(x) => return Err(PyValueError::new_err(format!("no plant {x}"))),
    };
    PLANT.store(v, Relaxed);
    Ok(())
}

fn hooks() -> PyResult<Arc<Hooks>> {
    HOOKS.read().unwrap().clone().ok_or_else(|| PyException::new_err("relations_core: rel_install hasn't run"))
}

/// This file's own failure, as a `TermFault`.
fn fault(p: Python<'_>, h: &Hooks, site: &str, text: String) -> PyErr {
    match h.fault.bind(p).call1((site, text)) {
        Ok(x) => PyErr::from_value(x),
        Err(e) => e,
    }
}

/// An ordinary exception from a term read or from reaching the session becomes a fault; a `BaseException` goes on up as itself.
fn faulted<T>(p: Python<'_>, h: &Hooks, site: &str, r: PyResult<T>) -> PyResult<T> {
    r.map_err(|e| if e.is_instance_of::<PyException>(p) { fault(p, h, site, e.to_string()) } else { e })
}

/// A resolved term: the query's table and the id in it.
struct Linked<'py> {
    table: Bound<'py, PyTermTable>,
    id: u32,
}

/// The current query's term id for the object `x`, or None. See the file's header.
fn term_of<'py>(c: &SessionCore, h: &Hooks, x: &Bound<'py, PyAny>) -> PyResult<Option<Linked<'py>>> {
    let p = x.py();
    tick(session::LINK_CALLS);
    if PLANT.load(Relaxed) == LINK_NONE {
        tick(session::LINK_NONE);
        tick(session::REL_PLANT);
        return Ok(None);
    }
    let tl = h.term_live.bind(p);
    tick(session::LINK_CROSS_CURRENT);
    let q = faulted(p, h, "link", tl.call_method0(intern!(p, "current")))?;
    if q.is_none() || !faulted(p, h, "link", q.getattr(intern!(p, "kept")))?.is_none() {
        tick(session::LINK_NO_TABLE);
        return Ok(None);
    }
    let table = faulted(p, h, "link", q.getattr(intern!(p, "table")).and_then(|t| t.cast_into::<PyTermTable>().map_err(Into::into)))?;
    tick(session::LINK_CROSS_HASH);
    let nid = faulted(p, h, "link", c.node_quiet(x))?;
    match nid {
        Some(n) => {
            let held = table.try_borrow().map_err(|e| fault(p, h, "link", e.to_string()))?.link_get(c.serial, n, x);
            match held {
                Ok(Some(id)) => {
                    tick(session::LINK_HIT);
                    return Ok(Some(Linked { table, id }));
                }
                Ok(None) => {}
                Err(()) => tick(session::LINK_SECOND),
            }
        }
        None => tick(session::LINK_NO_NODE),
    }
    // Python's one rule, including that a row counts only for its own class. It may add a row, so no borrow is held.
    tick(session::LINK_CROSS_TERM_ID);
    let got = faulted(p, h, "link", tl.call_method1(intern!(p, "term_id"), (&q, x, intern!(p, "link"))))?;
    if got.is_none() {
        tick(session::LINK_NONE);
        return Ok(None);
    }
    let id: u32 = faulted(p, h, "link", got.extract().map_err(Into::into))?;
    tick(session::LINK_RESOLVED);
    if let Some(n) = nid {
        table.try_borrow_mut().map_err(|e| fault(p, h, "link", e.to_string()))?.link_put(c.serial, n, x, id);
    }
    Ok(Some(Linked { table, id }))
}

fn read<'py, T>(p: Python<'py>, h: &Hooks, l: &Linked<'py>, f: impl FnOnce(&PyTermTable, u32) -> T) -> PyResult<T> {
    let t = l.table.try_borrow().map_err(|e| fault(p, h, "link-read", e.to_string()))?;
    Ok(f(&t, l.id))
}

/// `rel.session`, and the core under it.
fn session_of<'py>(p: Python<'py>, h: &Hooks, rel: &Bound<'py, PyAny>) -> PyResult<(Bound<'py, PyAny>, Bound<'py, SessionCore>)> {
    let s = rel.getattr(intern!(p, "session"))?;
    let c = faulted(
        p,
        h,
        "session",
        s.getattr(intern!(p, "table")).and_then(|t| t.getattr(intern!(p, "core"))).and_then(|c| c.cast_into::<SessionCore>().map_err(Into::into)),
    )?;
    Ok((s, c))
}

/// `s.ensure(e, {preds})`: a real set in the literal's order, since discovery may read its order.
fn ensure(s: &Bound<'_, PyAny>, e: &Bound<'_, PyAny>, preds: &[&str]) -> PyResult<()> {
    let p = s.py();
    s.call_method1(intern!(p, "ensure"), (e, PySet::new(p, preds)?))?;
    Ok(())
}

fn is_number(c: &SessionCore, h: &Hooks, e: &Bound<'_, PyAny>) -> PyResult<bool> {
    let p = e.py();
    match term_of(c, h, e)? {
        Some(l) => read(p, h, &l, |t, i| t.read_is_number(i)),
        None => h.relations.bind(p).getattr(intern!(p, "_is_number"))?.call1((e,))?.is_truthy(),
    }
}

/// `_closed_extended_real`: True, False, None, or what `Engine.is_` said.
fn closed_extended_real<'py>(rel: &Bound<'py, PyAny>, s: &Bound<'py, PyAny>, c: &SessionCore, h: &Hooks, e: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    let p = rel.py();
    tick(session::REL_CLOSED);
    let yes = || PyBool::new(p, true).to_owned().into_any();
    let no = || PyBool::new(p, false).to_owned().into_any();
    let none = || p.None().into_bound(p);
    match term_of(c, h, e)? {
        Some(l) => {
            let (rational, number, nan) = read(p, h, &l, |t, i| (t.read_is_rational(i), t.read_is_number(i), t.read_is_nan(i)))?;
            if rational {
                return Ok(yes());
            }
            if !number {
                return Ok(none());
            }
            if nan {
                return Ok(no());
            }
        }
        None => {
            // `getattr(e, "is_Rational", False)`
            if let Some(v) = e.getattr_opt(intern!(p, "is_Rational"))? {
                if v.is_truthy()? {
                    return Ok(yes());
                }
            }
            let r = h.relations.bind(p);
            if !r.getattr(intern!(p, "_is_number"))?.call1((e,))?.is_truthy()? {
                return Ok(none());
            }
            if e.is(&p.import(intern!(p, "sympy"))?.getattr(intern!(p, "S"))?.getattr(intern!(p, "NaN"))?) {
                return Ok(no());
            }
        }
    }
    s.getattr(intern!(p, "engine"))?.call_method1(intern!(p, "is_"), (e, intern!(p, "extended_real")))
}

#[pyfunction]
fn rel_closed_extended_real<'py>(rel: &Bound<'py, PyAny>, e: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    let h = hooks()?;
    let (s, c) = session_of(rel.py(), &h, rel)?;
    closed_extended_real(rel, &s, &c.borrow(), &h, e)
}

#[pyfunction]
fn rel_order_sides<'py>(rel: &Bound<'py, PyAny>, var: i32, atom: &Bound<'py, PyAny>) -> PyResult<bool> {
    let p = rel.py();
    tick(session::REL_ORDER_SIDES);
    let h = hooks()?;
    let (s, c) = session_of(p, &h, rel)?;
    let c = c.borrow();
    let mut need = vec![];
    for e in atom.getattr(intern!(p, "expr"))?.try_iter()? {
        let e = e?;
        let v = closed_extended_real(rel, &s, &c, &h, &e)?;
        if v.is(PyBool::new(p, false)) {
            c.emit_direct(p, &[-var])?;
            return Ok(true);
        }
        if v.is_none() {
            need.push(e);
        }
    }
    for e in need {
        ensure(&s, &e, &["extended_real"])?;
        let v = c.var_direct(intern!(p, "extended_real").as_any(), &e)?;
        if PLANT.load(Relaxed) == DROP_SIDES {
            tick(session::REL_PLANT);
            continue;
        }
        c.emit_direct(p, &[-var, v])?;
    }
    Ok(false)
}

/// Exactly two items, as `a, b = x` unpacks them.
fn two<'py>(x: &Bound<'py, PyAny>) -> PyResult<(Bound<'py, PyAny>, Bound<'py, PyAny>)> {
    let mut v = x.try_iter()?.collect::<PyResult<Vec<_>>>()?;
    if v.len() != 2 {
        return Err(PyValueError::new_err(format!("expected 2 values to unpack, got {}", v.len())));
    }
    let b = v.pop().unwrap();
    Ok((v.pop().unwrap(), b))
}

#[pyfunction]
fn rel_order_infinite<'py>(rel: &Bound<'py, PyAny>, var: i32, sides: &Bound<'py, PyAny>) -> PyResult<()> {
    let p = rel.py();
    tick(session::REL_ORDER_INFINITE);
    let h = hooks()?;
    let (s, c) = session_of(p, &h, rel)?;
    let c = c.borrow();
    let r = h.relations.bind(p);
    let fraction = r.getattr(intern!(p, "Fraction"))?;
    let (pos, neg, ext_real) = (intern!(p, "positive_infinite"), intern!(p, "negative_infinite"), intern!(p, "extended_real"));
    let mut push: Vec<(Vec<i32>, Vec<i32>, bool, bool)> = vec![];
    let mut ext = vec![];
    let mut exact = true;
    // A real set: `==` joins here as it does in Python's.
    let seen = PySet::empty(p)?;
    for side in sides.try_iter()? {
        let (form, inf) = two(&side?)?;
        let (mut up, mut down) = (vec![], vec![]);
        for item in form.call_method0(intern!(p, "items"))?.try_iter()? {
            let (u, co) = two(&item?)?;
            if is_number(&c, &h, &u)? {
                continue;
            }
            let (nonzero, positive) = if co.get_type().is(&fraction) {
                (co.is_truthy()?, co.gt(0)?)
            } else {
                match r.getattr(intern!(p, "sign"))?.call1((&co,)) {
                    Ok(sg) => (sg.is_truthy()?, sg.gt(0)?),
                    // Unknown sign: no clauses 2. What `ensure` and `var` did for earlier terms stays.
                    Err(e) if e.is_instance(p, &r.getattr(intern!(p, "Undecided"))?) => return Ok(()),
                    Err(e) => return Err(e),
                }
            };
            if !nonzero {
                exact = false;
                continue;
            }
            ensure(&s, &u, &["extended_real", "positive_infinite", "negative_infinite"])?;
            let (a, b) = (c.var_direct(pos.as_any(), &u)?, c.var_direct(neg.as_any(), &u)?);
            if positive {
                up.push(a);
                down.push(b);
            } else {
                down.push(a);
                up.push(b);
            }
            if !seen.contains(&u)? {
                seen.add(&u)?;
                ext.push(-c.var_direct(ext_real.as_any(), &u)?);
            }
        }
        push.push((up, down, inf.gt(0)?, inf.lt(0)?));
    }
    if push.len() != 2 {
        return Err(PyValueError::new_err(format!("expected 2 sides, got {}", push.len())));
    }
    let (up_b, down_b, cup_b, cdown_b) = push.pop().unwrap();
    let (up_a, down_a, cup_a, cdown_a) = push.pop().unwrap();
    if cup_a || cdown_b {
        return c.emit_direct(p, &[-var]);
    }
    for &l in &up_a {
        if PLANT.load(Relaxed) == DROP_INFINITE {
            tick(session::REL_PLANT);
            continue;
        }
        c.emit_direct(p, &[-l, -var])?;
    }
    for &l in &down_b {
        c.emit_direct(p, &[-l, -var])?;
    }
    if !exact {
        return Ok(());
    }
    let rest: Vec<i32> = up_a.iter().chain(&down_b).chain(&ext).copied().chain([var]).collect();
    if cdown_a {
        c.emit_direct(p, &rest)?;
    } else {
        for &l in &down_a {
            let mut cl = vec![-l];
            cl.extend(&rest);
            c.emit_direct(p, &cl)?;
        }
    }
    let rest: Vec<i32> = down_b.iter().chain(&up_a).chain(&ext).copied().chain([var]).collect();
    if cup_b {
        c.emit_direct(p, &rest)?;
    } else {
        for &l in &up_b {
            let mut cl = vec![-l];
            cl.extend(&rest);
            c.emit_direct(p, &cl)?;
        }
    }
    Ok(())
}

#[pyfunction]
fn rel_trichotomy<'py>(rel: &Bound<'py, PyAny>, var: i32, atom: &Bound<'py, PyAny>) -> PyResult<()> {
    let p = rel.py();
    tick(session::REL_TRICHOTOMY);
    if PLANT.load(Relaxed) == SKIP_TRICHOTOMY {
        tick(session::REL_PLANT);
        return Ok(());
    }
    let h = hooks()?;
    let (s, c) = session_of(p, &h, rel)?;
    let c = c.borrow();
    let r = h.relations.bind(p);
    let (a, b) = two(&atom.getattr(intern!(p, "expr"))?)?;
    let args = r.getattr(intern!(p, "Args"))?.call1((PyTuple::new(p, [&b, &a])?,))?;
    let rev = r.getattr(intern!(p, "P"))?.call1((intern!(p, "lt"), args))?;
    let Some(rvar) = c.custom_direct(&rev)? else { return Ok(()) };
    let lk = rel.getattr(intern!(p, "_link_lt"))?;
    let la = lk.call_method1(intern!(p, "get"), (atom,))?;
    if !la.is_none() && la.is(&lk.call_method1(intern!(p, "get"), (&rev,))?) {
        return Ok(());
    }
    let eqa = r.getattr(intern!(p, "relation_atom"))?.call1((intern!(p, "eq"), &a, &b))?;
    if c.custom_direct(&eqa)?.is_none() {
        rel.getattr(intern!(p, "_aux_eq"))?.call_method1(intern!(p, "add"), (&eqa,))?;
    }
    let eq: i32 = rel.call_method1(intern!(p, "_atom_var"), (&eqa,))?.extract()?;
    rel.call_method1(intern!(p, "_note_sides"), (&eqa, 2))?;
    let sel_a: i32 = rel.call_method1(intern!(p, "_atom_selector"), (atom,))?.extract()?;
    let sel_r: i32 = rel.call_method1(intern!(p, "_atom_selector"), (&rev,))?.extract()?;
    let both = [-sel_a, -sel_r];
    // A list of its own: `_add_role` keeps it.
    Cx { rel, s: &s, c: &c, h: &h }.add_role(&eqa, PyList::new(p, both)?.as_any(), intern!(p, "tri").as_any())?;
    let mut clause = vec![both[0], both[1], var, rvar, eq];
    for e in r.getattr(intern!(p, "_ext_atoms"))?.call1((&a, &b))?.try_iter()? {
        let x = e?.getattr(intern!(p, "expr"))?;
        ensure(&s, &x, &["extended_real"])?;
        clause.push(-c.var_direct(intern!(p, "extended_real").as_any(), &x)?);
    }
    if PLANT.load(Relaxed) == DROP_TRICHOTOMY {
        tick(session::REL_PLANT);
        return Ok(());
    }
    c.emit_direct(p, &clause)
}

#[pyfunction]
fn rel_mention_number<'py>(rel: &Bound<'py, PyAny>, e: &Bound<'py, PyAny>) -> PyResult<()> {
    let p = rel.py();
    tick(session::REL_MENTION);
    let h = hooks()?;
    let num_sel = rel.getattr(intern!(p, "num_sel"))?;
    if num_sel.contains(e)? {
        return Ok(());
    }
    let (s, c) = session_of(p, &h, rel)?;
    let c = c.borrow();
    let structural = match term_of(&c, &h, e)? {
        Some(l) => read(p, &h, &l, |t, i| t.read_structural(i))?,
        None => h.euf_adapter.bind(p).getattr(intern!(p, "structural"))?.call1((e,))?.is_truthy()?,
    };
    if !structural {
        return Ok(());
    }
    let sel = fresh(&s, &c, true)?;
    num_sel.set_item(e, sel)?;
    Cx { rel, s: &s, c: &c, h: &h }.tsource(e, IE, PyList::new(p, [-sel])?.as_any())?;
    rel.getattr(intern!(p, "_xextra"))?.call_method1(intern!(p, "append"), (e,))?;
    Ok(())
}

#[pyfunction]
fn rel_link_integer<'py>(rel: &Bound<'py, PyAny>, ad: &Bound<'py, PyAny>, e: &Bound<'py, PyAny>, g: i32) -> PyResult<()> {
    let p = rel.py();
    tick(session::REL_LINK_INTEGER);
    let h = hooks()?;
    let form = ad.call_method1(intern!(p, "integer_form"), (e,))?;
    if form.is_none() {
        return Ok(());
    }
    let (s, c) = session_of(p, &h, rel)?;
    let c = c.borrow();
    let i = fresh(&s, &c, false)?;
    ad.call_method1(intern!(p, "register_integer"), (s.getattr(intern!(p, "solver"))?, i, &form))?;
    let guard: Vec<i32> = guard(rel, &s, &c, &h, ad, &form.get_item(1)?)?.extract()?;
    let z = c.var_direct(intern!(p, "integer").as_any(), e)?;
    let with = |x: [i32; 3]| guard.iter().copied().chain(x).collect::<Vec<i32>>();
    c.emit_direct(p, &with([-z, i, g]))?;
    c.emit_direct(p, &with([z, -i, g]))
}

/// `_fresh`.
fn fresh(s: &Bound<'_, PyAny>, c: &SessionCore, inert: bool) -> PyResult<i32> {
    let p = s.py();
    tick(session::REL_FRESH);
    let mut v = c.aux_direct();
    if PLANT.load(Relaxed) == FRESH_SKEW {
        tick(session::REL_PLANT);
        v = c.aux_direct();
    }
    c.ensure_vars_direct(p, v)?;
    if inert {
        if PLANT.load(Relaxed) == FRESH_NOT_INERT {
            tick(session::REL_PLANT);
        } else {
            s.getattr(intern!(p, "solver"))?.call_method1(intern!(p, "set_inert"), (v,))?;
        }
    }
    Ok(v)
}

#[pyfunction]
#[pyo3(signature = (rel, inert=false))]
fn rel_fresh(rel: &Bound<'_, PyAny>, inert: bool) -> PyResult<i32> {
    let h = hooks()?;
    let (s, c) = session_of(rel.py(), &h, rel)?;
    fresh(&s, &c.borrow(), inert)
}

/// `_bound`. What `register_bounds` returns is read as it's emitted, as Python's `for` does.
fn bound(rel: &Bound<'_, PyAny>, s: &Bound<'_, PyAny>, c: &SessionCore, ad: &Bound<'_, PyAny>, u: &Bound<'_, PyAny>) -> PyResult<()> {
    let p = rel.py();
    tick(session::REL_BOUND);
    let Some(register) = ad.getattr_opt(intern!(p, "register_bounds"))? else { return Ok(()) };
    if register.is_none() {
        return Ok(());
    }
    // A bound method, so the adapter can call it as Python's would; `session_live` routes it back here.
    let vs = register.call1((s.getattr(intern!(p, "solver"))?, u, rel.getattr(intern!(p, "_fresh"))?))?;
    for v in vs.try_iter()? {
        let v: i32 = v?.extract()?;
        if PLANT.load(Relaxed) == DROP_BOUND {
            tick(session::REL_PLANT);
            continue;
        }
        c.emit_direct(p, &[v])?;
    }
    Ok(())
}

#[pyfunction]
fn rel_bound(rel: &Bound<'_, PyAny>, ad: &Bound<'_, PyAny>, u: &Bound<'_, PyAny>) -> PyResult<()> {
    let h = hooks()?;
    let (s, c) = session_of(rel.py(), &h, rel)?;
    bound(rel, &s, &c.borrow(), ad, u)
}

/// `_guard`. The memo's list is put in before it's filled, as Python's is, so a callback that comes back in sees it partial, and
/// every caller holds that one list. It stays Python's dict on `rel`, since it isn't a term table and it dies with the session.
fn guard<'py>(rel: &Bound<'py, PyAny>, s: &Bound<'py, PyAny>, c: &SessionCore, h: &Hooks, ad: &Bound<'py, PyAny>, terms: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyList>> {
    let p = rel.py();
    tick(session::REL_GUARD);
    let tup = PyTuple::new(p, terms.try_iter()?.collect::<PyResult<Vec<_>>>()?)?;
    let key = PyTuple::new(p, [ad.clone(), tup.into_any()])?;
    let memo = rel.getattr(intern!(p, "_guards"))?;
    let got = memo.call_method1(intern!(p, "get"), (&key,))?;
    if !got.is_none() {
        return got.cast_into::<PyList>().map_err(Into::into);
    }
    let out = PyList::empty(p);
    memo.set_item(&key, &out)?;
    for u in terms.try_iter()? {
        let u = u?;
        if is_number(c, h, &u)? {
            let bounded = rel.getattr(intern!(p, "_bounded"))?;
            if !bounded.contains(&u)? {
                bounded.call_method1(intern!(p, "add"), (&u,))?;
                bound(rel, s, c, ad, &u)?;
            }
            if s.getattr(intern!(p, "engine"))?.call_method1(intern!(p, "is_"), (&u, intern!(p, "real")))?.is(PyBool::new(p, true)) {
                continue;
            }
        }
        ensure(s, &u, &["real"])?;
        let v = c.var_direct(intern!(p, "real").as_any(), &u)?;
        if PLANT.load(Relaxed) == DROP_GUARD {
            tick(session::REL_PLANT);
            continue;
        }
        out.append(-v)?;
    }
    Ok(out)
}

#[pyfunction]
fn rel_guard<'py>(rel: &Bound<'py, PyAny>, ad: &Bound<'py, PyAny>, terms: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyList>> {
    let h = hooks()?;
    let (s, c) = session_of(rel.py(), &h, rel)?;
    guard(rel, &s, &c.borrow(), &h, ad, terms)
}

/// `_eq_infinity`. It replaces C1's plan: `_interpret` was its only caller. It holds the atom's own objects, so nothing is
/// rebuilt and no term goes back to a node.
fn eq_infinity<'py>(rel: &Bound<'py, PyAny>, s: &Bound<'py, PyAny>, c: &SessionCore, h: &Hooks, var: i32, atom: &Bound<'py, PyAny>) -> PyResult<()> {
    let p = rel.py();
    tick(session::REL_EQ_INFINITY);
    let sy = p.import(intern!(p, "sympy"))?.getattr(intern!(p, "S"))?;
    let (a, b) = two(&atom.getattr(intern!(p, "expr"))?)?;
    for (inf, pred) in [(intern!(p, "Infinity"), intern!(p, "positive_infinite")), (intern!(p, "NegativeInfinity"), intern!(p, "negative_infinite"))] {
        let inf = sy.getattr(inf)?;
        let e = if b.is(&inf) {
            &a
        } else if a.is(&inf) {
            &b
        } else {
            continue;
        };
        if is_number(c, h, e)? {
            let v = s.getattr(intern!(p, "engine"))?.call_method1(intern!(p, "is_"), (e, pred))?;
            if !v.is_none() {
                return c.emit_direct(p, &[if v.is_truthy()? { var } else { -var }]);
            }
        }
        s.call_method1(intern!(p, "ensure"), (e, PySet::new(p, [pred])?))?;
        let pv = c.var_direct(pred.as_any(), e)?;
        let g: i32 = rel.call_method1(intern!(p, "_atom_selector"), (atom,))?.extract()?;
        c.emit_direct(p, &[-var, pv, -g])?;
        if PLANT.load(Relaxed) == DROP_EQ_INFINITY {
            tick(session::REL_PLANT);
            return Ok(());
        }
        return c.emit_direct(p, &[var, -pv, -g]);
    }
    Ok(())
}

#[pyfunction]
fn rel_eq_infinity<'py>(rel: &Bound<'py, PyAny>, var: i32, atom: &Bound<'py, PyAny>) -> PyResult<()> {
    let h = hooks()?;
    let (s, c) = session_of(rel.py(), &h, rel)?;
    eq_infinity(rel, &s, &c.borrow(), &h, var, atom)
}

/// `_interpret`. The adapters, `sympy_atom`, `_note_sides` and `_adapter` stay Python and are called back.
#[pyfunction]
fn rel_interpret<'py>(rel: &Bound<'py, PyAny>, atom: &Bound<'py, PyAny>) -> PyResult<bool> {
    let p = rel.py();
    tick(session::REL_INTERPRET);
    let h = hooks()?;
    let (s, c) = session_of(p, &h, rel)?;
    let c = c.borrow();
    let r = h.relations.bind(p);
    let solver = s.getattr(intern!(p, "solver"))?;
    let Some(var) = c.custom_direct(atom)? else { return Err(PyKeyError::new_err(atom.clone().unbind())) };
    let pred = atom.getattr(intern!(p, "pred"))?;
    let order = pred.eq(intern!(p, "lt"))?;
    let link = if order { rel.getattr(intern!(p, "_link_lt"))?.call_method1(intern!(p, "get"), (atom,))? } else { p.None().into_bound(p) };
    if !link.is_none() {
        ensure(&s, &link, &["extended_real"])?;
    } else if order && rel_order_sides(rel, var, atom)? {
        return Ok(true);
    }
    if order {
        rel_trichotomy(rel, var, atom)?;
    }
    let eq = pred.eq(intern!(p, "eq"))?;
    if eq {
        eq_infinity(rel, &s, &c, &h, var, atom)?;
    }
    let sat = r.getattr(intern!(p, "sympy_atom"))?.call1((atom,))?;
    let mut ok = false;
    let (twins, lterms, eterms) = (PyList::empty(p), PyList::empty(p), PyList::empty(p));
    for spec in rel.getattr(intern!(p, "specs"))?.try_iter()? {
        let spec = spec?;
        let ad = rel.call_method1(intern!(p, "_adapter"), (&spec,))?;
        if !spec.getattr(intern!(p, "guarded"))?.is_truthy()? {
            if ad.call_method1(intern!(p, "register"), (&solver, var, &sat))?.is_truthy()? {
                ok = true;
                if eq && ad.getattr_opt(intern!(p, "node_term"))?.is_some() {
                    eterms.call_method1(intern!(p, "extend"), (ad.call_method1(intern!(p, "interned"), (atom.getattr(intern!(p, "expr"))?,))?,))?;
                    if !rel.getattr(intern!(p, "_aux_eq"))?.contains(atom)? {
                        rel.call_method1(intern!(p, "_note_sides"), (atom, 2))?;
                    } else if rel.getattr(intern!(p, "_link_eq"))?.contains(atom)? {
                        rel.call_method1(intern!(p, "_note_sides"), (atom, 1))?;
                    }
                }
            }
            continue;
        }
        if order && ad.getattr_opt(intern!(p, "order_sides"))?.is_some() {
            let sides = ad.call_method1(intern!(p, "order_sides"), (&sat,))?;
            if !sides.is_none() {
                if !link.is_none() && r.getattr(intern!(p, "_own_term"))?.call1((&sides, &link))?.is_truthy()? {
                    s.call_method1(intern!(p, "ensure"), (&link, r.getattr(intern!(p, "_INF_PREDS"))?))?;
                } else {
                    rel_order_infinite(rel, var, &sides)?;
                }
                if sides.get_item(0)?.get_item(1)?.is_truthy()? || sides.get_item(1)?.get_item(1)?.is_truthy()? {
                    ok = true;
                    continue;
                }
            }
        }
        let terms = ad.call_method1(intern!(p, "terms"), (&sat,))?;
        if terms.is_none() {
            continue;
        }
        let t = fresh(&s, &c, false)?;
        if !ad.call_method1(intern!(p, "register"), (&solver, t, &sat))?.is_truthy()? {
            continue;
        }
        ok = true;
        let g = guard(rel, &s, &c, &h, &ad, &terms)?;
        lterms.call_method1(intern!(p, "extend"), (&terms,))?;
        if eq {
            twins.append((t, &g))?;
            continue;
        }
        let lits: Vec<i32> = g.extract()?;
        let with = |x: [i32; 2]| lits.iter().copied().chain(x).collect::<Vec<i32>>();
        c.emit_direct(p, &with([-var, t]))?;
        if PLANT.load(Relaxed) == DROP_INTERPRET {
            tick(session::REL_PLANT);
            continue;
        }
        c.emit_direct(p, &with([var, -t]))?;
    }
    let info = PyTuple::new(p, [twins.into_any(), lterms.into_any(), eterms.into_any()])?;
    rel.getattr(intern!(p, "_info"))?.set_item(atom, &info)?;
    let cx = Cx { rel, s: &s, c: &c, h: &h };
    for role in rel.getattr(intern!(p, "_roles"))?.call_method1(intern!(p, "get"), (atom, PyTuple::empty(p)))?.try_iter()? {
        let (kind, g) = two(&role?)?;
        cx.apply_role(atom, info.as_any(), &kind, &g)?;
    }
    Ok(ok)
}

/// `_link`.
#[pyfunction]
fn rel_link<'py>(rel: &Bound<'py, PyAny>, e: &Bound<'py, PyAny>) -> PyResult<()> {
    let p = rel.py();
    tick(session::REL_LINK);
    let h = hooks()?;
    let (s, c) = session_of(p, &h, rel)?;
    let c = c.borrow();
    let r = h.relations.bind(p);
    let zero_obj = p.import(intern!(p, "sympy"))?.getattr(intern!(p, "S"))?.getattr(intern!(p, "Zero"))?;
    ensure(&s, e, &["extended_positive", "extended_negative", "zero"])?;
    let pos = c.var_direct(intern!(p, "extended_positive").as_any(), e)?;
    let neg = c.var_direct(intern!(p, "extended_negative").as_any(), e)?;
    let zero = c.var_direct(intern!(p, "zero").as_any(), e)?;
    let atom = r.getattr(intern!(p, "relation_atom"))?;
    let gta = atom.call1((intern!(p, "lt"), &zero_obj, e))?;
    let lta = atom.call1((intern!(p, "lt"), e, &zero_obj))?;
    let link_lt = rel.getattr(intern!(p, "_link_lt"))?;
    link_lt.set_item(&gta, e)?;
    link_lt.set_item(&lta, e)?;
    let gt: i32 = rel.call_method1(intern!(p, "_atom_var"), (&gta,))?.extract()?;
    let lt: i32 = rel.call_method1(intern!(p, "_atom_var"), (&lta,))?.extract()?;
    let eqa = r.getattr(intern!(p, "relation_atom"))?.call1((intern!(p, "eq"), e, &zero_obj))?;
    if c.custom_direct(&eqa)?.is_none() {
        rel.getattr(intern!(p, "_aux_eq"))?.call_method1(intern!(p, "add"), (&eqa,))?;
        rel.getattr(intern!(p, "_link_eq"))?.call_method1(intern!(p, "add"), (&eqa,))?;
    }
    let eq: i32 = rel.call_method1(intern!(p, "_atom_var"), (&eqa,))?.extract()?;
    let sel = fresh(&s, &c, true)?;
    rel.getattr(intern!(p, "link_sel"))?.set_item(e, sel)?;
    let g = -sel;
    // One guard object: `_tsource` drops repeats of it.
    let gl = PyList::new(p, [g])?;
    let link_of = rel.getattr(intern!(p, "_link_of"))?;
    let cx = Cx { rel, s: &s, c: &c, h: &h };
    for f in [&gta, &lta, &eqa] {
        link_of.set_item(f, e)?;
        cx.add_role(f, gl.as_any(), intern!(p, "link").as_any())?;
    }
    c.emit_direct(p, &[-pos, gt, g])?;
    c.emit_direct(p, &[-gt, pos, g])?;
    c.emit_direct(p, &[-neg, lt, g])?;
    c.emit_direct(p, &[-lt, neg, g])?;
    c.emit_direct(p, &[-zero, eq, g])?;
    if PLANT.load(Relaxed) == DROP_LINK {
        tick(session::REL_PLANT);
    } else {
        c.emit_direct(p, &[-eq, zero, g])?;
    }
    if r.getattr(intern!(p, "INTEGERS"))?.is_truthy()? {
        for spec in rel.getattr(intern!(p, "specs"))?.try_iter()? {
            let spec = spec?;
            if spec.getattr(intern!(p, "guarded"))?.is_truthy()? {
                let ad = rel.call_method1(intern!(p, "_adapter"), (&spec,))?;
                if ad.getattr_opt(intern!(p, "integer_form"))?.is_some() {
                    rel_link_integer(rel, &ad, e, g)?;
                }
            }
        }
    }
    Ok(())
}

/// `selectors_of`: sorted and distinct, so a `BTreeSet`. The three maps stay Python's dicts, so `==` joins as it does there.
#[pyfunction]
fn rel_selectors_of<'py>(rel: &Bound<'py, PyAny>, atoms: &Bound<'py, PyAny>) -> PyResult<Vec<i32>> {
    let p = rel.py();
    tick(session::REL_SELECTORS);
    let h = hooks()?;
    let r = h.relations.bind(p);
    let (index, rels) = (r.getattr(intern!(p, "PRED_INDEX"))?, r.getattr(intern!(p, "RELATION_ATOMS"))?);
    let sel = rel.getattr(intern!(p, "link_sel"))?.cast_into::<PyDict>()?;
    let nsel = rel.getattr(intern!(p, "num_sel"))?.cast_into::<PyDict>()?;
    let status = rel.getattr(intern!(p, "status"))?;
    let asel = rel.getattr(intern!(p, "atom_sel"))?.cast_into::<PyDict>()?;
    let mut out = std::collections::BTreeSet::new();
    for a in atoms.try_iter()? {
        let a = a?;
        let pred = a.getattr(intern!(p, "pred"))?;
        if index.contains(&pred)? {
            let e = a.getattr(intern!(p, "expr"))?;
            if let Some(v) = sel.get_item(&e)? {
                out.insert(v.extract::<i32>()?);
            } else if let Some(v) = nsel.get_item(&e)? {
                out.insert(v.extract::<i32>()?);
            }
        } else if rels.contains(&pred)? {
            if status.call_method1(intern!(p, "get"), (&a,))?.is_truthy()? {
                for e in a.getattr(intern!(p, "expr"))?.try_iter()? {
                    if let Some(v) = sel.get_item(e?)? {
                        out.insert(v.extract::<i32>()?);
                    }
                }
            }
            if let Some(v) = asel.get_item(&a)? {
                if PLANT.load(Relaxed) == DROP_SELECTOR {
                    tick(session::REL_PLANT);
                } else {
                    out.insert(v.extract::<i32>()?);
                }
            }
        }
    }
    Ok(out.into_iter().collect())
}

// C2c: roles, the per-term variables, and predicate transfer. Their maps stay Python's dicts, lists and sets on `rel`, as `_guard`'s
// memo does: they aren't term tables, they die with the session, and `==` joins as it does there. Of those, the sets (`_xcand`,
// `_xpart`, `_xpairs`, `_xcounted`) are only added to and asked `in`, and what is walked is a list, a tuple or a dict's insertion order.
const SD: usize = 0;
const EN: usize = 1;
const MC: usize = 2;
const IE: usize = 3;
const IL: usize = 4;

fn planted(x: u8) -> bool {
    let on = PLANT.load(Relaxed) == x;
    if on {
        tick(session::REL_PLANT);
    }
    on
}

/// `g + tail`, read when it's emitted, as Python's `+` is: `_guard`'s list can still be filling.
fn with_tail(g: &Bound<'_, PyAny>, tail: &[i32]) -> PyResult<Vec<i32>> {
    let mut v: Vec<i32> = g.extract()?;
    v.extend_from_slice(tail);
    Ok(v)
}

/// `(e.func, len(e.args))`, the key of `_xheads`.
fn head<'py>(e: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyTuple>> {
    let p = e.py();
    (e.getattr(intern!(p, "func"))?, e.getattr(intern!(p, "args"))?.len()?).into_pyobject(p)
}

/// `x in cand or x in xside`.
fn mergeable(cand: &Bound<'_, PyAny>, xside: &Bound<'_, PyAny>, x: &Bound<'_, PyAny>) -> PyResult<bool> {
    Ok(cand.contains(x)? || xside.contains(x)?)
}

fn rational_flag(x: &Bound<'_, PyAny>) -> PyResult<bool> {
    x.getattr(intern!(x.py(), "is_Rational"))?.is_truthy()
}

/// What C2c's methods share.
struct Cx<'a, 'py> {
    rel: &'a Bound<'py, PyAny>,
    s: &'a Bound<'py, PyAny>,
    c: &'a SessionCore,
    h: &'a Hooks,
}

impl<'py> Cx<'_, 'py> {
    fn dict(&self, name: &Bound<'py, pyo3::types::PyString>) -> PyResult<Bound<'py, PyDict>> {
        self.rel.getattr(name)?.cast_into::<PyDict>().map_err(Into::into)
    }

    fn solver(&self) -> PyResult<Bound<'py, PyAny>> {
        self.s.getattr(intern!(self.s.py(), "solver"))
    }

    /// `structural(e)`: the term's row if it has one. No row is an ordinary answer, and that read goes to Python's own function.
    fn structural(&self, e: &Bound<'py, PyAny>) -> PyResult<bool> {
        let p = e.py();
        match term_of(self.c, self.h, e)? {
            Some(l) => read(p, self.h, &l, |t, i| t.read_structural(i)),
            None => self.h.euf_adapter.bind(p).getattr(intern!(p, "structural"))?.call1((e,))?.is_truthy(),
        }
    }

    /// `_add_role`.
    fn add_role(&self, atom: &Bound<'py, PyAny>, g: &Bound<'py, PyAny>, kind: &Bound<'py, PyAny>) -> PyResult<()> {
        let p = atom.py();
        tick(session::REL_ADD_ROLE);
        let map = self.dict(intern!(p, "_roles"))?;
        match map.get_item(atom)? {
            None => map.set_item(atom, PyList::new(p, [(kind, g)])?)?,
            Some(roles) => {
                for r in roles.try_iter()? {
                    let (k, h) = two(&r?)?;
                    if k.eq(kind)? && h.eq(g)? {
                        return Ok(());
                    }
                }
                roles.call_method1(intern!(p, "append"), ((kind, g),))?;
            }
        }
        if planted(DROP_ADD_ROLE) {
            return Ok(());
        }
        if let Some(info) = self.dict(intern!(p, "_info"))?.get_item(atom)? {
            self.apply_role(atom, &info, kind, g)?;
        }
        Ok(())
    }

    /// `_apply_role`.
    fn apply_role(&self, atom: &Bound<'py, PyAny>, info: &Bound<'py, PyAny>, kind: &Bound<'py, PyAny>, g: &Bound<'py, PyAny>) -> PyResult<()> {
        let p = atom.py();
        tick(session::REL_APPLY_ROLE);
        let (twins, lterms, eterms) = (info.get_item(0)?, info.get_item(1)?, info.get_item(2)?);
        if twins.is_truthy()? {
            let Some(var) = self.c.custom_direct(atom)? else { return Err(PyKeyError::new_err(atom.clone().unbind())) };
            for tw in twins.try_iter()? {
                let (t, guard) = two(&tw?)?;
                let t: i32 = t.extract()?;
                let mut c1: Vec<i32> = guard.extract()?;
                c1.extend(with_tail(g, &[-var, t])?);
                self.c.emit_direct(p, &c1)?;
                if planted(DROP_APPLY_ROLE) {
                    continue;
                }
                let mut c2: Vec<i32> = guard.extract()?;
                c2.extend(with_tail(g, &[var, -t])?);
                self.c.emit_direct(p, &c2)?;
            }
        }
        let link = kind.eq(intern!(p, "link"))?;
        if link {
            for u in lterms.try_iter()? {
                self.tsource(&u?, IL, g)?;
            }
            for u in eterms.try_iter()? {
                self.tsource(&u?, IE, g)?;
            }
        }
        if atom.getattr(intern!(p, "pred"))?.ne(intern!(p, "eq"))? || !eterms.is_truthy()? || kind.eq(intern!(p, "iface"))? {
            return Ok(());
        }
        let expr = atom.getattr(intern!(p, "expr"))?;
        if link {
            self.tsource(&self.rel.getattr(intern!(p, "_link_of"))?.get_item(atom)?, SD, g)?;
            let first = expr.get_item(0)?;
            let side = if is_number(self.c, self.h, &first)? { first } else { expr.get_item(1)? };
            self.tsource(&side, SD, g)
        } else {
            for e in expr.try_iter()? {
                let e = e?;
                let rational = match e.getattr_opt(intern!(p, "is_Rational"))? {
                    Some(x) => x.is_truthy()?,
                    None => false,
                };
                if !rational && !planted(DROP_CANDIDACY) {
                    self.tsource(&e, EN, g)?;
                }
                self.tsource(&e, SD, g)?;
            }
            Ok(())
        }
    }

    /// `_tsource`.
    fn tsource(&self, u: &Bound<'py, PyAny>, k: usize, g: &Bound<'py, PyAny>) -> PyResult<()> {
        let p = u.py();
        tick(session::REL_TSOURCE);
        let map = self.dict(intern!(p, "_tsrc"))?;
        let key = (u, k).into_pyobject(p)?;
        match map.get_item(&key)? {
            None => map.set_item(&key, PyList::new(p, [g])?)?,
            Some(lst) => {
                if lst.get_item(-1)?.is(g) {
                    return Ok(());
                }
                lst.call_method1(intern!(p, "append"), (g,))?;
            }
        }
        if let Some(tv) = self.dict(intern!(p, "_tv"))?.get_item(u)? {
            let v: i32 = tv.get_item(k)?.extract()?;
            if v != 0 {
                if planted(DROP_TSOURCE) {
                    return Ok(());
                }
                self.c.emit_direct(p, &with_tail(g, &[v])?)?;
            } else if k < MC && tv.get_item(MC)?.extract::<i32>()? != 0 {
                self.tvar(u, k)?;
            }
        }
        Ok(())
    }

    /// `_tvar`.
    fn tvar(&self, u: &Bound<'py, PyAny>, k: usize) -> PyResult<i32> {
        let p = u.py();
        tick(session::REL_TVAR);
        let map = self.dict(intern!(p, "_tv"))?;
        let tv = match map.get_item(u)? {
            Some(t) => t,
            None => {
                let t = PyList::new(p, [0, 0, 0, 0, 0])?.into_any();
                map.set_item(u, &t)?;
                t
            }
        };
        let v: i32 = tv.get_item(k)?.extract()?;
        if v != 0 {
            return Ok(v);
        }
        let v = fresh(self.s, self.c, true)?;
        tv.set_item(k, v)?;
        let tsrc = self.dict(intern!(p, "_tsrc"))?;
        if k == MC {
            for j in [SD, EN] {
                let w: i32 = tv.get_item(j)?.extract()?;
                if w != 0 {
                    if !planted(DROP_TVAR_MC) {
                        self.c.emit_direct(p, &[-w, v])?;
                    }
                } else if tsrc.contains((u, j))? {
                    self.tvar(u, j)?;
                }
            }
            return Ok(v);
        }
        if let Some(lst) = tsrc.get_item((u, k))? {
            for g in lst.try_iter()? {
                if planted(DROP_TVAR) {
                    continue;
                }
                self.c.emit_direct(p, &with_tail(&g?, &[v])?)?;
            }
        }
        if k == SD || k == EN {
            let m: i32 = tv.get_item(MC)?.extract()?;
            if m != 0 && !planted(DROP_TVAR_MC) {
                self.c.emit_direct(p, &[-v, m])?;
            }
        }
        Ok(v)
    }

    /// `_share_guard`.
    fn share_guard(&self, u: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyList>> {
        tick(session::REL_SHARE_GUARD);
        let il = self.tvar(u, IL)?;
        let ie = self.tvar(u, IE)?;
        if planted(SHARE_GUARD_ONE) {
            return PyList::new(u.py(), [-il]);
        }
        PyList::new(u.py(), [-il, -ie])
    }

    /// `_congruent`.
    fn congruent(&self, node: &Bound<'py, PyAny>) -> PyResult<bool> {
        let p = node.py();
        tick(session::REL_CONGRUENT);
        let Some(others) = self.dict(intern!(p, "_xheads"))?.get_item(head(node)?)? else { return Ok(false) };
        if others.len()? < 2 {
            return Ok(false);
        }
        if self.rel.getattr(intern!(p, "_xadapter"))?.call_method1(intern!(p, "term_of"), (node,))?.is_none()
            && !self.rel.getattr(intern!(p, "num_sel"))?.contains(node)?
        {
            return Ok(false);
        }
        let (cand, xside) = (self.rel.getattr(intern!(p, "_xcand"))?, self.rel.getattr(intern!(p, "_xside"))?);
        let args = node.getattr(intern!(p, "args"))?;
        for o in others.try_iter()? {
            let o = o?;
            if o.is(node) || o.eq(node)? {
                continue;
            }
            let mut differ = false;
            let mut broke = false;
            for pair in args.try_iter()?.zip(o.getattr(intern!(p, "args"))?.try_iter()?) {
                let (a, b) = (pair.0?, pair.1?);
                if a.eq(&b)? {
                    continue;
                }
                if !(mergeable(&cand, &xside, &a)? && mergeable(&cand, &xside, &b)?) || (rational_flag(&a)? && rational_flag(&b)?) {
                    broke = true;
                    break;
                }
                differ = true;
            }
            if !broke && differ {
                return Ok(!planted(CONGRUENT_NEVER));
            }
        }
        Ok(false)
    }

    /// `_engage_transfer`. The theory's class is read at each call, as Python's `from ... import` is: `backend` and tests replace it.
    fn engage_transfer(&self) -> PyResult<()> {
        let p = self.rel.py();
        tick(session::REL_ENGAGE);
        if !self.s.getattr(intern!(p, "engine"))?.getattr(intern!(p, "transfer"))?.is_truthy()? {
            return Ok(());
        }
        let mut ad = None;
        for spec in self.rel.getattr(intern!(p, "specs"))?.try_iter()? {
            let spec = spec?;
            if !spec.getattr(intern!(p, "guarded"))?.is_truthy()? {
                let a = self.rel.call_method1(intern!(p, "_adapter"), (&spec,))?;
                if a.getattr_opt(intern!(p, "node_term"))?.is_some() {
                    ad = Some(a);
                    break;
                }
            }
        }
        let Some(ad) = ad else { return Ok(()) };
        let class = p.import(intern!(p, "satassume.theories.transfer"))?.getattr(intern!(p, "TransferTheory"))?;
        let solver = self.solver()?;
        ad.call_method1(intern!(p, "attach"), (&solver,))?;
        let th = class.call1((ad.getattr(intern!(p, "theory"))?,))?;
        solver.call_method1(intern!(p, "attach_theory"), (&th,))?;
        let sel = fresh(self.s, self.c, true)?;
        th.call_method1(intern!(p, "guard"), (sel,))?;
        if !planted(DROP_ENGAGE) {
            solver.call_method1(intern!(p, "register_atom"), (&th, sel, (intern!(p, "enable"),)))?;
        }
        self.rel.setattr(intern!(p, "xfer_sel"), sel)?;
        self.rel.setattr(intern!(p, "_xadapter"), &ad)?;
        self.rel.setattr(intern!(p, "xfer"), &th)?;
        self.s.setattr(intern!(p, "xfer"), self.rel)
    }

    /// `_transfer_terms`.
    fn transfer_terms(&self) -> PyResult<bool> {
        let p = self.rel.py();
        tick(session::REL_TRANSFER_TERMS);
        let sy = p.import(intern!(p, "sympy"))?;
        let (basic, expr, rational) = (sy.getattr(intern!(p, "Basic"))?, sy.getattr(intern!(p, "Expr"))?, sy.getattr(intern!(p, "Rational"))?);
        let rel = self.rel;
        let (ad, th) = (rel.getattr(intern!(p, "_xadapter"))?, rel.getattr(intern!(p, "xfer"))?);
        let mut visited = false;
        let sides = rel.getattr(intern!(p, "_xside"))?;
        let n = sides.len()?;
        let from: usize = rel.getattr(intern!(p, "_xterm"))?.extract()?;
        if from < n {
            let new = sides.try_iter()?.skip(from).take(n - from).collect::<PyResult<Vec<_>>>()?;
            rel.setattr(intern!(p, "_xterm"), n)?;
            for e in &new {
                if e.is_instance(&rational)? {
                    let t = ad.call_method1(intern!(p, "term_of"), (e,))?;
                    if !t.is_none() && !planted(DROP_FIXED) {
                        let facts = self.h.relations.bind(p).getattr(intern!(p, "_number_facts"))?.call1((self.s.getattr(intern!(p, "engine"))?, e))?;
                        th.call_method1(intern!(p, "set_fixed"), (t, facts))?;
                    }
                    continue;
                }
                if e.is_instance(&expr)? && !self.c.base_contains_direct(e)? {
                    if planted(DROP_TERMS_SIDE) {
                        continue;
                    }
                    self.s.call_method1(intern!(p, "ensure"), (e,))?;
                    visited = true;
                }
            }
        }
        let new = ad.call_method1(intern!(p, "terms_since"), (rel.getattr(intern!(p, "_xtcur"))?,))?;
        let extra = rel.getattr(intern!(p, "_xextra"))?;
        if new.is_truthy()? || extra.is_truthy()? {
            let cur: usize = rel.getattr(intern!(p, "_xtcur"))?.extract()?;
            rel.setattr(intern!(p, "_xtcur"), cur + new.len()?)?;
            if extra.is_truthy()? {
                new.call_method1(intern!(p, "extend"), (&extra,))?;
                extra.call_method0(intern!(p, "clear"))?;
            }
            let heads = self.dict(intern!(p, "_xheads"))?;
            let counted = rel.getattr(intern!(p, "_xcounted"))?;
            // A dict, as Python's: distinct by `==`, in insertion order.
            let grown = PyDict::new(p);
            for e in new.try_iter()? {
                let e = e?;
                if !counted.contains(&e)? && e.is_instance(&basic)? && self.structural(&e)? {
                    counted.call_method1(intern!(p, "add"), (&e,))?;
                    let k = head(&e)?;
                    match heads.get_item(&k)? {
                        None => heads.set_item(&k, PyList::new(p, [&e])?)?,
                        Some(h) => {
                            h.call_method1(intern!(p, "append"), (&e,))?;
                            grown.set_item(&k, p.None())?;
                        }
                    }
                }
            }
            if !grown.is_empty() {
                let hn: i64 = rel.getattr(intern!(p, "_xhn"))?.extract()?;
                rel.setattr(intern!(p, "_xhn"), hn + 1)?;
                for k in grown.as_any().try_iter()? {
                    for e in heads.as_any().get_item(k?)?.try_iter()? {
                        let e = e?;
                        if e.is_instance(&expr)? && !self.c.base_contains_direct(&e)? {
                            if planted(DROP_TERMS) {
                                continue;
                            }
                            self.s.call_method1(intern!(p, "ensure"), (&e,))?;
                            visited = true;
                        }
                    }
                }
            }
        }
        Ok(visited)
    }

    /// `_xswitch`. Moved with `sync_transfer`, its only caller.
    fn xswitch(&self, node: &Bound<'py, PyAny>, t: &Bound<'py, PyAny>) -> PyResult<()> {
        let p = node.py();
        tick(session::REL_XSWITCH);
        let solver = self.solver()?;
        let th = self.rel.getattr(intern!(p, "xfer"))?;
        let en = self.tvar(node, EN)?;
        let sd = self.tvar(node, SD)?;
        for v in th.call_method1(intern!(p, "switch"), (t, en, sd))?.try_iter()? {
            let v = v?;
            if planted(DROP_XSWITCH) {
                continue;
            }
            solver.call_method1(intern!(p, "register_atom"), (&th, v, (intern!(p, "on"),)))?;
        }
        Ok(())
    }

    /// `sync_transfer`. `slots` is read past its view: a custom atom's slot is built only for Python to see it isn't a tuple.
    fn sync_transfer(&self) -> PyResult<()> {
        let p = self.rel.py();
        let rel = self.rel;
        tick(session::REL_SYNC_TRANSFER);
        let mut i: usize = rel.getattr(intern!(p, "_xslot"))?.extract()?;
        let n = self.c.n_slots_direct();
        let nside = rel.getattr(intern!(p, "_xsides_n"))?;
        if i >= n && nside.eq(rel.getattr(intern!(p, "_xnsides"))?)? && rel.getattr(intern!(p, "_xhn"))?.eq(rel.getattr(intern!(p, "_xhseen"))?)? {
            return Ok(());
        }
        let r = self.h.relations.bind(p);
        let npred: usize = r.getattr(intern!(p, "NPRED"))?.extract()?;
        let sy = p.import(intern!(p, "sympy"))?;
        let (basic, rational, nan) = (sy.getattr(intern!(p, "Basic"))?, sy.getattr(intern!(p, "Rational"))?, sy.getattr(intern!(p, "nan"))?);
        let pend = rel.getattr(intern!(p, "_xpend"))?;
        while i < n {
            if let Some(node) = self.c.block_direct(p, i) {
                if node.is_instance(&basic)? && !node.call_method1(intern!(p, "has"), (&nan,))?.is_truthy()? {
                    pend.call_method1(intern!(p, "append"), ((&node, i),))?;
                }
                i += npred;
            } else {
                i += 1;
            }
        }
        rel.setattr(intern!(p, "_xslot"), n)?;
        rel.setattr(intern!(p, "_xnsides"), &nside)?;
        rel.setattr(intern!(p, "_xhseen"), rel.getattr(intern!(p, "_xhn"))?)?;
        let cand = rel.getattr(intern!(p, "_xcand"))?;
        let part = rel.getattr(intern!(p, "_xpart"))?;
        let xside = self.dict(intern!(p, "_xside"))?;
        let ad = rel.getattr(intern!(p, "_xadapter"))?;
        let solver = self.solver()?;
        let th = rel.getattr(intern!(p, "xfer"))?;
        let polar: i32 = r.getattr(intern!(p, "BASIS_INDEX"))?.get_item(intern!(p, "polar"))?.extract()?;
        let mut changed = true;
        while changed && pend.is_truthy()? {
            changed = false;
            let keep = PyList::empty(p);
            for entry in pend.try_iter()? {
                let entry = entry?;
                let (node, b) = two(&entry)?;
                let b: i32 = b.extract()?;
                let lv: i64 = match xside.get_item(&node)? {
                    Some(x) => x.extract()?,
                    None => 0,
                };
                if lv == 2 || (self.structural(&node)? && self.congruent(&node)?) {
                    cand.call_method1(intern!(p, "add"), (&node,))?;
                    changed = true;
                    let t = ad.call_method1(intern!(p, "node_term"), (&node,))?;
                    self.c.ensure_vars_direct(p, b + npred as i32 - 1)?;
                    let is_rational = node.is_instance(&rational)?;
                    // `_number_basis` is a sorted tuple.
                    let preds: Vec<i32> = if is_rational {
                        r.getattr(intern!(p, "_number_basis"))?.call1((self.s.getattr(intern!(p, "engine"))?, &node))?.extract()?
                    } else {
                        (0..npred as i32).collect()
                    };
                    let full = !is_rational || preds.len() == npred;
                    for k in preds {
                        if k != polar || !part.contains(&node)? {
                            if k == 0 && planted(DROP_SYNC) {
                                continue;
                            }
                            let tag = if full { (&t, k).into_pyobject(p)?.into_any() } else { (&t, k, true).into_pyobject(p)?.into_any() };
                            solver.call_method1(intern!(p, "register_atom"), (&th, b + k, tag, false))?;
                        }
                    }
                    if !is_rational {
                        self.xswitch(&node, &t)?;
                    }
                    continue;
                }
                if lv == 1 && !part.contains(&node)? {
                    part.call_method1(intern!(p, "add"), (&node,))?;
                    let t = ad.call_method1(intern!(p, "node_term"), (&node,))?;
                    if !planted(DROP_SYNC_POLAR) {
                        solver.call_method1(intern!(p, "register_atom"), (&th, b + polar, (&t, polar, true), false))?;
                    }
                    self.xswitch(&node, &t)?;
                }
                keep.append(&entry)?;
            }
            pend.set_item(pyo3::types::PySlice::full(p), &keep)?;
        }
        self.congruence_pairs()
    }

    /// `_congruence_pairs`. Groups are walked in `_xheads`' insertion order and pairs by position.
    fn congruence_pairs(&self) -> PyResult<()> {
        let p = self.rel.py();
        let rel = self.rel;
        tick(session::REL_CONGRUENCE_PAIRS);
        let (xside, cand, done) = (rel.getattr(intern!(p, "_xside"))?, rel.getattr(intern!(p, "_xcand"))?, rel.getattr(intern!(p, "_xpairs"))?);
        for group in rel.getattr(intern!(p, "_xheads"))?.call_method0(intern!(p, "values"))?.try_iter()? {
            let group = group?.cast_into::<PyList>()?;
            let n = group.len();
            if n < 2 {
                continue;
            }
            for j in 1..n {
                let g2 = group.get_item(j)?;
                let g2_args = g2.getattr(intern!(p, "args"))?;
                for f in group.get_slice(0, j).iter() {
                    let key = (&f, &g2).into_pyobject(p)?;
                    if done.contains(&key)? {
                        continue;
                    }
                    let mut diff = Vec::new();
                    // Python's `ok`: Some(true), Some(false), or None for two distinct rationals.
                    let mut ok = Some(true);
                    for pair in f.getattr(intern!(p, "args"))?.try_iter()?.zip(g2_args.try_iter()?) {
                        let (x, y) = (pair.0?, pair.1?);
                        if x.eq(&y)? {
                            continue;
                        }
                        if rational_flag(&x)? && rational_flag(&y)? {
                            ok = None;
                            break;
                        }
                        if !(mergeable(&cand, &xside, &x)? && mergeable(&cand, &xside, &y)?) {
                            ok = Some(false);
                            break;
                        }
                        diff.push((x, y));
                    }
                    if ok.is_none() || (ok == Some(true) && !diff.is_empty()) {
                        done.call_method1(intern!(p, "add"), (&key,))?;
                    }
                    if ok != Some(true) || diff.is_empty() {
                        continue;
                    }
                    let mut body = vec![-self.tvar(&f, IE)?, -self.tvar(&g2, IE)?];
                    for (x, y) in &diff {
                        body.push(-self.tvar(x, MC)?);
                        body.push(-self.tvar(y, MC)?);
                    }
                    let mut c1 = body.clone();
                    c1.push(self.tvar(&f, EN)?);
                    self.c.emit_direct(p, &c1)?;
                    if planted(DROP_CONGRUENCE) {
                        continue;
                    }
                    let mut c2 = body;
                    c2.push(self.tvar(&g2, EN)?);
                    self.c.emit_direct(p, &c2)?;
                }
            }
        }
        Ok(())
    }
}

/// Runs `f` with `rel`'s session. A callback can come back in; the core is frozen, so holding this borrow across one is safe.
fn with_cx<'py, T>(rel: &Bound<'py, PyAny>, f: impl FnOnce(&Cx<'_, 'py>) -> PyResult<T>) -> PyResult<T> {
    let h = hooks()?;
    let (s, c) = session_of(rel.py(), &h, rel)?;
    let c = c.borrow();
    f(&Cx { rel, s: &s, c: &c, h: &h })
}

#[pyfunction]
fn rel_add_role<'py>(rel: &Bound<'py, PyAny>, atom: &Bound<'py, PyAny>, g: &Bound<'py, PyAny>, kind: &Bound<'py, PyAny>) -> PyResult<()> {
    with_cx(rel, |x| x.add_role(atom, g, kind))
}

#[pyfunction]
fn rel_apply_role<'py>(rel: &Bound<'py, PyAny>, atom: &Bound<'py, PyAny>, info: &Bound<'py, PyAny>, kind: &Bound<'py, PyAny>, g: &Bound<'py, PyAny>) -> PyResult<()> {
    with_cx(rel, |x| x.apply_role(atom, info, kind, g))
}

#[pyfunction]
fn rel_tsource<'py>(rel: &Bound<'py, PyAny>, u: &Bound<'py, PyAny>, k: usize, g: &Bound<'py, PyAny>) -> PyResult<()> {
    with_cx(rel, |x| x.tsource(u, k, g))
}

#[pyfunction]
fn rel_tvar<'py>(rel: &Bound<'py, PyAny>, u: &Bound<'py, PyAny>, k: usize) -> PyResult<i32> {
    with_cx(rel, |x| x.tvar(u, k))
}

#[pyfunction]
fn rel_share_guard<'py>(rel: &Bound<'py, PyAny>, u: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyList>> {
    with_cx(rel, |x| x.share_guard(u))
}

#[pyfunction]
fn rel_congruent<'py>(rel: &Bound<'py, PyAny>, node: &Bound<'py, PyAny>) -> PyResult<bool> {
    with_cx(rel, |x| x.congruent(node))
}

#[pyfunction]
fn rel_engage_transfer(rel: &Bound<'_, PyAny>) -> PyResult<()> {
    with_cx(rel, |x| x.engage_transfer())
}

#[pyfunction]
fn rel_transfer_terms(rel: &Bound<'_, PyAny>) -> PyResult<bool> {
    with_cx(rel, |x| x.transfer_terms())
}

#[pyfunction]
fn rel_sync_transfer(rel: &Bound<'_, PyAny>) -> PyResult<()> {
    with_cx(rel, |x| x.sync_transfer())
}

#[pyfunction]
fn rel_xswitch<'py>(rel: &Bound<'py, PyAny>, node: &Bound<'py, PyAny>, t: &Bound<'py, PyAny>) -> PyResult<()> {
    with_cx(rel, |x| x.xswitch(node, t))
}

#[pyfunction]
fn rel_congruence_pairs(rel: &Bound<'_, PyAny>) -> PyResult<()> {
    with_cx(rel, |x| x.congruence_pairs())
}

/// The link alone, for its tests.
#[pyfunction]
fn rel_link_probe(core: &Bound<'_, SessionCore>, x: &Bound<'_, PyAny>) -> PyResult<Option<u32>> {
    let h = hooks()?;
    Ok(term_of(&core.borrow(), &h, x)?.map(|l| l.id))
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(rel_link_probe, m)?)?;
    m.add_function(wrap_pyfunction!(rel_install, m)?)?;
    m.add_function(wrap_pyfunction!(rel_plant, m)?)?;
    m.add_function(wrap_pyfunction!(rel_closed_extended_real, m)?)?;
    m.add_function(wrap_pyfunction!(rel_order_sides, m)?)?;
    m.add_function(wrap_pyfunction!(rel_order_infinite, m)?)?;
    m.add_function(wrap_pyfunction!(rel_trichotomy, m)?)?;
    m.add_function(wrap_pyfunction!(rel_mention_number, m)?)?;
    m.add_function(wrap_pyfunction!(rel_link_integer, m)?)?;
    m.add_function(wrap_pyfunction!(rel_fresh, m)?)?;
    m.add_function(wrap_pyfunction!(rel_bound, m)?)?;
    m.add_function(wrap_pyfunction!(rel_guard, m)?)?;
    m.add_function(wrap_pyfunction!(rel_eq_infinity, m)?)?;
    m.add_function(wrap_pyfunction!(rel_interpret, m)?)?;
    m.add_function(wrap_pyfunction!(rel_link, m)?)?;
    m.add_function(wrap_pyfunction!(rel_selectors_of, m)?)?;
    m.add_function(wrap_pyfunction!(rel_add_role, m)?)?;
    m.add_function(wrap_pyfunction!(rel_apply_role, m)?)?;
    m.add_function(wrap_pyfunction!(rel_tsource, m)?)?;
    m.add_function(wrap_pyfunction!(rel_tvar, m)?)?;
    m.add_function(wrap_pyfunction!(rel_share_guard, m)?)?;
    m.add_function(wrap_pyfunction!(rel_congruent, m)?)?;
    m.add_function(wrap_pyfunction!(rel_engage_transfer, m)?)?;
    m.add_function(wrap_pyfunction!(rel_transfer_terms, m)?)?;
    m.add_function(wrap_pyfunction!(rel_sync_transfer, m)?)?;
    m.add_function(wrap_pyfunction!(rel_xswitch, m)?)?;
    m.add_function(wrap_pyfunction!(rel_congruence_pairs, m)?)
}
