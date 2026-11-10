//! Step 5c1: `Session`'s discovery, `ensure`, `discover`, `_discover`, `incomplete` and `escalate` (`engine.py:772-850`),
//! over the session's own Python containers: `frontier` (a deque, replaced by a new one where Python replaces it),
//! `pending`, `pending_c`, `demand` and `deferred` stay Python objects that Python reads later, so state is Python's by
//! construction. `node` is `session_live._node`'s body, against the core directly.
//! `_flush`, `_compile`, `_emit_pattern` and `_compile_pending` moved to Rust in 5c2 (`compile_loop.rs`); still Python: the visit itself (`_core_visit`, through the core).
//! Every read Python makes, Rust makes in the same order, including the `node in self.base` reads that tick `py:node`.
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::types::{PyList, PySet};

use crate::relations_core::{
    planted, DROP_DISCOVER_FLUSH, DROP_DISCOVER_VISIT, DROP_ENSURE_DEMAND, DROP_ESC_COMPILE, DROP_ESC_DEFERRED, DROP_ESC_PATTERN,
    INCOMPLETE_NEVER, TRUNCATED_NEVER,
};
use crate::session::{tick, SessionCore, SES_DISCOVER, SES_ENSURE, SES_ESCALATE, SES_INCOMPLETE};

fn core_of<'py>(s: &Bound<'py, PyAny>) -> PyResult<Bound<'py, SessionCore>> {
    let p = s.py();
    Ok(s.getattr(intern!(p, "table"))?.getattr(intern!(p, "core"))?.cast_into::<SessionCore>()?)
}

/// `deque()` or `deque([x])`, a new object each time, as Python makes one.
fn deque<'py>(p: Python<'py>, x: Option<&Bound<'py, PyAny>>) -> PyResult<Bound<'py, PyAny>> {
    let d = p.import(intern!(p, "collections"))?.getattr(intern!(p, "deque"))?;
    match x {
        None => d.call0(),
        Some(x) => d.call1((PyList::new(p, [x])?,)),
    }
}

fn attr<'py>(s: &Bound<'py, PyAny>, name: &Bound<'py, pyo3::types::PyString>) -> PyResult<Bound<'py, PyAny>> {
    s.getattr(name)
}

/// `n in self.base`: the view's `__contains__` is `core.base_get(n) is not None`, which ticks `py:node`.
fn in_base(c: &SessionCore, n: &Bound<'_, PyAny>) -> PyResult<bool> {
    Ok(c.base_get(n)?.is_some())
}

/// `session_live._node`: `Session.node` under the core.
fn node(s: &Bound<'_, PyAny>, c: &SessionCore, n: &Bound<'_, PyAny>, demanded: &Bound<'_, PyAny>) -> PyResult<i32> {
    let p = s.py();
    if let Some(b) = c.base_get(n)? {
        if !demanded.is_none()
            && (attr(s, intern!(p, "pending"))?.contains(n)? || attr(s, intern!(p, "pending_c"))?.contains(n)?)
        {
            crate::compile_loop::compile_pending(s, n, demanded)?;
        }
        return Ok(b);
    }
    c.visit(n, demanded)
}

/// `Session._discover`.
fn discover_inner(s: &Bound<'_, PyAny>, c: &SessionCore, demanded: &Bound<'_, PyAny>) -> PyResult<()> {
    let p = s.py();
    let (pending, pending_c) = (attr(s, intern!(p, "pending"))?, attr(s, intern!(p, "pending_c"))?);
    loop {
        let fr = attr(s, intern!(p, "frontier"))?;
        if !fr.is_truthy()? {
            break;
        }
        let n = fr.call_method0(intern!(p, "popleft"))?;
        if in_base(c, &n)? && !pending.contains(&n)? && !pending_c.contains(&n)? {
            continue;
        }
        if demanded.is_none() {
            if planted(DROP_DISCOVER_VISIT) {
                continue;
            }
            node(s, c, &n, &p.None().into_bound(p))?;
        } else {
            let d = attr(s, intern!(p, "demand"))?.call_method1(intern!(p, "get"), (&n, PySet::empty(p)?))?;
            node(s, c, &n, &d)?;
        }
    }
    s.setattr(intern!(p, "frontier"), deque(p, None)?)
}

#[pyfunction]
#[pyo3(signature = (s, n, demanded=None))]
fn ses_ensure(s: &Bound<'_, PyAny>, n: &Bound<'_, PyAny>, demanded: Option<Bound<'_, PyAny>>) -> PyResult<()> {
    tick(SES_ENSURE);
    let p = s.py();
    let demanded = demanded.unwrap_or_else(|| p.None().into_bound(p));
    let core = core_of(s)?;
    let c = core.borrow();
    if !demanded.is_none() && !planted(DROP_ENSURE_DEMAND) {
        let d = attr(s, intern!(p, "demand"))?.call_method1(intern!(p, "setdefault"), (n, PySet::empty(p)?))?;
        let basis_of = p.import(intern!(p, "satassume.engine"))?.getattr(intern!(p, "BASIS_OF"))?;
        for q in demanded.try_iter()? {
            d.call_method1(intern!(p, "update"), (basis_of.get_item(q?)?,))?;
        }
    }
    if in_base(&c, n)? && !attr(s, intern!(p, "pending"))?.contains(n)? && !attr(s, intern!(p, "pending_c"))?.contains(n)? {
        if attr(s, intern!(p, "frontier"))?.is_truthy()? {
            s.setattr(intern!(p, "frontier"), deque(p, None)?)?;
        }
        return Ok(());
    }
    s.setattr(intern!(p, "frontier"), deque(p, Some(n))?)?;
    discover_inner(s, &c, &demanded)
}

