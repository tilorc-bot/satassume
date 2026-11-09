//! Step 6d: `knowledge/templates/_common.py`'s per-query rows on Rust.
//!
//! `facts` and `units` (the pattern cache, `MAX_CACHE`'s clear-all, `TemplateKeyError`'s shape check, `units`' closing
//! over the rule base), the `Compiled` a template hands the engine, `instantiate` (`Compiled.formulas`/`wide_formulas`),
//! `Rules` (`rule`, `equiv`), `lits`, `ge2_alternatives`, `consts_of`, `pattern_key` and `const_key`. `resolve` and
//! `Pattern.__init__` were already Rust (6c, `Knowledge.resolve`/`build_pattern`); here they are called from Rust.
//!
//! What stays Python, each call named and counted: the template's `gen()` (the templates' own code until 6g(b)/(c)),
//! `const_value` (a SymPy-semantics read of a numeric constant, `common:python:const_value`), and everything on a kept
//! query (`common:kept:<name>`: Python's own function runs, as `rust_resolve` did).
//!
//! Data stays in Python's types, so everything Python can read later is what Python would have built: the cache is
//! `_common._CACHE` itself (the epoch memo `state.memos` empties and `register` clears), its values are `Pattern`s and a
//! template's result is a `Compiled`, both made with `__new__` and their slots set, their `__init__` not run.
use super::knowledge::{self, BuiltPattern};
use super::py::{extract_rules, pattern, PyKnowledge};
use pyo3::exceptions::{PyKeyError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyFrozenSet, PyList, PyTuple, PyType};
use std::collections::HashMap;

pub const PLANTS: &[&str] = &[
    "common-facts-drop",       // facts: drops the last clause of each non-empty pattern facts builds
    "common-units-drop",       // units: drops the last clause of each non-empty pattern units builds
    "common-max-cache-off",    // MAX_CACHE: never clears
    "common-key-shape-off",    // TemplateKeyError: shape check skipped
    "common-compiled-swap",    // Compiled: the last two objects swapped
    "common-wide-drop",        // instantiate: the last formula dropped
    "common-rule-drop",        // Rules.rule: the last of two or more premises dropped
    "common-equiv-one",        // Rules.equiv: only the first direction
    "common-lits-flip",        // lits: the sign flipped
    "common-ge2-drop",         // ge2_alternatives: the third alternative dropped
    "common-consts-of-skip",   // consts_of: the last constant left out
    "common-pattern-key-type", // pattern_key: the constants' types left out
    "common-const-key-type",   // const_key: the type left out
];

fn bump(c: &mut HashMap<String, u64>, k: &str) {
    *c.entry(k.to_string()).or_insert(0) += 1;
}

#[pyclass(name = "Common")]
pub struct Common {
    pub(crate) kn: Py<PyKnowledge>,
    cache: Py<PyDict>,
    max_cache: usize,
    pub(crate) max_expand: u128,
    pattern_t: Py<PyType>,
    compiled_t: Py<PyType>,
    key_error_t: Py<PyAny>,
    fault_t: Py<PyAny>,
    contradiction: String,
    pub(crate) const_value: Py<PyAny>,
    /// `term_live._local`: its `stack`'s last `_Query` has `kept` set on a kept query. Read, never called.
    local: Py<PyAny>,
    /// Python's own functions, by name, for kept queries.
    py_fns: Py<PyDict>,
    /// `P`, `Not`, `Or`, `Implies`, `And`.
    pub(crate) ctors: [Py<PyAny>; 5],
    counts: std::sync::Mutex<HashMap<String, u64>>,
    pub(crate) plant: String,
}

impl Common {
    pub(crate) fn kept(&self, py: Python<'_>) -> PyResult<bool> {
        let s = match self.local.bind(py).getattr("stack") {
            Ok(s) => s,
            Err(e) if e.is_instance_of::<pyo3::exceptions::PyAttributeError>(py) => return Ok(false),
            Err(e) => return Err(e),
        };
        let n = s.len()?;
        if n == 0 {
            return Ok(false);
        }
        Ok(!s.get_item(n - 1)?.getattr("kept")?.is_none())
    }

