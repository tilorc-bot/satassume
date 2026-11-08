//! Step 5c10b: context sessions and verdicts (inventory part 5, INVENTORY-state.md :288-290). Rows `Engine._context_session`,
//! `_build_context_memoized`, `_build_context`, `verdict` and `_complete_check` (`engine.py:1835-1983`) run here; their
//! containers `_failed`, `_verdict` and `_context_sessions` are Rust-native `EngineMemo`s (engmemo.rs slots 5-7).
//!
//! - **Semantics as Python's**, step for step: the epoch test and `_check_version`, the memo of `INCONSISTENT`, `_failed`'s
//!   bound 10,000 and `_verdict`'s 20,000 (emptied when full, tested here as Python's callers did), the complete check and its
//!   fallback to a plain session, `link_set`.
//! - **The quiet handler at engine.py:1906** (`except Exception` round `_complete_check`) is here: an `Uninterpreted` or a
//!   BaseException passes, any other exception makes `v` None. Each catch is counted (`ctx:caught`) and written to
//!   `handler_count`'s rows under Python's site name `Engine._build_context`.
//! - **Calls among the five are direct Rust calls**, unless the class attribute (or the instance's) isn't the one session_live
//!   installed: a test's or a tool's patch (`catch_count`, `mock.patch.object`) is then called by name, counted `ctx:cb_patched`.
//! - **Called back by name, counted, each with the step that removes it:** `_check_version` and `_fresh_session`
//!   (`ctx:cb_check_version`, `ctx:cb_fresh_session`; 5c10d), the module helpers `_gave_up`, `_exhausted`,
//!   `_noncommutative_atoms` (`ctx:cb_helpers`; 5c10d), `stats["set_checks"]` (`ctx:py_stats`; 5c10d). `theory_scope`,
//!   `_within_budget` and the Session and Solver methods are read by name as Python reads them; each is Rust under the default
//!   backend.
use pyo3::exceptions::{PyException, PyValueError};
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyTuple};

use crate::engmemo;
use crate::relations_core::{
    planted, CTX_BUILD_NO_FALLBACK, CTX_BUILD_NO_LINK, CTX_CHECK_NO_ESCALATE, CTX_CHECK_NO_TRUNCATED, CTX_CHECK_RAISE,
    CTX_FAILED_NO_MEMO, CTX_SESSION_INCONSISTENT_PASS, CTX_SESSIONS_STORE, CTX_VERDICT_NO_BOUND, CTX_VERDICT_SKIP_BUDGET,
};
use crate::session::{
    tick, CTX_BUILD_CONTEXT, CTX_BUILD_MEMOIZED, CTX_CAUGHT, CTX_CB_CHECK_VERSION, CTX_CB_FRESH_SESSION, CTX_CB_HELPERS,
    CTX_CB_PATCHED, CTX_COMPLETE_CHECK, CTX_CONTEXT_SESSION, CTX_FAILED_HIT, CTX_FALLBACK, CTX_PY_STATS, CTX_VERDICT,
    CTX_VERDICT_HIT,
};

fn engine_mod(p: Python<'_>) -> PyResult<Bound<'_, PyModule>> {
    p.import(intern!(p, "satassume.engine"))
}

fn konst<'py>(p: Python<'py>, name: &str) -> PyResult<Bound<'py, PyAny>> {
    engine_mod(p)?.getattr(name)
}

/// The engine's attribute `name` when it isn't the one session_live installed (a patch on the instance or the class).
fn patched<'py>(eng: &Bound<'py, PyAny>, name: &str) -> PyResult<Option<Bound<'py, PyAny>>> {
    let p = eng.py();
    if let Ok(d) = eng.getattr(intern!(p, "__dict__")) {
        if let Ok(d) = d.cast_into::<PyDict>() {
            if d.contains(name)? {
                tick(CTX_CB_PATCHED);
                return Ok(Some(eng.getattr(name)?));
            }
        }
    }
    let ours = p.import(intern!(p, "session_live"))?.getattr(intern!(p, "CTX_RUST"))?.get_item(name)?;
    let cls = eng.get_type().getattr(name)?;
    if cls.is(&ours) {
        return Ok(None);
    }
    tick(CTX_CB_PATCHED);
    Ok(Some(eng.getattr(name)?))
}

