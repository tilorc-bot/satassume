//! Step 6i(a) (issue 323): the outer templates of `knowledge/templates/{special,rootof,nodes,physics,stats}.py` on Rust,
//! so dispatch.rs no longer runs them as Python (`registry:python:NAME`, the no-rows-spec fallback).
//!
//! Each builds the same key, consts, objects and node slot as its Python template and hands 6d's `facts`/`units` a Rust
//! `gen` (tf6.rs's builders, 6f's). What stays Python, each call named and counted under `outer:`:
//! - conversion reads of the input node (the 6f reclass ruling): `crootof_units`' `expr.poly` coefficients and index,
//!   `randomsymbol_units`' declared `is_positive`/`is_integer`/`is_real` and `pspace.is_real`, and the class attributes
//!   `is_Integer`, `is_Atom`, `is_number`;
//! - `multigamma`'s value at a constant `x` (`expr.func(x, p)`, SymPy's evaluation: `outer:multigamma_value:sympy`, the
//!   unruled callback that was `f6:multigamma_value:python`) and the value's `const_value` reads (6d's named callback);
//! - `term_live.scaffold` for `multigamma`'s derived slots `2*x` and `2*x - p + 1` (temporary construction, counted as
//!   `scaffold:rebuilt:f6` there, as 6f's shells did);
//! - a whole template on Python where the node can't be read here (`outer:python:NAME:REASON`): no query, or an `x`
//!   with no id of its own class. Kept queries never reach this file (dispatch.rs runs the template, `registry:kept:`).
use super::common::Common;
use super::py::{refuse, PyTermTable};
use super::rat::Rat;
use super::tcore::Rule;
use super::tf6;
use super::TermId;
use num_bigint::BigInt;
use num_traits::One;
use pyo3::prelude::*;
use pyo3::types::{PyCFunction, PyDict, PyList, PyTuple};

pub const PLANTS: &[&str] = &[
    "outer-multigamma-p",     // 280: multigamma's rules for p + 1 (p = 1 gets p = 2's pole rules)
    "outer-multigamma-value", // 281: multigamma's value at a constant x dropped (no value_units)
    "outer-rootof-index",     // 282: crootof's root_facts for index + 1 (realroots.rs reads the next root)
    "outer-accum-real",       // 283: accumbounds' real rule dropped
    "outer-idx-integer",      // 284: idx's unit fact integer flipped
    "outer-quantity-positive", // 285: quantity's unit fact positive flipped
    "outer-random-real",      // 286: randomsymbol's real fact dropped
];

const SPECIAL: &str = "satassume.knowledge.templates.special";
const ROOTOF: &str = "satassume.knowledge.templates.rootof";
const NODES: &str = "satassume.knowledge.templates.nodes";
const PHYSICS: &str = "satassume.knowledge.templates.physics";
const STATS: &str = "satassume.knowledge.templates.stats";

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Outer {
    Multigamma,
    CRootOf,
    AccumBounds,
    Idx,
    Quantity,
    RandomSymbol,
}

impl Outer {
    /// The built-in template `t` (module, qualname) this file answers for, or None.
    pub fn of(t: &Bound<'_, PyAny>, name: &str) -> PyResult<Option<Outer>> {
        let Ok(m) = t.getattr("__module__").and_then(|m| m.extract::<String>()) else { return Ok(None) };
        Ok(match (m.as_str(), name) {
            (SPECIAL, "multigamma_templates") => Some(Outer::Multigamma),
            (ROOTOF, "crootof_units") => Some(Outer::CRootOf),
            (NODES, "accumbounds_templates") => Some(Outer::AccumBounds),
            (NODES, "idx_units") => Some(Outer::Idx),
            (PHYSICS, "quantity_units") => Some(Outer::Quantity),
            (STATS, "randomsymbol_units") => Some(Outer::RandomSymbol),
            _ => None,
        })
    }

