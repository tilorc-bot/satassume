//! Step 6g(a): the template registry's per-node path (`registry.py` `clauses_for`, `templates_for`, `_split`;
//! `templates/__init__.py` `_applied_to_nan`, `_may_be_nan`), called by the engine directly.
//!
//! What stays Python: `register` and `lazy` (the user's API and import-time registration), `_load` (imports the
//! declared modules, called back once per class and epoch, named and counted), and the templates themselves until
//! 6g(b)/(c) move them (each call named and counted). A class with a template not registered by a built-in module
//! goes whole to Python's `TemplateRegistry.clauses_for` (`registry:python:user`): Rust never answers for it.
//!
//! The memo and the class cache are keyed on Python objects, as Python's `_clauses_cache` and `_mro_cache` are, and
//! are emptied whenever `state.epoch.EPOCH[0]` moves (registering bumps it), so no entry outlives the templates in
//! force when it was made.
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyTuple, PyType};
use std::collections::{HashMap, HashSet};
use std::sync::Arc;

const CLAUSES_CACHE_SIZE: usize = 50_000;
const OWN_FACTS: &str = "_satassume_own_facts";

/// 6g(b): a built-in rows template (`wiring`'s `any_arity`, `product`, `addition`) runs on Rust.
enum Tpl {
    Python,
    Rows(Arc<super::rows_tpl::RowsTpl>),
    /// 6i(a): a hand-written outer template of special, rootof, nodes, physics or stats (outer_tpl.rs).
    Outer(super::outer_tpl::Outer),
    /// 6i(b): functions.py's slotted `_unary` and `nary` (fn_tpl.rs).
    Slotted(Arc<super::fn_tpl::Slotted>),
}

struct ClassEntry {
    /// `(template, counter name, Rust's)`, most specific class first, as `templates_for`.
    templates: Vec<(Py<PyAny>, String, Tpl)>,
    /// A template registered by someone other than a built-in module: the whole node goes to Python.
    user: bool,
}

#[pyclass(name = "Dispatch")]
pub struct Dispatch {
    registry: Py<PyAny>,
    py_clauses_for: Py<PyAny>,
    epoch: Py<PyList>,
    compiled_t: Py<PyType>,
    p_t: Py<PyType>,
    formula_t: Py<PyType>,
    application_t: Py<PyType>,
    basic_t: Py<PyType>,
    nan: Py<PyAny>,
    specials: Vec<Py<PyAny>>,
    vocab: HashSet<String>,
    builtin: Vec<String>,
    seen_epoch: i64,
    memo: Py<PyDict>,
    /// class -> index into `entries`, a dict so classes equal under `==` share an entry, as in `_mro_cache`
    /// (undefined functions compare by SymPy's rule, not identity).
    classes: Py<PyDict>,
    entries: Vec<Arc<ClassEntry>>,
    counts: HashMap<String, u64>,
    plant: String,
    /// 6d's `Common`, for `wide_formulas`; None: Python's method, called back.
    common: Option<Py<super::common::Common>>,
}

fn bump(c: &mut HashMap<String, u64>, k: &str) {
    *c.entry(k.to_string()).or_insert(0) += 1;
}

