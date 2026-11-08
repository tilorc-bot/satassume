//! Step 6g(b): `knowledge/templates/wiring.py`'s rows families on Rust, run from `Dispatch`'s class entry in place of
//! the Python template: `any_arity` (with `piecewise_values` for Piecewise), `product`, `addition`, and what they call
//! per node: `rows_block`, `rules_for`, `matches`, `expand`, `_placements`, `_allowed`, `_instances`, `_clauses`,
//! `_wide_of`, `wide_formulas`, `_wide`.
//!
//! The family's rows (`gen.terms`, `gen.specs`, `gen.schemas`, already Rust's `RowsGen`) are read once when the class
//! entry is built (per class and registry epoch). Per node, the template reads the node's SymPy arguments (class
//! attributes, `type`, `==`, `is`), builds the block with 6d's `Common` (`consts_of`, `pattern_key`, `facts`), and hands
//! `facts` a Rust `gen` that builds the rules only for a new pattern, as Python's lambda does.
//!
//! Still called back, each named and counted (`rows:python:<name>`): `constant_value` (`_rows_runtime`'s, through
//! `wiring.constant_value`, already swapped to Rust's with Python's for Floats), `const_value` (6d's named callback),
//! `Integer(len(rest))` for `count` (SymPy construction), and the core pieces `product`/`addition` call
//! (`_mul_factor_sets`, `_quotient_templates`, `_half_split`, `_half_templates`, `_bound_split`, `_bound_templates`,
//! `_recip_templates`, `_imag_split`, `_imag_templates`): 6e's shells over Rust, which 6g(c) removes. They are looked up
//! in `wiring`'s namespace per call, so whatever is bound there (Python's or the core swap's) is what runs, as on Python.
//! A kept query runs the Python template whole (`registry:kept:<name>`).
use super::common::Common;
use super::py::{refuse, PyTermTable};
use super::tcore::Rest;
use super::TermId;
use pyo3::IntoPyObjectExt;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyCFunction, PyDict, PyList, PyModule, PyTuple};
use std::collections::HashMap;
use std::sync::Arc;

/// `SOME_PER_ARGUMENT` in wiring.py.
pub const SOME_PER_ARGUMENT: usize = 32;

pub const PLANTS: &[&str] = &[
    "rows-block-key-n",        // rows_block: keyed with n rounded down to even, so nodes of 2k and 2k + 1 arguments share
                               // patterns (sa-port-144's n + 1 shifted every key alike, so no two could meet: void)
    "rows-rules-for-shape",    // rules_for: a rule's shape not checked
    "rows-of-constant-skip",   // rules_for: no terms of the constant
    "rows-matches-constant",   // matches: 'constant' always met
    "rows-expand-drop-last",   // expand: the last rule of each node dropped
    "rows-placements-first",   // _placements: only the first placement
    "rows-matches-coefficient",// matches: 'coefficient' met without a Number at 0 (was rows-allowed-coefficient, on
                               // `_allowed`'s 'coefficient' pick, which no compiled row has: void by construction)
    "rows-instances-others",   // _instances: `others` left out of the premises
    "rows-count-flip",         // _instances: `count` decided the other way
    "rows-clauses-concl-only", // _clauses: premises not counted (was rows-clauses-one, conclusions not counted: a
                               // conclusion has at most 2 clauses and no Max/Min/Piecewise rule of 1-32 arguments crosses
                               // MAX_EXPAND by that, so it could not change a decision: void by the rows' data)
    "rows-wide-drop",          // wide_formulas: the last formula dropped
    "rows-piecewise-last",     // piecewise_values: the final True not required
    "rows-mul-sets-first",     // product: only the first factor tuple
    "rows-add-bound-skip",     // addition: `c0 + c1*u` and `c0 + c1/v` left out
    "rows-pow-key-same",       // power: `b is e` left out of the key, so x**x and x**y share a pattern
    "rows-pow-times-skip",     // power: the terms `k*e` not built
    "rows-pow-head-any",       // matches: ('head', 'exp') always met
    "rows-pow-irrational-skip",// power: the irrational b**(p/q) rule left out
    "rows-pow-ipi-skip",       // power: `ipi_rules` not added
    "rows-pow-unit-drop",      // power: `_unit_power_units`' facts dropped
    "rows-half-parity",        // 6g(c) direct `_half_split`: each term's parity flipped
    "rows-bound-coeff-one",    // 6g(c) direct `_bound_split`: the coefficient c read as 1
    "rows-imag-drop-last",     // 6g(c) direct `_imag_split`: the last term dropped (fired 0 on core with len > 1)
    "rows-pow-of-constant-skip",// power: the terms of the constant not computed
    "rows-mul-ipi-drop",       // 6g(c2) direct `_mul_factor_sets`: the (c, I, pi, s) set dropped
    "rows-quot-swap",          // 6g(c2) direct `_quotient_templates`: slots a and v swapped
    "rows-exp-arg-none",       // 6g(c3) direct `_exp_arg`: None for exp(u) and E**u
    "rows-unit-angle-neg",     // 6g(c3) direct `_unit_angle`: the angle negated
    "rows-ipi-split-neg",      // 6g(c3) direct `ipi_split`: the coefficient c negated
    "rows-irrational-false",   // 6g(c3) direct `irrational_root`: False where it is True
    "rows-unit-power-drop-last",// 6g(c3) direct `_unit_power_units`: the last fact dropped
    "rows-pow-bound-drop-last",// 6g(c3) direct `_pow_bound_templates`: the last bound premise dropped (none left: no split)
    "rows-ipi-rules-drop-last",// 6g(c3) direct `ipi_rules`: the last rule dropped
];

/// 6g(c3): the shells whose args `split` passes as a tuple (the others take one argument).
const MULTI: &[&str] = &["irrational_root", "_unit_power_units"];
/// 6g(c2)/(c3): the splits of one term (the ids come from the term itself, as a 1-tuple).
const ONE: &[&str] = &["_mul_factor_sets", "_quotient_templates", "_exp_arg", "_unit_angle", "ipi_split", "_pow_bound_templates"];

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Family {
    AnyArity,
    Product,
    Addition,
    Power,
}

/// `power(gen)`'s rows, read once: the terms of `gen.terms[2]` by kind (slots from 3), `gen.specs[2]` with the
/// terms each rule names.
struct PowerRows {
    s_slot: usize,
    nobjs: usize,
    shifts: Vec<(usize, usize, Py<PyAny>)>,
    inner: Vec<(usize, usize)>,
    times: Vec<(usize, usize, Py<PyAny>)>,
    of_constant: Vec<(usize, usize, Py<PyAny>)>,
    rules: Vec<(Vec<Lit>, Vec<Lit>, Option<Vec<Option<ShapeItem>>>, Vec<usize>)>,
}

enum Pick {
    Any,
    Coefficient,
    Value(Py<PyAny>),
    Constant,
}

enum ShapeItem {
    Value(Py<PyAny>),
    Same(usize),
    Head,
    Coefficient,
    Constant,
}

type Lit = (i64, String, bool);

struct Spec {
    prem: Vec<Lit>,
    concl: Vec<Lit>,
    shape: Option<Vec<Option<ShapeItem>>>,
}

enum W {
    Slot(usize),
    Node,
    Every,
    Some,
    Others,
    Count,
}

type SLit = (W, String, bool);

struct Schema {
    at_most: Option<usize>,
    picks: Vec<Pick>,
    /// group of each pick, by first appearance (Python's dict of groups)
    groups: Vec<Vec<usize>>,
    rules: Vec<(Vec<SLit>, Vec<SLit>)>,
}

pub struct RowsTpl {
    pub family: Family,
    pub name: String,
    tag: Py<PyAny>,
    /// `gen.terms`: n -> `(i, t)` of each term of the constant, slots n + 1, ...
    terms: HashMap<usize, Vec<(usize, Py<PyAny>)>>,
    specs: HashMap<usize, Vec<Spec>>,
    schemas: Vec<Schema>,
    piecewise: bool,
    leave_out_wide: bool,
    power: Option<PowerRows>,
    /// the Python template, for kept queries
    pub py_template: Py<PyAny>,
    wiring: Py<PyModule>,
}

fn lit3(x: &Bound<'_, PyAny>) -> PyResult<Lit> {
    let (k, p, s): (i64, String, bool) = x.extract()?;
    Ok((k, p, s))
}

