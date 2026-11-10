//! Step 5c1: `Session`'s discovery, `ensure`, `discover`, `_discover`, `incomplete` and `escalate` (`engine.py:772-850`),
//! over the session's containers: `frontier`, `pending`, `pending_c`, `demand` and `deferred`, held in the session core
//! since state part 3 (ses_cont.rs; Python reads them through views; a session with no core keeps Python's own objects).
//! `node` is `session_live._node`'s body, against the core directly.
//! `_flush`, `_compile`, `_emit_pattern` and `_compile_pending` moved to Rust in 5c2 (`compile_loop.rs`); still Python: the visit itself (`_core_visit`, through the core).
//! Every read Python makes, Rust makes in the same order, including the `node in self.base` reads that tick `py:node`.
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::types::PySet;

use crate::relations_core::{
    planted, DROP_DISCOVER_FLUSH, DROP_DISCOVER_VISIT, DROP_ENSURE_DEMAND, DROP_ESC_COMPILE, DROP_ESC_DEFERRED, DROP_ESC_PATTERN,
    INCOMPLETE_NEVER, TRUNCATED_NEVER,
};
use crate::ses_cont::{Ses, SD_DEMAND, SD_PENDING, SD_PENDING_C, SQ_DEFERRED, SQ_FRONTIER};
use crate::session::{tick, SessionCore, SES_DISCOVER, SES_ENSURE, SES_ESCALATE, SES_INCOMPLETE};

fn core_of<'py>(s: &Bound<'py, PyAny>) -> PyResult<Bound<'py, SessionCore>> {
    let p = s.py();
    Ok(s.getattr(intern!(p, "table"))?.getattr(intern!(p, "core"))?.cast_into::<SessionCore>()?)
}

/// `n in self.base`: the view's `__contains__` is `core.base_get(n) is not None`, which ticks `py:node`.
fn in_base(c: &SessionCore, n: &Bound<'_, PyAny>) -> PyResult<bool> {
    Ok(c.base_get(n)?.is_some())
}

/// `session_live._node`: `Session.node` under the core.
fn node<'py>(s: &Bound<'py, PyAny>, ses: &Ses<'py>, c: &SessionCore, n: &Bound<'py, PyAny>, demanded: &Bound<'py, PyAny>) -> PyResult<i32> {
    if let Some(b) = c.base_get(n)? {
        if !demanded.is_none() && (ses.d_contains(SD_PENDING, n)? || ses.d_contains(SD_PENDING_C, n)?) {
            crate::compile_loop::compile_pending(s, n, demanded)?;
        }
        return Ok(b);
    }
    c.visit(n, demanded)
}

/// `Session._discover`.
fn discover_inner<'py>(s: &Bound<'py, PyAny>, ses: &Ses<'py>, c: &SessionCore, demanded: &Bound<'py, PyAny>) -> PyResult<()> {
    let p = s.py();
    while ses.q_truthy(SQ_FRONTIER)? {
        let n = ses.q_popleft(SQ_FRONTIER)?;
        if in_base(c, &n)? && !ses.d_contains(SD_PENDING, &n)? && !ses.d_contains(SD_PENDING_C, &n)? {
            continue;
        }
        if demanded.is_none() {
            if planted(DROP_DISCOVER_VISIT) {
                continue;
            }
            node(s, ses, c, &n, &p.None().into_bound(p))?;
        } else {
            let mut d = ses.d_get(SD_DEMAND, &n)?;
            if d.is_none() {
                d = PySet::empty(p)?.into_any();
            }
            node(s, ses, c, &n, &d)?;
        }
    }
    ses.frontier_reset(None)
}

#[pyfunction]
#[pyo3(signature = (s, n, demanded=None))]
fn ses_ensure<'py>(s: &Bound<'py, PyAny>, n: &Bound<'py, PyAny>, demanded: Option<Bound<'py, PyAny>>) -> PyResult<()> {
    tick(SES_ENSURE);
    let p = s.py();
    let demanded = demanded.unwrap_or_else(|| p.None().into_bound(p));
    let core = core_of(s)?;
    let c = core.borrow();
    let ses = Ses::Core(core.clone());
    if !demanded.is_none() && !planted(DROP_ENSURE_DEMAND) {
        let mut d = ses.d_get(SD_DEMAND, n)?;
        if d.is_none() {
            d = PySet::empty(p)?.into_any();
            ses.d_set(SD_DEMAND, n, &d)?;
            d = ses.d_get(SD_DEMAND, n)?;       // what the dict holds, as `setdefault` returns it
        }
        if !d.is_none() {
            let basis_of = p.import(intern!(p, "satassume.engine"))?.getattr(intern!(p, "BASIS_OF"))?;
            for q in demanded.try_iter()? {
                d.call_method1(intern!(p, "update"), (basis_of.get_item(q?)?,))?;
            }
        }
    }
    if in_base(&c, n)? && !ses.d_contains(SD_PENDING, n)? && !ses.d_contains(SD_PENDING_C, n)? {
        if ses.q_truthy(SQ_FRONTIER)? {
            ses.frontier_reset(None)?;
        }
        return Ok(());
    }
    ses.frontier_reset(Some(n))?;
    discover_inner(s, &ses, &c, &demanded)
}