#[pyfunction]
#[pyo3(signature = (s, demanded=None))]
fn ses_discover_raw(s: &Bound<'_, PyAny>, demanded: Option<Bound<'_, PyAny>>) -> PyResult<()> {
    let p = s.py();
    let core = core_of(s)?;
    let c = core.borrow();
    discover_inner(s, &c, &demanded.unwrap_or_else(|| p.None().into_bound(p)))
}

#[pyfunction]
fn ses_discover(s: &Bound<'_, PyAny>) -> PyResult<()> {
    tick(SES_DISCOVER);
    let p = s.py();
    if !planted(DROP_DISCOVER_FLUSH) {
        crate::compile_loop::flush(s, &p.None().into_bound(p))?;
    }
    let core = core_of(s)?;
    let c = core.borrow();
    discover_inner(s, &c, &p.None().into_bound(p))
}

#[pyfunction]
fn ses_incomplete(s: &Bound<'_, PyAny>) -> PyResult<bool> {
    tick(SES_INCOMPLETE);
    let p = s.py();
    let r = attr(s, intern!(p, "pending"))?.is_truthy()?
        || attr(s, intern!(p, "pending_c"))?.is_truthy()?
        || attr(s, intern!(p, "deferred"))?.is_truthy()?;
    Ok(r && !planted(INCOMPLETE_NEVER))
}

/// `pending or pending_c or deferred or frontier`, each read afresh, left to right.
fn any_left(s: &Bound<'_, PyAny>) -> PyResult<bool> {
    let p = s.py();
    Ok(attr(s, intern!(p, "pending"))?.is_truthy()?
        || attr(s, intern!(p, "pending_c"))?.is_truthy()?
        || attr(s, intern!(p, "deferred"))?.is_truthy()?
        || attr(s, intern!(p, "frontier"))?.is_truthy()?)
}

#[pyfunction]
#[pyo3(signature = (s, budget=None))]
fn ses_escalate(s: &Bound<'_, PyAny>, budget: Option<Bound<'_, PyAny>>) -> PyResult<()> {
    tick(SES_ESCALATE);
    let p = s.py();
    // `budget = _UNCAPPED` (float("inf")) when None; `added < budget` is Python's own comparison.
    let budget = match budget {
        Some(b) if !b.is_none() => b,
        _ => p.import(intern!(p, "satassume.engine"))?.getattr(intern!(p, "_UNCAPPED"))?,
    };
    let core = core_of(s)?;
    let c = core.borrow();
    let none = p.None().into_bound(p);
    let mut added: i64 = 0;
    while any_left(s)? && added.into_pyobject(p)?.lt(&budget)? {
        let pending_c = attr(s, intern!(p, "pending_c"))?;
        if pending_c.is_truthy()? {
            let item = pending_c.call_method0(intern!(p, "popitem"))?;
            let pend = item.get_item(1)?;
            if !planted(DROP_ESC_PATTERN) {
                for x in pend.try_iter()? {
                    let mut it = x?.try_iter()?;
                    let (cl, bs) = (it.next().unwrap()?, it.next().unwrap()?);
                    crate::compile_loop::emit_pattern(s, &cl, &bs, &none)?;
                }
            }
            added += 1;
            continue;
        }
        let pending = attr(s, intern!(p, "pending"))?;
        if pending.is_truthy()? {
            let item = pending.call_method0(intern!(p, "popitem"))?;
            if !planted(DROP_ESC_COMPILE) {
                crate::compile_loop::compile(s, &item.get_item(0)?, &item.get_item(1)?)?;
            }
            added += 1;
            continue;
        }
        let fr = attr(s, intern!(p, "frontier"))?;
        if fr.is_truthy()? {
            let n = fr.call_method0(intern!(p, "popleft"))?;
            if !in_base(&c, &n)? {
                node(s, &c, &n, &none)?;
                added += 1;
            }
            continue;
        }
        let n = attr(s, intern!(p, "deferred"))?.call_method0(intern!(p, "pop"))?;
        if !in_base(&c, &n)? {
            if planted(DROP_ESC_DEFERRED) {
                continue;
            }
            node(s, &c, &n, &none)?;
            added += 1;
        }
    }
    if any_left(s)? {
        let mut cut = attr(s, intern!(p, "pending"))?.is_truthy()? || attr(s, intern!(p, "pending_c"))?.is_truthy()?;
        if !cut {
            for n in attr(s, intern!(p, "deferred"))?.try_iter()? {
                if !in_base(&c, &n?)? {
                    cut = true;
                    break;
                }
            }
        }
        if !cut {
            for n in attr(s, intern!(p, "frontier"))?.try_iter()? {
                if !in_base(&c, &n?)? {
                    cut = true;
                    break;
                }
            }
        }
        if cut && !planted(TRUNCATED_NEVER) {
            crate::session::ses_set_flag(s, crate::session::SS_TRUNCATED, true)?;
        }
    }
    s.setattr(intern!(p, "frontier"), deque(p, None)?)
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(ses_ensure, m)?)?;
    m.add_function(wrap_pyfunction!(ses_discover_raw, m)?)?;
    m.add_function(wrap_pyfunction!(ses_discover, m)?)?;
    m.add_function(wrap_pyfunction!(ses_incomplete, m)?)?;
    m.add_function(wrap_pyfunction!(ses_escalate, m)?)
}