    /// The innermost query's `_Query` (term_live), or None when there is none or it is kept: the core shells' `query()`.
    pub(crate) fn query<'py>(&self, py: Python<'py>) -> PyResult<Option<Bound<'py, PyAny>>> {
        let s = match self.local.bind(py).getattr("stack") {
            Ok(s) => s,
            Err(e) if e.is_instance_of::<pyo3::exceptions::PyAttributeError>(py) => return Ok(None),
            Err(e) => return Err(e),
        };
        let n = s.len()?;
        if n == 0 {
            return Ok(None);
        }
        let q = s.get_item(n - 1)?;
        Ok(if q.getattr("kept")?.is_none() { Some(q) } else { None })
    }

    pub(crate) fn fired(&self) {
        self.bump("plant:fired");
    }

    pub(crate) fn bump(&self, k: &str) {
        bump(&mut self.counts.lock().unwrap(), k);
    }

    fn fault(&self, py: Python<'_>, what: &str, e: PyErr) -> PyErr {
        self.bump("fault");
        match self.fault_t.bind(py).call1((format!("{what}: {e}"),)) {
            Ok(v) => PyErr::from_value(v),
            Err(e2) => e2,
        }
    }

    /// knowledge_core_live's `shadow_split`, present only under knowledge_live's shadow.
    pub(crate) fn shadow_split<'py>(&self, py: Python<'py>) -> PyResult<Option<Bound<'py, PyAny>>> {
        self.py_fns.bind(py).get_item("_shadow_split")
    }

    fn py_fn<'py>(&self, py: Python<'py>, name: &str) -> PyResult<Bound<'py, PyAny>> {
        self.py_fns.bind(py).get_item(name)?.ok_or_else(|| PyKeyError::new_err(name.to_string()))
    }

    fn compiled<'py>(&self, py: Python<'py>, objs: &Bound<'py, PyAny>, pat: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        let ct = self.compiled_t.bind(py);
        let c = ct.call_method1("__new__", (ct,))?;
        let mut objs = objs.clone();
        if self.plant == "common-compiled-swap" && objs.len()? >= 2 {
            self.fired();
            let l: Vec<Bound<'py, PyAny>> = objs.try_iter()?.collect::<PyResult<_>>()?;
            let mut l = l;
            let n = l.len();
            l.swap(n - 1, n - 2);
            objs = PyTuple::new(py, l)?.into_any();
        }
        c.setattr("objs", objs)?;
        c.setattr("pattern", pat)?;
        Ok(c)
    }

    fn new_pattern<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let pt = self.pattern_t.bind(py);
        pt.call_method1("__new__", (pt,))
    }

    /// The cache's entry for `key`, after `MAX_CACHE`'s clear-all if it is full.
    fn room(&self, py: Python<'_>) -> PyResult<()> {
        let c = self.cache.bind(py);
        if c.len() >= self.max_cache {
            if self.plant == "common-max-cache-off" {
                self.fired();
                return Ok(());
            }
            self.bump("common:cache-clear");
            c.clear();
        }
        Ok(())
    }

    fn drop_last(&self, pat: &Bound<'_, PyAny>) -> PyResult<()> {
        let cl = pat.getattr("clauses")?.cast_into::<PyList>()?;
        let n = cl.len();
        if n > 0 {
            self.fired();
            cl.del_item(n - 1)?;
        }
        Ok(())
    }
}

/// `Pattern.__init__`'s fields from Rust's `build_pattern`, as `knowledge_live.rust_pattern` set them.
fn built_fields<'py>(
    py: Python<'py>,
    p: &Bound<'py, PyAny>,
    rules: &Bound<'py, PyList>,
    node: i64,
    nobjs: usize,
    b: &BuiltPattern,
) -> PyResult<()> {
    let clauses = PyList::empty(py);
    for c in &b.clauses {
        let preds: Vec<usize> = c.iter().filter(|l| l.0 == node).map(|l| l.1).collect();
        let internal: Vec<(i64, usize)> = c.iter().map(|&(k, i, n)| (k, 2 * i + n as usize)).collect();
        clauses.append((PyTuple::new(py, c)?, PyFrozenSet::new(py, preds)?, PyTuple::new(py, internal)?))?;
    }
    let child_preds = PyDict::new(py);
    for (k, v) in &b.child_preds {
        child_preds.set_item(k, PyFrozenSet::new(py, v)?)?;
    }
    let wide = PyList::empty(py);
    for &i in &b.wide {
        wide.append(rules.get_item(i)?)?;      // `tuple(rules[i])` of a tuple is the tuple itself
    }
    p.setattr("rules", rules)?;
    p.setattr("node", node)?;
    p.setattr("nobjs", nobjs)?;
    p.setattr("complete", false)?;
    p.setattr("clauses", clauses)?;
    p.setattr("used", PyTuple::new(py, &b.used)?)?;
    p.setattr("child_preds", child_preds)?;
    p.setattr("wide", wide)?;
    Ok(())
}