fn shape_of(s: &Bound<'_, PyAny>) -> PyResult<Vec<Option<ShapeItem>>> {
    let mut out = Vec::new();
    for x in s.try_iter()? {
        let x = x?;
        if x.is_none() {
            out.push(None);
            continue;
        }
        let kind: String = x.get_item(0)?.extract()?;
        out.push(Some(match kind.as_str() {
            "value" => ShapeItem::Value(x.get_item(1)?.unbind()),
            "same" => ShapeItem::Same(x.get_item(1)?.extract()?),
            "head" => {
                if x.get_item(1)?.extract::<String>()? != "exp" {
                    return Err(PyValueError::new_err("Pow: no template matches this head"));
                }
                ShapeItem::Head
            }
            "coefficient" => ShapeItem::Coefficient,
            "constant" => ShapeItem::Constant,
            k => return Err(PyValueError::new_err(format!("rows template: shape {k} not keyed for any arity"))),
        }));
    }
    Ok(out)
}

fn slit(x: &Bound<'_, PyAny>) -> PyResult<SLit> {
    let w = x.get_item(0)?;
    let p: String = x.get_item(1)?.extract()?;
    let s: bool = x.get_item(2)?.extract()?;
    let w = if let Ok(i) = w.extract::<usize>() {
        if w.is_instance_of::<pyo3::types::PyBool>() {
            return Err(PyValueError::new_err("rows template: a bool slot"));
        }
        W::Slot(i)
    } else {
        match w.extract::<String>()?.as_str() {
            "node" => W::Node,
            "every" => W::Every,
            "some" => W::Some,
            "others" => W::Others,
            "count" => W::Count,
            o => return Err(PyValueError::new_err(format!("rows template: schema word {o}"))),
        }
    };
    Ok((w, p, s))
}

impl RowsTpl {
    /// From the attributes `wiring` gives a rows template: `_satassume_rows = (family, tag, gen, piecewise,
    /// leave_out_wide)`.
    pub fn from_template(t: &Bound<'_, PyAny>, name: String) -> PyResult<Option<RowsTpl>> {
        let py = t.py();
        let Ok(spec) = t.getattr("_satassume_rows") else { return Ok(None) };
        let family = match spec.get_item(0)?.extract::<String>()?.as_str() {
            "any_arity" => Family::AnyArity,
            "product" => Family::Product,
            "addition" => Family::Addition,
            "power" => Family::Power,
            _ => return Ok(None),
        };
        let tag = spec.get_item(1)?.unbind();
        let gen = spec.get_item(2)?;
        let piecewise: bool = spec.get_item(3)?.extract()?;
        let leave_out_wide: bool = spec.get_item(4)?.extract()?;
        if family == Family::Power {
            let wiring = py.import("satassume.knowledge.templates.wiring")?.unbind();
            return Ok(Some(RowsTpl {
                family, name, tag, terms: HashMap::new(), specs: HashMap::new(), schemas: Vec::new(), piecewise,
                leave_out_wide, power: Some(power_rows(&gen)?), py_template: t.clone().unbind(), wiring,
            }));
        }
        let mut terms = HashMap::new();
        for (n, ts) in gen.getattr("terms")?.cast::<PyDict>()?.iter() {
            let mut v = Vec::new();
            for t in ts.try_iter()? {
                let t = t?;
                let kind: String = t.get_item(0)?.extract()?;
                if kind != "of_constant" {
                    return Ok(None); // wiring refuses these at registration
                }
                v.push((t.get_item(1)?.extract()?, t.get_item(2)?.unbind()));
            }
            terms.insert(n.extract()?, v);
        }
        let mut specs = HashMap::new();
        for (n, rs) in gen.getattr("specs")?.cast::<PyDict>()?.iter() {
            let mut v = Vec::new();
            for r in rs.try_iter()? {
                let r = r?;
                let prem = r.get_item(0)?.try_iter()?.map(|x| lit3(&x?)).collect::<PyResult<_>>()?;
                let concl = r.get_item(1)?.try_iter()?.map(|x| lit3(&x?)).collect::<PyResult<_>>()?;
                let shape = if r.len()? > 2 { Some(shape_of(&r.get_item(2)?)?) } else { None };
                v.push(Spec { prem, concl, shape });
            }
            specs.insert(n.extract()?, v);
        }
        let mut schemas = Vec::new();
        for s in gen.getattr("schemas")?.try_iter()? {
            let s = s?;
            let at_most: Option<usize> = s.get_item(0)?.extract()?;
            let mut picks = Vec::new();
            let mut gkeys: Vec<Bound<'_, PyAny>> = Vec::new();
            let mut groups: Vec<Vec<usize>> = Vec::new();
            for (i, p) in s.get_item(1)?.try_iter()?.enumerate() {
                let p = p?;
                let kind = p.get_item(0)?;
                picks.push(if kind.is_none() {
                    Pick::Any
                } else {
                    match kind.get_item(0)?.extract::<String>()?.as_str() {
                        "coefficient" => Pick::Coefficient,
                        "value" => Pick::Value(kind.get_item(1)?.unbind()),
                        _ => Pick::Constant,
                    }
                });
                let g = p.get_item(1)?;
                let mut at = None;
                for (j, k) in gkeys.iter().enumerate() {
                    if k.eq(&g)? {
                        at = Some(j);
                        break;
                    }
                }
                match at {
                    Some(j) => groups[j].push(i),
                    None => {
                        gkeys.push(g);
                        groups.push(vec![i]);
                    }
                }
            }
            let mut rules = Vec::new();
            for r in s.get_item(2)?.try_iter()? {
                let r = r?;
                let prem = r.get_item(0)?.try_iter()?.map(|x| slit(&x?)).collect::<PyResult<_>>()?;
                let concl = r.get_item(1)?.try_iter()?.map(|x| slit(&x?)).collect::<PyResult<_>>()?;
                rules.push((prem, concl));
            }
            schemas.push(Schema { at_most, picks, groups, rules });
        }
        let wiring = py.import("satassume.knowledge.templates.wiring")?.unbind();
        Ok(Some(RowsTpl {
            family, name, tag, terms, specs, schemas, piecewise, leave_out_wide, power: None, py_template: t.clone().unbind(),
            wiring,
        }))
    }