#[pyfunction]
#[pyo3(signature = (s, demanded=None))]
fn ses_discover_raw<'py>(s: &Bound<'py, PyAny>, demanded: Option<Bound<'py, PyAny>>) -> PyResult<()> {
    let p = s.py();
    let core = core_of(s)?;
    let c = core.borrow();
    discover_inner(s, &Ses::Core(core.clone()), &c, &demanded.unwrap_or_else(|| p.None().into_bound(p)))
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
    discover_inner(s, &Ses::Core(core.clone()), &c, &p.None().into_bound(p))
}

#[pyfunction]
fn ses_incomplete(s: &Bound<'_, PyAny>) -> PyResult<bool> {
    tick(SES_INCOMPLETE);
    let ses = Ses::of(s);
    let r = ses.d_truthy(SD_PENDING)? || ses.d_truthy(SD_PENDING_C)? || ses.q_truthy(SQ_DEFERRED)?;
    Ok(r && !planted(INCOMPLETE_NEVER))
}

/// `pending or pending_c or deferred or frontier`, each read afresh, left to right.
fn any_left(ses: &Ses<'_>) -> PyResult<bool> {
    Ok(ses.d_truthy(SD_PENDING)? || ses.d_truthy(SD_PENDING_C)? || ses.q_truthy(SQ_DEFERRED)? || ses.q_truthy(SQ_FRONTIER)?)
}

#[pyfunction]
#[pyo3(signature = (s, budget=None))]
fn ses_escalate<'py>(s: &Bound<'py, PyAny>, budget: Option<Bound<'py, PyAny>>) -> PyResult<()> {
    tick(SES_ESCALATE);
    let p = s.py();
    // `budget = _UNCAPPED` (float("inf")) when None; `added < budget` is Python's own comparison.
    let budget = match budget {
        Some(b) if !b.is_none() => b,
        _ => p.import(intern!(p, "satassume.engine"))?.getattr(intern!(p, "_UNCAPPED"))?,
    };
    let core = core_of(s)?;
    let c = core.borrow();
    let ses = Ses::Core(core.clone());
    let none = p.None().into_bound(p);
    let mut added: i64 = 0;
    while any_left(&ses)? && added.into_pyobject(p)?.lt(&budget)? {
        if ses.d_truthy(SD_PENDING_C)? {
            let (_, pend) = ses.d_popitem(SD_PENDING_C)?;
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
        if ses.d_truthy(SD_PENDING)? {
            let (n, items) = ses.d_popitem(SD_PENDING)?;
            if !planted(DROP_ESC_COMPILE) {
                crate::compile_loop::compile(s, &n, &items)?;
            }
            added += 1;
            continue;
        }
        if ses.q_truthy(SQ_FRONTIER)? {
            let n = ses.q_popleft(SQ_FRONTIER)?;
            if !in_base(&c, &n)? {
                node(s, &ses, &c, &n, &none)?;
                added += 1;
            }
            continue;
        }
        let n = ses.q_pop(SQ_DEFERRED)?;
        if !in_base(&c, &n)? {
            if planted(DROP_ESC_DEFERRED) {
                continue;
            }
            node(s, &ses, &c, &n, &none)?;
            added += 1;
        }
    }
    if any_left(&ses)? {
        let mut cut = ses.d_truthy(SD_PENDING)? || ses.d_truthy(SD_PENDING_C)?;
        if !cut {
            for n in ses.q_items(SQ_DEFERRED)? {
                if !in_base(&c, &n)? {
                    cut = true;
                    break;
                }
            }
        }
        if !cut {
            for n in ses.q_items(SQ_FRONTIER)? {
                if !in_base(&c, &n)? {
                    cut = true;
                    break;
                }
            }
        }
        if cut && !planted(TRUNCATED_NEVER) {
            crate::session::ses_set_flag(s, crate::session::SS_TRUNCATED, true)?;
        }
    }
    ses.frontier_reset(None)
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(ses_ensure, m)?)?;
    m.add_function(wrap_pyfunction!(ses_discover_raw, m)?)?;
    m.add_function(wrap_pyfunction!(ses_discover, m)?)?;
    m.add_function(wrap_pyfunction!(ses_incomplete, m)?)?;
    m.add_function(wrap_pyfunction!(ses_escalate, m)?)
}