    pub fn name(self) -> &'static str {
        match self {
            Outer::Multigamma => "multigamma_templates",
            Outer::CRootOf => "crootof_units",
            Outer::AccumBounds => "accumbounds_templates",
            Outer::Idx => "idx_units",
            Outer::Quantity => "quantity_units",
            Outer::RandomSymbol => "randomsymbol_units",
        }
    }

    /// The template's result for `expr` (what `split` takes), or None to run the Python template `t` (counted).
    pub fn call<'py>(self, c: &Common, t: &Bound<'py, PyAny>, expr: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        let r = match self {
            Outer::Idx => Some(const_units(c, expr, "idx", "outer-idx-integer")?),
            Outer::Quantity => Some(const_units(c, expr, "quantity", "outer-quantity-positive")?),
            Outer::RandomSymbol => Some(randomsymbol(c, expr)?),
            Outer::AccumBounds => Some(accumbounds(c, expr)?),
            Outer::CRootOf => Some(crootof(c, expr)?),
            Outer::Multigamma => multigamma(c, expr)?,
        };
        match r {
            Some(r) => Ok(r),
            None => t.call1((expr,)),
        }
    }
}

fn units_gen<'py>(py: Python<'py>, facts: Vec<(&'static str, bool)>) -> PyResult<Bound<'py, PyCFunction>> {
    PyCFunction::new_closure(py, None, None, move |t: &Bound<'_, PyTuple>, _kw: Option<&Bound<'_, PyDict>>| -> PyResult<Py<PyAny>> {
        Ok(facts.clone().into_pyobject(t.py())?.into_any().unbind())
    })
}

fn rules_gen<'py>(py: Python<'py>, rules: Vec<Rule>) -> PyResult<Bound<'py, PyCFunction>> {
    PyCFunction::new_closure(py, None, None, move |t: &Bound<'_, PyTuple>, _kw: Option<&Bound<'_, PyDict>>| -> PyResult<Py<PyAny>> {
        Ok(rules.clone().into_pyobject(t.py())?.into_any().unbind())
    })
}

fn flip_last(c: &Common, mut f: Vec<(&'static str, bool)>, plant: &str) -> Vec<(&'static str, bool)> {
    if c.plant == plant {
        c.fired();
        if let Some(l) = f.last_mut() {
            l.1 = !l.1;
        }
    }
    f
}

/// `nodes.idx_units`, `physics.quantity_units`: `units((tag,), gen, expr)`.
fn const_units<'py>(c: &Common, expr: &Bound<'py, PyAny>, tag: &str, plant: &str) -> PyResult<Bound<'py, PyAny>> {
    let py = expr.py();
    c.bump(&format!("outer:rust:{tag}"));
    let f = tf6::const_units(tag).expect("idx and quantity have constant unit facts");
    let gen = units_gen(py, flip_last(c, f, plant))?;
    c.units(py, PyTuple::new(py, [tag])?.as_any(), gen.as_any(), expr)
}

/// `stats.randomsymbol_units`: the declared facts read by conversion, `_random_units` here.
fn randomsymbol<'py>(c: &Common, expr: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    let py = expr.py();
    c.bump("outer:rust:random");
    c.bump("outer:conversion:random");
    let sym = expr.getattr("symbol")?;
    let opt = |v: Bound<'py, PyAny>| -> PyResult<Option<bool>> { if v.is_none() { Ok(None) } else { Ok(Some(v.is_truthy()?)) } };
    let positive = opt(sym.getattr("is_positive")?)?;
    let integer = opt(sym.getattr("is_integer")?)?;
    // `bool(sym.is_real or expr.pspace.is_real)`: Python's `or` reads the space only when the symbol's is falsy
    let sr = sym.getattr("is_real")?;
    let real = if sr.is_truthy()? { true } else { expr.getattr("pspace")?.getattr("is_real")?.is_truthy()? };
    let mut out = tf6::randomsymbol_units(positive, integer, real);
    if c.plant == "outer-random-real" && real {
        c.fired();
        out.pop();
    }
    // `('random', out)`, `out` a tuple of `(pred, value)` tuples as Python's `tuple(_random_units(...))`
    let tup = PyTuple::new(py, out.iter().map(|(p, v)| (*p, *v)).collect::<Vec<_>>())?;
    let key = PyTuple::new(py, [PyString(py, "random"), tup.into_any()])?;
    let gen = units_gen(py, out)?;
    c.units(py, key.as_any(), gen.as_any(), expr)
}

#[allow(non_snake_case)]
fn PyString<'py>(py: Python<'py>, s: &str) -> Bound<'py, PyAny> {
    pyo3::types::PyString::new(py, s).into_any()
}