fn epoch_check(eng: &Bound<'_, PyAny>) -> PyResult<()> {
    let p = eng.py();
    let cur = engine_mod(p)?.getattr(intern!(p, "_EPOCH"))?.get_item(0)?;
    if eng.getattr(intern!(p, "_epoch"))?.ne(&cur)? {
        tick(CTX_CB_CHECK_VERSION);
        eng.call_method0(intern!(p, "_check_version"))?;
    }
    Ok(())
}

fn helper(p: Python<'_>, name: &str, s: &Bound<'_, PyAny>) -> PyResult<bool> {
    tick(CTX_CB_HELPERS);
    engine_mod(p)?.getattr(name)?.call1((s,))?.is_truthy()
}

fn inconsistent_err(p: Python<'_>) -> PyResult<PyErr> {
    Ok(PyErr::from_value(konst(p, "InconsistentAssumptions")?.call1(("inconsistent assumptions",))?))
}

type Built<'py> = (Bound<'py, PyAny>, Bound<'py, PyAny>);

fn split(r: Bound<'_, PyAny>) -> PyResult<Built<'_>> {
    let t = r.cast_into::<PyTuple>()?;
    Ok((t.get_item(0)?, t.get_item(1)?))
}

/// `Engine._context_session`.
#[pyfunction]
#[pyo3(signature = (eng, assumptions, proposition=None))]
fn ctx_context_session<'py>(eng: &Bound<'py, PyAny>, assumptions: &Bound<'py, PyAny>, proposition: Option<&Bound<'py, PyAny>>) -> PyResult<Bound<'py, PyTuple>> {
    tick(CTX_CONTEXT_SESSION);
    let p = eng.py();
    epoch_check(eng)?;
    let inc = konst(p, "INCONSISTENT")?;
    let verdicts = eng.getattr(intern!(p, "_verdict"))?;
    if let Some(v) = engmemo::get(&verdicts, assumptions)? {
        if v.is(&inc) {
            tick(CTX_VERDICT_HIT);
            return Err(inconsistent_err(p)?);
        }
    }
    let (s, lits) = memoized(eng, assumptions, proposition)?;
    if s.getattr(intern!(p, "verdict"))?.is(&inc) && !planted(CTX_SESSION_INCONSISTENT_PASS) {
        return Err(inconsistent_err(p)?);
    }
    if planted(CTX_SESSIONS_STORE) {
        engmemo::set(&eng.getattr(intern!(p, "_context_sessions"))?, assumptions, PyTuple::new(p, [&s, &lits])?.as_any())?;
    }
    PyTuple::new(p, [s, lits])
}

fn memoized<'py>(eng: &Bound<'py, PyAny>, assumptions: &Bound<'py, PyAny>, proposition: Option<&Bound<'py, PyAny>>) -> PyResult<Built<'py>> {
    if let Some(f) = patched(eng, "_build_context_memoized")? {
        return split(f.call1((assumptions, proposition))?);
    }
    build_memoized(eng, assumptions, proposition)
}

fn build_memoized<'py>(eng: &Bound<'py, PyAny>, assumptions: &Bound<'py, PyAny>, proposition: Option<&Bound<'py, PyAny>>) -> PyResult<Built<'py>> {
    tick(CTX_BUILD_MEMOIZED);
    let p = eng.py();
    let failed = eng.getattr(intern!(p, "_failed"))?;
    let unint = konst(p, "Uninterpreted")?;
    if let Some(msg) = engmemo::get(&failed, assumptions)? {
        tick(CTX_FAILED_HIT);
        return Err(PyErr::from_value(unint.call1((msg,))?));
    }
    let built = match patched(eng, "_build_context")? {
        Some(f) => f.call1((assumptions, proposition)).and_then(split),
        None => build_context(eng, assumptions, proposition),
    };
    let (s, lits) = match built {
        Ok(b) => b,
        Err(e) => {
            if e.is_instance(p, &unint.cast_into()?) && !planted(CTX_FAILED_NO_MEMO) {
                if engmemo::len(&failed)? >= 10_000 {
                    engmemo::clear(&failed)?;
                }
                engmemo::set(&failed, assumptions, e.value(p).str()?.as_any())?;
            }
            return Err(e);
        }
    };
    let verdicts = eng.getattr(intern!(p, "_verdict"))?;
    if !planted(CTX_VERDICT_NO_BOUND) && engmemo::len(&verdicts)? >= 20_000 {
        engmemo::clear(&verdicts)?;
    }
    engmemo::set(&verdicts, assumptions, &s.getattr(intern!(p, "verdict"))?)?;
    Ok((s, lits))
}

