//! Step 6i(b) (issue 323): functions.py's slotted templates on Rust, so dispatch.rs no longer runs them as Python
//! (`registry:python:_unary.<locals>.template`, `registry:python:nary.<locals>.template`, the no-rows-spec fallback).
//!
//! `wiring.template` tags each with `_satassume_slotted = (kind, tag, gen, half, units)`:
//! - `('unary', tag, gen, half, units)`: `functions._unary(tag, gen', slots, units)` with `slots(x)` the terms `x + c`
//!   for `c` in `gen.shifts` (`functions.shifted`), then `x/2` when `half` (`_genocchi_half`: `gen'` is `gen` plus
//!   `_genocchi_half_rules` at that slot), and `units` one of `'asin'`/`'acos'` (`_in_unit_interval_units`), `'value'`
//!   (`_value_units`) or None;
//! - `('nary', tag, gen, False, None)`: `functions.nary(tag, gen, slots, arity=gen.arity)` with `slots(args)` the terms
//!   `args[i] + c` for `(i, c)` in `gen.terms[len(args)]`.
//!
//! Each builds the same key, consts, objects and node slot as the Python template and hands 6d's `facts` the rows' rules
//! (read once from `gen.specs`, as rows_tpl.rs's Unary family does). What stays Python, each named and counted under `fn:`:
//! - the derived slot objects `x + c` and `x/2`: built in the query's table (tf6.rs `f6_shifted`, `f6_halved`) and rebuilt
//!   in SymPy by `term_live.scaffold` (temporary construction, `scaffold:rebuilt:f6`, checked against Rust's form);
//! - `_value_units`' value `expr.func(c)` (SymPy's evaluation of an input constant's function value,
//!   `fn:value:sympy`, the same kind of callback as special.py's `outer:multigamma_value:sympy`), and its `value_units`
//!   through the name functions.py bound (knowledge_live rebinds it to `rust_value_units`; a module attribute read);
//! - the `P`/`Not` input formulas of the unit-interval facts (as rows_tpl.rs's `_unit_power_units`);
//! - a whole template on Python where the node can't be read here (`fn:python:NAME:REASON`): no query, or an argument a
//!   slot is built from with no id of its own class. Kept queries never reach this file (dispatch.rs runs the template).
use super::common::Common;
use super::py::{refuse, PyTermTable};
use super::rat::Rat;
use super::TermId;
use num_bigint::BigInt;
use pyo3::prelude::*;
use pyo3::types::{PyCFunction, PyDict, PyList, PyString, PyTuple};
use std::collections::HashMap;

pub const PLANTS: &[&str] = &[
    "fn-unary-drop-last",      // 340: a slotted unary template's last rule dropped
    "fn-nary-drop-last",       // 341: an nary template's last rule dropped
    "fn-unit-interval-flip",   // 342: asin/acos of a constant: the [-1, 1] test flipped
    "fn-value-drop",           // 343: _value_units' value facts dropped
    "fn-genocchi-half-flip",   // 344: _genocchi_half's two rules swap their signs
    "fn-unary-shift",          // 345: a unary slot is x + c + 1
];

/// `functions.MAX_VALUE_ARG`.
const MAX_VALUE_ARG: i64 = 200;
const FUNCTIONS: &str = "satassume.knowledge.templates.functions";

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Units {
    None,
    Asin,
    Acos,
    Value,
}

type RuleSpec = (Py<PyAny>, Py<PyAny>);

pub struct Slotted {
    name: String,
    tag: String,
    nary: bool,
    /// nary: `arity` (None: any)
    arities: Option<Vec<usize>>,
    /// `gen.specs`: `n -> rules`; `one` when there is a single key
    specs: HashMap<usize, Vec<RuleSpec>>,
    one: Vec<RuleSpec>,
    /// unary: `gen.shifts`; nary: `gen.terms[n]` as `(i, c)`
    terms: HashMap<usize, Vec<(usize, Rat)>>,
    half: bool,
    units: Units,
}

fn rat_of(c: &Bound<'_, PyAny>) -> PyResult<Option<Rat>> {
    if !c.getattr("is_Rational")?.is_truthy()? {
        return Ok(None);
    }
    Ok(Some(Rat::new(c.getattr("p")?.extract()?, c.getattr("q")?.extract()?)))
}

