//! `lra_adapter.py`'s term work on the per-query table (component 4, slice D, issue 323): `_lin`, `_closed`, `_linear`,
//! `_constraint`, `interpret`, `_side`, `order_sides`, `integer_form`, `closed_sign`, and `constfield.py`'s `_from_sympy`.
//! Each function follows the Python line for line, because answers have to match it. `relation` stays conversion.
//!
//! Python is still read in three places, each counted in `Counts`:
//! - The registry. `PI`, `E`, `radical` and `_generic` are Python's, so there's one registry and it has its history. An
//!   `Element` crosses by `Num::from_py`.
//! - R9. `constant_bounds` on an input term, read-only.
//! - `from_sympy(Mul(*closed))` when Rust's `mul` refuses the closed factors. That builds a term in SymPy: scaffolding, and
//!   it has to reach zero before any backend PR.
//!
//! A derived term has no Python object here, since the caller's scaffold can't run while the table is borrowed. A callback
//! that would need one refuses, so that query answers on Python.

use super::algebra::is_rational_kind;
use super::rat::Rat as TRat;
use super::table::{flag, fact, Kind, Refuse, TermTable};
use super::TermId;
use crate::constfield::{module, rat_of, CfErr, Num};
use crate::rat::Rat;
use num_bigint::BigInt;
use num_traits::{Signed, ToPrimitive};
use pyo3::exceptions::{PyTypeError, PyValueError, PyZeroDivisionError};
use pyo3::prelude::*;
use pyo3::types::PyList;
use std::collections::HashMap;
use std::sync::atomic::{AtomicU64, AtomicU8, Ordering::Relaxed};

const IS_ADD: u32 = 1 << 0;
const IS_MUL: u32 = 1 << 1;
const IS_POW: u32 = 1 << 2;
const IS_RATIONAL: u32 = 1 << 5;
const IS_INTEGER: u32 = 1 << 6;

/// `_MAX_POW` (constfield.py:1372).
const MAX_POW: i64 = 64;

/// Python reads during search, process-wide; `lra_counts` hands them out.
pub struct Counts {
    pub registry: AtomicU64,
    pub generic: AtomicU64,
    pub bounds: AtomicU64,
    pub closed_mul_direct: AtomicU64,
    pub closed_mul_rust: AtomicU64,
    pub closed_mul_scaffold: AtomicU64,
    pub product_terms: AtomicU64,
    pub keys: AtomicU64,
}

pub static COUNTS: Counts = Counts {
    registry: AtomicU64::new(0),
    generic: AtomicU64::new(0),
    bounds: AtomicU64::new(0),
    closed_mul_direct: AtomicU64::new(0),
    closed_mul_rust: AtomicU64::new(0),
    closed_mul_scaffold: AtomicU64::new(0),
    product_terms: AtomicU64::new(0),
    keys: AtomicU64::new(0),
};

/// Planted bugs, for showing the comparison catches a wrong answer here. 0 is none.
pub static PLANT: AtomicU8 = AtomicU8::new(0);
pub const PLANT_COEFF: u8 = 1; // `_lin`'s closed or rational coefficient of a Mul loses its sign.
pub const PLANT_SORT: u8 = 2; // the sort sites sort backwards.
pub const PLANT_PI: u8 = 3; // `_from_sympy` reads pi as E.
pub const PLANT_NEGATE_EQ: u8 = 4; // an eq's sign normalisation doesn't run.

fn planted(p: u8) -> bool {
    PLANT.load(Relaxed) == p
}

pub enum E {
    /// `_Unhandled` or `_Unread`.
    Unread,
    Cf(CfErr),
    Refuse(Refuse),
    Py(PyErr),
}

impl From<CfErr> for E {
    fn from(e: CfErr) -> E {
        E::Cf(e)
    }
}

impl From<Refuse> for E {
    fn from(e: Refuse) -> E {
        E::Refuse(e)
    }
}

impl From<PyErr> for E {
    fn from(e: PyErr) -> E {
        E::Py(e)
    }
}

type Res<T> = Result<T, E>;

/// The linear form: a dict in first-seen order.
#[derive(Default)]
pub struct Form {
    pub items: Vec<(TermId, Num)>,
    index: HashMap<TermId, usize>,
}