/// `Engine._build_context_memoized`.
#[pyfunction]
#[pyo3(signature = (eng, assumptions, proposition=None))]
fn ctx_build_context_memoized<'py>(eng: &Bound<'py, PyAny>, assumptions: &Bound<'py, PyAny>, proposition: Option<&Bound<'py, PyAny>>) -> PyResult<Bound<'py, PyTuple>> {
    let (s, l) = build_memoized(eng, assumptions, proposition)?;
    PyTuple::new(eng.py(), [s, l])
}

fn fresh<'py>(eng: &Bound<'py, PyAny>, scope: &Bound<'py, PyAny>, assumptions: &Bound<'py, PyAny>) -> PyResult<Built<'py>> {
    let p = eng.py();
    tick(CTX_CB_FRESH_SESSION);
    let s = eng.call_method1(intern!(p, "_fresh_session"), (scope,))?;
    let lits = s.call_method1(intern!(p, "assume_formula"), (assumptions,))?;
    Ok((s, lits))
}

fn build_context<'py>(eng: &Bound<'py, PyAny>, assumptions: &Bound<'py, PyAny>, proposition: Option<&Bound<'py, PyAny>>) -> PyResult<Built<'py>> {
    tick(CTX_BUILD_CONTEXT);
    let p = eng.py();
    tick(CTX_PY_STATS);
    let stats = eng.getattr(intern!(p, "stats"))?;
    let n = stats.get_item("set_checks")?;
    stats.set_item("set_checks", n.add(1)?)?;
    let em = engine_mod(p)?;
    let scope = em.getattr(intern!(p, "theory_scope"))?.call1((assumptions, proposition, eng.getattr(intern!(p, "_extensions"))?))?;
    let (mut s, mut lits) = fresh(eng, &scope, assumptions)?;
    let checked = (|| -> PyResult<Bound<'py, PyAny>> {
        let al = s.call_method0(intern!(p, "assumption_lits"))?;
        match patched(eng, "_complete_check")? {
            Some(f) => f.call1((&s, &al)),
            None => complete_check(&s, &al),
        }
    })();
    let unint = konst(p, "Uninterpreted")?;
    let v = match checked {
        Ok(v) => Some(v),
        Err(e) if e.is_instance(p, &unint.cast_into()?) => return Err(e),
        Err(e) if e.is_instance_of::<PyException>(p) => {
            // engine.py:1906: the check could not conclude; not evidence either way
            tick(CTX_CAUGHT);
            handler_row(p, "Engine._build_context", &e)?;
            None
        }
        Err(e) => return Err(e),
    };
    let inc = konst(p, "INCONSISTENT")?;
    if let Some(v) = &v {
        if v.is(&inc) {
            s.setattr(intern!(p, "verdict"), v)?;
            return Ok((s, lits));
        }
    }
    let v = match v {
        Some(v) if !helper(p, "_gave_up", &s)? || planted(CTX_BUILD_NO_FALLBACK) => v,
        _ => {
            tick(CTX_FALLBACK);
            (s, lits) = fresh(eng, &scope, assumptions)?;
            konst(p, "UNKNOWN")?
        }
    };
    s.setattr(intern!(p, "verdict"), v)?;
    if !planted(CTX_BUILD_NO_LINK) {
        s.call_method0(intern!(p, "link_set"))?;
    }
    Ok((s, lits))
}

/// `handler_count`'s row for this catch, under Python's site name; nothing if it isn't loaded.
fn handler_row(p: Python<'_>, site: &str, err: &PyErr) -> PyResult<()> {
    let mods = p.import(intern!(p, "sys"))?.getattr(intern!(p, "modules"))?;
    if let Some(h) = mods.call_method1(intern!(p, "get"), ("handler_count",))?.extract::<Option<Bound<'_, PyAny>>>()? {
        if h.hasattr("rust_handled")? {
            h.call_method1("rust_handled", (site, err.value(p)))?;
        }
    }
    Ok(())
}