/// `nodes.accumbounds_templates`.
fn accumbounds<'py>(c: &Common, expr: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    let py = expr.py();
    c.bump("outer:rust:accum");
    let args = expr.getattr("args")?;
    let consts = c.consts_of(py, &args)?;
    let key = c.pattern_key(py, PyString(py, "AccumBounds").as_any(), &2i64.into_pyobject(py)?.into_any(), &consts)?;
    let mut objs: Vec<Bound<'py, PyAny>> = args.try_iter()?.collect::<PyResult<_>>()?;
    objs.push(expr.clone());
    let objs = PyTuple::new(py, objs)?;
    let mut rules = tf6::accum_rules();
    if c.plant == "outer-accum-real" {
        c.fired();
        rules.pop();
    }
    let gen = rules_gen(py, rules)?;
    c.facts(py, &key, gen.as_any(), &consts, objs.as_any(), 2)
}

/// `rootof.crootof_units`: `_coefficients` and `int(expr.index)` are conversion (6f reclass ruling); `_facts` is tf6.rs's
/// `rootof_facts` over realroots.rs.
fn crootof<'py>(c: &Common, expr: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    let py = expr.py();
    c.bump("outer:rust:crootof");
    c.bump("outer:conversion:crootof");
    let int = py.import("builtins")?.getattr("int")?;
    let poly = expr.getattr("poly")?;
    let coeffs: Option<Vec<BigInt>> = if poly.getattr("domain")?.getattr("is_ZZ")?.is_truthy()? {
        let mut v = Vec::new();
        for x in poly.getattr("rep")?.call_method0("to_list")?.try_iter()? {
            v.push(int.call1((x?,))?.extract::<BigInt>()?);
        }
        Some(v)
    } else {
        None
    };
    let index: BigInt = int.call1((expr.getattr("index")?,))?.extract()?;
    let ckey = match &coeffs {
        Some(v) => PyTuple::new(py, v.iter().map(|x| x.clone().into_pyobject(py)).collect::<PyResult<Vec<_>>>()?)?.into_any(),
        None => py.None().into_bound(py),
    };
    let key = PyTuple::new(py, [PyString(py, "crootof"), ckey, index.clone().into_pyobject(py)?.into_any()])?;
    let mut at = index;
    if c.plant == "outer-rootof-index" && coeffs.is_some() {
        c.fired();
        at += 1;
    }
    if coeffs.is_some() {
        c.bump("outer:realroots:root_facts");
    }
    let facts = tf6::rootof_facts(coeffs.as_deref(), &at);
    let gen = units_gen(py, facts)?;
    c.units(py, key.as_any(), gen.as_any(), expr)
}