#[pyclass(name = "Rules")]
pub struct RulesSpec {
    #[pyo3(get)]
    rules: Py<PyList>,
    plant: bool,
    equiv_plant: bool,
}

#[pymethods]
impl RulesSpec {
    /// `And(premises) -> conclusion` (a literal or a list = `Or`).
    fn rule(&self, py: Python<'_>, premises: &Bound<'_, PyAny>, conclusion: &Bound<'_, PyAny>) -> PyResult<()> {
        let ps = PyList::empty(py);
        for x in premises.try_iter()? {
            ps.append(x?)?;
        }
        if self.plant && ps.len() >= 2 {
            PLANT_FIRED.with(|c| c.set(c.get() + 1));
            ps.del_item(ps.len() - 1)?;
        }
        let cs = if conclusion.is_instance_of::<PyList>() { conclusion.clone() } else { PyList::new(py, [conclusion])?.into_any() };
        self.rules.bind(py).append((ps, cs))
    }

    /// `cond -> (a <-> b)` as two rules.
    fn equiv(&self, py: Python<'_>, cond: &Bound<'_, PyAny>, a: &Bound<'_, PyAny>, b: &Bound<'_, PyAny>) -> PyResult<()> {
        let c: Vec<Bound<'_, PyAny>> = cond.try_iter()?.collect::<PyResult<_>>()?;
        let mut p1 = c.clone();
        p1.push(a.clone());
        self.rule(py, PyList::new(py, p1)?.as_any(), b)?;
        if self.equiv_plant {
            PLANT_FIRED.with(|c| c.set(c.get() + 1));
            return Ok(());
        }
        let mut p2 = c;
        p2.push(b.clone());
        self.rule(py, PyList::new(py, p2)?.as_any(), a)
    }
}

thread_local! {
    /// Plants fired inside `Rules`, which holds no counts of its own; `Common.counts` adds them.
    static PLANT_FIRED: std::cell::Cell<u64> = const { std::cell::Cell::new(0) };
}

#[pymethods]
impl Common {
    #[new]
    #[allow(clippy::too_many_arguments)]
    fn new(
        kn: Py<PyKnowledge>,
        cache: Py<PyDict>,
        max_cache: usize,
        max_expand: u64,
        pattern_t: Py<PyType>,
        compiled_t: Py<PyType>,
        key_error_t: Py<PyAny>,
        fault_t: Py<PyAny>,
        contradiction: String,
        const_value: Py<PyAny>,
        local: Py<PyAny>,
        py_fns: Py<PyDict>,
        ctors: (Py<PyAny>, Py<PyAny>, Py<PyAny>, Py<PyAny>, Py<PyAny>),
    ) -> Self {
        Common {
            kn,
            cache,
            max_cache,
            max_expand: max_expand as u128,
            pattern_t,
            compiled_t,
            key_error_t,
            fault_t,
            contradiction,
            const_value,
            local,
            py_fns,
            ctors: [ctors.0, ctors.1, ctors.2, ctors.3, ctors.4],
            counts: std::sync::Mutex::new(HashMap::new()),
            plant: String::new(),
        }
    }

    fn set_plant(&mut self, p: &str) -> PyResult<()> {
        if !PLANTS.contains(&p) && !super::rows_tpl::PLANTS.contains(&p) && !super::outer_tpl::PLANTS.contains(&p) {
            return Err(PyValueError::new_err(format!("unknown plant {p}")));
        }
        self.plant = p.to_string();
        Ok(())
    }

    fn counts(&self) -> HashMap<String, u64> {
        let mut c = self.counts.lock().unwrap().clone();
        let f = PLANT_FIRED.with(|c| c.get());
        if f > 0 {
            *c.entry("plant:fired".to_string()).or_insert(0) += f;
        }
        c
    }

    fn clear_counts(&mut self) {
        self.counts.lock().unwrap().clear();
        PLANT_FIRED.with(|c| c.set(0));
    }