    /// 6g(c): `name`'s core split straight from the query's table (tcore.rs), as knowledge_core_live.py's shell computes it,
    /// with no Python between. Falls back to the shell (`wiring_fn`, counted `rows:python:NAME`) wherever the shell does
    /// something this doesn't: no query or a kept one, an arg that isn't an input term of its own class, or a result that
    /// is a derived term or a product rest (SymPy scaffolding, `core:kept_product`).
    fn split<'py>(&self, py: Python<'py>, c: &Common, name: &str, args: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        if let Some((r, shown)) = direct_split(py, c, name, args)? {
            c.bump(&format!("rows:rust:{name}"));
            // knowledge_live's shadow: Python's split for this result, compared by knowledge_core_live (the shell's `check`).
            // `_quotient_templates` shows its shape `(a, v, t)` or None, as the shell's shadow compares.
            if let Some(f) = c.shadow_split(py)? {
                f.call1((name, args, shown.as_ref().unwrap_or(&r)))?;
            }
            return Ok(r);
        }
        let f = self.wiring_fn(py, c, name)?;
        if MULTI.contains(&name) {
            f.call1(args.cast::<PyTuple>()?.clone())
        } else {
            f.call1((args,))
        }
    }

    fn wiring_fn<'py>(&self, py: Python<'py>, c: &Common, name: &str) -> PyResult<Bound<'py, PyAny>> {
        c.bump(&format!("rows:python:{name}"));
        self.wiring.bind(py).getattr(name)
    }

    /// The template: `(result for split)`.
    pub fn call<'py>(self: &Arc<Self>, c: &Bound<'py, Common>, expr: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        let py = expr.py();
        let cr = c.borrow();
        match self.family {
            Family::AnyArity => {
                let args = if self.piecewise {
                    match piecewise_values(&cr, expr)? {
                        Some(a) => a,
                        None => return Ok(py.None().into_bound(py)),
                    }
                } else {
                    expr.getattr("args")?
                };
                let block = self.block(c, &args, expr)?;
                let wide = self.wide_of(&cr, expr, &args)?;
                if wide.is_empty() {
                    return Ok(block);
                }
                let out = PyList::new(py, [block])?;
                for f in wide.iter() {
                    out.append(f)?;
                }
                Ok(out.into_any())
            }
            Family::Product => {
                let args = expr.getattr("args")?;
                if args.len()? == 0 {
                    return Ok(PyTuple::empty(py).into_any());
                }
                let out = PyList::empty(py);
                let sets = self.split(py, &cr, "_mul_factor_sets", expr)?;
                for (i, fs) in sets.try_iter()?.enumerate() {
                    if i > 0 && cr.plant == "rows-mul-sets-first" {
                        cr.fired();
                        break;
                    }
                    out.append(self.block(c, &fs?, expr)?)?;
                }
                let quot = self.split(py, &cr, "_quotient_templates", expr)?;
                if !quot.is_none() {
                    out.append(quot)?;
                }
                for f in self.wide_of(&cr, expr, &args)?.iter() {
                    out.append(f)?;
                }
                Ok(if out.len() == 1 { out.get_item(0)? } else { out.into_any() })
            }
            Family::Addition => {
                let args = expr.getattr("args")?;
                if args.len()? == 0 {
                    return Ok(PyTuple::empty(py).into_any());
                }
                let out = PyList::new(py, [self.block(c, &args, expr)?])?;
                for f in self.wide_of(&cr, expr, &args)?.iter() {
                    out.append(f)?;
                }
                let split = self.split(py, &cr, "_half_split", &args)?;
                if !split.is_none() {
                    out.append(self.wiring_fn(py, &cr, "_half_templates")?.call1((expr, split))?)?;
                }
                let split = self.split(py, &cr, "_bound_split", &args)?;
                if !split.is_none() {
                    if cr.plant == "rows-add-bound-skip" {
                        cr.fired();
                    } else {
                        out.append(self.wiring_fn(py, &cr, "_bound_templates")?.call1((expr, &split))?)?;
                        let recip = self.wiring_fn(py, &cr, "_recip_templates")?.call1((expr, &split))?;
                        if !recip.is_none() {
                            out.append(recip)?;
                        }
                    }
                }
                let terms = self.split(py, &cr, "_imag_split", &args)?;
                if !terms.is_none() {
                    let imag = self.wiring_fn(py, &cr, "_imag_templates")?.call1((expr, terms))?;
                    if !imag.is_none() {
                        out.append(imag)?;
                    }
                }
                Ok(if out.len() == 1 { out.get_item(0)? } else { out.into_any() })
            }
            Family::Power => {
                drop(cr);
                self.pow_call(c, expr)
            }
        }
    }

    /// `rows_block(tag, gen, leave_out_wide)(args, expr)`.
    fn block<'py>(self: &Arc<Self>, c: &Bound<'py, Common>, args: &Bound<'py, PyAny>, expr: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        let py = expr.py();
        let cr = c.borrow();
        cr.bump("rows:block");
        let args = PyTuple::new(py, args.try_iter()?.collect::<PyResult<Vec<_>>>()?)?;
        let n = args.len();
        let consts = cr.consts_of(py, args.as_any())?;
        let mut objs: Vec<Bound<'py, PyAny>> = args.iter().collect();
        objs.push(expr.clone());
        for _ in 0..self.terms.get(&n).map_or(0, |t| t.len()) {
            objs.push(py.None().into_bound(py));
        }
        let objs = PyTuple::new(py, objs)?;
        let mut kn = n;
        if cr.plant == "rows-block-key-n" && n % 2 == 1 {
            cr.fired();
            kn = n - 1;
        }
        let key = cr.pattern_key(py, self.tag.bind(py), &kn.into_pyobject(py)?.into_any(), &consts)?;
        let me = self.clone();
        let cobj = c.clone().unbind();
        let a = args.clone().unbind();
        let cd = consts.clone().unbind();
        let gen = PyCFunction::new_closure(py, None, None, move |t: &Bound<'_, PyTuple>, _kw: Option<&Bound<'_, PyDict>>| -> PyResult<Py<PyAny>> {
            let py = t.py();
            let c = cobj.bind(py).borrow();
            let r = me.rules_for(py, &c, a.bind(py), cd.bind(py).cast::<PyDict>()?)?;
            Ok(r.into_any().unbind())
        })?;
        cr.facts(py, &key, gen.as_any(), &consts, objs.as_any(), n as i64)
    }

    /// `rules_for(gen, args, consts, leave_out_wide)`: `consts` gets the terms of the constant.
    fn rules_for<'py>(&self, py: Python<'py>, c: &Common, args: &Bound<'py, PyTuple>, consts: &Bound<'py, PyDict>) -> PyResult<Bound<'py, PyList>> {
        c.bump("rows:rules_for");
        let n = args.len();
        if let Some(ts) = self.terms.get(&n) {
            if c.plant == "rows-of-constant-skip" && !ts.is_empty() {
                c.fired();
            } else {
                for (k, (i, t)) in ts.iter().enumerate() {
                    if let Some(cv) = consts.get_item(*i)? {
                        if cv.getattr("is_Number")?.is_truthy()? {
                            let v = self.wiring_fn(py, c, "constant_value")?.call1((t.bind(py), &cv))?;
                            consts.set_item(n + 1 + k, v)?;
                        }
                    }
                }
            }
        }
        let out = PyList::empty(py);
        for r in self.specs.get(&n).map(|v| v.as_slice()).unwrap_or(&[]) {
            if let Some(shape) = &r.shape {
                if !self.matches(py, c, shape, args, consts)? {
                    if c.plant == "rows-rules-for-shape" {
                        c.fired();
                    } else {
                        continue;
                    }
                }
            }
            let mut missing = false;
            for (k, _, _) in r.prem.iter().chain(r.concl.iter()) {
                if *k > n as i64 && !consts.contains(*k)? {
                    missing = true;
                    break;
                }
            }
            if missing {
                continue;
            }
            out.append((PyList::new(py, &r.prem)?, PyList::new(py, &r.concl)?))?;
        }
        for r in self.expand(py, c, n, consts)? {
            out.append((PyList::new(py, &r.0)?, PyList::new(py, &r.1)?))?;
        }
        Ok(out)
    }

    /// `expand(gen.schemas, n, consts, leave_out_wide)`.
    fn expand(&self, py: Python<'_>, c: &Common, n: usize, consts: &Bound<'_, PyDict>) -> PyResult<Vec<(Vec<Lit>, Vec<Lit>)>> {
        c.bump("rows:expand");
        let mut out = Vec::new();
        for s in &self.schemas {
            if n < s.picks.len() || s.at_most.is_some_and(|m| n > m) {
                continue;
            }
            for placed in placements(c, s, n, consts)? {
                let rest: Vec<usize> = (0..n).filter(|i| !placed.contains(i)).collect();
                for (prem, concl) in &s.rules {
                    if n > SOME_PER_ARGUMENT && prem.iter().any(|(w, _, _)| matches!(w, W::Some)) {
                        continue;
                    }
                    out.extend(instances(py, c, prem, concl, &placed, &rest, n)?);
                }
            }
        }
        if self.leave_out_wide {
            let mut kept = Vec::with_capacity(out.len());
            for r in out {
                if clauses(c, &r)? <= c.max_expand {
                    kept.push(r);
                }
            }
            out = kept;
        }
        if c.plant == "rows-expand-drop-last" && !out.is_empty() {
            c.fired();
            out.pop();
        }
        Ok(out)
    }

    /// `_wide_of(gen, expr, args)`, with `wide_formulas` and `_wide`.
    fn wide_of<'py>(&self, c: &Common, expr: &Bound<'py, PyAny>, args: &Bound<'py, PyAny>) -> PyResult<Vec<Bound<'py, PyAny>>> {
        let py = expr.py();
        let args: Vec<Bound<'py, PyAny>> = args.try_iter()?.collect::<PyResult<_>>()?;
        let n = args.len();
        if n <= SOME_PER_ARGUMENT {
            return Ok(vec![]);
        }
        c.bump("rows:wide_formulas");
        let consts = c.consts_of(py, PyTuple::new(py, &args)?.as_any())?;
        let consts = consts.cast::<PyDict>()?;
        let mut out = Vec::new();
        for s in &self.schemas {
            if s.at_most.is_some_and(|m| n > m) {
                continue;
            }
            for (prem, concl) in &s.rules {
                if prem.iter().any(|(w, _, _)| matches!(w, W::Some)) {
                    if let Some(f) = wide(py, c, expr, &args, consts, prem, concl)? {
                        out.push(f);
                    }
                }
            }
        }
        if c.plant == "rows-wide-drop" && !out.is_empty() {
            c.fired();
            out.pop();
        }
        Ok(out)
    }
}