fn atom_number(o: &Bound<'_, PyAny>) -> PyResult<bool> {
    Ok(o.getattr("is_Atom")?.is_truthy()? && o.getattr("is_number")?.is_truthy()?)
}

impl Slotted {
    /// The template `t` if `wiring` tagged it `_satassume_slotted` and its rows are what this file builds, else None (it
    /// stays `registry:python:NAME`).
    pub fn of(t: &Bound<'_, PyAny>, name: &str) -> PyResult<Option<Slotted>> {
        let Ok(spec) = t.getattr("_satassume_slotted") else { return Ok(None) };
        let nary = match spec.get_item(0)?.extract::<String>()?.as_str() {
            "unary" => false,
            "nary" => true,
            _ => return Ok(None),
        };
        let tag: String = spec.get_item(1)?.extract()?;
        let gen = spec.get_item(2)?;
        let half: bool = spec.get_item(3)?.extract()?;
        let u = spec.get_item(4)?;
        let units = if u.is_none() {
            Units::None
        } else {
            match u.extract::<String>()?.as_str() {
                "asin" => Units::Asin,
                "acos" => Units::Acos,
                "value" => Units::Value,
                _ => return Ok(None),
            }
        };
        if !gen.getattr("plain")?.is_truthy()? {
            return Ok(None);
        }
        let sp = gen.getattr("specs")?.cast_into::<PyDict>()?;
        let mut specs = HashMap::new();
        let mut one = Vec::new();
        for (n, rs) in sp.iter() {
            let n: usize = n.extract()?;
            let mut v = Vec::new();
            for r in rs.try_iter()? {
                let r = r?;
                if r.len()? != 2 {
                    return Ok(None);
                }
                v.push((r.get_item(0)?.unbind(), r.get_item(1)?.unbind()));
            }
            one.extend(v.iter().map(|(a, b)| (a.clone_ref(t.py()), b.clone_ref(t.py()))));
            specs.insert(n, v);
        }
        // unary: `gen(R, c)` would pick `specs[c]` by the constant argument when the rows have several keys
        if !nary && specs.len() > 1 {
            return Ok(None);
        }
        let mut terms = HashMap::new();
        if nary {
            for (n, ts) in gen.getattr("terms")?.cast_into::<PyDict>()?.iter() {
                let mut v = Vec::new();
                for tm in ts.try_iter()? {
                    let tm = tm?;
                    let Ok(i) = tm.get_item(0)?.extract::<usize>() else { return Ok(None) };
                    let Some(c) = rat_of(&tm.get_item(1)?)? else { return Ok(None) };
                    v.push((i, c));
                }
                terms.insert(n.extract::<usize>()?, v);
            }
        } else {
            let mut v = Vec::new();
            for c in gen.getattr("shifts")?.try_iter()? {
                let Some(c) = rat_of(&c?)? else { return Ok(None) };
                v.push((0usize, c));
            }
            terms.insert(1usize, v);
        }
        let arities = if nary {
            let a = gen.getattr("arity")?;
            if a.is_none() {
                None
            } else if let Ok(n) = a.extract::<usize>() {
                Some(vec![n])
            } else {
                Some(a.extract::<Vec<usize>>()?)
            }
        } else {
            None
        };
        Ok(Some(Slotted { name: name.to_string(), tag, nary, arities, specs, one, terms, half, units }))
    }

    pub fn name(&self) -> &str {
        &self.name
    }