    /// `Compiled(objs, pattern)`, made as `facts`/`units` make theirs (`__new__`, slots set), for knowledge_live's
    /// `rust_compiled` (the symbol/constant/value templates' result).
    fn make_compiled<'py>(&self, py: Python<'py>, objs: &Bound<'py, PyAny>, pat: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        self.bump("common:compiled");
        self.compiled(py, objs, pat)
    }

    /// `_common.facts(key, gen, consts, objs, node)`.
    pub(crate) fn facts<'py>(
        &self,
        py: Python<'py>,
        key: &Bound<'py, PyAny>,
        gen: &Bound<'py, PyAny>,
        consts: &Bound<'py, PyAny>,
        objs: &Bound<'py, PyAny>,
        node: i64,
    ) -> PyResult<Bound<'py, PyAny>> {
        if self.kept(py)? {
            self.bump("common:kept:facts");
            return self.py_fn(py, "facts")?.call1((key, gen, consts, objs, node));
        }
        self.bump("common:facts");
        let nobjs = objs.len()?;
        let cache = self.cache.clone_ref(py).into_bound(py);
        let pat = match cache.get_item(key)? {
            Some(pat) => {
                let (pn, pk): (i64, usize) = (pat.getattr("node")?.extract()?, pat.getattr("nobjs")?.extract()?);
                if pn != node || pk != nobjs {
                    if self.plant == "common-key-shape-off" {
                        self.fired();
                    } else {
                        self.bump("common:key-error");
                        let msg = format!(
                            "template key {} is cached with node slot {pn} over {pk} objects, used with node slot {node} over {nobjs}",
                            key.repr()?
                        );
                        return Err(PyErr::from_value(self.key_error_t.bind(py).call1((msg,))?));
                    }
                }
                pat
            }
            None => {
                self.room(py)?;
                self.bump("common:python:gen");
                let raw = gen.call0()?;
                // `resolve(gen(), consts)`: the constants by slot, read by `const_value` (called back).
                let cd = consts.cast::<PyDict>()?;
                let mut slots: Vec<i64> = Vec::new();
                for (k, c) in cd.iter() {
                    if !c.is_none() {
                        slots.push(k.extract()?);
                    }
                }
                let rules = extract_rules(&raw).map_err(|e| self.fault(py, "resolve", e))?;
                let cv = self.const_value.clone_ref(py).into_bound(py);
                let mut reads = 0u64;
                let r = knowledge::resolve(
                    &rules,
                    |k| slots.contains(&k),
                    |k, pred| -> PyResult<Option<bool>> {
                        reads += 1;
                        let c = cd.get_item(k)?.ok_or_else(|| PyKeyError::new_err(k))?;
                        let v = cv.call1((c, pred))?;
                        v.extract().map_err(|e: PyErr| {
                            pyo3::exceptions::PyTypeError::new_err(format!("const_value of {pred}: {e}"))
                        })
                    },
                );
                *self.counts.lock().unwrap().entry("common:python:const_value".to_string()).or_insert(0) += reads;
                let resolved = match r {
                    Ok(Some(rs)) => rs,
                    Ok(None) => {
                        self.bump("common:contradiction");
                        return Err(PyValueError::new_err(self.contradiction.clone()));
                    }
                    Err(e) => return Err(e),       // the read's own, as on Python
                };
                let rl = PyList::empty(py);
                for (ps, cs) in &resolved {
                    rl.append((PyTuple::new(py, ps)?, PyTuple::new(py, cs)?))?;
                }
                let b = self.kn.get().0.build_pattern(&resolved, node, self.max_expand).map_err(PyKeyError::new_err)?;
                if !b.wide.is_empty() {
                    *self.counts.lock().unwrap().entry("common:wide".to_string()).or_insert(0) += b.wide.len() as u64;
                }
                let p = self.new_pattern(py)?;
                built_fields(py, &p, &rl, node, nobjs, &b)?;
                if self.plant == "common-facts-drop" {
                    self.drop_last(&p)?;
                }
                cache.set_item(key, &p)?;
                p
            }
        };
        self.compiled(py, objs, &pat)
    }

    /// `_common.units(key, gen, obj)`.
    pub(crate) fn units<'py>(
        &self,
        py: Python<'py>,
        key: &Bound<'py, PyAny>,
        gen: &Bound<'py, PyAny>,
        obj: &Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyAny>> {
        if self.kept(py)? {
            self.bump("common:kept:units");
            return self.py_fn(py, "units")?.call1((key, gen, obj));
        }
        self.bump("common:units");
        let cache = self.cache.clone_ref(py).into_bound(py);
        let pat = match cache.get_item(key)? {
            Some(p) => p,
            None => {
                self.room(py)?;
                self.bump("common:python:gen");
                let mut facts: Vec<(String, bool)> = Vec::new();
                for x in gen.call0()?.try_iter()? {
                    let x = x?;
                    facts.push((x.get_item(0)?.extract()?, x.get_item(1)?.is_truthy()?));
                }
                let f: Vec<(&str, bool)> = facts.iter().map(|(p, v)| (p.as_str(), *v)).collect();
                let k = &self.kn.get().0;
                let up = k.units(&f).map_err(PyKeyError::new_err)?;
                let r = pattern(py, k, &up)?;
                let (rules, clauses, used, complete): (Bound<'py, PyAny>, Bound<'py, PyAny>, bool, bool) = r.extract()?;
                let p = self.new_pattern(py)?;
                p.setattr("rules", rules)?;
                p.setattr("node", 0)?;
                p.setattr("nobjs", 1)?;
                p.setattr("clauses", clauses)?;
                p.setattr("used", if used { PyTuple::new(py, [0])? } else { PyTuple::empty(py) })?;
                p.setattr("child_preds", PyDict::new(py))?;
                p.setattr("complete", complete)?;
                p.setattr("wide", PyList::empty(py))?;
                if self.plant == "common-units-drop" {
                    self.drop_last(&p)?;
                }
                cache.set_item(key, &p)?;
                p
            }
        };
        let objs = PyTuple::new(py, [obj])?;
        self.compiled(py, objs.as_any(), &pat)
    }

    /// `instantiate(rules, objs)`: the formulas of `rules` over the concrete `objs`.
    pub(crate) fn instantiate<'py>(&self, py: Python<'py>, rules: &Bound<'py, PyAny>, objs: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyList>> {
        self.bump("common:instantiate");
        let [p, not, or, implies, and] = &self.ctors;
        let (p, not, or, implies, and) = (p.bind(py), not.bind(py), or.bind(py), implies.bind(py), and.bind(py));
        let mut atoms: HashMap<(i64, String), Bound<'py, PyAny>> = HashMap::new();
        let mut mk = |l: &Bound<'py, PyAny>| -> PyResult<Bound<'py, PyAny>> {
            let (k, pred, pos): (i64, String, Bound<'py, PyAny>) = l.extract()?;
            let a = match atoms.get(&(k, pred.clone())) {
                Some(a) => a.clone(),
                None => {
                    let a = p.call1((pred.as_str(), objs.get_item(k)?))?;
                    atoms.insert((k, pred), a.clone());
                    a
                }
            };
            if pos.is_truthy()? { Ok(a) } else { not.call1((a,)) }
        };
        let out = PyList::empty(py);
        for r in rules.try_iter()? {
            let r = r?;
            let (ps, cs) = (r.get_item(0)?, r.get_item(1)?);
            let cs: Vec<Bound<'py, PyAny>> = cs.try_iter()?.collect::<PyResult<_>>()?;
            let c = if cs.len() == 1 {
                mk(&cs[0])?
            } else {
                let xs: Vec<Bound<'py, PyAny>> = cs.iter().map(&mut mk).collect::<PyResult<_>>()?;
                or.call1(PyTuple::new(py, xs)?)?
            };
            let ps: Vec<Bound<'py, PyAny>> = ps.try_iter()?.collect::<PyResult<_>>()?;
            if ps.is_empty() {
                out.append(c)?;
            } else if ps.len() == 1 {
                out.append(implies.call1((mk(&ps[0])?, c))?)?;
            } else {
                let xs: Vec<Bound<'py, PyAny>> = ps.iter().map(&mut mk).collect::<PyResult<_>>()?;
                out.append(implies.call1((and.call1(PyTuple::new(py, xs)?)?, c))?)?;
            }
        }
        if self.plant == "common-wide-drop" && !out.is_empty() {
            self.fired();
            out.del_item(out.len() - 1)?;
        }
        Ok(out)
    }

    /// `Compiled.wide_formulas()` of a `Compiled`, for the registry's `_split`.
    pub(crate) fn wide_formulas<'py>(&self, py: Python<'py>, c: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyList>> {
        let (w, objs) = (c.getattr("pattern")?.getattr("wide")?, c.getattr("objs")?);
        self.instantiate(py, &w, &objs)
    }

    /// `Rules()`: Rust's, or Python's on a kept query.
    fn make_rules<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        if self.kept(py)? {
            self.bump("common:kept:Rules");
            return self.py_fn(py, "Rules")?.call0();
        }
        self.bump("common:Rules");
        let r = RulesSpec {
            rules: PyList::empty(py).unbind(),
            plant: self.plant == "common-rule-drop",
            equiv_plant: self.plant == "common-equiv-one",
        };
        Ok(Bound::new(py, r)?.into_any())
    }

    #[pyo3(signature = (ks, pred, pos=true))]
    fn lits<'py>(&self, py: Python<'py>, ks: &Bound<'py, PyAny>, pred: &Bound<'py, PyAny>, pos: bool) -> PyResult<Bound<'py, PyAny>> {
        if self.kept(py)? {
            self.bump("common:kept:lits");
            return self.py_fn(py, "lits")?.call1((ks, pred, pos));
        }
        self.bump("common:lits");
        let mut pos = pos;
        if self.plant == "common-lits-flip" {
            self.fired();
            pos = !pos;
        }
        let out = PyList::empty(py);
        for k in ks.try_iter()? {
            out.append((k?, pred, pos))?;
        }
        Ok(out.into_any())
    }

    fn ge2_alternatives<'py>(&self, py: Python<'py>, k: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        if self.kept(py)? {
            self.bump("common:kept:ge2_alternatives");
            return self.py_fn(py, "ge2_alternatives")?.call1((k,));
        }
        self.bump("common:ge2_alternatives");
        let a = PyList::new(py, [(k, "prime", true)])?;
        let b = PyList::new(py, [(k, "composite", true)])?;
        let c = PyList::new(py, [(k, "even", true), (k, "positive", true)])?;
        if self.plant == "common-ge2-drop" {
            self.fired();
            return Ok(PyTuple::new(py, [a, b])?.into_any());
        }
        Ok(PyTuple::new(py, [a, b, c])?.into_any())
    }

    /// The constants among `args` by position: `is_Atom and is_number`, both class attributes on atoms.
    pub(crate) fn consts_of<'py>(&self, py: Python<'py>, args: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        if self.kept(py)? {
            self.bump("common:kept:consts_of");
            return self.py_fn(py, "consts_of")?.call1((args,));
        }
        self.bump("common:consts_of");
        let d = PyDict::new(py);
        for (k, a) in args.try_iter()?.enumerate() {
            let a = a?;
            if a.getattr("is_Atom")?.is_truthy()? && a.getattr("is_number")?.is_truthy()? {
                d.set_item(k, a)?;
            }
        }
        if self.plant == "common-consts-of-skip" && !d.is_empty() {
            self.fired();
            let last = d.keys().get_item(d.len() - 1)?;
            d.del_item(last)?;
        }
        Ok(d.into_any())
    }

    pub(crate) fn pattern_key<'py>(&self, py: Python<'py>, tag: &Bound<'py, PyAny>, n: &Bound<'py, PyAny>, consts: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        if self.kept(py)? {
            self.bump("common:kept:pattern_key");
            return self.py_fn(py, "pattern_key")?.call1((tag, n, consts));
        }
        self.bump("common:pattern_key");
        let d = consts.cast::<PyDict>()?;
        let mut items: Vec<(i64, Bound<'py, PyAny>)> = Vec::with_capacity(d.len());
        for (k, c) in d.iter() {
            items.push((k.extract()?, c));
        }
        items.sort_by_key(|x| x.0);
        let notype = self.plant == "common-pattern-key-type";
        if notype && !items.is_empty() {
            self.fired();
        }
        let parts = PyList::empty(py);
        for (k, c) in items {
            if notype {
                parts.append((k, c))?;
            } else {
                parts.append((k, c.get_type(), c))?;
            }
        }
        Ok(PyTuple::new(py, [tag.clone(), n.clone(), PyTuple::new(py, parts)?.into_any()])?.into_any())
    }

    pub(crate) fn const_key<'py>(&self, py: Python<'py>, obj: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        if self.kept(py)? {
            self.bump("common:kept:const_key");
            return self.py_fn(py, "const_key")?.call1((obj,));
        }
        self.bump("common:const_key");
        if self.plant == "common-const-key-type" {
            self.fired();
            return Ok(PyTuple::new(py, [obj.clone()])?.into_any());
        }
        Ok(PyTuple::new(py, [obj.get_type().into_any(), obj.clone()])?.into_any())
    }
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Common>()?;
    m.add_class::<RulesSpec>()
}