/// `const_value(x, pred)`, 6d's named callback: True, False or None.
fn const_value(c: &Common, x: &Bound<'_, PyAny>, pred: &str) -> PyResult<Option<bool>> {
    c.bump("rows:python:const_value");
    c.const_value.bind(x.py()).call1((x, pred))?.extract()
}

fn integer<'py>(py: Python<'py>, c: &Common, n: usize) -> PyResult<Bound<'py, PyAny>> {
    c.bump("rows:python:Integer");
    py.import("sympy")?.getattr("Integer")?.call1((n,))
}

fn is_number_at(consts: &Bound<'_, PyDict>, k: usize) -> PyResult<bool> {
    match consts.get_item(k)? {
        Some(v) => v.getattr("is_Number")?.is_truthy(),
        None => Ok(false),
    }
}

fn same_value(a: &Bound<'_, PyAny>, v: &Bound<'_, PyAny>) -> PyResult<bool> {
    Ok(a.get_type().is(&v.get_type()) && a.eq(v)?)
}

impl RowsTpl {
/// `matches(shape, args, consts)`: 'head' (Pow's) through `_exp_arg`, called back.
fn matches(&self, py: Python<'_>, c: &Common, shape: &[Option<ShapeItem>], args: &Bound<'_, PyTuple>, consts: &Bound<'_, PyDict>) -> PyResult<bool> {
    c.bump("rows:matches");
    for (i, s) in shape.iter().enumerate() {
        let Some(s) = s else { continue };
        let a = args.get_item(i)?;
        let ok = match s {
            ShapeItem::Value(v) => same_value(&a, v.bind(py))?,
            ShapeItem::Same(j) => a.is(&args.get_item(*j)?),
            ShapeItem::Head => {
                let m = !self.split(py, c, "_exp_arg", &a)?.is_none();
                if !m && c.plant == "rows-pow-head-any" {
                    c.fired();
                    true
                } else {
                    m
                }
            }
            ShapeItem::Coefficient => {
                let m = i == 0 && is_number_at(consts, 0)?;
                if !m && c.plant == "rows-matches-coefficient" {
                    c.fired();
                    true
                } else {
                    m
                }
            }
            ShapeItem::Constant => {
                let m = consts.contains(i)?;
                if !m && c.plant == "rows-matches-constant" {
                    c.fired();
                    true
                } else {
                    m
                }
            }
        };
        if !ok {
            return Ok(false);
        }
    }
    Ok(true)
}
}
/// `power(gen)`'s reading of `gen.terms[2]` and `gen.specs[2]`.
fn power_rows(gen: &Bound<'_, PyAny>) -> PyResult<PowerRows> {
    let first = 3usize;
    let terms = gen.getattr("terms")?.get_item(2)?;
    let (mut shifts, mut inner, mut times, mut of_constant) = (Vec::new(), Vec::new(), Vec::new(), Vec::new());
    let mut k = first;
    for t in terms.try_iter()? {
        let t = t?;
        let kind = t.get_item(0)?;
        match kind.extract::<String>().ok().as_deref() {
            Some("inner") => inner.push((k, t.get_item(1)?.extract()?)),
            Some("times") => times.push((k, t.get_item(1)?.extract()?, t.get_item(2)?.unbind())),
            Some("of_constant") => of_constant.push((k, t.get_item(1)?.extract()?, t.get_item(2)?.unbind())),
            _ => shifts.push((k, kind.extract()?, t.get_item(1)?.unbind())),
        }
        k += 1;
    }
    let s_slot = k;
    let mut rules = Vec::new();
    for r in gen.getattr("specs")?.get_item(2)?.try_iter()? {
        let r = r?;
        let prem: Vec<Lit> = r.get_item(0)?.try_iter()?.map(|x| lit3(&x?)).collect::<PyResult<_>>()?;
        let concl: Vec<Lit> = r.get_item(1)?.try_iter()?.map(|x| lit3(&x?)).collect::<PyResult<_>>()?;
        let shape = if r.len()? > 2 && !r.get_item(2)?.is_none() { Some(shape_of(&r.get_item(2)?)?) } else { None };
        let mut terms_of: Vec<usize> =
            prem.iter().chain(concl.iter()).filter(|l| l.0 >= first as i64).map(|l| l.0 as usize).collect();
        terms_of.sort();
        terms_of.dedup();
        rules.push((prem, concl, shape, terms_of));
    }
    Ok(PowerRows { s_slot, nobjs: s_slot + 1, shifts, inner, times, of_constant, rules })
}

fn atom_number(x: &Bound<'_, PyAny>) -> PyResult<bool> {
    Ok(x.getattr("is_Atom")?.is_truthy()? && x.getattr("is_number")?.is_truthy()?)
}

/// `const_key(obj)`: `(type(obj), obj)`.
fn const_key<'py>(x: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    Ok(PyTuple::new(x.py(), [x.get_type().into_any(), x.clone()])?.into_any())
}

impl RowsTpl {
    /// `power(gen)`'s template: the node's constants, objects and key; the rules (rows whose terms exist and whose
    /// shape the node has, `ipi_rules`, `irrational_root`) built only for a new pattern; then `_unit_power_units` or
    /// `_pow_bound_templates`. The core pieces are called back by name; `Mul(k, e)` and `b + c` are SymPy
    /// construction (scaffolding, counted `rows:python:Mul`/`rows:python:Add`).
    fn pow_call<'py>(self: &Arc<Self>, c: &Bound<'py, Common>, expr: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        let py = expr.py();
        let cr = c.borrow();
        let pw = self.power.as_ref().expect("power rows");
        cr.bump("rows:power");
        let args = expr.getattr("args")?.cast_into::<PyTuple>()?;
        let (b, e) = (args.get_item(0)?, args.get_item(1)?);
        let consts = PyDict::new(py);
        if atom_number(&b)? {
            consts.set_item(0, &b)?;
        }
        if atom_number(&e)? {
            consts.set_item(1, &e)?;
        }
        let none = py.None().into_bound(py);
        let mut objs: Vec<Bound<'py, PyAny>> = vec![b.clone(), e.clone(), expr.clone()];
        objs.resize(pw.nobjs, none.clone());
        let mut u: Option<Bound<'py, PyAny>> = None;
        for (k, i) in &pw.inner {
            let r = self.split(py, &cr, "_exp_arg", &args.get_item(*i)?)?;
            u = if r.is_none() { None } else { Some(r) };
            if let Some(u) = &u {
                objs[*k] = u.clone();
                if atom_number(u)? {
                    consts.set_item(*k, u)?;
                }
            }
        }
        let mut ipi: Option<(Bound<'py, PyAny>, bool)> = None;
        let exp1 = py.import("sympy")?.getattr("S")?.getattr("Exp1")?;
        if b.is(&exp1) && !consts.contains(1)? {
            let split = self.split(py, &cr, "ipi_split", &e)?;
            if !split.is_none() {
                let (cc, s_) = (split.get_item(0)?, split.get_item(1)?);
                ipi = Some((cc, !s_.is_none()));
                if !s_.is_none() {
                    objs[pw.s_slot] = s_.clone();
                    if atom_number(&s_)? {
                        consts.set_item(pw.s_slot, &s_)?;
                    }
                }
            }
        }
        let has_t = !consts.contains(1)? && !e.getattr("is_number")?.is_truthy()?;
        for (k, i, cc) in &pw.times {
            let a = args.get_item(*i)?;
            if !a.getattr("is_number")?.is_truthy()? {
                if cr.plant == "rows-pow-times-skip" {
                    cr.fired();
                    continue;
                }
                cr.bump("rows:python:Mul");
                objs[*k] = py.import("sympy")?.getattr("Mul")?.call1((cc.bind(py), &a))?;
            }
        }
        let has_b1 = has_t && !consts.contains(0)? && !b.getattr("is_number")?.is_truthy()?;
        if has_b1 {
            for (k, i, cc) in &pw.shifts {
                cr.bump("rows:python:Add");
                objs[*k] = args.get_item(*i)?.add(cc.bind(py))?;
            }
        }
        let angle = self.split(py, &cr, "_unit_angle", &b)?;
        let mut same = b.is(&e);
        if same && cr.plant == "rows-pow-key-same" {
            cr.fired();
            same = false;
        }
        let ukey = match &u {
            None => false.into_pyobject(py)?.to_owned().into_any(),
            Some(u) if atom_number(u)? => const_key(u)?,
            Some(_) => true.into_pyobject(py)?.to_owned().into_any(),
        };
        let ipikey = match &ipi {
            None => none.clone(),
            Some((cc, s)) => PyTuple::new(py, [cc.clone(), s.into_pyobject(py)?.to_owned().into_any()])?.into_any(),
        };
        let key = PyTuple::new(py, [
            "pow".into_pyobject(py)?.into_any(),
            if consts.contains(0)? { const_key(&b)? } else { none.clone() },
            if consts.contains(1)? { const_key(&e)? } else { none.clone() },
            same.into_pyobject(py)?.to_owned().into_any(),
            angle.clone(),
            ukey,
            ipikey,
            if consts.contains(pw.s_slot)? { const_key(&objs[pw.s_slot])? } else { none.clone() },
            has_t.into_pyobject(py)?.to_owned().into_any(),
            has_b1.into_pyobject(py)?.to_owned().into_any(),
        ])?;
        let objs_t = PyTuple::new(py, &objs)?;
        let me = self.clone();
        let cobj = c.clone().unbind();
        let cd = consts.clone().unbind();
        let ot = objs_t.clone().unbind();
        let at = args.clone().unbind();
        let ipi_p = ipi.as_ref().map(|(cc, s)| (cc.clone().unbind(), *s));
        let gen = PyCFunction::new_closure(py, None, None, move |t: &Bound<'_, PyTuple>, _kw: Option<&Bound<'_, PyDict>>| -> PyResult<Py<PyAny>> {
            let py = t.py();
            let c = cobj.bind(py).borrow();
            let r = me.pow_build(py, &c, at.bind(py), ot.bind(py), cd.bind(py), ipi_p.as_ref())?;
            Ok(r.into_any().unbind())
        })?;
        let out = cr.facts(py, &key.into_any(), gen.as_any(), consts.as_any(), objs_t.as_any(), 2)?;
        if !angle.is_none() && e.getattr("is_number")?.is_truthy()? {
            let a3 = PyTuple::new(py, [angle.clone(), e.clone(), expr.clone()])?.into_any();
            let units = self.split(py, &cr, "_unit_power_units", &a3)?;
            let l = PyList::new(py, [out])?;
            if cr.plant == "rows-pow-unit-drop" {
                cr.fired();
            } else {
                for x in units.try_iter()? {
                    l.append(x?)?;
                }
            }
            return Ok(l.into_any());
        }
        let bound = self.split(py, &cr, "_pow_bound_templates", expr)?;
        if !bound.is_none() {
            return Ok(PyList::new(py, [out, bound])?.into_any());
        }
        Ok(out)
    }