impl Dispatch {
    /// `_redefines(mro[:i], base)`: a class below overrides an `_eval_is_<fact>` handler `base` has.
    fn redefines(&self, below: &[Bound<'_, PyAny>], base: &Bound<'_, PyAny>) -> PyResult<bool> {
        for k in below {
            let d = k.getattr("__dict__")?;
            for n in d.try_iter()? {
                let n = n?;
                let s: String = match n.extract() {
                    Ok(s) => s,
                    Err(_) => continue,
                };
                if let Some(fact) = s.strip_prefix("_eval_is_") {
                    if self.vocab.contains(fact) && !base.getattr(s.as_str()).map(|v| v.is_none()).unwrap_or(true) {
                        return Ok(true);
                    }
                }
            }
        }
        Ok(false)
    }

    fn is_builtin(&self, t: &Bound<'_, PyAny>) -> bool {
        match t.getattr("__module__").and_then(|m| m.extract::<String>()) {
            Ok(m) => self.builtin.iter().any(|b| m == *b || m.starts_with(&format!("{b}."))),
            Err(_) => false,
        }
    }

    /// `_may_be_nan(a)`.
    fn may_be_nan(&self, a: &Bound<'_, PyAny>) -> PyResult<bool> {
        let py = a.py();
        if a.is(self.nan.bind(py)) {
            return Ok(true);
        }
        if !a.is_instance(self.basic_t.bind(py))? || a.getattr("is_Atom")?.is_truthy()? {
            return Ok(false);
        }
        for b in a.getattr("args")?.try_iter()? {
            let b = b?;
            if self.specials.iter().any(|c| b.is(c.bind(py))) || self.may_be_nan(&b)? {
                return Ok(true);
            }
        }
        Ok(false)
    }

    /// `_applied_to_nan(expr)`, the registry's `opaque`.
    fn opaque(&self, e: &Bound<'_, PyAny>) -> PyResult<bool> {
        if !e.is_instance(self.application_t.bind(e.py()))? {
            return Ok(false);
        }
        for a in e.getattr("args")?.try_iter()? {
            if self.may_be_nan(&a?)? {
                return Ok(true);
            }
        }
        Ok(false)
    }
}

/// `_split(result, compiled, formulas)`; `wide_formulas` is `_common`'s (6d), called back and counted.
fn split(
    slf: &Bound<'_, Dispatch>,
    r: &Bound<'_, PyAny>,
    compiled: &Bound<'_, PyList>,
    formulas: &Bound<'_, PyList>,
) -> PyResult<()> {
    let py = r.py();
    if r.is_none() || r.is(&pyo3::types::PyBool::new(py, true).to_owned()) {
        return Ok(());
    }
    let (ct, pt, ft) = {
        let d = slf.borrow();
        (d.compiled_t.clone_ref(py), d.p_t.clone_ref(py), d.formula_t.clone_ref(py))
    };
    if r.get_type().is(ct.bind(py)) {
        compiled.append(r)?;
        if r.getattr("pattern")?.getattr("wide")?.is_truthy()? {
            let common = slf.borrow().common.as_ref().map(|c| c.clone_ref(py));
            let fs: Bound<'_, PyAny> = match common {
                Some(c) => {
                    bump(&mut slf.borrow_mut().counts, "registry:rust:wide_formulas");
                    c.bind(py).borrow().wide_formulas(py, r)?.into_any()
                }
                None => {
                    bump(&mut slf.borrow_mut().counts, "registry:python:wide_formulas");
                    r.call_method0("wide_formulas")?
                }
            };
            for f in fs.try_iter()? {
                formulas.append(f?)?;
            }
        }
        return Ok(());
    }
    if r.is(&pyo3::types::PyBool::new(py, false).to_owned()) || r.is_instance(pt.bind(py))? || r.is_instance(ft.bind(py))? {
        formulas.append(r)?;
        return Ok(());
    }
    for x in r.try_iter()? {
        split(slf, &x?, compiled, formulas)?;
    }
    Ok(())
}

/// Empties the memo and the class cache when `state.epoch.EPOCH[0]` has moved since the last call.
fn sync_epoch(slf: &Bound<'_, Dispatch>) -> PyResult<()> {
    let py = slf.py();
    let mut d = slf.borrow_mut();
    let now: i64 = d.epoch.bind(py).get_item(0)?.extract()?;
    if now != d.seen_epoch {
        if d.plant == "dispatch-ignores-epoch" {
            if !d.entries.is_empty() || d.memo.bind(py).len() > 0 {
                bump(&mut d.counts, "plant:fired");
            }
        } else {
            d.memo.bind(py).clear();
            d.classes.bind(py).clear();
            d.entries.clear();
        }
        d.seen_epoch = now;
        bump(&mut d.counts, "registry:epoch-clear");
    }
    Ok(())
}