/// `special.multigamma_templates`. None: the Python template runs (counted).
fn multigamma<'py>(c: &Common, expr: &Bound<'py, PyAny>) -> PyResult<Option<Bound<'py, PyAny>>> {
    let py = expr.py();
    let args = expr.getattr("args")?;
    if args.len()? != 2 {
        c.bump("outer:rust:multigamma:none");
        return Ok(Some(py.None().into_bound(py)));
    }
    let (x, p) = (args.get_item(0)?, args.get_item(1)?);
    // `p.is_Integer and p > 0`
    if !p.getattr("is_Integer")?.is_truthy()? {
        c.bump("outer:rust:multigamma:none");
        return Ok(Some(py.None().into_bound(py)));
    }
    let pv: BigInt = p.getattr("p")?.extract()?;
    if pv <= BigInt::from(0) {
        c.bump("outer:rust:multigamma:none");
        return Ok(Some(py.None().into_bound(py)));
    }
    let Some(q) = c.query(py)? else {
        c.bump("outer:python:multigamma_templates:no-query");
        return Ok(None);
    };
    let table = q.getattr("table")?.cast_into::<PyTermTable>()?;
    let ids = q.getattr("ids")?;
    let objects = q.getattr("objects")?;
    let i = ids.call_method1("get", (&x,))?;
    let xi = if i.is_none() {
        None
    } else {
        let i: u32 = i.extract()?;
        if objects.get_item(i)?.get_type().is(&x.get_type()) { Some(TermId(i)) } else { None }
    };
    let Some(xi) = xi else {
        c.bump("outer:python:multigamma_templates:derived-x");
        return Ok(None);
    };
    c.bump("outer:rust:multigamma");
    let (yi, di) = {
        let mut tb = table.borrow_mut();
        let tt = tb.tt_mut();
        let yi = tt.f6_doubled(xi).map_err(refuse)?;
        let one_minus_p = Rat::new(BigInt::one() - &pv, BigInt::one());
        let di = tt.f6_shifted(yi, &one_minus_p).map_err(refuse)?;
        (yi, di)
    };
    let scaffold = py.import("term_live")?.getattr("scaffold")?;
    let y = scaffold.call1((&q, yi.0, "f6"))?;
    let d = scaffold.call1((&q, di.0, "f6"))?;
    let objs = [x.clone(), p.clone(), expr.clone(), y, d];
    let consts = PyDict::new(py);
    let mut is_const = [false; 5];
    for (k, o) in objs.iter().enumerate() {
        if k != 2 && o.getattr("is_Atom")?.is_truthy()? && o.getattr("is_number")?.is_truthy()? {
            consts.set_item(k, o)?;
            is_const[k] = true;
        }
    }
    let key = PyList::new(py, [PyString(py, "multigamma"), pv.clone().into_pyobject(py)?.into_any()])?;
    for k in [0usize, 3, 4] {
        if is_const[k] {
            key.append(c.const_key(py, &objs[k])?)?;
        } else {
            key.append(py.None())?;
        }
    }
    let key = PyTuple::new(py, key.iter())?;
    let mut rp = pv.clone();
    if c.plant == "outer-multigamma-p" {
        c.fired();
        rp += 1;
    }
    let gen = rules_gen(py, tf6::multigamma_rules(&rp))?;
    let objs_t = PyTuple::new(py, objs.iter())?;
    let out = c.facts(py, key.as_any(), gen.as_any(), consts.as_any(), objs_t.as_any(), 2)?;
    if is_const[0] && pv <= BigInt::from(MAX_MULTIGAMMA_P) {
        // `_multigamma_value(expr, x, p)`: SymPy evaluates; None if it raises ValueError, TypeError or ArithmeticError
        c.bump("outer:multigamma_value:sympy");
        let v = match expr.getattr("func")?.call1((&x, &p)) {
            Ok(v) => Some(v),
            Err(e) => {
                let b = py.import("builtins")?;
                let caught = [b.getattr("ValueError")?, b.getattr("TypeError")?, b.getattr("ArithmeticError")?];
                if caught.iter().any(|t| e.is_instance(py, t)) {
                    None
                } else {
                    return Err(e);
                }
            }
        };
        if let Some(v) = v {
            let nan = py.import("sympy")?.getattr("S")?.getattr("NaN")?;
            if v.getattr("is_Atom")?.is_truthy()? && v.getattr("is_number")?.is_truthy()? && !v.is(&nan) {
                if c.plant == "outer-multigamma-value" {
                    c.fired();
                    return Ok(Some(out));
                }
                let vu = value_units(c, &v, expr)?;
                return Ok(Some(PyList::new(py, [out, vu])?.into_any()));
            }
        }
    }
    Ok(Some(out))
}

/// `special.MAX_MULTIGAMMA_P`.
const MAX_MULTIGAMMA_P: i64 = 50;

/// `atoms.value_units(value, obj)`: `units(('const', const_key(value)), gen, obj)`, `gen` reading `const_value` (6d's named
/// callback) over `atoms._CONST_BASIS`.
fn value_units<'py>(c: &Common, value: &Bound<'py, PyAny>, obj: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    let py = obj.py();
    c.bump("outer:rust:value_units");
    let basis: Vec<String> = py.import("satassume.knowledge.templates.atoms")?.getattr("_CONST_BASIS")?.extract()?;
    let cv = c.const_value.clone_ref(py);
    let val = value.clone().unbind();
    // read only when `units` builds the pattern (a cache miss), as Python's `gen` (6d's named
    // `const_value` callback; not counted here, as atoms.py's own gen isn't)
    let gen = PyCFunction::new_closure(py, None, None, move |t: &Bound<'_, PyTuple>, _kw: Option<&Bound<'_, PyDict>>| -> PyResult<Py<PyAny>> {
        let py = t.py();
        let out = PyList::empty(py);
        for pred in &basis {
            let v = cv.bind(py).call1((val.bind(py), pred.as_str()))?;
            if !v.is_none() {
                out.append((pred.as_str(), v))?;
            }
        }
        Ok(out.into_any().unbind())
    })?;
    let key = PyTuple::new(py, [PyString(py, "const"), c.const_key(py, value)?])?;
    c.units(py, key.as_any(), gen.as_any(), obj)
}