    /// `power`'s `build()`: run by `facts` only for a new pattern, adding the terms of the constants to `consts`.
    fn pow_build<'py>(&self, py: Python<'py>, c: &Common, args: &Bound<'py, PyTuple>, objs: &Bound<'py, PyTuple>,
                      consts: &Bound<'py, PyDict>, ipi: Option<&(Py<PyAny>, bool)>) -> PyResult<Bound<'py, PyList>> {
        let pw = self.power.as_ref().expect("power rows");
        c.bump("rows:pow_build");
        for (k, i, t) in &pw.of_constant {
            if let Some(cv) = consts.get_item(*i)? {
                if cv.getattr("is_Number")?.is_truthy()? {
                    if c.plant == "rows-pow-of-constant-skip" {
                        c.fired();
                        continue;
                    }
                    let v = self.wiring_fn(py, c, "constant_value")?.call1((t.bind(py), &cv))?;
                    consts.set_item(*k, v)?;
                }
            }
        }
        let mut exist = Vec::new();
        for k in 3..pw.nobjs {
            if !objs.get_item(k)?.is_none() || consts.contains(k)? {
                exist.push(k);
            }
        }
        let out = PyList::empty(py);
        for (prem, concl, shape, terms_of) in &pw.rules {
            if !terms_of.iter().all(|k| exist.contains(k)) {
                continue;
            }
            if let Some(shape) = shape {
                if !self.matches(py, c, shape, args, consts)? {
                    continue;
                }
            }
            out.append((PyList::new(py, prem)?, PyList::new(py, concl)?))?;
        }
        if let Some((cc, has_s)) = ipi {
            if c.plant == "rows-pow-ipi-skip" {
                c.fired();
            } else {
                let o = out.clone().unbind();
                let rule = PyCFunction::new_closure(py, None, None, move |t: &Bound<'_, PyTuple>, _kw: Option<&Bound<'_, PyDict>>| -> PyResult<Py<PyAny>> {
                    let py = t.py();
                    let prem = PyList::new(py, t.get_item(0)?.try_iter()?.collect::<PyResult<Vec<_>>>()?)?;
                    let concl = t.get_item(1)?;
                    let concl = if concl.is_instance_of::<PyList>() { concl } else { PyList::new(py, [concl])?.into_any() };
                    o.bind(py).append((prem, concl))?;
                    Ok(py.None())
                })?;
                let s = if *has_s { pw.s_slot.into_pyobject(py)?.into_any() } else { py.None().into_bound(py) };
                if c.kept(py)? {
                    self.wiring_fn(py, c, "ipi_rules")?.call1((rule, cc.bind(py), s, 2))?;
                } else {
                    // 6g(c3): IPI_TABLE's rows straight from tcore.rs (knowledge_core_live's `ipi_rules` without the shell).
                    c.bump("rows:rust:ipi_rules");
                    let mut r = super::tcore::ipi_rules(&rat_of(cc.bind(py))?, has_s.then_some(pw.s_slot), 2);
                    if r.len() > 1 && c.plant == "rows-ipi-rules-drop-last" {
                        c.fired();
                        r.pop();
                    }
                    let r = r.into_pyobject(py)?;
                    if let Some(f) = c.shadow_split(py)? {
                        f.call1(("ipi_rules", (cc.bind(py), &s, 2), &r))?;
                    }
                    for x in r.try_iter()? {
                        let x = x?;
                        rule.call1((x.get_item(0)?, x.get_item(1)?))?;
                    }
                }
            }
        }
        let none = py.None().into_bound(py);
        let c0 = consts.get_item(0)?.unwrap_or(none.clone());
        let c1 = consts.get_item(1)?.unwrap_or(none);
        let a2 = PyTuple::new(py, [c0, c1])?.into_any();
        if self.split(py, c, "irrational_root", &a2)?.is_truthy()? {
            if c.plant == "rows-pow-irrational-skip" {
                c.fired();
            } else {
                out.append((PyList::empty(py), PyList::new(py, [(2i64, "irrational", true)])?))?;
            }
        }
        Ok(out)
    }
}


/// `_allowed(kind, n, consts)`.
fn allowed(c: &Common, kind: &Pick, n: usize, consts: &Bound<'_, PyDict>) -> PyResult<Vec<usize>> {
    let py = consts.py();
    Ok(match kind {
        Pick::Any => (0..n).collect(),
        Pick::Coefficient => {
            let num = is_number_at(consts, 0)?;
            if 0 < n && num {
                vec![0]
            } else {
                vec![]
            }
        }
        _ => {
            let mut at: Vec<usize> = Vec::new();
            for k in consts.keys() {
                let k: usize = k.extract()?;
                if k < n {
                    at.push(k);
                }
            }
            at.sort_unstable();
            if let Pick::Value(v) = kind {
                let mut r = Vec::new();
                for k in at {
                    if same_value(&consts.get_item(k)?.unwrap(), v.bind(py))? {
                        r.push(k);
                    }
                }
                r
            } else {
                at
            }
        }
    })
}

/// k-combinations of `xs` in lexicographic order, as `itertools.combinations`.
fn combinations(xs: &[usize], k: usize) -> Vec<Vec<usize>> {
    fn go(xs: &[usize], k: usize, from: usize, cur: &mut Vec<usize>, out: &mut Vec<Vec<usize>>) {
        if cur.len() == k {
            out.push(cur.clone());
            return;
        }
        for i in from..xs.len() {
            cur.push(xs[i]);
            go(xs, k, i + 1, cur, out);
            cur.pop();
        }
    }
    let mut out = Vec::new();
    go(xs, k, 0, &mut Vec::new(), &mut out);
    out
}