/// `Engine._build_context`.
#[pyfunction]
#[pyo3(signature = (eng, assumptions, proposition=None))]
fn ctx_build_context<'py>(eng: &Bound<'py, PyAny>, assumptions: &Bound<'py, PyAny>, proposition: Option<&Bound<'py, PyAny>>) -> PyResult<Bound<'py, PyTuple>> {
    let (s, l) = build_context(eng, assumptions, proposition)?;
    PyTuple::new(eng.py(), [s, l])
}

/// `Engine.verdict`.
#[pyfunction]
fn ctx_verdict<'py>(eng: &Bound<'py, PyAny>, assumptions: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    tick(CTX_VERDICT);
    let p = eng.py();
    epoch_check(eng)?;
    tick(CTX_CB_HELPERS);
    if engine_mod(p)?.getattr(intern!(p, "_noncommutative_atoms"))?.call1((assumptions,))?.is_truthy()? {
        return konst(p, "UNKNOWN");
    }
    if !planted(CTX_VERDICT_SKIP_BUDGET) && !eng.call_method1(intern!(p, "_within_budget"), (assumptions,))?.is_truthy()? {
        return konst(p, "UNKNOWN");
    }
    if let Some(v) = engmemo::get(&eng.getattr(intern!(p, "_verdict"))?, assumptions)? {
        tick(CTX_VERDICT_HIT);
        return Ok(v);
    }
    memoized(eng, assumptions, None)?.0.getattr(intern!(p, "verdict"))
}

/// `Engine._complete_check` (a staticmethod).
#[pyfunction]
fn ctx_complete_check<'py>(s: &Bound<'py, PyAny>, lits: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    complete_check(s, lits)
}

fn complete_check<'py>(s: &Bound<'py, PyAny>, lits: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    tick(CTX_COMPLETE_CHECK);
    let p = s.py();
    if planted(CTX_CHECK_RAISE) {
        return Err(PyValueError::new_err("planted ctx-check-raise"));
    }
    let solver = s.getattr(intern!(p, "solver"))?;
    let sync = |s: &Bound<'py, PyAny>| -> PyResult<()> {
        let x = s.getattr(intern!(p, "xfer"))?;
        if !x.is_none() {
            x.call_method0(intern!(p, "sync_transfer"))?;
        }
        Ok(())
    };
    let conflict = || -> PyResult<bool> {
        Ok(!solver.call_method0(intern!(p, "propagate"))?.is_truthy()?
            || solver.call_method1(intern!(p, "implied"), (lits,))?.is_none())
    };
    sync(s)?;
    if conflict()? {
        return konst(p, "INCONSISTENT");
    }
    if s.getattr(intern!(p, "incomplete"))?.is_truthy()? && !planted(CTX_CHECK_NO_ESCALATE) {
        s.call_method0(intern!(p, "escalate"))?;
        sync(s)?;
        if conflict()? {
            return konst(p, "INCONSISTENT");
        }
    }
    if !solver.call_method1(intern!(p, "solve"), (lits,))?.is_truthy()? {
        return konst(p, "INCONSISTENT");
    }
    if !planted(CTX_CHECK_NO_TRUNCATED)
        && (helper(p, "_gave_up", s)?
            || helper(p, "_exhausted", s)?
            || s.getattr(intern!(p, "incomplete"))?.is_truthy()?
            || s.getattr(intern!(p, "truncated"))?.is_truthy()?)
    {
        return konst(p, "UNKNOWN");
    }
    konst(p, "CONSISTENT")
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(ctx_context_session, m)?)?;
    m.add_function(wrap_pyfunction!(ctx_build_context_memoized, m)?)?;
    m.add_function(wrap_pyfunction!(ctx_build_context, m)?)?;
    m.add_function(wrap_pyfunction!(ctx_verdict, m)?)?;
    m.add_function(wrap_pyfunction!(ctx_complete_check, m)?)
}