/// `templates_for(cls)`, with the user check; cached per class until the epoch moves.
fn class_entry(slf: &Bound<'_, Dispatch>, cls: &Bound<'_, PyType>) -> PyResult<Arc<ClassEntry>> {
    let py = cls.py();
    let classes = slf.borrow().classes.clone_ref(py);
    if let Some(i) = classes.bind(py).get_item(cls)? {
        let i: usize = i.extract()?;
        return Ok(slf.borrow().entries[i].clone());
    }
    let registry = slf.borrow().registry.clone_ref(py);
    let registry = registry.bind(py);
    if registry.getattr("_lazy")?.is_truthy()? {
        bump(&mut slf.borrow_mut().counts, "registry:python:_load");
        registry.call_method1("_load", (cls,))?;
    }
    let by_class = registry.getattr("_by_class")?;
    let by_class = by_class.cast::<PyDict>()?;
    let mro: Vec<Bound<'_, PyAny>> = cls.getattr("__mro__")?.try_iter()?.collect::<PyResult<_>>()?;
    let mut templates = Vec::new();
    let mut user = false;
    for (i, base) in mro.iter().enumerate() {
        let Some(ts) = by_class.get_item(base)? else { continue };
        let ts: Vec<Bound<'_, PyAny>> = ts.try_iter()?.collect::<PyResult<_>>()?;
        if ts.is_empty() {
            continue;
        }
        let mut only_own = i > 0 && slf.borrow().redefines(&mro[..i], base)?;
        if only_own && slf.borrow().plant == "dispatch-redefines-off" {
            bump(&mut slf.borrow_mut().counts, "plant:fired");
            only_own = false;
        }
        for t in ts {
            if only_own && !t.getattr(OWN_FACTS).map(|v| v.is_truthy().unwrap_or(false)).unwrap_or(false) {
                continue;
            }
            if !slf.borrow().is_builtin(&t) {
                if slf.borrow().plant == "dispatch-user-off" {
                    bump(&mut slf.borrow_mut().counts, "plant:fired");
                } else {
                    user = true;
                }
            }
            let name = t
                .getattr("__qualname__")
                .or_else(|_| t.getattr("__name__"))
                .and_then(|n| n.extract::<String>())
                .unwrap_or_else(|_| "?".into());
            let rows = if slf.borrow().is_builtin(&t) && slf.borrow().plant != "dispatch-rows-off" {
                super::rows_tpl::RowsTpl::from_template(&t, name.clone())?
            } else {
                None
            };
            let outer = if rows.is_none() && slf.borrow().is_builtin(&t) && slf.borrow().plant != "dispatch-outer-off" {
                super::outer_tpl::Outer::of(&t, &name)?
            } else {
                None
            };
            let slotted = if rows.is_none() && outer.is_none() && slf.borrow().is_builtin(&t)
                && slf.borrow().plant != "dispatch-slotted-off"
            {
                super::fn_tpl::Slotted::of(&t, &name)?
            } else {
                None
            };
            match (rows, outer, slotted) {
                (Some(r), _, _) => templates.push((t.unbind(), format!("registry:rust:{name}"), Tpl::Rows(Arc::new(r)))),
                (None, Some(o), _) => templates.push((t.unbind(), format!("registry:rust:{name}"), Tpl::Outer(o))),
                (None, None, Some(s)) => {
                    templates.push((t.unbind(), format!("registry:rust:{name}"), Tpl::Slotted(Arc::new(s))))
                }
                (None, None, None) => templates.push((t.unbind(), format!("registry:python:{name}"), Tpl::Python)),
            }
        }
    }
    let e = Arc::new(ClassEntry { templates, user });
    let mut d = slf.borrow_mut();
    let i = d.entries.len();
    d.entries.push(e.clone());
    classes.bind(py).set_item(cls, i)?;
    Ok(e)
}

#[pymethods]
impl Dispatch {
    /// `registry`: the `TemplateRegistry`; `py_clauses_for`: its Python `clauses_for` (the user path);
    /// `epoch`: `state.epoch.EPOCH`; `builtin`: module names whose templates count as built in.
    #[new]
    #[allow(clippy::too_many_arguments)]
    fn new(
        py: Python<'_>,
        registry: Py<PyAny>,
        py_clauses_for: Py<PyAny>,
        epoch: Py<PyList>,
        compiled_t: Py<PyType>,
        p_t: Py<PyType>,
        formula_t: Py<PyType>,
        application_t: Py<PyType>,
        basic_t: Py<PyType>,
        nan: Py<PyAny>,
        specials: Vec<Py<PyAny>>,
        vocab: HashSet<String>,
        builtin: Vec<String>,
    ) -> PyResult<Self> {
        let seen_epoch = epoch.bind(py).get_item(0)?.extract()?;
        Ok(Dispatch {
            registry, py_clauses_for, epoch, compiled_t, p_t, formula_t, application_t, basic_t, nan, specials, vocab,
            builtin, seen_epoch, memo: PyDict::new(py).unbind(), classes: PyDict::new(py).unbind(), entries: Vec::new(), counts: HashMap::new(),
            plant: String::new(),
            common: None,
        })
    }

    /// 6d: `Compiled.wide_formulas` on Rust's `Common`, or Python's (None).
    fn set_common(&mut self, c: Option<Py<super::common::Common>>) {
        self.common = c;
    }