/// `_placements(picks, n, consts)`: each placement, in Python's generator order.
fn placements(c: &Common, s: &Schema, n: usize, consts: &Bound<'_, PyDict>) -> PyResult<Vec<Vec<usize>>> {
    c.bump("rows:placements");
    let allowed: Vec<Vec<usize>> = s.picks.iter().map(|k| allowed(c, k, n, consts)).collect::<PyResult<_>>()?;
    let mut out = Vec::new();
    let mut placed = vec![usize::MAX; s.picks.len()];
    fn place(gi: usize, used: &mut Vec<usize>, s: &Schema, allowed: &[Vec<usize>], placed: &mut Vec<usize>, out: &mut Vec<Vec<usize>>) {
        if gi == s.groups.len() {
            out.push(placed.clone());
            return;
        }
        let members = &s.groups[gi];
        let free: Vec<usize> = allowed[members[0]].iter().copied().filter(|p| !used.contains(p)).collect();
        for at in combinations(&free, members.len()) {
            for (i, p) in members.iter().zip(at.iter()) {
                placed[*i] = *p;
            }
            let before = used.len();
            used.extend(at.iter().copied());
            place(gi + 1, used, s, allowed, placed, out);
            used.truncate(before);
        }
    }
    place(0, &mut Vec::new(), s, &allowed, &mut placed, &mut out);
    if c.plant == "rows-placements-first" && out.len() > 1 {
        c.fired();
        out.truncate(1);
    }
    Ok(out)
}

/// `_instances(prem, concl, placed, rest, n)`.
fn instances(
    py: Python<'_>,
    c: &Common,
    prem: &[SLit],
    concl: &[SLit],
    placed: &[usize],
    rest: &[usize],
    n: usize,
) -> PyResult<Vec<(Vec<Lit>, Vec<Lit>)>> {
    c.bump("rows:instances");
    let lits = |w: &W, p: &str, s: bool| -> Vec<Lit> {
        match w {
            W::Node => vec![(n as i64, p.to_string(), s)],
            W::Slot(i) => vec![(placed[*i] as i64, p.to_string(), s)],
            _ => rest.iter().map(|&j| (j as i64, p.to_string(), s)).collect(),
        }
    };
    let mut ps: Vec<Lit> = Vec::new();
    let mut others: Vec<(&str, bool)> = Vec::new();
    let mut some_: Option<(&str, bool)> = None;
    for (w, p, s) in prem {
        match w {
            W::Count => {
                let mut differs = const_value(c, &integer(py, c, rest.len())?, p)? != Some(*s);
                if c.plant == "rows-count-flip" {
                    c.fired();
                    differs = !differs;
                }
                if differs {
                    return Ok(vec![]);
                }
            }
            W::Some => some_ = Some((p, *s)),
            W::Others => {
                if c.plant == "rows-instances-others" {
                    c.fired();
                } else {
                    others.push((p, *s));
                }
            }
            _ => ps.extend(lits(w, p, *s)),
        }
    }
    let cs: Vec<Lit> = concl.iter().flat_map(|(w, p, s)| lits(w, p, *s)).collect();
    let Some((sp, ss)) = some_ else { return Ok(vec![(ps, cs)]) };
    Ok(rest
        .iter()
        .map(|&k| {
            let mut r = ps.clone();
            for &j in rest {
                if j != k {
                    for (p, s) in &others {
                        r.push((j as i64, p.to_string(), *s));
                    }
                }
            }
            r.push((k as i64, sp.to_string(), ss));
            (r, cs.clone())
        })
        .collect())
}

/// `_clauses(rule)`: the number of clauses of the rule over the basis.
fn clauses(c: &Common, r: &(Vec<Lit>, Vec<Lit>)) -> PyResult<u128> {
    c.bump("rows:clauses");
    let kn = &c.kn.get().0;
    let mut k: u128 = 1;
    for (_, p, s) in &r.0 {
        k = k.saturating_mul(kn.cnf(p, !*s).map_err(pyo3::exceptions::PyKeyError::new_err)?.len() as u128);
    }
    if c.plant == "rows-clauses-concl-only" && !r.0.is_empty() {
        c.fired();
        k = 1;
    }
    for (_, p, s) in &r.1 {
        k = k.saturating_mul(kn.cnf(p, *s).map_err(pyo3::exceptions::PyKeyError::new_err)?.len() as u128);
    }
    Ok(k)
}

fn atom<'py>(c: &Common, py: Python<'py>, pred: &str, sign: bool, obj: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    let a = c.ctors[0].bind(py).call1((pred, obj))?;
    if sign { Ok(a) } else { c.ctors[1].bind(py).call1((a,)) }
}

/// `_wide(expr, args, consts, prem, concl)`.
fn wide<'py>(
    py: Python<'py>,
    c: &Common,
    expr: &Bound<'py, PyAny>,
    args: &[Bound<'py, PyAny>],
    consts: &Bound<'py, PyDict>,
    prem: &[SLit],
    concl: &[SLit],
) -> PyResult<Option<Bound<'py, PyAny>>> {
    let every: Vec<(&str, bool)> =
        prem.iter().filter(|(w, _, _)| matches!(w, W::Every | W::Others)).map(|(_, p, s)| (p.as_str(), *s)).collect();
    let somes: Vec<(&str, bool)> = prem.iter().filter(|(w, _, _)| matches!(w, W::Some)).map(|(_, p, s)| (p.as_str(), *s)).collect();
    if somes.len() != 1 {
        return Err(PyValueError::new_err("_wide: not one `some`"));
    }
    let (sp, ss) = somes[0];
    c.bump("rows:wide");
    for (w, p, s) in prem {
        if matches!(w, W::Count) && const_value(c, &integer(py, c, args.len())?, p)? != Some(*s) {
            return Ok(None);
        }
    }
    let (mut weak, mut strong, mut met) = (Vec::new(), Vec::new(), false);
    for (k, a) in args.iter().enumerate() {
        match consts.get_item(k)? {
            None => {
                for (p, s) in &every {
                    weak.push(atom(c, py, p, *s, a)?);
                }
                strong.push(atom(c, py, sp, ss, a)?);
            }
            Some(cv) => {
                let mut drop = false;
                for (p, s) in &every {
                    if const_value(c, &cv, p)? != Some(*s) {
                        drop = true;
                        break;
                    }
                }
                if drop {
                    return Ok(None);
                }
                if const_value(c, &cv, sp)? == Some(ss) {
                    met = true;
                }
            }
        }
    }
    if !(met || !strong.is_empty()) {
        return Ok(None);
    }
    let mut ps: Vec<Bound<'py, PyAny>> = Vec::new();
    for (w, p, s) in prem {
        if matches!(w, W::Node) {
            ps.push(atom(c, py, p, *s, expr)?);
        }
    }
    ps.extend(weak);
    if !met {
        ps.push(c.ctors[2].bind(py).call1(PyTuple::new(py, &strong)?)?);
    }
    let cs: Vec<Bound<'py, PyAny>> = concl.iter().map(|(_, p, s)| atom(c, py, p, *s, expr)).collect::<PyResult<_>>()?;
    let cc = if cs.len() == 1 { cs[0].clone() } else { c.ctors[2].bind(py).call1(PyTuple::new(py, &cs)?)? };
    if ps.is_empty() {
        return Ok(Some(cc));
    }
    let and = c.ctors[4].bind(py).call1(PyTuple::new(py, &ps)?)?;
    Ok(Some(c.ctors[3].bind(py).call1((and, cc))?))
}

/// `piecewise_values(expr)`.
fn piecewise_values<'py>(c: &Common, expr: &Bound<'py, PyAny>) -> PyResult<Option<Bound<'py, PyAny>>> {
    let py = expr.py();
    c.bump("rows:piecewise_values");
    let args: Vec<Bound<'py, PyAny>> = expr.getattr("args")?.try_iter()?.collect::<PyResult<_>>()?;
    let sympy = py.import("sympy")?;
    let t = sympy.getattr("S")?.getattr("true")?;
    match args.last() {
        None => return Ok(None),
        Some(last) => {
            if !last.getattr("cond")?.is(&t) {
                if c.plant == "rows-piecewise-last" {
                    c.fired();
                } else {
                    return Ok(None);
                }
            }
        }
    }
    let expr_t = sympy.getattr("Expr")?;
    let mut values = Vec::with_capacity(args.len());
    for a in &args {
        let v = a.getattr("expr")?;
        if !v.is_instance(&expr_t)? {
            return Ok(None);
        }
        values.push(v);
    }
    Ok(Some(PyTuple::new(py, values)?.into_any()))
}