impl Form {
    fn add(&mut self, t: TermId, scale: &Num) -> Res<()> {
        // out[e] = out.get(e, Fraction(0)) + scale
        match self.index.get(&t) {
            Some(&i) => {
                let v = self.items[i].1.add(scale)?;
                self.items[i].1 = v;
            }
            None => {
                self.index.insert(t, self.items.len());
                self.items.push((t, Num::zero().add(scale)?));
            }
        }
        Ok(())
    }
}

/// `_constraint`'s result.
pub enum Constraint {
    Value(bool),
    Payload { items: Vec<(TermId, Num)>, rhs: Num, strict: bool, equality: bool, positive: bool },
}

pub struct Lra<'a, 'py> {
    pub t: &'a mut TermTable,
    pub py: Python<'py>,
    /// Input term by id, as `_Query.objects` holds them.
    pub objects: Bound<'py, PyAny>,
    pub generic: bool,
}

fn big_rat(r: &TRat) -> Num {
    Num::Q(Rat::norm_big(r.n.clone(), r.d.clone()))
}

impl<'py> Lra<'_, 'py> {
    fn flags(&self, t: TermId) -> u32 {
        self.t.class_of(t).flags
    }

    fn kind(&self, t: TermId) -> Kind {
        self.t.class_of(t).kind
    }

    fn is_expr(&self, t: TermId) -> bool {
        self.flags(t) & flag::IS_EXPR != 0
    }

    fn free(&self, t: TermId) -> bool {
        !self.t.row(t).free.is_empty()
    }

    /// What `isinstance(e, Expr) and not is_Matrix and not is_MatrixExpr` reads.
    fn plain_expr(&self, t: TermId) -> bool {
        self.is_expr(t) && self.flags(t) & flag::IS_MATRIX == 0
    }

    /// `e.has(*_BAD)`, off the bits conversion read.
    fn has_bad(&self, t: TermId) -> Result<bool, Refuse> {
        let bits = self.t.row(t).bits;
        if bits & fact::READ == 0 {
            return Err(Refuse("lra: a term whose facts weren't read"));
        }
        Ok(bits & (fact::NAN | fact::BAD) != 0)
    }

    /// The value of a term with `is_Rational`. A class of its own with that flag refuses.
    fn rational(&self, t: TermId) -> Result<TRat, Refuse> {
        if !is_rational_kind(self.kind(t)) {
            return Err(Refuse("lra: is_Rational on a class of its own"));
        }
        self.t.rat(t).ok_or(Refuse("lra: is_Rational with no value"))
    }

    fn object(&self, t: TermId) -> Res<Bound<'py, PyAny>> {
        if t.0 as usize >= self.t.n_input {
            return Err(E::Refuse(Refuse("lra: a callback on a derived term")));
        }
        Ok(self.objects.get_item(t.0)?)
    }

    // `_lin`, lra_adapter.py:179.
    pub fn lin(&mut self, e: TermId, scale: &Num, out: &mut Form, c: &mut Num) -> Res<()> {
        if !self.plain_expr(e) {
            return Err(E::Unread);
        }
        if !self.free(e) {
            return self.closed(e, scale, out, c);
        }
        let flags = self.flags(e);
        let args: Vec<TermId> = self.t.row(e).args.to_vec();
        if flags & IS_ADD != 0 {
            for a in args {
                self.lin(a, scale, out, c)?;
            }
            return Ok(());
        }
        if flags & IS_MUL != 0 {
            let mut coeff = TRat::int(1);
            let mut rest = Vec::new();
            let mut closed = Vec::new();
            for f in args {
                if self.free(f) {
                    rest.push(f);
                } else if self.flags(f) & IS_RATIONAL != 0 {
                    coeff = coeff.mul(&self.rational(f)?);
                } else {
                    closed.push(f);
                }
            }
            if !closed.is_empty() || !coeff.is_one() {
                let t = if rest.len() == 1 { Some(rest[0]) } else { self.kept_product(&rest)? };
                let Some(t) = t else { return Err(E::Unread) };
                if coeff.is_zero() {
                    return Err(E::Unread);
                }
                let mut k = big_rat(&coeff);
                if !closed.is_empty() {
                    let Some(v) = self.closed_product(&closed)? else { return Err(E::Unread) };
                    k = v.mul(&k)?;
                }
                if planted(PLANT_COEFF) {
                    k = k.neg();
                }
                let s = scale.mul(&k)?;
                return self.lin(t, &s, out, c);
            }
            if rest.len() == 1 {
                return self.lin(rest[0], scale, out, c);
            }
        }
        out.add(e, scale)
    }

    /// `domain.kept_product`, on Rust's `mul`, which refuses what it can't build exactly.
    fn kept_product(&mut self, factors: &[TermId]) -> Res<Option<TermId>> {
        COUNTS.product_terms.fetch_add(1, Relaxed);
        let t = self.t.mul(factors.to_vec())?;
        if self.flags(t) & IS_MUL == 0 {
            return Ok(None);
        }
        let mut got: Vec<TermId> = self.t.row(t).args.to_vec();
        let mut want = factors.to_vec();
        got.sort();
        want.sort();
        Ok((got == want).then_some(t))
    }

    /// `from_sympy(Mul(*closed), generic=...)`, lra_adapter.py:213. One factor builds nothing. For more, Rust's `mul` gives
    /// the term `Mul` would, and the field reads that. When `mul` refuses, Python builds it, and that's counted.
    fn closed_product(&mut self, closed: &[TermId]) -> Res<Option<Num>> {
        if closed.len() == 1 {
            COUNTS.closed_mul_direct.fetch_add(1, Relaxed);
            return self.from_sympy(closed[0]);
        }
        match self.t.mul(closed.to_vec()) {
            Ok(m) => {
                COUNTS.closed_mul_rust.fetch_add(1, Relaxed);
                self.from_sympy(m)
            }
            Err(_) => {
                COUNTS.closed_mul_scaffold.fetch_add(1, Relaxed);
                let objs = closed.iter().map(|f| self.object(*f)).collect::<Res<Vec<_>>>()?;
                let py = self.py;
                let mul = py.import("sympy.core.mul")?.getattr("Mul")?;
                let built = mul.call1(pyo3::types::PyTuple::new(py, objs)?)?;
                let kw = pyo3::types::PyDict::new(py);
                kw.set_item("generic", self.generic)?;
                let v = module(py)?.getattr("from_sympy")?.call((built,), Some(&kw))?;
                Ok(if v.is_none() { None } else { Some(Num::from_py(&v)?) })
            }
        }
    }

    // `_closed`, lra_adapter.py:225.
    fn closed(&mut self, e: TermId, scale: &Num, out: &mut Form, c: &mut Num) -> Res<()> {
        if !self.is_expr(e) {
            return Err(E::Refuse(Refuse("lra: a closed term that isn't an expression")));
        }
        let flags = self.flags(e);
        if flags & IS_RATIONAL != 0 {
            *c = c.add(&scale.mul(&big_rat(&self.rational(e)?))?)?;
            return Ok(());
        }
        let args: Vec<TermId> = self.t.row(e).args.to_vec();
        if flags & IS_ADD != 0 {
            for a in args {
                self.closed(a, scale, out, c)?;
            }
            return Ok(());
        }
        // c, rest = e.as_coeff_Mul(); a Float head has c.is_Rational False, a head of 1 has c == 1, and neither splits.
        if flags & IS_MUL != 0 {
            if flags & flag::PLAIN_OPS == 0 {
                return Err(E::Refuse(Refuse("lra: a Mul class with its own coefficient split")));
            }
            let head = args.first().copied();
            if let Some(h) = head {
                if self.flags(h) & IS_RATIONAL != 0 {
                    let r = self.rational(h)?;
                    if !r.is_one() {
                        let (_, rest) = self.t.coeff_mul(e)?;
                        let s = scale.mul(&big_rat(&r))?;
                        return self.closed(rest, &s, out, c);
                    }
                }
            }
        } else if flags & flag::PLAIN_OPS == 0 && self.t.class_of(e).flags & flag::IS_NUMBER == 0 && self.kind(e) != Kind::Float {
            return Err(E::Refuse(Refuse("lra: a class with its own coefficient split")));
        }
        if let Some(v) = self.from_sympy(e)? {
            *c = c.add(&scale.mul(&v)?)?;
            return Ok(());
        }
        if self.t.row(e).bits & fact::FLOAT != 0 {
            return Err(E::Unread);
        }
        if self.constant_bounds(e)?.is_none() {
            return Err(E::Unread);
        }
        out.add(e, scale)
    }

    /// R9: `lra_bounds.constant_bounds`, read-only on the input term.
    fn constant_bounds(&mut self, e: TermId) -> Res<Option<(Rat, Rat)>> {
        COUNTS.bounds.fetch_add(1, Relaxed);
        let o = self.object(e)?;
        let m = self.py.import("satassume.theories.lra.lra_bounds")?;
        let b = m.getattr("constant_bounds")?.call1((o,))?;
        if b.is_none() {
            return Ok(None);
        }
        Ok(Some((rat_of(&b.get_item(0)?)?, rat_of(&b.get_item(1)?)?)))
    }

    /// `from_sympy`, constfield.py:1353: `_Unread`, `Undecided` and `ZeroDivisionError` read as None.
    pub fn from_sympy(&mut self, e: TermId) -> Res<Option<Num>> {
        match self.from_sympy_(e) {
            Ok(v) => Ok(Some(v)),
            Err(E::Unread) => Ok(None),
            Err(E::Cf(x)) if x.is_undecided() || x.is_zero_div() => Ok(None),
            Err(E::Py(x)) => {
                let py = self.py;
                let m = module(py)?;
                if x.is_instance(py, &m.getattr("Undecided")?)
                    || x.is_instance_of::<PyZeroDivisionError>(py)
                    || x.is_instance(py, &m.getattr("_Unread")?)
                {
                    Ok(None)
                } else {
                    Err(E::Py(x))
                }
            }
            Err(x) => Err(x),
        }
    }

    fn registry(&self, name: &str) -> Res<Num> {
        COUNTS.registry.fetch_add(1, Relaxed);
        Ok(Num::from_py(&module(self.py)?.getattr(name)?)?)
    }

    // `_from_sympy`, constfield.py:1375.
    fn from_sympy_(&mut self, e: TermId) -> Res<Num> {
        if !self.is_expr(e) {
            return Err(E::Unread);
        }
        let flags = self.flags(e);
        if flags & IS_RATIONAL != 0 {
            return Ok(big_rat(&self.rational(e)?));
        }
        match self.kind(e) {
            Kind::Pi => return self.registry(if planted(PLANT_PI) { "E" } else { "PI" }),
            Kind::Exp1 => return self.registry("E"),
            _ => {}
        }
        let bits = self.t.row(e).bits;
        if bits & fact::READ == 0 {
            return Err(E::Refuse(Refuse("lra: a term whose facts weren't read")));
        }
        if self.free(e) || bits & (fact::FLOAT | fact::NAN | fact::BAD) != 0 {
            return Err(E::Unread);
        }
        let args: Vec<TermId> = self.t.row(e).args.to_vec();
        if flags & IS_ADD != 0 {
            let mut r = Num::zero();
            for a in args {
                r = r.add(&self.from_sympy_(a)?)?;
            }
            return Ok(r);
        }
        if flags & IS_MUL != 0 {
            let mut r = Num::one();
            for a in args {
                r = r.mul(&self.from_sympy_(a)?)?;
            }
            return Ok(r);
        }
        if flags & IS_POW != 0 {
            let (b, x) = (args[0], args[1]);
            if self.flags(x) & IS_INTEGER != 0 {
                let n = self.rational(x)?.n;
                if n.abs() <= BigInt::from(MAX_POW) {
                    return Ok(self.from_sympy_(b)?.pow(n.to_i64().unwrap())?);
                }
            }
            if self.flags(b) & IS_RATIONAL != 0 && self.flags(x) & IS_RATIONAL != 0 {
                let br = self.rational(b)?;
                let xr = self.rational(x)?;
                if br.n.is_positive() && xr.n.abs() <= BigInt::from(MAX_POW) && xr.d <= BigInt::from(MAX_POW) {
                    COUNTS.registry.fetch_add(1, Relaxed);
                    let v = module(self.py)?
                        .getattr("radical")?
                        .call1((big_rat(&br).to_py(self.py)?, xr.d.clone()))?;
                    return Ok(Num::from_py(&v)?.pow(xr.n.to_i64().unwrap())?);
                }
            }
        }
        if flags & flag::IS_EXP != 0 {
            if let Some(&a) = args.first() {
                if self.flags(a) & IS_INTEGER != 0 {
                    let n = self.rational(a)?.n;
                    if n.abs() <= BigInt::from(MAX_POW) {
                        return Ok(self.registry("E")?.pow(n.to_i64().unwrap())?);
                    }
                }
            }
        }
        if !self.generic {
            return Err(E::Unread);
        }
        COUNTS.generic.fetch_add(1, Relaxed);
        let o = self.object(e)?;
        Ok(Num::from_py(&module(self.py)?.getattr("_generic")?.call1((o,))?)?)
    }

    /// `sorted(terms, key=default_sort_key)`. Python computes a key for every term even when there's one, and a key can raise
    /// or read, so Rust asks for each too. Ties stay in input order, as a stable sort leaves them.
    fn sort_terms<T>(&mut self, items: &mut [T], id: impl Fn(&T) -> TermId) -> Res<()> {
        for it in items.iter() {
            COUNTS.keys.fetch_add(1, Relaxed);
            self.t.sort_key(id(it))?;
        }
        let mut err = None;
        let t = &*self.t;
        items.sort_by(|a, b| match t.key_cmp(id(a), id(b)) {
            Ok(o) => {
                if planted(PLANT_SORT) {
                    o.reverse()
                } else {
                    o
                }
            }
            Err(x) => {
                err.get_or_insert(x);
                std::cmp::Ordering::Equal
            }
        });
        match err {
            Some(x) => Err(E::Refuse(x)),
            None => Ok(()),
        }
    }

    // `_constraint`, lra_adapter.py:318.
    fn constraint(&mut self, name: &str, form: &Form, k: &Num) -> Res<Constraint> {
        let flip = name == "gt" || name == "ge";
        let name = match name {
            "gt" => "lt",
            "ge" => "le",
            n => n,
        };
        let mut k = if flip { k.neg() } else { k.clone() };
        let mut items = Vec::new();
        for (t, c) in &form.items {
            let c = if flip { c.neg() } else { c.clone() };
            if c.nonzero()? {
                items.push((*t, c));
            }
        }
        self.sort_terms(&mut items, |x| x.0)?;
        if (name == "eq" || name == "ne") && !planted(PLANT_NEGATE_EQ) && !items.is_empty() && items[0].1.lt(&Num::zero())? {
            for x in items.iter_mut() {
                x.1 = x.1.neg();
            }
            k = k.neg();
        }
        if items.is_empty() {
            // Python builds a dict of all four, so all four run, and any of them can raise.
            let z = Num::zero();
            let (lt, le, eq) = (k.lt(&z)?, k.le(&z)?, k.py_eq(&z)?);
            let ne = !k.py_eq(&z)?;
            return Ok(Constraint::Value(match name {
                "lt" => lt,
                "le" => le,
                "eq" => eq,
                _ => ne,
            }));
        }
        Ok(Constraint::Payload {
            items,
            rhs: k.neg(),
            strict: name == "lt",
            equality: name == "eq" || name == "ne",
            positive: name != "ne",
        })
    }

    // `_linear` and `interpret`, lra_adapter.py:289 and :337. `relation` is the caller's, so a name is one of the six.
    pub fn interpret(&mut self, name: &str, lhs: TermId, rhs: TermId) -> Res<Option<(Constraint, Vec<TermId>)>> {
        let r = (|| -> Res<_> {
            for s in [lhs, rhs] {
                if !self.is_expr(s) || self.has_bad(s)? {
                    return Err(E::Unread);
                }
            }
            let mut form = Form::default();
            let mut k = Num::zero();
            self.lin(lhs, &Num::one(), &mut form, &mut k)?;
            self.lin(rhs, &Num::one().neg(), &mut form, &mut k)?;
            let c = self.constraint(name, &form, &k)?;
            let mut terms: Vec<TermId> = form.items.iter().map(|x| x.0).collect();
            self.sort_terms(&mut terms, |x| *x)?;
            Ok((c, terms))
        })();
        self.unread(r)
    }

    /// `except _UNREAD: return None`, lra_adapter.py:152.
    fn unread<T>(&self, r: Res<T>) -> Res<Option<T>> {
        match r {
            Ok(v) => Ok(Some(v)),
            Err(E::Unread) => Ok(None),
            Err(E::Cf(x)) if x.is_undecided() || x.is_zero_div() => Ok(None),
            Err(E::Cf(CfErr::Py(x))) | Err(E::Py(x)) => {
                let py = self.py;
                if x.is_instance_of::<PyTypeError>(py)
                    || x.is_instance_of::<PyValueError>(py)
                    || x.is_instance_of::<PyZeroDivisionError>(py)
                    || x.is_instance(py, &module(py)?.getattr("Undecided")?)
                {
                    Ok(None)
                } else {
                    Err(E::Py(x))
                }
            }
            Err(x) => Err(x),
        }
    }

    // `_side`, lra_adapter.py:359.
    fn side(&mut self, e: TermId) -> Res<(Form, i8)> {
        if !self.plain_expr(e) {
            return Err(E::Unread);
        }
        let parts: Vec<TermId> =
            if self.flags(e) & IS_ADD != 0 { self.t.row(e).args.to_vec() } else { vec![e] };
        let mut inf = 0i8;
        let mut form = Form::default();
        let mut c = Num::zero();
        for t in parts {
            let sign = match self.kind(t) {
                Kind::Infinity => 1,
                Kind::NegativeInfinity => -1,
                _ => 0,
            };
            if sign != 0 {
                if inf != 0 && inf != sign {
                    return Err(E::Unread);
                }
                inf = sign;
                continue;
            }
            if self.has_bad(t)? {
                return Err(E::Unread);
            }
            self.lin(t, &Num::one(), &mut form, &mut c)?;
        }
        Ok((form, inf))
    }

    // `order_sides`, lra_adapter.py:382. The caller has checked the name is `lt`.
    pub fn order_sides(&mut self, a: TermId, b: TermId) -> Res<Option<((Form, i8), (Form, i8))>> {
        let r = (|| -> Res<_> { Ok((self.side(a)?, self.side(b)?)) })();
        self.unread(r)
    }

    // `integer_form`, lra_adapter.py:400.
    pub fn integer_form(&mut self, e: TermId) -> Res<Option<(Vec<(TermId, Num)>, Num, Vec<TermId>)>> {
        if !self.is_expr(e) || self.has_bad(e)? {
            return Ok(None);
        }
        let r = (|| -> Res<_> {
            let mut form = Form::default();
            let mut c = Num::zero();
            self.lin(e, &Num::one(), &mut form, &mut c)?;
            let mut keys: Vec<TermId> = form.items.iter().map(|x| x.0).collect();
            self.sort_terms(&mut keys, |x| *x)?;
            let mut items = Vec::new();
            for t in &keys {
                let v = &form.items[form.index[t]].1;
                if v.nonzero()? {
                    items.push((*t, v.clone()));
                }
            }
            // `bool(const[0])`, `bool(c == 1)`: an undecidable constant reads as "not read".
            c.nonzero()?;
            for (_, v) in &items {
                v.py_eq(&Num::one())?;
            }
            Ok((items, c, keys))
        })();
        self.unread(r)
    }

    // `closed_sign`, lra_adapter.py:254.
    pub fn closed_sign(&mut self, e: TermId) -> Res<(Option<i32>, bool)> {
        if let Some(v) = self.from_sympy(e)? {
            return match v.sign() {
                Ok(s) => Ok((Some(s), true)),
                Err(x) if x.is_undecided() => Ok((None, true)),
                Err(x) => Err(E::Cf(x)),
            };
        }
        let Some((lo, hi)) = self.constant_bounds(e)? else { return Ok((None, false)) };
        let z = Rat::ZERO;
        Ok((if lo >= z { Some(1) } else if hi <= z { Some(-1) } else { None }, true))
    }
}

/// A form as a list of `(id, coefficient)`, in dict order.
pub fn items_py<'py>(py: Python<'py>, items: &[(TermId, Num)]) -> PyResult<Bound<'py, PyList>> {
    let mut out = Vec::with_capacity(items.len());
    for (t, c) in items {
        out.push((t.0, c.to_py(py)?));
    }
    PyList::new(py, out)
}