    fn short(&self) -> &'static str {
        if self.nary { "nary" } else { "unary" }
    }

    /// The template's result for `expr` (what `split` takes); the Python template `t` where this can't read the node
    /// (counted).
    pub fn call<'py>(&self, c: &Common, t: &Bound<'py, PyAny>, expr: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        let r = if self.nary { self.nary_call(c, expr)? } else { self.unary_call(c, expr)? };
        match r {
            Some(r) => Ok(r),
            None => t.call1((expr,)),
        }
    }

    /// The slot objects `args[i] + c` (and `x/2`), built in the query's table and rebuilt by `term_live.scaffold`; None
    /// when there is no query or an argument has no id of its own class (counted `fn:python:...`).
    fn slots<'py>(&self, c: &Common, args: &Bound<'py, PyTuple>, n: usize) -> PyResult<Option<Vec<Bound<'py, PyAny>>>> {
        let py = args.py();
        let ts = self.terms.get(&n).map(|v| v.as_slice()).unwrap_or(&[]);
        if ts.is_empty() && !self.half {
            return Ok(Some(Vec::new()));
        }
        let Some(q) = c.query(py)? else {
            c.bump(&format!("fn:python:{}:no-query", self.short()));
            return Ok(None);
        };
        let table = q.getattr("table")?.cast_into::<PyTermTable>()?;
        let ids = q.getattr("ids")?;
        let objects = q.getattr("objects")?;
        let id_of = |a: &Bound<'py, PyAny>| -> PyResult<Option<TermId>> {
            let i = ids.call_method1("get", (a,))?;
            if i.is_none() {
                return Ok(None);
            }
            let i: u32 = i.extract()?;
            Ok(if objects.get_item(i)?.get_type().is(&a.get_type()) { Some(TermId(i)) } else { None })
        };
        let mut want = Vec::new();
        for (i, k) in ts {
            let Some(ai) = id_of(&args.get_item(*i)?)? else {
                c.bump(&format!("fn:python:{}:derived-arg", self.short()));
                return Ok(None);
            };
            let mut k = k.clone();
            if c.plant == "fn-unary-shift" && !self.nary {
                c.fired();
                k = k.add(&Rat::int(1));
            }
            want.push((ai, Some(k)));
        }
        if self.half {
            let Some(ai) = id_of(&args.get_item(0)?)? else {
                c.bump(&format!("fn:python:{}:derived-arg", self.short()));
                return Ok(None);
            };
            want.push((ai, None));
        }
        let made: Vec<TermId> = {
            let mut tb = table.borrow_mut();
            let tt = tb.tt_mut();
            let mut v = Vec::with_capacity(want.len());
            for (ai, k) in &want {
                v.push(match k {
                    Some(k) => tt.f6_shifted(*ai, k).map_err(refuse)?,
                    None => tt.f6_halved(*ai).map_err(refuse)?,
                });
            }
            v
        };
        let scaffold = py.import("term_live")?.getattr("scaffold")?;
        let mut out = Vec::with_capacity(made.len());
        for i in made {
            out.push(scaffold.call1((&q, i.0, "f6"))?);
        }
        Ok(Some(out))
    }

    fn rules<'py>(&self, py: Python<'py>, c: &Common, pick: Option<usize>, half_slot: Option<usize>) -> PyResult<Bound<'py, PyList>> {
        let out = PyList::empty(py);
        let mut rules: &[RuleSpec] = match pick {
            Some(n) if self.specs.len() > 1 => self.specs.get(&n).map(|v| v.as_slice()).unwrap_or(&[]),
            _ => &self.one,
        };
        let plant = if self.nary { "fn-nary-drop-last" } else { "fn-unary-drop-last" };
        if !rules.is_empty() && c.plant == plant {
            c.fired();
            rules = &rules[..rules.len() - 1];
        }
        for (prem, concl) in rules {
            let prem = PyList::new(py, prem.bind(py).try_iter()?.collect::<PyResult<Vec<_>>>()?)?;
            let concl = PyList::new(py, concl.bind(py).try_iter()?.collect::<PyResult<Vec<_>>>()?)?;
            out.append((prem, concl))?;
        }
        if let Some(h) = half_slot {
            // `_genocchi_half_rules(R, h)`
            c.bump("fn:rust:genocchi_half");
            let (mut a, mut b) = ("positive", "negative");
            if c.plant == "fn-genocchi-half-flip" {
                c.fired();
                std::mem::swap(&mut a, &mut b);
            }
            for (par, sign) in [("even", a), ("odd", b)] {
                let prem = PyList::new(py, [(0usize, "even", true), (0usize, "positive", true), (h, par, true)])?;
                let concl = PyList::new(py, [(1usize, sign, true)])?;
                out.append((prem, concl))?;
            }
        }
        Ok(out)
    }

    /// `functions._unary(tag, gen, slots, units)`'s template.
    fn unary_call<'py>(&self, c: &Common, expr: &Bound<'py, PyAny>) -> PyResult<Option<Bound<'py, PyAny>>> {
        let py = expr.py();
        let args = expr.getattr("args")?.cast_into::<PyTuple>()?;
        if args.len() != 1 {
            c.bump("fn:rust:unary:none");
            return Ok(Some(py.None().into_bound(py)));
        }
        let Some(slots) = self.slots(c, &args, 1)? else { return Ok(None) };
        c.bump("fn:rust:unary");
        let x = args.get_item(0)?;
        let consts = PyDict::new(py);
        let key = PyList::new(py, [PyString::new(py, &self.tag).into_any(), py.None().into_bound(py)])?;
        let x_const = atom_number(&x)?;
        if x_const {
            consts.set_item(0, &x)?;
            key.set_item(1, c.const_key(py, &x)?)?;
        }
        let mut objs = vec![x.clone(), expr.clone()];
        for o in slots {
            let i = objs.len();
            if atom_number(&o)? {
                consts.set_item(i, &o)?;
                key.append(c.const_key(py, &o)?)?;
            } else {
                key.append(py.None())?;
            }
            objs.push(o);
        }
        let half_slot = if self.half { Some(objs.len() - 1) } else { None };
        let rules = self.rules(py, c, None, half_slot)?.unbind();
        let gen = PyCFunction::new_closure(py, None, None, move |t: &Bound<'_, PyTuple>, _kw: Option<&Bound<'_, PyDict>>| -> PyResult<Py<PyAny>> {
            Ok(PyList::new(t.py(), rules.bind(t.py()).iter())?.into_any().unbind())
        })?;
        let key = PyTuple::new(py, key.iter())?;
        let objs_t = PyTuple::new(py, objs.iter())?;
        let out = c.facts(py, key.as_any(), gen.as_any(), consts.as_any(), objs_t.as_any(), 1)?;
        if self.units == Units::None || !x_const {
            return Ok(Some(out));
        }
        let res = PyList::new(py, [out])?;
        match self.units {
            Units::Asin | Units::Acos => {
                for f in self.unit_interval(c, &x, expr)? {
                    res.append(f)?;
                }
            }
            Units::Value => {
                if let Some(f) = self.value(c, &x, expr)? {
                    res.append(f)?;
                }
            }
            Units::None => {}
        }
        Ok(Some(res.into_any()))
    }

    /// `functions._unit_interval_units(kind, c, expr)`: exact comparisons of a Rational or a Float `c` (its `_mpf_`,
    /// as SymPy's Float compares with an Integer) with -1 and 1.
    fn unit_interval<'py>(&self, c: &Common, cv: &Bound<'py, PyAny>, expr: &Bound<'py, PyAny>) -> PyResult<Vec<Bound<'py, PyAny>>> {
        let py = expr.py();
        let r = if let Some(r) = rat_of(cv)? {
            r
        } else if cv.getattr("is_Float")?.is_truthy()? {
            let m = cv.getattr("_mpf_")?;
            let sign: i64 = m.get_item(0)?.extract()?;
            let man: BigInt = m.get_item(1)?.extract()?;
            let exp: i64 = m.get_item(2)?.extract()?;
            let man = if sign != 0 { -man } else { man };
            if exp >= 0 {
                Rat::new(man << (exp as usize), BigInt::from(1))
            } else {
                Rat::new(man, BigInt::from(1) << ((-exp) as usize))
            }
        } else {
            c.bump("fn:rust:unit_interval:other");
            return Ok(Vec::new());
        };
        c.bump("fn:rust:unit_interval");
        let one = Rat::int(1);
        let mut inside = r >= Rat::int(-1) && r <= one;
        if c.plant == "fn-unit-interval-flip" {
            c.fired();
            inside = !inside;
        }
        let acos = self.units == Units::Acos;
        let mut facts: Vec<(&str, bool)> = vec![("finite", true), ("complex", true)];
        if inside {
            facts.push(("real", true));
            let zero = Rat::int(0);
            if acos {
                facts.push((if r < one { "positive" } else { "zero" }, true));
            } else {
                facts.push((if r > zero { "positive" } else if r < zero { "negative" } else { "zero" }, true));
            }
        } else {
            facts.push(("extended_real", false));
            facts.push(("imaginary", acos && r > one));
        }
        let f = py.import("satassume.sat.formula")?;
        let (p, not) = (f.getattr("P")?, f.getattr("Not")?);
        let mut out = Vec::new();
        for (pred, v) in facts {
            let a = p.call1((pred, expr))?;
            out.push(if v { a } else { not.call1((a,))? });
        }
        Ok(out)
    }

    /// `functions._value_units(c, expr)`: `expr.func(c)` for an Integer `|c| <= 200` (SymPy evaluates, the named callback
    /// `fn:value:sympy`); None if it raises ValueError, TypeError or ArithmeticError, or isn't an atom number or is nan;
    /// else `value_units(v, expr)` through the name functions.py bound.
    fn value<'py>(&self, c: &Common, cv: &Bound<'py, PyAny>, expr: &Bound<'py, PyAny>) -> PyResult<Option<Bound<'py, PyAny>>> {
        let py = expr.py();
        if !cv.getattr("is_Integer")?.is_truthy()? {
            return Ok(None);
        }
        let n: BigInt = cv.getattr("p")?.extract()?;
        if n > BigInt::from(MAX_VALUE_ARG) || n < BigInt::from(-MAX_VALUE_ARG) {
            return Ok(None);
        }
        c.bump("fn:value:sympy");
        let v = match expr.getattr("func")?.call1((cv,)) {
            Ok(v) => v,
            Err(e) => {
                let b = py.import("builtins")?;
                let caught = [b.getattr("ValueError")?, b.getattr("TypeError")?, b.getattr("ArithmeticError")?];
                if caught.iter().any(|t| e.is_instance(py, t)) {
                    return Ok(None);
                } else if e.is_instance_of::<pyo3::exceptions::PyException>(py) {
                    return Err(c.fault(py, "fn:value:sympy", e));
                } else {
                    return Err(e);
                }
            }
        };
        let nan = py.import("sympy")?.getattr("S")?.getattr("NaN")?;
        if !atom_number(&v)? || v.is(&nan) {
            return Ok(None);
        }
        if c.plant == "fn-value-drop" {
            c.fired();
            return Ok(None);
        }
        c.bump("fn:value_units");
        Ok(Some(py.import(FUNCTIONS)?.getattr("value_units")?.call1((&v, expr))?))
    }

    /// `functions.nary(tag, gen, slots, arity)`'s template.
    fn nary_call<'py>(&self, c: &Common, expr: &Bound<'py, PyAny>) -> PyResult<Option<Bound<'py, PyAny>>> {
        let py = expr.py();
        let args = expr.getattr("args")?.cast_into::<PyTuple>()?;
        let n = args.len();
        if let Some(a) = &self.arities {
            if !a.contains(&n) {
                c.bump("fn:rust:nary:none");
                return Ok(Some(py.None().into_bound(py)));
            }
        }
        let Some(slots) = self.slots(c, &args, n)? else { return Ok(None) };
        c.bump("fn:rust:nary");
        let mut objs: Vec<Bound<'py, PyAny>> = args.iter().collect();
        objs.push(expr.clone());
        objs.extend(slots);
        let consts = PyDict::new(py);
        for (k, o) in objs.iter().enumerate() {
            if k != n && atom_number(o)? {
                consts.set_item(k, o)?;
            }
        }
        let tag = PyTuple::new(py, [PyString::new(py, &self.tag).into_any(), n.into_pyobject(py)?.into_any()])?;
        let key = c.pattern_key(py, tag.as_any(), objs.len().into_pyobject(py)?.as_any(), consts.as_any())?;
        let rules = self.rules(py, c, Some(n), None)?.unbind();
        let gen = PyCFunction::new_closure(py, None, None, move |t: &Bound<'_, PyTuple>, _kw: Option<&Bound<'_, PyDict>>| -> PyResult<Py<PyAny>> {
            Ok(PyList::new(t.py(), rules.bind(t.py()).iter())?.into_any().unbind())
        })?;
        let objs_t = PyTuple::new(py, objs.iter())?;
        Ok(Some(c.facts(py, &key, gen.as_any(), consts.as_any(), objs_t.as_any(), n as i64)?))
    }
}