/// The query's ids for rows_tpl.rs's direct core calls: knowledge_core_live.py's `ids_of` and `obj` for input terms.
struct QIds<'py> {
    table: Bound<'py, PyTermTable>,
    ids: Bound<'py, PyAny>,
    objects: Bound<'py, PyAny>,
    n_input: usize,
}

impl<'py> QIds<'py> {
    fn of(py: Python<'py>, c: &Common) -> PyResult<Option<Self>> {
        let Some(q) = c.query(py)? else { return Ok(None) };
        let table = q.getattr("table")?.cast_into::<PyTermTable>()?;
        let n_input = table.borrow().tt().n_input;
        Ok(Some(QIds { table, ids: q.getattr("ids")?, objects: q.getattr("objects")?, n_input }))
    }

    /// The ids of `xs`, each an input term of its own class (`==` can join classes), or None.
    fn ids(&self, xs: &Bound<'py, PyAny>) -> PyResult<Option<Vec<TermId>>> {
        let mut out = Vec::new();
        for x in xs.try_iter()? {
            let x = x?;
            let i = self.ids.call_method1("get", (&x,))?;
            if i.is_none() {
                return Ok(None);
            }
            let i: u32 = i.extract()?;
            if !self.objects.get_item(i)?.get_type().is(&x.get_type()) {
                return Ok(None);
            }
            out.push(TermId(i));
        }
        Ok(if out.is_empty() { None } else { Some(out) })
    }

    /// The SymPy object of an input id; None for a derived one (the shell's `scaffold`).
    fn obj(&self, t: TermId) -> PyResult<Option<Bound<'py, PyAny>>> {
        Ok(if (t.0 as usize) < self.n_input { Some(self.objects.get_item(t.0)?) } else { None })
    }

    fn one(&self, t: &Rest) -> PyResult<Option<Bound<'py, PyAny>>> {
        match t {
            Rest::One(t) => self.obj(*t),
            Rest::Product(_) => Ok(None),
        }
    }
}

/// `Some((result, shown))` (result Python's None for no split) when computed here, `None` to go to the shell; `shown` is
/// what the shadow compares when it isn't the result.
type Direct<'py> = Option<(Bound<'py, PyAny>, Option<Bound<'py, PyAny>>)>;

fn direct_split<'py>(py: Python<'py>, c: &Common, name: &str, args: &Bound<'py, PyAny>) -> PyResult<Direct<'py>> {
    if name == "irrational_root" {
        // `irrational_root(b, e)` with a constant missing is False, query or not (core.py's first two tests).
        if args.get_item(0)?.is_none() || args.get_item(1)?.is_none() {
            return Ok(Some((false.into_bound_py_any(py)?, None)));
        }
    }
    let Some(q) = QIds::of(py, c)? else { return Ok(None) };
    // The one-term splits take the term itself; `_unit_power_units(angle, e, expr)` reads `e`; the Add splits take its
    // terms and `irrational_root` its two constants.
    let of = match name {
        "_unit_power_units" => PyTuple::new(py, [args.get_item(1)?])?.into_any(),
        n if ONE.contains(&n) => PyTuple::new(py, [args])?.into_any(),
        _ => args.clone(),
    };
    let Some(ids) = q.ids(&of)? else { return Ok(None) };
    let r = {
        let tb = q.table.borrow();
        direct_rows(py, c, &q, tb.tt(), name, args, &ids)?
    };
    match r {
        Some(Direct1::Done(r)) => Ok(Some((r, None))),
        Some(Direct1::Quotient(None)) => Ok(Some((py.None().into_bound(py), Some(py.None().into_bound(py))))),
        Some(Direct1::Quotient(Some((a, v, t, number)))) => {
            // `core.facts(('mul_quot', const_key(a) if consts else None), _quotient_rules, consts, (a, v, t, expr), 3)`.
            let shape = PyTuple::new(py, [&a, &v, &t])?.into_any();
            let consts = PyDict::new(py);
            let key_c = if a.getattr("is_Atom")?.is_truthy()? && number {
                consts.set_item(0, &a)?;
                const_key(&a)?
            } else {
                py.None().into_bound(py)
            };
            let key = ("mul_quot", key_c).into_bound_py_any(py)?;
            let gen = py.import("satassume.knowledge.templates.core")?.getattr("_quotient_rules")?;
            let objs = if c.plant == "rows-quot-swap" {
                c.fired();
                PyTuple::new(py, [&v, &a, &t, args])?
            } else {
                PyTuple::new(py, [&a, &v, &t, args])?
            };
            let r = c.facts(py, &key, &gen, consts.as_any(), objs.as_any(), 3)?;
            Ok(Some((r, Some(shape))))
        }
        Some(Direct1::PowBound(None)) => Ok(Some((py.None().into_bound(py), Some(py.None().into_bound(py))))),
        Some(Direct1::PowBound(Some(pb))) => {
            // `core.facts(('pow_bound', c0, c1, const_key(e) if consts else None), gen, consts, (u, e, b, expr), 3)`, gen
            // IPI-free: `pow_bound_rules(idx)` (knowledge_core_live's `core_pow_bound_rules`).
            let PowBound { b, e, c0, c1, u, idx, number } = pb;
            let shown = (&c0, &c1, &u, PyList::new(py, &idx)?).into_bound_py_any(py)?;
            let consts = PyDict::new(py);
            let key_e = if number {
                consts.set_item(1, &e)?;
                const_key(&e)?
            } else {
                py.None().into_bound(py)
            };
            let key = ("pow_bound", &c0, &c1, key_e).into_bound_py_any(py)?;
            let gen = PyCFunction::new_closure(py, None, None, move |t: &Bound<'_, PyTuple>, _kw: Option<&Bound<'_, PyDict>>| -> PyResult<Py<PyAny>> {
                Ok(super::tcore::pow_bound_rules(&idx).into_pyobject(t.py())?.into_any().unbind())
            })?;
            let objs = PyTuple::new(py, [&u, &e, &b, args])?;
            let r = c.facts(py, &key, gen.as_any(), consts.as_any(), objs.as_any(), 3)?;
            Ok(Some((r, Some(shown))))
        }
        None => Ok(None),
    }
}