    fn set_plant(&mut self, p: String) {
        self.plant = p;
    }

    fn counts(&self) -> HashMap<String, u64> {
        self.counts.clone()
    }

    fn clear_counts(&mut self) {
        self.counts.clear();
    }

    /// `registry.opaque(expr)`, for direct tests.
    fn is_opaque(&self, e: &Bound<'_, PyAny>) -> PyResult<bool> {
        self.opaque(e)
    }

    /// `(compiled, formulas)` for `expr`, as `TemplateRegistry.clauses_for`. The result must not be mutated.
    /// `registry.templates_for(cls)`: the same class walk `clauses_for` uses (MRO, `_redefines`, lazy `_load`), for
    /// conversion's class rows (convert.py), so no registry Python runs per query there.
    fn templates_for<'py>(slf: &Bound<'py, Self>, cls: &Bound<'py, PyType>) -> PyResult<Vec<Py<PyAny>>> {
        let py = cls.py();
        sync_epoch(slf)?;
        bump(&mut slf.borrow_mut().counts, "registry:templates_for");
        let e = class_entry(slf, cls)?;
        Ok(e.templates.iter().map(|(t, _, _)| t.clone_ref(py)).collect())
    }

    fn clauses_for<'py>(slf: &Bound<'py, Self>, expr: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        let py = expr.py();
        sync_epoch(slf)?;
        let memo = slf.borrow().memo.clone_ref(py);
        let memo = memo.bind(py);
        if let Some(r) = memo.get_item(expr)? {
            bump(&mut slf.borrow_mut().counts, "registry:memo");
            return Ok(r);
        }
        let cls = expr.get_type();
        let entry = class_entry(slf, &cls)?;
        if entry.user {
            bump(&mut slf.borrow_mut().counts, "registry:python:user");
            let f = slf.borrow().py_clauses_for.clone_ref(py);
            return f.bind(py).call1((expr,));
        }
        let compiled = PyList::empty(py);
        let formulas = PyList::empty(py);
        let mut opaque = slf.borrow().opaque(expr)?;
        if opaque && slf.borrow().plant == "dispatch-opaque-off" {
            bump(&mut slf.borrow_mut().counts, "plant:fired");
            opaque = false;
        }
        if opaque {
            bump(&mut slf.borrow_mut().counts, "registry:opaque");
        } else {
            let common = slf.borrow().common.as_ref().map(|c| c.clone_ref(py));
            for (t, name, tpl) in entry.templates.iter() {
                let r = match (tpl, &common) {
                    (Tpl::Rows(rt), Some(c)) if !c.bind(py).borrow().kept(py)? => {
                        bump(&mut slf.borrow_mut().counts, name);
                        rt.call(c.bind(py), expr)?
                    }
                    (Tpl::Rows(rt), _) => {
                        bump(&mut slf.borrow_mut().counts, &format!("registry:kept:{}", rt.name));
                        t.bind(py).call1((expr,))?
                    }
                    (Tpl::Outer(o), Some(c)) if !c.bind(py).borrow().kept(py)? => {
                        bump(&mut slf.borrow_mut().counts, name);
                        o.call(&c.bind(py).borrow(), t.bind(py), expr)?
                    }
                    (Tpl::Outer(o), _) => {
                        bump(&mut slf.borrow_mut().counts, &format!("registry:kept:{}", o.name()));
                        t.bind(py).call1((expr,))?
                    }
                    (Tpl::Slotted(sl), Some(c)) if !c.bind(py).borrow().kept(py)? => {
                        bump(&mut slf.borrow_mut().counts, name);
                        sl.call(&c.bind(py).borrow(), t.bind(py), expr)?
                    }
                    (Tpl::Slotted(sl), _) => {
                        bump(&mut slf.borrow_mut().counts, &format!("registry:kept:{}", sl.name()));
                        t.bind(py).call1((expr,))?
                    }
                    (Tpl::Python, _) => {
                        bump(&mut slf.borrow_mut().counts, name);
                        t.bind(py).call1((expr,))?
                    }
                };
                split(slf, &r, &compiled, &formulas)?;
            }
        }
        if memo.len() >= CLAUSES_CACHE_SIZE {
            memo.clear();
        }
        let r = PyTuple::new(py, [compiled.into_any(), formulas.into_any()])?.into_any();
        memo.set_item(expr, &r)?;
        bump(&mut slf.borrow_mut().counts, "registry:rust");
        Ok(r)
    }
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Dispatch>()
}