enum Direct1<'py> {
    Done(Bound<'py, PyAny>),
    /// `(a, v, v**k, a is a number)` or no shape; facts are built after the table's borrow ends.
    Quotient(Option<(Bound<'py, PyAny>, Bound<'py, PyAny>, Bound<'py, PyAny>, bool)>),
    /// `_pow_bound_templates`' split or none.
    PowBound(Option<PowBound<'py>>),
}

struct PowBound<'py> {
    b: Bound<'py, PyAny>,
    e: Bound<'py, PyAny>,
    c0: Bound<'py, PyAny>,
    c1: Bound<'py, PyAny>,
    u: Bound<'py, PyAny>,
    idx: Vec<usize>,
    /// `e.is_number`: e is a constant of the pattern.
    number: bool,
}

fn direct_rows<'py>(
    py: Python<'py>,
    c: &Common,
    q: &QIds<'py>,
    t: &super::table::TermTable,
    name: &str,
    args: &Bound<'py, PyAny>,
    ids: &[TermId],
) -> PyResult<Option<Direct1<'py>>> {
    match name {
        "_mul_factor_sets" => {
            // `[expr.args, (c, rest), ((c,) if c != 1 else ()) + (I, pi, s)]`; a product rest (`kept_product`) goes to
            // the shell, and every ct set has one (it is the Mul's other >= 2 factors).
            let (ct, ipi) = t.core_mul_factor_sets(ids[0]).map_err(refuse)?;
            if ct.is_some() {
                return Ok(None);
            }
            let out = PyList::new(py, [args.getattr("args")?])?;
            if let Some((k, r)) = ipi {
                let Some(s) = q.one(&r)? else { return Ok(None) };
                if s.getattr("is_Mul")?.is_truthy()? && c.plant == "rows-mul-ipi-drop" {
                    c.fired();
                } else if s.getattr("is_Mul")?.is_truthy()? {
                    let sp = py.import("sympy")?;
                    let (p, d) = super::py::core_pq(&k);
                    let k = sp.getattr("Rational")?.call1((p, d))?;
                    let mut set: Vec<Bound<'py, PyAny>> = Vec::new();
                    if !k.eq(1)? {
                        set.push(k);
                    }
                    set.push(sp.getattr("S")?.getattr("ImaginaryUnit")?);
                    set.push(sp.getattr("S")?.getattr("Pi")?);
                    set.push(s);
                    out.append(PyTuple::new(py, set)?)?;
                }
            }
            Ok(Some(Direct1::Done(out.into_any())))
        }
        "_quotient_templates" => {
            let Some((a, v, w)) = t.core_quotient_shape(ids[0]).map_err(refuse)? else {
                return Ok(Some(Direct1::Quotient(None)));
            };
            let (Some(ao), Some(vo), Some(wo)) = (q.obj(a)?, q.obj(v)?, q.obj(w)?) else { return Ok(None) };
            let number = t.core_is_number(a).map_err(refuse)?;
            Ok(Some(Direct1::Quotient(Some((ao, vo, wo, number)))))
        }
        "_pow_bound_templates" => {
            let Some((b, e)) = t.core_pow_bound_shape(ids[0]).map_err(refuse)? else {
                return Ok(Some(Direct1::PowBound(None)));
            };
            let bargs = t.row(b).args.to_vec();
            let Some((c0, (k, r))) = t.core_bound_split(&bargs).map_err(refuse)? else {
                return Ok(Some(Direct1::PowBound(None)));
            };
            let (Some(bo), Some(eo), Some(c0), Some(u)) = (q.obj(b)?, q.obj(e)?, q.obj(c0)?, q.one(&r)?) else { return Ok(None) };
            let c1 = match k {
                Some(k) => match q.obj(k)? {
                    Some(o) => o,
                    None => return Ok(None),
                },
                None => sympy_one(py)?,
            };
            let mut idx = super::tcore::not_unit_premises(&rat_of(&c0)?, &rat_of(&c1)?);
            if !idx.is_empty() && c.plant == "rows-pow-bound-drop-last" {
                c.fired();
                idx.pop();
            }
            if idx.is_empty() {
                return Ok(Some(Direct1::PowBound(None)));
            }
            let number = t.core_is_number(e).map_err(refuse)?;
            Ok(Some(Direct1::PowBound(Some(PowBound { b: bo, e: eo, c0, c1, u, idx, number }))))
        }
        _ => Ok(direct_pow(py, c, q, t, name, args, ids)?.map(Direct1::Done)),
    }
}

/// 6g(c3) the Pow family's one-term pieces: `Some(result)`, `None` to go to the shell.
fn direct_pow<'py>(
    py: Python<'py>,
    c: &Common,
    q: &QIds<'py>,
    t: &super::table::TermTable,
    name: &str,
    args: &Bound<'py, PyAny>,
    ids: &[TermId],
) -> PyResult<Option<Bound<'py, PyAny>>> {
    let none = || Ok(Some(py.None().into_bound(py)));
    let rational = |r: &super::rat::Rat| -> PyResult<Bound<'py, PyAny>> {
        let (p, d) = super::py::core_pq(r);
        py.import("sympy")?.getattr("Rational")?.call1((p, d))
    };
    match name {
        "_exp_arg" => {
            let Some(u) = t.core_exp_arg(ids[0]).map_err(refuse)? else { return none() };
            if c.plant == "rows-exp-arg-none" {
                c.fired();
                return none();
            }
            Ok(q.obj(u)?)
        }
        "_unit_angle" => {
            let Some(mut a) = t.core_unit_angle(ids[0]).map_err(refuse)? else { return none() };
            if c.plant == "rows-unit-angle-neg" {
                c.fired();
                a = super::rat::Rat::new(-a.n.clone(), a.d.clone());
            }
            Ok(Some(rational(&a)?))
        }
        "ipi_split" => {
            let Some((mut k, s)) = t.core_pi_split(ids[0], true).map_err(refuse)? else { return none() };
            let s = match &s {
                None => py.None().into_bound(py),
                Some(r) => match q.one(r)? {
                    Some(o) => o,
                    None => return Ok(None),
                },
            };
            if c.plant == "rows-ipi-split-neg" {
                c.fired();
                k = super::rat::Rat::new(-k.n.clone(), k.d.clone());
            }
            Ok(Some((rational(&k)?, s).into_bound_py_any(py)?))
        }
        "irrational_root" => {
            let mut r = t.core_irrational_root(ids[0], ids[1]).map_err(refuse)?;
            if r && c.plant == "rows-irrational-false" {
                c.fired();
                r = false;
            }
            Ok(Some(r.into_bound_py_any(py)?))
        }
        "_unit_power_units" => {
            // A non-Rational exponent goes to the shell (its counted SymPy `as_real_imag` fallback).
            let Some(mut facts) = t.core_unit_power_units(&rat_of(&args.get_item(0)?)?, ids[0]).map_err(refuse)? else {
                return Ok(None);
            };
            if !facts.is_empty() && c.plant == "rows-unit-power-drop-last" {
                c.fired();
                facts.pop();
            }
            let f = py.import("satassume.sat.formula")?;
            let (p, not) = (f.getattr("P")?, f.getattr("Not")?);
            let expr = args.get_item(2)?;
            let out = PyList::empty(py);
            for (pred, v) in facts {
                let a = p.call1((pred, &expr))?;
                out.append(if v { a } else { not.call1((a,))? })?;
            }
            Ok(Some(out.into_any()))
        }
        _ => Ok(direct_add(py, c, q, t, name, ids)?),
    }
}

/// The Add family's splits: `Some(result)` (Python's None for no split), `None` to go to the shell.
fn direct_add<'py>(
    py: Python<'py>,
    c: &Common,
    q: &QIds<'py>,
    t: &super::table::TermTable,
    name: &str,
    ids: &[TermId],
) -> PyResult<Option<Bound<'py, PyAny>>> {
    let ids = ids.to_vec();
    let none = || Ok(Some(py.None().into_bound(py)));
    match name {
        "_half_split" => {
            let Some((a0, terms)) = t.core_half_split(&ids).map_err(refuse)? else { return none() };
            let out = PyList::empty(py);
            for (a, (_c, r)) in &terms {
                let Some(o) = q.one(r)? else { return Ok(None) };
                let a = if c.plant == "rows-half-parity" {
                    c.fired();
                    1 - *a
                } else {
                    *a
                };
                out.append((a, o))?;
            }
            Ok(Some((a0, out).into_bound_py_any(py)?))
        }
        "_bound_split" => {
            let Some((c0, (k, r))) = t.core_bound_split(&ids).map_err(refuse)? else { return none() };
            let (Some(c0), Some(u)) = (q.obj(c0)?, q.one(&r)?) else { return Ok(None) };
            let k = match k {
                Some(k) if c.plant == "rows-bound-coeff-one" => {
                    c.fired();
                    let _ = k;
                    sympy_one(py)?
                }
                Some(k) => match q.obj(k)? {
                    Some(o) => o,
                    None => return Ok(None),
                },
                None => sympy_one(py)?,
            };
            Ok(Some((c0, k, u).into_bound_py_any(py)?))
        }
        "_imag_split" => {
            let Some(mut terms) = t.core_imag_split(&ids).map_err(refuse)? else { return none() };
            if !terms.is_empty() && c.plant == "rows-imag-drop-last" {
                c.fired();
                terms.pop();
            }
            let out = PyList::empty(py);
            for (k, x) in &terms {
                let k = match k {
                    Some(k) => match q.obj(*k)? {
                        Some(o) => o,
                        None => return Ok(None),
                    },
                    None => sympy_one(py)?,
                };
                let x = match x {
                    Some(x) => match q.obj(*x)? {
                        Some(o) => o,
                        None => return Ok(None),
                    },
                    None => py.None().into_bound(py),
                };
                out.append((k, x))?;
            }
            Ok(Some(out.into_any()))
        }
        _ => Ok(None),
    }
}

/// A SymPy Rational's `(p, q)` as a Rat.
fn rat_of(x: &Bound<'_, PyAny>) -> PyResult<super::rat::Rat> {
    Ok(super::rat::Rat::new(x.getattr("p")?.extract()?, x.getattr("q")?.extract()?))
}

fn sympy_one(py: Python<'_>) -> PyResult<Bound<'_, PyAny>> {
    py.import("sympy")?.getattr("S")?.getattr("One")
}
