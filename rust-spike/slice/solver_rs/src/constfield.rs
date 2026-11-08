//! Port of satassume/theories/lra/constfield.py: exact numbers in Q(c1, ..., ck). Line numbers below are that file's.
//!
//! The reference is the Python module, exactly: the same normal form, the same size decisions, the same exception at
//! the same point, the same things evaluated in the same order. rust-spike/slice/test_cf_diff.py compares the two.
//!
//! Python stays the owner of: the registry (`_CONSTANTS`, read live by index; nothing about a constant is cached here
//! except the integers of an enclosure, tied to the very tuple in `Constant._cache`), `constant`, `radical`,
//! `_from_sympy`, `pi_laurent`, `to_sympy` and `__repr__` (used lazily for an Undecided's message).
//! Native here: the enclosures of pi, E and radicals, when `_enclose` is still the module's own. They fill
//! `Constant._cache` as Python does, so that state stays the same.
//!
//! Not the same as Python, by design, and invisible in the numbers: `_sympy_inner_gcd` is a primitive PRS here (the
//! monic gcd and cofactors are unique); `_enc`, `_hash`, `_size_`, `_vars` of a Python Element aren't read or written
//! (`_sign`, which can change an answer when limits change, is, both ways).
#![allow(dead_code)]

use crate::rat::Rat;
use num_bigint::BigInt;
use num_integer::Integer;
use num_traits::{One, Signed, ToPrimitive, Zero};
use pyo3::exceptions::{PyArithmeticError, PyTypeError, PyValueError, PyZeroDivisionError};
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{PyDict, PyFrozenSet, PySet, PyTuple};
use std::cell::{Cell, OnceCell, RefCell};
use std::collections::HashMap;
use std::hash::{Hash, Hasher};
use std::rc::Rc;
use std::sync::atomic::{AtomicU64, Ordering};

pub const MODULE: &str = "satassume.theories.lra.constfield";

// ---------------------------------------------------------------------------------------------------------------------
// errors
// ---------------------------------------------------------------------------------------------------------------------

/// Which `raise Undecided(...)` of the module, with the number its message names.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum UndecidedKind {
    Nonzero,
    Sign,
    Floor,
    NotInteger,
}

/// Which `raise TooLarge(...)`, with what its f-string reads at the raise.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum TooLargeKind {
    Coefficient(i64),
    Product,
    ProductTerms,
    CommonDenominator(i64),
    Checked(i64, i64, i64),
    Scale(i64),
    Budget(i64, i64, i64),
    Power(i128),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ZeroDivKind {
    /// Element's: "division by zero" (:1075, :1091).
    Element,
    /// Fraction's: `Fraction(1, 0)`. CPython 3.12 prints the zero's denominator, which is always 1.
    Fraction,
}

#[derive(Debug)]
pub enum CfErr {
    Undecided(UndecidedKind, Poly, Poly),
    TooLarge(TooLargeKind),
    ZeroDiv(ZeroDivKind),
    Arithmetic(&'static str),
    Py(PyErr),
}

pub type R<T> = Result<T, CfErr>;

impl CfErr {
    /// Python's `except Undecided`: TooLarge is a subclass, and a callback may raise either itself.
    pub fn is_undecided(&self) -> bool {
        match self {
            CfErr::Undecided(..) | CfErr::TooLarge(_) => true,
            CfErr::Py(e) => Python::attach(|py| {
                module(py).and_then(|m| m.getattr("Undecided")).map(|t| e.is_instance(py, &t)).unwrap_or(false)
            }),
            _ => false,
        }
    }

    /// Python's `except ZeroDivisionError`, also for a callback's.
    pub fn is_zero_div(&self) -> bool {
        match self {
            CfErr::ZeroDiv(_) => true,
            CfErr::Py(e) => Python::attach(|py| e.is_instance_of::<PyZeroDivisionError>(py)),
            _ => false,
        }
    }

    pub fn py_err(self, py: Python<'_>) -> PyResult<PyErr> {
        let m = module(py)?;
        Ok(match self {
            CfErr::Py(e) => e,
            CfErr::ZeroDiv(ZeroDivKind::Element) => PyZeroDivisionError::new_err("division by zero"),
            CfErr::ZeroDiv(ZeroDivKind::Fraction) => PyZeroDivisionError::new_err("Fraction(1, 0)"),
            CfErr::Arithmetic(s) => PyArithmeticError::new_err(s),
            CfErr::Undecided(kind, n, d) => {
                let el = new_py_element(py, &n, &d)?;
                let short: String = m.getattr("_short")?.call1((el,))?.extract()?;
                let text = match kind {
                    UndecidedKind::Nonzero => format!("cannot show {short} nonzero"),
                    UndecidedKind::Sign => format!("cannot decide the sign of {short}"),
                    UndecidedKind::Floor => format!("cannot decide the floor of {short}"),
                    UndecidedKind::NotInteger => format!("cannot show that {short} is no integer"),
                };
                PyErr::from_value(m.getattr("Undecided")?.call1((text,))?)
            }
            CfErr::TooLarge(kind) => {
                let text = match kind {
                    TooLargeKind::Coefficient(b) => format!("a coefficient exceeds {b} bits"),
                    TooLargeKind::Product => "a product exceeds the size budget".to_string(),
                    TooLargeKind::ProductTerms => "a product has more terms than the size budget".to_string(),
                    TooLargeKind::CommonDenominator(b) => format!("a common denominator exceeds {b} bits"),
                    TooLargeKind::Checked(deg, terms, bits) => {
                        format!("a number of degree {deg}, {terms} terms, {bits}-bit coefficients exceeds the size budget")
                    }
                    TooLargeKind::Scale(bits) => format!("{bits}-bit coefficients exceed the size budget"),
                    TooLargeKind::Budget(deg, bits, work) => format!(
                        "a result of degree {deg}, {bits}-bit coefficients, {work} term products exceeds the size budget"
                    ),
                    TooLargeKind::Power(deg) => format!("a power of degree {deg} exceeds the size budget"),
                };
                PyErr::from_value(m.getattr("TooLarge")?.call1((text,))?)
            }
        })
    }
}

impl From<CfErr> for PyErr {
    fn from(e: CfErr) -> PyErr {
        Python::attach(|py| e.py_err(py).unwrap_or_else(|x| x))
    }
}

impl From<PyErr> for CfErr {
    fn from(e: PyErr) -> CfErr {
        CfErr::Py(e)
    }
}

// ---------------------------------------------------------------------------------------------------------------------
// the Python module and the limits
// ---------------------------------------------------------------------------------------------------------------------

static MODULE_CELL: PyOnceLock<Py<PyModule>> = PyOnceLock::new();
static FRACTION: PyOnceLock<(Py<PyAny>, Py<PyAny>)> = PyOnceLock::new();

pub fn module(py: Python<'_>) -> PyResult<Bound<'_, PyModule>> {
    MODULE_CELL.get_or_try_init(py, || Ok(py.import(MODULE)?.unbind())).map(|m| m.bind(py).clone())
}

/// `(Fraction, Fraction._from_coprime_ints or Fraction)`.
fn fraction_types(py: Python<'_>) -> PyResult<&(Py<PyAny>, Py<PyAny>)> {
    FRACTION.get_or_try_init(py, || {
        let fr = py.import("fractions")?.getattr("Fraction")?;
        let make = fr.getattr_opt("_from_coprime_ints")?.unwrap_or_else(|| fr.clone());
        Ok((fr.unbind(), make.unbind()))
    })
}

/// constfield's module-level limits, as last read (see `refresh_limits`).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Limits {
    pub prec_start: i64,
    pub prec_cap: i64,
    pub max_degree: i64,
    pub max_terms: i64,
    pub max_bits: i64,
    pub max_work: i64,
    pub euclid_max_deg: i64,
}

thread_local! {
    static LIMITS: Cell<Option<Limits>> = const { Cell::new(None) };
    /// (constant index, prec) -> the tuple in `Constant._cache` and its integers. Tied to that object's identity.
    static ENCLOSURES: RefCell<HashMap<(u32, i64), (Py<PyAny>, Rc<(BigInt, BigInt)>)>> = RefCell::new(HashMap::new());
}

/// `ENCLOSURES`' bound (step 5c9a: a registry table is bounded; it had none), as `NativeTable.size` gives it.
pub(crate) const ENCLOSURES_SIZE: usize = 100_000;

/// memos.rs's accessors of `ENCLOSURES`.
pub(crate) fn enclosures_len() -> usize {
    ENCLOSURES.with(|m| m.borrow().len())
}

pub(crate) fn enclosures_clear() {
    ENCLOSURES.with(|m| m.borrow_mut().clear());
}

/// `[((index, prec), (lo, hi))]`, converted for the registry view's `items()`.
pub(crate) fn enclosures_items(p: Python<'_>) -> PyResult<Vec<(Py<PyAny>, Py<PyAny>)>> {
    ENCLOSURES.with(|m| {
        m.borrow().iter().map(|(k, (t, _))| Ok(((k.0, k.1).into_pyobject(p)?.into_any().unbind(), t.clone_ref(p)))).collect()
    })
}

fn read_limits(py: Python<'_>) -> PyResult<Limits> {
    let m = module(py)?;
    // Past i64 means "no limit" for anything a Poly can reach, as an unbounded Python int would.
    let read = |name: &str| -> PyResult<i64> {
        let x: BigInt = m.getattr(name)?.extract()?;
        Ok(x.to_i64().unwrap_or(if x.is_negative() { i64::MIN } else { i64::MAX }))
    };
    Ok(Limits {
        prec_start: read("PREC_START")?,
        prec_cap: read("PREC_CAP")?,
        max_degree: read("MAX_DEGREE")?,
        max_terms: read("MAX_TERMS")?,
        max_bits: read("MAX_BITS")?,
        max_work: read("MAX_WORK")?,
        euclid_max_deg: read("_EUCLID_MAX_DEG")?,
    })
}

/// Rereads the limits from the Python module. Call at hook entry when a session has constants.
pub fn refresh_limits() -> PyResult<()> {
    let l = Python::attach(read_limits)?;
    LIMITS.with(|c| c.set(Some(l)));
    Ok(())
}

/// The limits in force. The first read happens here; it can only fail if the Python module can't be imported, and no
/// Element can exist then.
#[inline]
pub fn lim() -> Limits {
    if let Some(l) = LIMITS.with(|c| c.get()) {
        return l;
    }
    let l = Python::attach(read_limits).expect("constfield's limits");
    LIMITS.with(|c| c.set(Some(l)));
    l
}

// ---------------------------------------------------------------------------------------------------------------------
// polynomials (:198-657): a rational, or (v, coefficients lowest first: at least two, the last nonzero)
// ---------------------------------------------------------------------------------------------------------------------

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub enum Poly {
    Q(Rat),
    T(u32, Rc<[Poly]>),
}
use Poly::{Q as PQ, T as PT};

#[inline]
fn pzero() -> Poly {
    PQ(Rat::ZERO)
}

#[inline]
fn pone() -> Poly {
    PQ(Rat::ONE)
}

#[inline]
fn is_zero(p: &Poly) -> bool {
    matches!(p, PQ(r) if r.is_zero())
}

#[inline]
fn r_is_one(r: &Rat) -> bool {
    matches!(r, Rat::S(1, 1))
}

pub fn rat_parts(r: &Rat) -> (BigInt, BigInt) {
    match r {
        Rat::S(n, d) => (BigInt::from(*n), BigInt::from(*d)),
        Rat::B(b) => (b.0.clone(), b.1.clone()),
    }
}

/// `numerator.bit_length()`.
#[inline]
pub fn num_bits(r: &Rat) -> i64 {
    match r {
        Rat::S(n, _) => (64 - n.unsigned_abs().leading_zeros()) as i64,
        Rat::B(b) => b.0.bits() as i64,
    }
}

/// `denominator.bit_length()`.
#[inline]
pub fn den_bits(r: &Rat) -> i64 {
    match r {
        Rat::S(_, d) => (64 - d.unsigned_abs().leading_zeros()) as i64,
        Rat::B(b) => b.1.bits() as i64,
    }
}

fn mk(v: u32, mut cs: Vec<Poly>) -> Poly {
    while matches!(cs.last(), Some(c) if is_zero(c)) {
        cs.pop();
    }
    match cs.len() {
        0 => pzero(),
        1 => cs.pop().unwrap(),
        _ => PT(v, cs.into()),
    }
}

/// `a`'s main variable is larger than `b`'s: `b` goes to the constant coefficient.
fn add_low(a: &Poly, b: &Poly) -> Poly {
    if is_zero(b) {
        return a.clone();
    }
    let PT(v, cs) = a else { unreachable!() };
    let mut out = Vec::with_capacity(cs.len());
    out.push(add(&cs[0], b));
    out.extend(cs[1..].iter().cloned());
    PT(*v, out.into())
}

pub fn add(a: &Poly, b: &Poly) -> Poly {
    match (a, b) {
        (PQ(x), PQ(y)) => PQ(x.add(y)),
        (PQ(_), PT(..)) => add_low(b, a),
        (PT(..), PQ(_)) => add_low(a, b),
        (PT(va, ca), PT(vb, cb)) => {
            if va == vb {
                let (ca, cb) = if ca.len() < cb.len() { (cb, ca) } else { (ca, cb) };
                let mut cs: Vec<Poly> = ca.iter().zip(cb.iter()).map(|(x, y)| add(x, y)).collect();
                cs.extend(ca[cb.len()..].iter().cloned());
                mk(*va, cs)
            } else if va < vb {
                add_low(b, a)
            } else {
                add_low(a, b)
            }
        }
    }
}

pub fn neg(p: &Poly) -> Poly {
    match p {
        PQ(r) => PQ(r.neg()),
        PT(v, cs) => PT(*v, cs.iter().map(neg).collect()),
    }
}

fn sub(a: &Poly, b: &Poly) -> Poly {
    add(a, &neg(b))
}

/// `c * p` for a nonzero `c`.
pub fn scale(p: &Poly, c: &Rat) -> Poly {
    match p {
        PQ(r) => PQ(r.mul(c)),
        PT(v, cs) => PT(*v, cs.iter().map(|x| scale(x, c)).collect()),
    }
}

pub fn mul(a: &Poly, b: &Poly) -> Poly {
    match (a, b) {
        (PQ(x), PQ(y)) => PQ(x.mul(y)),
        (PQ(x), _) => {
            if x.is_zero() {
                pzero()
            } else if r_is_one(x) {
                b.clone()
            } else {
                scale(b, x)
            }
        }
        (_, PQ(y)) => {
            if y.is_zero() {
                pzero()
            } else if r_is_one(y) {
                a.clone()
            } else {
                scale(a, y)
            }
        }
        (PT(va, ca), PT(vb, cb)) => {
            if va == vb {
                let mut out = vec![pzero(); ca.len() + cb.len() - 1];
                for (i, x) in ca.iter().enumerate() {
                    if is_zero(x) {
                        continue;
                    }
                    for (j, y) in cb.iter().enumerate() {
                        if !is_zero(y) {
                            out[i + j] = add(&out[i + j], &mul(x, y));
                        }
                    }
                }
                return PT(*va, out.into()); // the leading product is nonzero
            }
            let (a, ca, b) = if va < vb { (vb, cb, a) } else { (va, ca, b) };
            PT(*a, ca.iter().map(|x| mul(x, b)).collect())
        }
    }
}

#[inline]
fn too_many_bits(q: &Rat, max_bits: i64) -> bool {
    den_bits(q) > max_bits || num_bits(q) > max_bits
}

fn add_low_bounded(a: &Poly, b: &Poly) -> R<Poly> {
    if is_zero(b) {
        return Ok(a.clone());
    }
    let PT(v, cs) = a else { unreachable!() };
    let mut out = Vec::with_capacity(cs.len());
    out.push(add_bounded(&cs[0], b)?);
    out.extend(cs[1..].iter().cloned());
    Ok(PT(*v, out.into()))
}

pub fn add_bounded(a: &Poly, b: &Poly) -> R<Poly> {
    match (a, b) {
        (PQ(x), PQ(y)) => {
            let r = x.add(y);
            let m = lim().max_bits;
            if too_many_bits(&r, m) {
                return Err(CfErr::TooLarge(TooLargeKind::Coefficient(m)));
            }
            Ok(PQ(r))
        }
        (PQ(_), PT(..)) => add_low_bounded(b, a),
        (PT(..), PQ(_)) => add_low_bounded(a, b),
        (PT(va, ca), PT(vb, cb)) => {
            if va == vb {
                let (ca, cb) = if ca.len() < cb.len() { (cb, ca) } else { (ca, cb) };
                let mut cs = Vec::with_capacity(ca.len());
                for (x, y) in ca.iter().zip(cb.iter()) {
                    cs.push(add_bounded(x, y)?);
                }
                cs.extend(ca[cb.len()..].iter().cloned());
                Ok(mk(*va, cs))
            } else if va < vb {
                add_low_bounded(b, a)
            } else {
                add_low_bounded(a, b)
            }
        }
    }
}

pub fn mul_bounded(a: &Poly, b: &Poly) -> R<Poly> {
    let (PT(va, ca), PT(vb, cb)) = (a, b) else {
        return Ok(mul(a, b));
    };
    if va == vb {
        let mut out = vec![pzero(); ca.len() + cb.len() - 1];
        for (i, x) in ca.iter().enumerate() {
            if is_zero(x) {
                continue;
            }
            for (j, y) in cb.iter().enumerate() {
                if !is_zero(y) {
                    out[i + j] = add_bounded(&out[i + j], &mul_bounded(x, y)?)?;
                }
            }
        }
        return Ok(PT(*va, out.into()));
    }
    let (a, ca, b) = if va < vb { (vb, cb, a) } else { (va, ca, b) };
    let mut out = Vec::with_capacity(ca.len());
    for x in ca.iter() {
        out.push(mul_bounded(x, b)?);
    }
    Ok(PT(*a, out.into()))
}

/// The multiplication `_budget_product` picked (:976).
type MulFn = fn(&Poly, &Poly) -> R<Poly>;

fn mul_plain(a: &Poly, b: &Poly) -> R<Poly> {
    Ok(mul(a, b))
}

type Size = (i64, i64, i64);

#[inline]
fn mul_fast(sa: Size, sb: Size) -> bool {
    if crate::lra::mutant(102) {
        return sa.1.min(sb.1) * (sa.2 + sb.2 + 1) < lim().max_bits;
    }
    sa.1.min(sb.1) * (sa.2 + sb.2 + 1) <= lim().max_bits
}

pub fn mul_checked(a: &Poly, b: &Poly) -> R<Poly> {
    if matches!(a, PQ(_)) || matches!(b, PQ(_)) {
        return Ok(mul(a, b));
    }
    let (sa, sb) = (psize(a), psize(b));
    let l = lim();
    if sa.0 + sb.0 > l.max_degree || sa.2 + sb.2 > l.max_bits || sa.1 * sb.1 > l.max_work {
        return Err(CfErr::TooLarge(TooLargeKind::Product));
    }
    let r = if mul_fast(sa, sb) { mul(a, b) } else { mul_bounded(a, b)? };
    if psize(&r).1 > l.max_terms {
        return Err(CfErr::TooLarge(TooLargeKind::ProductTerms));
    }
    Ok(r)
}

pub fn pow_checked(p: &Poly, mut k: i64) -> R<Poly> {
    let mut r = pone();
    let mut p = p.clone();
    while k != 0 {
        if k & 1 != 0 {
            r = mul_checked(&r, &p)?;
        }
        k >>= 1;
        if k != 0 {
            p = mul_checked(&p, &p)?;
        }
    }
    Ok(r)
}

#[inline]
fn deg(p: &Poly, v: u32) -> usize {
    match p {
        PT(w, cs) if *w == v => cs.len() - 1,
        _ => 0,
    }
}

#[inline]
fn lc(p: &Poly, v: u32) -> &Poly {
    match p {
        PT(w, cs) if *w == v => cs.last().unwrap(),
        _ => p,
    }
}

fn lcrec(mut p: &Poly) -> &Rat {
    loop {
        match p {
            PQ(r) => return r,
            PT(_, cs) => p = cs.last().unwrap(),
        }
    }
}

fn shift(p: &Poly, v: u32, k: usize) -> Poly {
    if k == 0 {
        return p.clone();
    }
    let mut cs = vec![pzero(); k];
    cs.push(p.clone());
    PT(v, cs.into())
}

const INEXACT: CfErr = CfErr::Arithmetic("inexact polynomial division");

pub fn divexact(a: &Poly, b: &Poly) -> R<Poly> {
    if is_zero(a) {
        return Ok(pzero());
    }
    let (vb, cb) = match b {
        PQ(c) => return Ok(if r_is_one(c) { a.clone() } else { scale(a, &c.inv()) }),
        PT(v, cs) => (*v, cs),
    };
    let PT(va, ca) = a else { return Err(INEXACT) };
    let va = *va;
    if va < vb {
        return Err(INEXACT);
    }
    if va > vb {
        let mut out = Vec::with_capacity(ca.len());
        for c in ca.iter() {
            out.push(divexact(c, b)?);
        }
        return Ok(PT(va, out.into()));
    }
    if a == b {
        return Ok(pone());
    }
    let j = monomial(b);
    if j != 0 {
        if ca.iter().take(j).any(|c| !is_zero(c)) {
            return Err(INEXACT);
        }
        let l = lc_q(b);
        let rest: Vec<Poly> =
            if r_is_one(l) { ca[j..].to_vec() } else { ca[j..].iter().map(|c| scale(c, &l.inv())).collect() };
        return Ok(mk(va, rest));
    }
    if let (Some(x), Some(y)) = (rats(ca), rats(cb)) {
        return Ok(mk(va, udiv(&x, &y)?.into_iter().map(PQ).collect()));
    }
    let db = cb.len() - 1;
    let lb = &cb[db];
    let mut q = vec![pzero(); ca.len().saturating_sub(db)];
    let mut r = a.clone();
    while !is_zero(&r) {
        let dr = deg(&r, va);
        if dr < db {
            return Err(INEXACT);
        }
        let t = divexact(lc(&r, va), lb)?;
        let m = mul(&shift(&t, va, dr - db), b);
        q[dr - db] = t;
        r = sub(&r, &m);
    }
    Ok(mk(va, q))
}

/// `b`'s leading coefficient, known rational (`monomial(b) != 0`).
fn lc_q(b: &Poly) -> &Rat {
    let PT(_, cs) = b else { unreachable!() };
    let PQ(l) = cs.last().unwrap() else { unreachable!() };
    l
}

fn monomial(p: &Poly) -> usize {
    let PT(_, cs) = p else { unreachable!() };
    if !matches!(cs.last(), Some(PQ(_))) {
        return 0;
    }
    if cs[..cs.len() - 1].iter().any(|c| !is_zero(c)) {
        return 0;
    }
    cs.len() - 1
}

fn order(p: &Poly) -> usize {
    let PT(_, cs) = p else { unreachable!() };
    cs.iter().position(|c| !is_zero(c)).expect("zero coefficient list")
}

/// The coefficients as rationals, if all are (a univariate polynomial).
fn rats(cs: &[Poly]) -> Option<Vec<Rat>> {
    cs.iter()
        .map(|c| match c {
            PQ(r) => Some(r.clone()),
            _ => None,
        })
        .collect()
}

fn udiv(a: &[Rat], b: &[Rat]) -> R<Vec<Rat>> {
    let mut r = a.to_vec();
    let db = b.len() - 1;
    let lb = &b[db];
    if r.len() <= db {
        return Err(INEXACT);
    }
    let mut q = vec![Rat::ZERO; r.len() - db];
    for k in (0..r.len() - db).rev() {
        let f = r[k + db].div(lb);
        if !f.is_zero() {
            for i in 0..db {
                r[k + i] = r[k + i].sub(&f.mul(&b[i]));
            }
        }
        q[k] = f;
    }
    if r[..db].iter().any(|x| !x.is_zero()) {
        return Err(INEXACT);
    }
    Ok(q)
}

fn monic(p: &Poly) -> Poly {
    let l = lcrec(p);
    if r_is_one(l) {
        p.clone()
    } else {
        scale(p, &l.inv())
    }
}

fn ugcd(a: &[Rat], b: &[Rat]) -> Vec<Rat> {
    let (mut a, mut b) = (a.to_vec(), b.to_vec());
    if a.len() < b.len() {
        std::mem::swap(&mut a, &mut b);
    }
    let l = b.last().unwrap().clone();
    if !r_is_one(&l) {
        b = b.iter().map(|c| c.div(&l)).collect();
    }
    loop {
        let db = b.len() - 1;
        while a.len() > db {
            let f = a.pop().unwrap();
            let s = a.len() - db;
            for i in 0..db {
                a[s + i] = a[s + i].sub(&f.mul(&b[i]));
            }
            while matches!(a.last(), Some(x) if x.is_zero()) {
                a.pop();
            }
        }
        if a.is_empty() {
            return b;
        }
        if a.len() == 1 {
            return vec![Rat::ONE];
        }
        let l = a.last().unwrap().clone();
        let next = if r_is_one(&l) { a } else { a.iter().map(|c| c.div(&l)).collect() };
        a = std::mem::replace(&mut b, next);
    }
}

/// `(g, a/g, b/g)` for nonzero polynomials, `g` their monic gcd (:510).
pub fn inner_gcd(a: &Poly, b: &Poly) -> R<(Poly, Poly, Poly)> {
    let (PT(va, ca), PT(vb, cb)) = (a, b) else {
        return Ok((pone(), a.clone(), b.clone()));
    };
    if a == b {
        let l = lcrec(a);
        let g = if r_is_one(l) { a.clone() } else { scale(a, &l.inv()) };
        return Ok((g, PQ(l.clone()), PQ(l.clone())));
    }
    if va == vb {
        let (ma, mb) = (monomial(a), monomial(b));
        if ma != 0 || mb != 0 {
            let x = if ma != 0 { ma } else { order(a) };
            let y = if mb != 0 { mb } else { order(b) };
            let j = x.min(y);
            if j == 0 {
                return Ok((pone(), a.clone(), b.clone()));
            }
            let g = shift(&pone(), *va, j);
            let (fa, fb) = (divexact(a, &g)?, divexact(b, &g)?);
            return Ok((g, fa, fb));
        }
        let e = lim().euclid_max_deg;
        if ca.len() as i64 <= e + 1 && cb.len() as i64 <= e + 1 {
            if let (Some(x), Some(y)) = (rats(ca), rats(cb)) {
                let g = ugcd(&x, &y);
                if g.len() == 1 {
                    return Ok((pone(), a.clone(), b.clone()));
                }
                let fa = mk(*va, udiv(&x, &g)?.into_iter().map(PQ).collect());
                let fb = mk(*va, udiv(&y, &g)?.into_iter().map(PQ).collect());
                return Ok((PT(*va, g.into_iter().map(PQ).collect()), fa, fb));
            }
        }
    }
    sympy_inner_gcd(a, b)
}

fn denominators(p: &Poly, acc: BigInt) -> R<BigInt> {
    match p {
        PQ(q) => {
            let d = match q {
                Rat::S(_, d) => BigInt::from(*d),
                Rat::B(b) => b.1.clone(),
            };
            if (&acc % &d).is_zero() {
                return Ok(acc);
            }
            let acc = &acc * &d / acc.gcd(&d);
            let m = lim().max_bits;
            if acc.bits() as i64 > m {
                return Err(CfErr::TooLarge(TooLargeKind::CommonDenominator(m)));
            }
            Ok(acc)
        }
        PT(_, cs) => {
            let mut acc = acc;
            for c in cs.iter() {
                acc = denominators(c, acc)?;
            }
            Ok(acc)
        }
    }
}

/// Top-level gcds answered by `heu_gcd`, and by the callback to Python. Written only, never read to choose a route.
static GCD_HEURISTIC: AtomicU64 = AtomicU64::new(0);
static GCD_CALLBACK: AtomicU64 = AtomicU64::new(0);
/// Rounds `heu_gcd` gave up at the size guard, at any level of its recursion. Written only, like the two above.
static GCD_GUARD: AtomicU64 = AtomicU64::new(0);
/// The largest `image_bits` seen. Written only: it shows how close a run came to the limit.
static GCD_MAX_IMAGE: AtomicU64 = AtomicU64::new(0);

/// The size guard's limit on `image_bits`, in bits. A fixed number, so the route depends on the input alone. Set by
/// `gcd_probe.py` with the guard off: at most 1 s up to about this size, then steep (36,024 bits 0.91 s, 90,908 bits 31 s,
/// where Python took under 1 s). It bounds each image, not the whole gcd. Plant 113 removes the guard.
const MAX_IMAGE_BITS: u64 = 1 << 15;

/// Python's `_sympy_inner_gcd` itself, for what `heu_gcd` gives up on: read-only on its inputs, and Python's behaviour
/// on hard inputs comes with it, including any stall of its own. Scaffolding: on the backend PR list with porting
/// SymPy's gcd.
fn python_inner_gcd(a: &Poly, b: &Poly) -> R<(Poly, Poly, Poly)> {
    GCD_CALLBACK.fetch_add(1, Ordering::Relaxed);
    Ok(Python::attach(|py| -> PyResult<(Poly, Poly, Poly)> {
        let r = module(py)?.getattr("_sympy_inner_gcd")?.call1((poly_to_py(py, a)?, poly_to_py(py, b)?))?;
        let t = r.cast::<PyTuple>().map_err(PyErr::from)?;
        Ok((poly_from_py(&t.get_item(0)?)?, poly_from_py(&t.get_item(1)?)?, poly_from_py(&t.get_item(2)?)?))
    })?)
}

/// Plant 108: a common divisor that isn't the greatest, `g` less the gcd of its coefficients in its main variable.
fn plant_drop_content(g: &Poly) -> Poly {
    let PT(_, cs) = g else { return g.clone() };
    let content = cs.iter().filter(|c| !is_zero(c)).try_fold(pzero(), |acc, c| {
        if is_zero(&acc) {
            Some(integer_primitive(c))
        } else {
            heu_gcd(&acc, &integer_primitive(c))
        }
    });
    match content {
        Some(c) if !matches!(c, PQ(_)) => divexact(g, &c).unwrap_or_else(|_| g.clone()),
        _ => g.clone(),
    }
}

/// What Python's `_sympy_inner_gcd` (:577) answers, with the same TooLarge first; the gcd itself is exact here.
pub fn sympy_inner_gcd(a: &Poly, b: &Poly) -> R<(Poly, Poly, Poly)> {
    denominators(a, BigInt::one())?;
    denominators(b, BigInt::one())?;
    let heuristic =
        if crate::lra::mutant(112) { None } else { heu_gcd(&integer_primitive(a), &integer_primitive(b)) };
    let Some(g) = heuristic else {
        return python_inner_gcd(a, b);
    };
    GCD_HEURISTIC.fetch_add(1, Ordering::Relaxed);
    let g = if crate::lra::mutant(108) { plant_drop_content(&g) } else { g };
    if matches!(g, PQ(_)) {
        return Ok((pone(), a.clone(), b.clone()));
    }
    let g = monic(&g);
    let fa = divexact(a, &g)?;
    let fb = divexact(b, &g)?;
    if crate::lra::mutant(104) {
        // the unscaled cofactor of a non-monic representative
        return Ok((g, scale(&fa, &Rat::S(2, 1)), fb));
    }
    Ok((g, fa, fb))
}

/// The same polynomial times a rational: integer coefficients, coprime.
fn integer_primitive(p: &Poly) -> Poly {
    fn walk(p: &Poly, den: &mut BigInt, num: &mut BigInt) {
        match p {
            PQ(r) => {
                if !r.is_zero() {
                    let (n, d) = rat_parts(r);
                    *num = num.gcd(&n);
                    *den = den.lcm(&d);
                }
            }
            PT(_, cs) => cs.iter().for_each(|c| walk(c, den, num)),
        }
    }
    let (mut den, mut num) = (BigInt::one(), BigInt::zero());
    walk(p, &mut den, &mut num);
    if num.is_zero() {
        return p.clone();
    }
    let g = den.gcd(&num);
    let f = Rat::norm_big(&den / &g, &num / &g);
    if r_is_one(&f) {
        p.clone()
    } else {
        scale(p, &f)
    }
}

/// `2**(sum of p's degree in each variable) * (sum of the absolute values of its coefficients)`, an integer polynomial's
/// bound on the coefficients of any factor (see `heu_gcd`).
fn factor_bound(p: &Poly) -> BigInt {
    fn walk(p: &Poly, degs: &mut Vec<(u32, usize)>, norm: &mut BigInt) {
        match p {
            PQ(r) => *norm += rat_parts(r).0.abs(),
            PT(v, cs) => {
                match degs.iter_mut().find(|d| d.0 == *v) {
                    Some(d) => d.1 = d.1.max(cs.len() - 1),
                    None => degs.push((*v, cs.len() - 1)),
                }
                cs.iter().for_each(|c| walk(c, degs, norm));
            }
        }
    }
    let (mut degs, mut norm) = (Vec::new(), BigInt::zero());
    walk(p, &mut degs, &mut norm);
    norm << degs.iter().map(|d| d.1).sum::<usize>()
}

/// The gcd of an integer polynomial's coefficients, added to `acc`.
fn int_content(p: &Poly, acc: BigInt) -> BigInt {
    match p {
        PQ(r) => acc.gcd(&rat_parts(r).0),
        PT(_, cs) => cs.iter().fold(acc, |a, c| int_content(c, a)),
    }
}

/// The bits of `p`'s largest integer coefficient.
fn coeff_bits(p: &Poly) -> u64 {
    match p {
        PQ(r) => rat_parts(r).0.bits(),
        PT(_, cs) => cs.iter().map(coeff_bits).max().unwrap_or(0),
    }
}

/// An estimate of the size of `p` evaluated at `x`: the bits of `x` times the degree in `v`, plus the coefficient bits.
fn image_bits(p: &Poly, v: u32, x: &BigInt) -> u64 {
    let deg = match p {
        PT(w, cs) if *w == v => cs.len() as u64 - 1,
        _ => 0,
    };
    x.bits().saturating_mul(deg).saturating_add(coeff_bits(p))
}

fn int_rat(n: &BigInt) -> Rat {
    Rat::norm_big(n.clone(), BigInt::one())
}

/// `p` with `v`, its largest variable or above, set to `x`.
fn eval_top(p: &Poly, v: u32, x: &Rat) -> Poly {
    match p {
        PT(w, cs) if *w == v => {
            let mut r = pzero();
            for c in cs.iter().rev() {
                r = add(&scale(&r, x), c);
            }
            r
        }
        _ => p.clone(),
    }
}

/// `p` coefficient by coefficient into `(-x/2, x/2]`.
fn symmetric_mod(p: &Poly, x: &BigInt) -> Poly {
    match p {
        PQ(r) => {
            let m = rat_parts(r).0.mod_floor(x);
            PQ(int_rat(&if &m + &m > *x { m - x } else { m }))
        }
        PT(v, cs) => mk(*v, cs.iter().map(|c| symmetric_mod(c, x)).collect()),
    }
}

/// The polynomial in `v` whose value at `x` is `h`, read off in base `x` with symmetric digits.
fn interpolate(h: &Poly, x: &BigInt, v: u32) -> Poly {
    let inv = int_rat(x).inv();
    let (mut h, mut digits) = (h.clone(), Vec::new());
    while !is_zero(&h) {
        let d = symmetric_mod(&h, x);
        h = scale(&sub(&h, &d), &inv);
        digits.push(d);
    }
    mk(v, digits)
}

/// `dmp_zz_heu_gcd`'s method on integer polynomials: evaluate the top variable `v` at a large integer `x`, take the gcd of
/// the images, read the gcd back from its image in base `x` and keep it only if it divides both. `None` when six points
/// fail, and the caller asks Python. Pure: nothing here reads a clock, a process counter or an earlier query.
///
/// It isn't SymPy's: it has no cofactor retries, and `x` starts above a bound on factors, not at SymPy's `2*min(norm)+29`
/// or lower, so SymPy's correctness doesn't transfer. An accepted candidate is the greatest divisor, by this argument.
/// Let `f, g` have coprime contents (the common `k` is taken out first) and `B = min(factor_bound(f), factor_bound(g))`,
/// `x > 2*B + 2`. The recursion gives `y = gcd(f(x), g(x))`, nonzero, in the lower variables, by induction on them. `h`,
/// the digits of `y`, has `h(x) = y` and coefficients in `(-x/2, x/2]`; write `h = n*p` with `p` primitive and `n` an
/// integer, so `|n| <= x/2`. Suppose `p` divides `f` and `g`, so the true gcd is `G = p*c` over the integers. `G(x)`
/// divides `y = n*p(x)`, so `c(x)` divides `n`: it's a nonzero integer `m` with `|m| <= x/2`, not a polynomial.
/// - If `v` isn't in `c`, then `c = m`, and `G` is primitive because the contents are coprime, so `m = +-1`: `p` is `G`.
/// - If `v` is in `c`, then `c - m = (v - x)*q` for a nonzero integer polynomial `q`. On the unit torus `|v - x| >= x - 1`,
///   so by Parseval the 2-norm of `(v - x)*q` is at least `(x - 1)*|q|_2 >= x - 1`, and `|c|_2 >= x - 1 - |m| >= x/2 - 1`.
///   But `c` divides `f`, and Mahler's measure is multiplicative and at least 1 on nonzero integer polynomials, so
///   `|c|_1 <= 2**(sum of c's degrees) * M(c) <= 2**(sum of f's degrees) * M(f) <= factor_bound(f)`, using `M(f) <= |f|_1`,
///   and the same for `g`. So `x/2 - 1 <= B`, a contradiction. The two inequalities are (4) and (5) of K. Mahler, "On some
///   inequalities for polynomials in several variables", J. London Math. Soc. 37 (1962) 341-344, reprinted in Documenta
///   Mathematica, Extra Volume Mahler Selecta (2019) 619-623.
/// SymPy's sup-norm start doesn't support the second case with several variables, since `|f|_2` isn't bounded by the
/// largest coefficient alone. Larger points cost larger integers, not correctness.
fn heu_gcd(f: &Poly, g: &Poly) -> Option<Poly> {
    let (cf, cg) = (int_content(f, BigInt::zero()), int_content(g, BigInt::zero()));
    let k = cf.gcd(&cg);
    let v = match (f, g) {
        (PT(a, _), PT(b, _)) => *a.max(b),
        (PT(a, _), _) | (_, PT(a, _)) => *a,
        _ => return Some(PQ(int_rat(&k))),
    };
    let kr = int_rat(&k);
    let kinv = kr.inv();
    let (f, g) = (scale(f, &kinv), scale(g, &kinv));
    let mut x = (factor_bound(&f).min(factor_bound(&g)) * 2u32) + 29u32;
    for _ in 0..6 {
        // The guard: x grows every round and the recursion multiplies sizes, so it's checked here and not up front.
        let bits = image_bits(&f, v, &x).max(image_bits(&g, v, &x));
        GCD_MAX_IMAGE.fetch_max(bits, Ordering::Relaxed);
        if bits > MAX_IMAGE_BITS && !crate::lra::mutant(113) {
            GCD_GUARD.fetch_add(1, Ordering::Relaxed);
            return None;
        }
        let xr = int_rat(&x);
        let (ff, gg) = (eval_top(&f, v, &xr), eval_top(&g, v, &xr));
        if !is_zero(&ff) && !is_zero(&gg) {
            let image = heu_gcd(&ff, &gg)?;
            let h = integer_primitive(&interpolate(&image, &x, v));
            // Plant 111 accepts without the division.
            if !is_zero(&h) && (crate::lra::mutant(111) || (divexact(&f, &h).is_ok() && divexact(&g, &h).is_ok())) {
                return Some(scale(&h, &kr));
            }
        }
        // SymPy's step, `73794*x*isqrt(isqrt(x))//27011`.
        x = &x * 73794u32 * x.sqrt().sqrt() / 27011u32;
    }
    None
}

/// `_gcd` (:595): monic; 0 for two zeros.
pub fn gcd(a: &Poly, b: &Poly) -> R<Poly> {
    if is_zero(a) {
        return Ok(if is_zero(b) { pzero() } else { monic(b) });
    }
    if is_zero(b) {
        return Ok(monic(a));
    }
    Ok(inner_gcd(a, b)?.0)
}

pub fn psize(p: &Poly) -> Size {
    let cs = match p {
        PQ(q) => return (0, if q.is_zero() { 0 } else { 1 }, num_bits(q).max(den_bits(q))),
        PT(_, cs) => cs,
    };
    if cs.iter().all(|c| matches!(c, PQ(_))) {
        let (mut terms, mut bits) = (0, 0);
        for c in cs.iter() {
            let PQ(c) = c else { unreachable!() };
            if !c.is_zero() {
                terms += 1;
                bits = bits.max(num_bits(c)).max(den_bits(c));
            }
        }
        return (cs.len() as i64 - 1, terms, bits);
    }
    let (mut dg, mut terms, mut bits) = (0, 0, 0);
    for (k, c) in cs.iter().enumerate() {
        if is_zero(c) {
            continue;
        }
        let (d, t, b) = psize(c);
        dg = dg.max(d + k as i64);
        terms += t;
        bits = bits.max(b);
    }
    (dg, terms, bits)
}

/// `_vars`: the distinct variables in the order `out.add` first sees them. A set's iteration order depends on it.
fn vars_seq(p: &Poly, out: &mut Vec<u32>) {
    if let PT(v, cs) = p {
        if !out.contains(v) {
            out.push(*v);
        }
        cs.iter().for_each(|c| vars_seq(c, out));
    }
}

// ---------------------------------------------------------------------------------------------------------------------
// interval evaluation (:664-687)
// ---------------------------------------------------------------------------------------------------------------------

type Pair = (BigInt, BigInt);

pub fn qenc(q: &Rat, prec: i64) -> Pair {
    let (n, d) = rat_parts(q);
    let n = n << prec as usize;
    let lo = n.div_floor(&d);
    let hi = if (&lo * &d) == n { lo.clone() } else { &lo + 1 };
    (lo, hi)
}

type Env = Vec<(u32, Rc<Pair>)>;

fn ieval(p: &Poly, prec: i64, env: &Env) -> Pair {
    let (v, cs) = match p {
        PQ(q) => return qenc(q, prec),
        PT(v, cs) => (*v, cs),
    };
    let t = &env.iter().find(|e| e.0 == v).expect("a constant outside the environment").1;
    let (tl, th) = (&t.0, &t.1);
    let (mut lo, mut hi) = ieval(cs.last().unwrap(), prec, env);
    let sh = prec as usize;
    for c in cs[..cs.len() - 1].iter().rev() {
        let (a, b, x, y) = (&lo * tl, &lo * th, &hi * tl, &hi * th);
        let mn = a.clone().min(b.clone()).min(x.clone()).min(y.clone());
        let mx = a.max(b).max(x).max(y);
        lo = mn >> sh;
        hi = -((-mx) >> sh);
        if !is_zero(c) {
            let (cl, ch) = ieval(c, prec, env);
            lo += cl;
            hi += ch;
        }
    }
    (lo, hi)
}

// ---------------------------------------------------------------------------------------------------------------------
// constants (:694-820): the registry is Python's
// ---------------------------------------------------------------------------------------------------------------------

fn py_constant<'py>(py: Python<'py>, i: u32) -> PyResult<Bound<'py, PyAny>> {
    module(py)?.getattr("_CONSTANTS")?.get_item(i)
}

fn transcendental(i: u32) -> R<bool> {
    Ok(Python::attach(|py| py_constant(py, i)?.getattr("transcendental")?.is_truthy())?)
}

fn scaled_down(val: BigInt, err: BigInt, guard: usize) -> Pair {
    (((&val - &err) >> guard), -((-(val + err)) >> guard))
}

fn atan_inv(x: u32, w: usize) -> (BigInt, BigInt) {
    let mut power = (BigInt::one() << w) / x;
    let x2 = x * x;
    let mut s = BigInt::zero();
    let mut k: u64 = 0;
    while !power.is_zero() {
        let term = &power / (2 * k + 1);
        if k & 1 != 0 {
            s -= term;
        } else {
            s += term;
        }
        power /= x2;
        k += 1;
    }
    (s, BigInt::from(3 * (k + 2)))
}

pub fn pi_enclose(prec: i64) -> Pair {
    let g: usize = if crate::lra::mutant(105) { 31 } else { 32 };
    let w = prec as usize + g;
    let (a, ea) = atan_inv(5, w);
    let (b, eb) = atan_inv(239, w);
    scaled_down(16 * a - 4 * b, 16 * ea + 4 * eb, g)
}

pub fn e_enclose(prec: i64) -> Pair {
    let g = 32usize;
    let w = prec as usize + g;
    let mut term = BigInt::one() << w;
    let mut s = BigInt::zero();
    let mut k: u64 = 0;
    while !term.is_zero() {
        s += &term;
        k += 1;
        term /= k;
    }
    scaled_down(s, BigInt::from(2 * k + 4), g)
}

fn iroot(n: &BigInt, b: u32) -> BigInt {
    if *n < BigInt::from(2) {
        return n.clone();
    }
    let sh = (n.bits() as usize).div_ceil(b as usize);
    let mut x = BigInt::one() << sh;
    let b1 = BigInt::from(b - 1);
    loop {
        let y = (&b1 * &x + n / x.pow(b - 1)) / b;
        if y >= x {
            return x;
        }
        x = y;
    }
}

/// The closure `radical` makes (:810).
pub fn root_enclose(p: &BigInt, q: &BigInt, b: u32, prec: i64) -> Pair {
    let n = p << (b as usize * prec as usize);
    let lo = iroot(&n.div_floor(q), b);
    let up = -((-&n).div_floor(q));
    let mut hi = iroot(&up, b);
    if hi.pow(b) < up {
        hi += 1;
    }
    (lo, hi)
}

enum Native {
    Pi,
    E,
    Root(BigInt, BigInt, u32),
}

/// A function of this module's still in its place under its own name, so a test's replacement never looks native.
fn own_fn<'py>(m: &Bound<'py, PyModule>, name: &str, f: &Bound<'py, PyAny>) -> PyResult<bool> {
    let g = m.getattr(name)?;
    Ok(f.is(&g) && g.getattr("__qualname__")?.extract::<String>()? == name)
}

fn native_of(py: Python<'_>, c: &Bound<'_, PyAny>) -> PyResult<Option<Native>> {
    let m = module(py)?;
    let f = c.getattr("_enclose")?;
    if own_fn(&m, "_pi_enclose", &f)? {
        return Ok(Some(Native::Pi));
    }
    if own_fn(&m, "_e_enclose", &f)? {
        return Ok(Some(Native::E));
    }
    // ("root", r, b), and the very closure of `radical`'s code
    let key = c.getattr("key")?;
    let Ok(key) = key.cast::<PyTuple>() else { return Ok(None) };
    if key.len() != 3 || !key.get_item(0)?.eq("root")? {
        return Ok(None);
    }
    let Some(code) = f.getattr_opt("__code__")? else { return Ok(None) };
    let radical_code = m.getattr("radical")?.getattr("__code__")?;
    let consts = radical_code.getattr("co_consts")?;
    let mut own = false;
    for x in consts.try_iter()? {
        own |= x?.is(&code);
    }
    if !own {
        return Ok(None);
    }
    let (r, b) = (key.get_item(1)?, key.get_item(2)?);
    let Ok(b) = b.extract::<u32>() else { return Ok(None) };
    let (p, q) = rat_parts(&rat_of(&r)?);
    Ok(Some(Native::Root(p, q, b)))
}

/// `_CONSTANTS[i].enclose(prec)` (:718): the same lookup in `_cache`, the same store. On a miss a native enclosure of a
/// module-own `_enclose`, or the Python method, which keeps its `lo <= hi` check and whatever a callback raises.
fn enclose(i: u32, prec: i64) -> R<Rc<Pair>> {
    Python::attach(|py| -> R<Rc<Pair>> {
        let c = py_constant(py, i)?;
        let cache = c.getattr("_cache")?;
        let cache = cache.cast::<PyDict>().map_err(PyErr::from)?;
        let hit = cache.get_item(prec)?.filter(|r| !r.is_none());
        let r = match hit {
            Some(r) => r,
            None => match native_of(py, &c)? {
                Some(n) => {
                    let (lo, hi) = match n {
                        Native::Pi => pi_enclose(prec),
                        Native::E => e_enclose(prec),
                        Native::Root(p, q, b) => root_enclose(&p, &q, b, prec),
                    };
                    let t = PyTuple::new(py, [lo.into_pyobject(py)?, hi.into_pyobject(py)?])?.into_any();
                    cache.set_item(prec, &t)?;
                    t
                }
                None => c.call_method1("enclose", (prec,))?,
            },
        };
        let known = ENCLOSURES.with(|m| {
            m.borrow().get(&(i, prec)).and_then(|(o, p)| if o.bind(py).is(&r) { Some(p.clone()) } else { None })
        });
        if let Some(p) = known {
            return Ok(p);
        }
        let (lo, hi): (BigInt, BigInt) = r.extract()?;
        let p = Rc::new((lo, hi));
        ENCLOSURES.with(|m| {
            let mut m = m.borrow_mut();
            if m.len() >= ENCLOSURES_SIZE {
                crate::session::tick(crate::session::MEMO_FULL);
                m.clear();
            }
            m.insert((i, prec), (r.unbind(), p.clone()))
        });
        Ok(p)
    })
}

/// The iteration order of the set (or frozenset of a set) Python's `_vars` would build. Only callbacks can see it: it
/// says which of two raising callbacks wins.
fn set_order(seq: &[u32], frozen: bool) -> R<Vec<u32>> {
    if seq.len() < 2 {
        return Ok(seq.to_vec());
    }
    Ok(Python::attach(|py| -> PyResult<Vec<u32>> {
        let s = PySet::empty(py)?;
        for v in seq {
            s.add(*v)?;
        }
        let it = if frozen { py.get_type::<PyFrozenSet>().call1((&s,))? } else { s.into_any() };
        it.try_iter()?.map(|x| x?.extract::<u32>()).collect()
    })?)
}

fn env(prec: i64, order: &[u32]) -> R<Env> {
    let mut e = Vec::with_capacity(order.len());
    for i in order {
        e.push((*i, enclose(*i, prec)?));
    }
    Ok(e)
}

// ---------------------------------------------------------------------------------------------------------------------
// elements (:906-1277)
// ---------------------------------------------------------------------------------------------------------------------

#[derive(Debug)]
pub struct Elem {
    n: Poly,
    d: Poly,
    sign: Cell<Option<i32>>,
    enc: RefCell<Option<(i64, Rc<Pair>)>>,
    size: Cell<Option<Size>>,
    /// `_varset`: first-seen order, then Python's iteration order.
    seq: OnceCell<Vec<u32>>,
    order: OnceCell<Vec<u32>>,
    /// The Python object this one came from or went to: `e + 0` is `e`, also after the boundary.
    py: OnceCell<Py<PyAny>>,
    /// Element._new step: a weak reference to the Rust `Element` pyclass this one last went to Python as, so a second crossing
    /// gives the same object while the first is alive (`e + 0` is `e`), with no cycle through the pyclass's `Rc`.
    pyw: RefCell<Option<Py<PyAny>>>,
}

fn elem(n: Poly, d: Poly) -> Rc<Elem> {
    Rc::new(Elem {
        n,
        d,
        sign: Cell::new(None),
        enc: RefCell::new(None),
        size: Cell::new(None),
        seq: OnceCell::new(),
        order: OnceCell::new(),
        py: OnceCell::new(),
        pyw: RefCell::new(None),
    })
}

impl Elem {
    pub fn numerator(&self) -> &Poly {
        &self.n
    }

    pub fn denominator(&self) -> &Poly {
        &self.d
    }

    fn size(&self) -> Size {
        if let Some(s) = self.size.get() {
            return s;
        }
        let (a, b) = (psize(&self.n), psize(&self.d));
        let s = (a.0.max(b.0), a.1.max(b.1), a.2.max(b.2));
        self.size.set(Some(s));
        s
    }

    fn seq(&self) -> &[u32] {
        self.seq.get_or_init(|| {
            let mut out = Vec::new();
            vars_seq(&self.n, &mut out);
            vars_seq(&self.d, &mut out);
            out
        })
    }

    fn order(&self) -> R<&[u32]> {
        if let Some(o) = self.order.get() {
            return Ok(o);
        }
        let o = set_order(self.seq(), true)?;
        Ok(self.order.get_or_init(|| o))
    }

    fn budget_scale(&self, q: &Rat) -> R<()> {
        let bits = self.size().2 + num_bits(q).max(den_bits(q));
        let m = lim().max_bits;
        if crate::lra::mutant(107) {
            if bits >= m {
                return Err(CfErr::TooLarge(TooLargeKind::Scale(bits)));
            }
            return Ok(());
        }
        if bits > m {
            return Err(CfErr::TooLarge(TooLargeKind::Scale(bits)));
        }
        Ok(())
    }

    fn budget_product(&self, o: &Elem) -> R<MulFn> {
        let (a, b) = (self.size(), o.size());
        let l = lim();
        if a.0 + b.0 > l.max_degree || a.2 + b.2 > l.max_bits || a.1 * b.1 > l.max_work {
            return Err(CfErr::TooLarge(TooLargeKind::Budget(a.0 + b.0, a.2 + b.2, a.1 * b.1)));
        }
        Ok(if mul_fast(a, b) { mul_plain } else { mul_bounded })
    }

    fn single_transcendental(&self, other: Option<&Elem>) -> R<bool> {
        let vs = self.seq();
        let the = match other {
            None => {
                if vs.len() != 1 {
                    return Ok(false);
                }
                vs[0]
            }
            Some(o) => {
                let mut all = vs.to_vec();
                for v in o.seq() {
                    if !all.contains(v) {
                        all.push(*v);
                    }
                }
                if all.len() != 1 {
                    return Ok(false);
                }
                all[0]
            }
        };
        transcendental(the)
    }

    /// `(start, cap)` of `_precisions` (:1123).
    fn precisions(&self) -> R<(i64, i64)> {
        let l = lim();
        let mut cap = l.prec_cap;
        let limits = Python::attach(|py| -> PyResult<Option<i64>> {
            let mut most = None;
            for i in self.seq() {
                let m = py_constant(py, *i)?.getattr("max_prec")?;
                if m.is_none() {
                    return Ok(None);
                }
                let m: i64 = m.extract()?;
                most = Some(most.map_or(m, |x: i64| x.max(m)));
            }
            Ok(most)
        })?;
        if let Some(m) = limits {
            cap = cap.min(m.saturating_mul(2));
        }
        Ok((l.prec_start, cap))
    }

    fn undecided(&self, kind: UndecidedKind) -> CfErr {
        CfErr::Undecided(kind, self.n.clone(), self.d.clone())
    }

    /// `_nonzero` (:1134): the numerator alone is evaluated, on its own set of variables.
    fn nonzero(&self) -> R<bool> {
        if self.sign.get().is_some() {
            return Ok(true);
        }
        let mut seq = Vec::new();
        vars_seq(&self.n, &mut seq);
        if seq.is_empty() {
            return Ok(true);
        }
        if !crate::lra::mutant(101) && seq.len() == 1 && transcendental(seq[0])? {
            return Ok(true);
        }
        let order = set_order(&seq, false)?;
        let (mut prec, cap) = self.precisions()?;
        while prec <= cap {
            let (lo, hi) = ieval(&self.n, prec, &env(prec, &order)?);
            if lo.is_positive() || hi.is_negative() {
                return Ok(true);
            }
            prec *= 2;
        }
        Err(self.undecided(UndecidedKind::Nonzero))
    }

    fn sign(&self) -> R<i32> {
        if let Some(s) = self.sign.get() {
            return Ok(s);
        }
        let order = self.order()?;
        let mut sd = if matches!(self.d, PQ(_)) { 1 } else { 0 };
        let (mut prec, cap) = self.precisions()?;
        while prec <= cap {
            let en = env(prec, order)?;
            if sd == 0 {
                let (dl, dh) = ieval(&self.d, prec, &en);
                sd = if dl.is_positive() {
                    1
                } else if dh.is_negative() {
                    -1
                } else {
                    0
                };
            }
            let (nl, nh) = ieval(&self.n, prec, &en);
            let sn = if nl.is_positive() {
                1
            } else if nh.is_negative() {
                -1
            } else {
                0
            };
            if sn != 0 && sd != 0 {
                let s = sn * sd;
                self.sign.set(Some(s));
                self.push_sign(s)?;
                return Ok(s);
            }
            prec *= 2;
        }
        Err(self.undecided(UndecidedKind::Sign))
    }

    /// Python caches the sign on the object: the object this one came from gets it too.
    fn push_sign(&self, s: i32) -> PyResult<()> {
        if let Some(o) = self.py.get() {
            Python::attach(|py| o.bind(py).setattr("_sign", s))?;
        }
        Ok(())
    }

    /// `enclosure` (:1170).
    pub fn enclosure(&self, prec: i64) -> R<Option<Rc<Pair>>> {
        if let Some((p, r)) = &*self.enc.borrow() {
            if *p == prec {
                return Ok(Some(r.clone()));
            }
        }
        let en = env(prec, self.order()?)?;
        let (nl, nh) = ieval(&self.n, prec, &en);
        let r = if matches!(self.d, PQ(_)) {
            (nl, nh)
        } else {
            let (dl, dh) = ieval(&self.d, prec, &en);
            if !dl.is_positive() && !dh.is_negative() {
                return Ok(None);
            }
            let sh = prec as usize;
            let corners = [(&nl << sh, &dl), (&nl << sh, &dh), (&nh << sh, &dl), (&nh << sh, &dh)];
            let lo = corners.iter().map(|(a, b)| a.div_floor(b)).min().unwrap();
            let hi = corners.iter().map(|(a, b)| -((-a).div_floor(b))).max().unwrap();
            (lo, hi)
        };
        let r = Rc::new(r);
        *self.enc.borrow_mut() = Some((prec, r.clone()));
        Ok(Some(r))
    }

    fn floor(&self) -> R<BigInt> {
        let (mut prec, cap) = self.precisions()?;
        while prec <= cap {
            if let Some(e) = self.enclosure(prec)? {
                let sh = prec as usize;
                let (lo, hi) = (&e.0 >> sh, &e.1 >> sh);
                if lo == hi {
                    return Ok(lo);
                }
            }
            prec *= 2;
        }
        Err(self.undecided(UndecidedKind::Floor))
    }

    fn is_integer(&self) -> R<bool> {
        if self.single_transcendental(None)? {
            return Ok(false);
        }
        let (mut prec, cap) = self.precisions()?;
        while prec <= cap {
            if let Some(e) = self.enclosure(prec)? {
                let sh = prec as usize;
                let f = &e.0 >> sh;
                if (&f << sh) < e.0 && e.1 < ((&f + 1) << sh) {
                    return Ok(false);
                }
            }
            prec *= 2;
        }
        Err(self.undecided(UndecidedKind::NotInteger))
    }
}

fn checked(x: Num) -> R<Num> {
    if let Num::E(e) = &x {
        let (deg, terms, bits) = e.size();
        let l = lim();
        if deg > l.max_degree || terms > l.max_terms || bits > l.max_bits {
            return Err(CfErr::TooLarge(TooLargeKind::Checked(deg, terms, bits)));
        }
    }
    Ok(x)
}

fn make(n: Poly, d: Poly) -> R<Num> {
    if let PQ(dq) = &d {
        if let PQ(nq) = &n {
            return Ok(Num::Q(nq.div(dq)));
        }
        let n = if r_is_one(dq) { n } else { scale(&n, &dq.inv()) };
        return Ok(Num::E(elem(n, pone())));
    }
    if is_zero(&n) {
        return Ok(Num::Q(Rat::ZERO));
    }
    let (_, mut n, mut d) = inner_gcd(&n, &d)?;
    let l = lcrec(&d).clone();
    if !r_is_one(&l) {
        let l = l.inv();
        n = scale(&n, &l);
        d = scale(&d, &l);
    }
    if matches!(d, PQ(_)) {
        return Ok(match n {
            PQ(r) => Num::Q(r),
            t => Num::E(elem(t, pone())),
        });
    }
    Ok(Num::E(elem(n, d)))
}

fn e_neg(e: &Elem) -> Rc<Elem> {
    elem(neg(&e.n), e.d.clone())
}

fn e_add_q(e: &Rc<Elem>, q: &Rat) -> R<Num> {
    if q.is_zero() {
        return Ok(Num::E(e.clone()));
    }
    e.budget_scale(q)?;
    let n = match &e.d {
        PQ(_) => add(&e.n, &PQ(q.clone())),
        d => add(&e.n, &scale(d, q)),
    };
    Ok(Num::E(elem(n, e.d.clone())))
}

fn e_add(a: &Rc<Elem>, b: &Rc<Elem>) -> R<Num> {
    let (an, ad, bn, bd) = (&a.n, &a.d, &b.n, &b.d);
    if ad == bd {
        return checked(make(add(an, bn), ad.clone())?);
    }
    let mulf = a.budget_product(b)?;
    if matches!(ad, PQ(_)) {
        let n = add(&mulf(an, bd)?, bn);
        return checked(Num::E(elem(n, bd.clone())));
    }
    if matches!(bd, PQ(_)) {
        let n = add(an, &mulf(bn, ad)?);
        return checked(Num::E(elem(n, ad.clone())));
    }
    let (g, ad1, bd1) = inner_gcd(ad, bd)?;
    if matches!(g, PQ(_)) {
        let x = mulf(an, bd)?;
        let y = mulf(bn, ad)?;
        let d = mulf(ad, bd)?;
        return checked(Num::E(elem(add(&x, &y), d)));
    }
    let x = mul_checked(an, &bd1)?;
    let y = mul_checked(bn, &ad1)?;
    let dd = mul_checked(&ad1, &bd1)?;
    let dd = mul_checked(&dd, &g)?;
    checked(make(add(&x, &y), dd)?)
}

fn e_mul_q(e: &Rc<Elem>, q: &Rat) -> R<Num> {
    if q.is_zero() {
        return Ok(Num::Q(Rat::ZERO));
    }
    if r_is_one(q) {
        return Ok(Num::E(e.clone()));
    }
    e.budget_scale(q)?;
    Ok(Num::E(elem(scale(&e.n, q), e.d.clone())))
}

fn e_mul(a: &Rc<Elem>, b: &Rc<Elem>) -> R<Num> {
    let mut mulf = a.budget_product(b)?;
    if matches!(a.d, PQ(_)) && matches!(b.d, PQ(_)) {
        return checked(make(mulf(&a.n, &b.n)?, pone())?);
    }
    let (g1, an, bd) = inner_gcd(&a.n, &b.d)?;
    let (g2, bn, ad) = inner_gcd(&b.n, &a.d)?;
    if !matches!(g1, PQ(_)) || !matches!(g2, PQ(_)) {
        mulf = mul_checked;
    }
    let n = mulf(&an, &bn)?;
    let d = mulf(&ad, &bd)?;
    if matches!(d, PQ(_)) {
        return checked(make(n, d)?);
    }
    checked(Num::E(elem(n, d)))
}

fn e_inverse(e: &Rc<Elem>) -> R<Rc<Elem>> {
    if !e.nonzero()? {
        return Err(CfErr::ZeroDiv(ZeroDivKind::Element));
    }
    let (n, d) = (&e.n, &e.d);
    if let PQ(c) = n {
        return Ok(elem(scale(d, &c.inv()), pone()));
    }
    let l = lcrec(n);
    if !r_is_one(l) {
        let l = l.inv();
        return Ok(elem(scale(d, &l), scale(n, &l)));
    }
    Ok(elem(d.clone(), n.clone()))
}

fn e_pow(e: &Rc<Elem>, k: i64) -> R<Num> {
    if k < 0 {
        let inv = e_inverse(e)?;
        return e_pow(&inv, -k);
    }
    if k == 0 {
        return Ok(Num::Q(Rat::ONE));
    }
    let (deg, _, bits) = e.size();
    let l = lim();
    if deg as i128 * k as i128 > l.max_degree as i128 || bits as i128 * k as i128 > l.max_bits as i128 {
        return Err(CfErr::TooLarge(TooLargeKind::Power(deg as i128 * k as i128)));
    }
    let n = pow_checked(&e.n, k)?;
    let d = pow_checked(&e.d, k)?;
    checked(Num::E(elem(n, d)))
}

/// `sign(self - o)` (:1191).
fn e_cmp(e: &Rc<Elem>, o: &Num) -> R<i32> {
    if let Num::E(b) = o {
        if b.n == e.n && b.d == e.d {
            return Ok(0);
        }
    }
    if !crate::lra::mutant(109) {
        let start = lim().prec_start;
        if let Some(a) = e.enclosure(start)? {
            let b = match o {
                Num::Q(q) => Some(Rc::new(qenc(q, start))),
                Num::E(x) => x.enclosure(start)?,
            };
            if let Some(b) = b {
                if a.1 < b.0 {
                    return Ok(-1);
                }
                if a.0 > b.1 {
                    return Ok(1);
                }
            }
        }
    }
    match Num::E(e.clone()).sub(o)? {
        Num::Q(r) => Ok(r.is_pos() as i32 - r.is_neg() as i32),
        Num::E(x) => x.sign(),
    }
}

// ---------------------------------------------------------------------------------------------------------------------
// numbers: a Fraction or an Element, with Python's operator dispatch
// ---------------------------------------------------------------------------------------------------------------------

#[derive(Clone, Debug)]
pub enum Num {
    Q(Rat),
    E(Rc<Elem>),
}

impl PartialEq for Num {
    fn eq(&self, o: &Num) -> bool {
        match (self, o) {
            (Num::Q(a), Num::Q(b)) => a == b,
            (Num::E(a), Num::E(b)) => Rc::ptr_eq(a, b) || (a.n == b.n && a.d == b.d),
            _ => false,
        }
    }
}

impl Eq for Num {}

impl Hash for Num {
    fn hash<H: Hasher>(&self, h: &mut H) {
        match self {
            Num::Q(r) => r.hash(h),
            Num::E(e) => {
                e.n.hash(h);
                e.d.hash(h);
            }
        }
    }
}

impl Num {
    pub fn zero() -> Num {
        Num::Q(Rat::ZERO)
    }

    pub fn one() -> Num {
        Num::Q(Rat::ONE)
    }

    /// `a + b`, `F + e` being `e.__radd__(F)`, the same code.
    pub fn add(&self, o: &Num) -> R<Num> {
        match (self, o) {
            (Num::Q(a), Num::Q(b)) => Ok(Num::Q(a.add(b))),
            (Num::E(e), Num::Q(q)) | (Num::Q(q), Num::E(e)) => e_add_q(e, q),
            (Num::E(a), Num::E(b)) => e_add(a, b),
        }
    }

    /// `e - x` is `e + (-x)` (:1037), `F - e` is `(-e) + F` (:1043).
    pub fn sub(&self, o: &Num) -> R<Num> {
        match (self, o) {
            (Num::Q(a), Num::Q(b)) => Ok(Num::Q(a.sub(b))),
            (Num::E(e), Num::Q(q)) => e_add_q(e, &q.neg()),
            (Num::E(a), Num::E(b)) => e_add(a, &e_neg(b)),
            (Num::Q(q), Num::E(e)) => e_add_q(&e_neg(e), q),
        }
    }

    pub fn mul(&self, o: &Num) -> R<Num> {
        match (self, o) {
            (Num::Q(a), Num::Q(b)) => Ok(Num::Q(a.mul(b))),
            (Num::E(e), Num::Q(q)) | (Num::Q(q), Num::E(e)) => e_mul_q(e, q),
            (Num::E(a), Num::E(b)) => e_mul(a, b),
        }
    }

    /// `e / F` (:1089), `e / x` checks `x` also when `x` is `e` (:1093), `F / e` is `e._inverse() * F` (:1102).
    pub fn div(&self, o: &Num) -> R<Num> {
        match (self, o) {
            (Num::Q(a), Num::Q(b)) => {
                if b.is_zero() {
                    return Err(CfErr::ZeroDiv(ZeroDivKind::Fraction));
                }
                Ok(Num::Q(a.div(b)))
            }
            (Num::E(e), Num::Q(q)) => {
                if q.is_zero() {
                    return Err(CfErr::ZeroDiv(ZeroDivKind::Element));
                }
                e_mul_q(e, &q.inv())
            }
            (Num::E(a), Num::E(b)) => {
                if b.n == a.n && b.d == a.d {
                    if !crate::lra::mutant(103) {
                        b.nonzero()?;
                    }
                    return Ok(Num::one());
                }
                e_mul(a, &e_inverse(b)?)
            }
            (Num::Q(q), Num::E(e)) => e_mul_q(&e_inverse(e)?, q),
        }
    }

    pub fn neg(&self) -> Num {
        match self {
            Num::Q(r) => Num::Q(r.neg()),
            Num::E(e) => Num::E(e_neg(e)),
        }
    }

    /// `e._inverse()` for an Element, `1 / F` for a Fraction.
    pub fn inverse(&self) -> R<Num> {
        match self {
            Num::Q(r) => {
                if r.is_zero() {
                    return Err(CfErr::ZeroDiv(ZeroDivKind::Fraction));
                }
                Ok(Num::Q(r.inv()))
            }
            Num::E(e) => Ok(Num::E(e_inverse(e)?)),
        }
    }

    /// `x ** k`.
    pub fn pow(&self, k: i64) -> R<Num> {
        match self {
            Num::E(e) => e_pow(e, k),
            Num::Q(r) => {
                if k < 0 && r.is_zero() {
                    return Err(CfErr::ZeroDiv(ZeroDivKind::Fraction));
                }
                let (base, k) = if k < 0 { (r.inv(), -k) } else { (r.clone(), k) };
                let (n, d) = rat_parts(&base);
                let k = u32::try_from(k).map_err(|_| PyValueError::new_err("exponent out of range"))?;
                Ok(Num::Q(Rat::norm_big(n.pow(k), d.pow(k))))
            }
        }
    }

    /// `abs(x)`: an Element's is `-x` when its sign is -1 (:1001).
    pub fn abs(&self) -> R<Num> {
        match self {
            Num::Q(r) => Ok(Num::Q(if r.is_neg() { r.neg() } else { r.clone() })),
            Num::E(e) => Ok(if e.sign()? < 0 { Num::E(e_neg(e)) } else { self.clone() }),
        }
    }

    pub fn formally_zero(&self) -> bool {
        matches!(self, Num::Q(r) if r.is_zero())
    }

    pub fn sign(&self) -> R<i32> {
        match self {
            Num::Q(r) => Ok(r.is_pos() as i32 - r.is_neg() as i32),
            Num::E(e) => e.sign(),
        }
    }

    /// `bool(x)`: `_nonzero` (:1134) for an Element, which isn't `sign`.
    pub fn nonzero(&self) -> R<bool> {
        match self {
            Num::Q(r) => Ok(!r.is_zero()),
            Num::E(e) => e.nonzero(),
        }
    }

    /// Python's `==`: `F == e` is `e.__eq__(F)` (Fraction answers NotImplemented), :1209.
    pub fn py_eq(&self, o: &Num) -> R<bool> {
        match (self, o) {
            (Num::Q(a), Num::Q(b)) => Ok(a == b),
            (Num::E(e), Num::Q(_)) => {
                if e.single_transcendental(None)? {
                    return Ok(false);
                }
                Ok(e_cmp(e, o)? == 0)
            }
            (Num::Q(_), Num::E(e)) => {
                if e.single_transcendental(None)? {
                    return Ok(false);
                }
                Ok(e_cmp(e, self)? == 0)
            }
            (Num::E(a), Num::E(b)) => {
                if b.n == a.n && b.d == a.d {
                    return Ok(true);
                }
                if a.single_transcendental(Some(b))? {
                    return Ok(false);
                }
                Ok(e_cmp(a, o)? == 0)
            }
        }
    }

    /// `self <op> o` by `_cmp`, a Fraction's left operand by the reflected method on the Element: `F < e` is
    /// `e > F`, so `e - F` is what gets evaluated.
    fn order(&self, o: &Num) -> R<std::cmp::Ordering> {
        Ok(match (self, o) {
            (Num::Q(a), Num::Q(b)) => a.cmp(b),
            (Num::E(e), _) => e_cmp(e, o)?.cmp(&0),
            (Num::Q(_), Num::E(e)) => e_cmp(e, self)?.cmp(&0).reverse(),
        })
    }

    pub fn lt(&self, o: &Num) -> R<bool> {
        Ok(self.order(o)?.is_lt())
    }

    pub fn le(&self, o: &Num) -> R<bool> {
        Ok(self.order(o)?.is_le())
    }

    pub fn gt(&self, o: &Num) -> R<bool> {
        Ok(self.order(o)?.is_gt())
    }

    pub fn ge(&self, o: &Num) -> R<bool> {
        Ok(self.order(o)?.is_ge())
    }

    pub fn floor(&self) -> R<Rat> {
        match self {
            Num::Q(r) => Ok(r.floor()),
            Num::E(e) => Ok(Rat::norm_big(e.floor()?, BigInt::one())),
        }
    }

    /// `-(-self).__floor__()` (:1259): the message of an Undecided names `-self`.
    pub fn ceil(&self) -> R<Rat> {
        match self {
            Num::Q(r) => Ok(r.ceil()),
            Num::E(e) => {
                if crate::lra::mutant(110) {
                    return Ok(Rat::norm_big(e.floor()? + 1, BigInt::one()));
                }
                Ok(Rat::norm_big(-e_neg(e).floor()?, BigInt::one()))
            }
        }
    }

    pub fn is_integer(&self) -> R<bool> {
        match self {
            Num::Q(r) => Ok(r.is_int()),
            Num::E(e) => e.is_integer(),
        }
    }

    /// `x.enclosure(prec)`; a Fraction has none, Python's `lra_cert.within` handles it apart.
    pub fn enclosure(&self, prec: i64) -> R<Option<Rc<Pair>>> {
        match self {
            Num::Q(r) => Ok(Some(Rc::new(qenc(r, prec)))),
            Num::E(e) => e.enclosure(prec),
        }
    }

    /// A Fraction (or an int, as `_coerce`) or an Element, reading `_n`, `_d` and `_sign`. It remembers the object.
    pub fn from_py(x: &Bound<'_, PyAny>) -> PyResult<Num> {
        if let Ok(pe) = x.cast::<PyElem>() {
            let e = pe.borrow().e.clone();
            if crate::relations_core::planted(crate::relations_core::ELEM_FROM_NEG) {
                return Ok(Num::E(e_neg(&e)));
            }
            return Ok(Num::E(e));
        }
        let py = x.py();
        let (fr, _) = fraction_types(py)?;
        let t = x.get_type();
        if t.is(fr.bind(py)) {
            return Ok(Num::Q(rat_of(x)?));
        }
        let m = module(py)?;
        if t.is(&m.getattr("Element")?) {
            let e = elem(poly_from_py(&x.getattr("_n")?)?, poly_from_py(&x.getattr("_d")?)?);
            let s = x.getattr("_sign")?;
            if !s.is_none() {
                e.sign.set(Some(s.extract()?));
            }
            let _ = e.py.set(x.clone().unbind());
            return Ok(Num::E(e));
        }
        if x.is_instance(fr.bind(py))? {
            return Ok(Num::Q(rat_of(x)?));
        }
        if x.is_instance_of::<pyo3::types::PyInt>() && !x.is_instance_of::<pyo3::types::PyBool>() {
            return Ok(Num::Q(Rat::norm_big(x.extract()?, BigInt::one())));
        }
        Err(PyTypeError::new_err(format!("not a number of constfield: {}", x.get_type().name()?)))
    }

    /// A Fraction, or the Element: the Python object it came from, else the Rust `Element` pyclass (Element._new step: no
    /// Python Element is built; `to_py_element` is the old route, for the bridges whose callers compare Python Elements).
    pub fn to_py<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        match self {
            Num::Q(r) => rat_to_py(py, r),
            Num::E(e) => {
                if let Some(o) = e.py.get() {
                    let o = o.bind(py).clone();
                    if let Some(s) = e.sign.get() {
                        o.setattr("_sign", s)?;
                    }
                    return Ok(o);
                }
                PyElem::of(py, e)
            }
        }
    }
}

/// pi's indeterminate, `_PI_INDEX` (:1322): a module constant set at import, read once.
static PI_INDEX: PyOnceLock<u32> = PyOnceLock::new();

/// `pi_laurent` (:1325) of an Element, exact and with no call into Python past `_PI_INDEX`'s one read: `{j: c}` as
/// pairs in the dict's order (`j` ascending), for an Element in pi alone whose denominator is a rational or a power of
/// pi; None for any other Element. Adapters step, part C2.
pub fn pi_laurent_elem(py: Python<'_>, e: &Elem) -> PyResult<Option<Vec<(i64, Rat)>>> {
    let pi = *PI_INDEX.get_or_try_init(py, || module(py)?.getattr("_PI_INDEX")?.extract::<u32>())?;
    let (j0, d) = match &e.d {
        PQ(r) => (0i64, r.clone()),
        PT(v, cs) => {
            let Some((last, init)) = cs.split_last() else { return Ok(None) };
            if *v != pi || !matches!(last, PQ(r) if r_is_one(r)) || init.iter().any(|c| !is_zero(c)) {
                return Ok(None);
            }
            ((cs.len() - 1) as i64, Rat::ONE)
        }
    };
    let scaled;
    let n = if r_is_one(&d) {
        &e.n
    } else {
        scaled = scale(&e.n, &d.inv());
        &scaled
    };
    Ok(match n {
        PQ(c) => Some(vec![(-j0, c.clone())]),
        PT(v, cs) => {
            if *v != pi || cs.iter().any(|c| !matches!(c, PQ(_))) {
                return Ok(None);
            }
            Some(
                cs.iter()
                    .enumerate()
                    .filter_map(|(i, c)| match c {
                        PQ(r) if !r.is_zero() => Some((i as i64 - j0, r.clone())),
                        _ => None,
                    })
                    .collect(),
            )
        }
    })
}

impl Num {
    /// The old `to_py`: a Python Element, `Element._new(n, d)` with the `_sign` known here, when it didn't come from one.
    pub fn to_py_element<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        match self {
            Num::E(e) if e.py.get().is_none() => {
                let o = new_py_element(py, &e.n, &e.d)?;
                if let Some(s) = e.sign.get() {
                    o.setattr("_sign", s)?;
                }
                let _ = e.py.set(o.clone().unbind());
                Ok(o)
            }
            _ => self.to_py(py),
        }
    }
}

fn new_py_element<'py>(py: Python<'py>, n: &Poly, d: &Poly) -> PyResult<Bound<'py, PyAny>> {
    module(py)?.getattr("Element")?.call_method1("_new", (poly_to_py(py, n)?, poly_to_py(py, d)?))
}

pub fn rat_of(x: &Bound<'_, PyAny>) -> PyResult<Rat> {
    let (n, d) = (x.getattr("numerator")?, x.getattr("denominator")?);
    if let (Ok(a), Ok(b)) = (n.extract::<i64>(), d.extract::<i64>()) {
        if a != i64::MIN {
            return Ok(Rat::S(a, b));
        }
    }
    Ok(Rat::norm_big(n.extract()?, d.extract()?))
}

pub fn rat_to_py<'py>(py: Python<'py>, r: &Rat) -> PyResult<Bound<'py, PyAny>> {
    let (_, make) = fraction_types(py)?;
    match r {
        Rat::S(n, d) => make.bind(py).call1((*n, *d)),
        Rat::B(b) => make.bind(py).call1((&b.0, &b.1)),
    }
}

pub fn poly_from_py(x: &Bound<'_, PyAny>) -> PyResult<Poly> {
    if let Ok(t) = x.cast::<PyTuple>() {
        if t.len() != 2 {
            return Err(PyValueError::new_err("not a polynomial"));
        }
        let v: u32 = t.get_item(0)?.extract()?;
        let cs = t.get_item(1)?;
        let cs = cs.cast::<PyTuple>().map_err(PyErr::from)?;
        let mut out = Vec::with_capacity(cs.len());
        for c in cs.iter() {
            out.push(poly_from_py(&c)?);
        }
        return Ok(PT(v, out.into()));
    }
    Ok(PQ(rat_of(x)?))
}

pub fn poly_to_py<'py>(py: Python<'py>, p: &Poly) -> PyResult<Bound<'py, PyAny>> {
    match p {
        PQ(r) => rat_to_py(py, r),
        PT(v, cs) => {
            let cs: Vec<Bound<'py, PyAny>> = cs.iter().map(|c| poly_to_py(py, c)).collect::<PyResult<_>>()?;
            Ok(PyTuple::new(py, [v.into_pyobject(py)?.into_any(), PyTuple::new(py, cs)?.into_any()])?.into_any())
        }
    }
}

// ---------------------------------------------------------------------------------------------------------------------
// bridges, for test_cf_diff.py and for install
// ---------------------------------------------------------------------------------------------------------------------

/// `constfield._sympy_inner_gcd`'s replacement: Python polynomials in, Python polynomials out. Limits are reread, as
/// the caller is Python's arithmetic and no hook entry went before.
#[pyfunction]
pub fn cf_inner_gcd<'py>(a: &Bound<'py, PyAny>, b: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    refresh_limits()?;
    let py = a.py();
    let (g, fa, fb) = sympy_inner_gcd(&poly_from_py(a)?, &poly_from_py(b)?)?;
    Ok(PyTuple::new(py, [poly_to_py(py, &g)?, poly_to_py(py, &fa)?, poly_to_py(py, &fb)?])?.into_any())
}

/// `(answered by heu_gcd, answered by the Python callback)`, top-level gcds since the process began.
#[pyfunction]
pub fn cf_gcd_counts() -> (u64, u64) {
    (GCD_HEURISTIC.load(Ordering::Relaxed), GCD_CALLBACK.load(Ordering::Relaxed))
}

/// `(rounds given up at heu_gcd's size guard, largest image_bits seen)`, since the process began.
#[pyfunction]
pub fn cf_gcd_guard_count() -> (u64, u64) {
    (GCD_GUARD.load(Ordering::Relaxed), GCD_MAX_IMAGE.load(Ordering::Relaxed))
}

#[pyfunction]
pub fn cf_refresh_limits() -> PyResult<()> {
    refresh_limits()
}

fn py_bool<'py>(py: Python<'py>, b: bool) -> Bound<'py, PyAny> {
    pyo3::types::PyBool::new(py, b).to_owned().into_any()
}

/// `num`, constfield.py:827. The Fraction and Element fast paths and an exact int stay here. Everything else is what
/// `Fraction(x)` accepts, a list only Python's constructor holds, so it asks that constructor, counted.
pub static NUM_PY: AtomicU64 = AtomicU64::new(0);

#[pyfunction]
pub fn cf_num<'py>(x: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    let py = x.py();
    let (fr, _) = fraction_types(py)?;
    let t = x.get_type();
    if t.is(fr.bind(py)) || x.is_exact_instance_of::<PyElem>() || t.is(&module(py)?.getattr("Element")?) {
        return Ok(x.clone());
    }
    if x.is_instance_of::<pyo3::types::PyFloat>() {
        return Err(PyTypeError::new_err(format!("not an exact number: {}", x.repr()?)));
    }
    if x.is_exact_instance_of::<pyo3::types::PyInt>() {
        return rat_to_py(py, &Rat::norm_big(x.extract()?, BigInt::one()));
    }
    NUM_PY.fetch_add(1, Ordering::Relaxed);
    fr.bind(py).call1((x,))
}

/// One operation of `Num`, on Python numbers. `b` is a number, or an int for `pow` and `enclosure`.
#[pyfunction]
#[pyo3(signature = (name, a, b=None))]
pub fn cf_op<'py>(
    name: &str,
    a: &Bound<'py, PyAny>,
    b: Option<&Bound<'py, PyAny>>,
) -> PyResult<Bound<'py, PyAny>> {
    let py = a.py();
    let x = Num::from_py(a)?;
    let num2 = || -> PyResult<Num> {
        Num::from_py(b.ok_or_else(|| PyValueError::new_err("a second operand is needed"))?)
    };
    let int2 = || -> PyResult<i64> { b.ok_or_else(|| PyValueError::new_err("an int is needed"))?.extract() };
    let boolean = |r: R<bool>| -> PyResult<Bound<'py, PyAny>> { Ok(py_bool(py, r?)) };
    let int = |r: R<Rat>| -> PyResult<Bound<'py, PyAny>> {
        let (n, _) = rat_parts(&r?);
        Ok(n.into_pyobject(py)?.into_any())
    };
    match name {
        "roundtrip" => x.to_py_element(py),
        // Element._new step: the Rust `Element` pyclass of a fresh copy (no Python origin), for test_elem_pyclass.py.
        "rust_element" => match &x {
            Num::E(e) => PyElem::of(py, &elem(e.n.clone(), e.d.clone())),
            Num::Q(_) => x.to_py(py),
        },
        "add" => x.add(&num2()?)?.to_py_element(py),
        "sub" => x.sub(&num2()?)?.to_py_element(py),
        "mul" => x.mul(&num2()?)?.to_py_element(py),
        "div" => x.div(&num2()?)?.to_py_element(py),
        "neg" => x.neg().to_py_element(py),
        "abs" => x.abs()?.to_py_element(py),
        "inverse" => x.inverse()?.to_py_element(py),
        "pow" => x.pow(int2()?)?.to_py_element(py),
        "formally_zero" => Ok(py_bool(py, x.formally_zero())),
        // lra_cert.rs's `laurent` (`pi_laurent`, adapters step C2), as a list of `(j, c)` in the dict's order, or None.
        "pi_laurent" => match crate::lra_cert::laurent(&x)? {
            None => Ok(py.None().into_bound(py)),
            Some(v) => {
                let items: Vec<Bound<'_, PyAny>> = v
                    .iter()
                    .map(|(j, c)| Ok(PyTuple::new(py, [j.into_pyobject(py)?.into_any(), rat_to_py(py, c)?])?.into_any()))
                    .collect::<PyResult<_>>()?;
                Ok(pyo3::types::PyList::new(py, items)?.into_any())
            }
        },
        "sign" => Ok(x.sign()?.into_pyobject(py)?.into_any()),
        "nonzero" => boolean(x.nonzero()),
        "py_eq" => boolean(x.py_eq(&num2()?)),
        "lt" => boolean(x.lt(&num2()?)),
        "le" => boolean(x.le(&num2()?)),
        "gt" => boolean(x.gt(&num2()?)),
        "ge" => boolean(x.ge(&num2()?)),
        "floor" => int(x.floor()),
        "ceil" => int(x.ceil()),
        "is_integer" => boolean(x.is_integer()),
        "enclosure" => match x.enclosure(int2()?)? {
            None => Ok(py.None().into_bound(py)),
            Some(p) => Ok(PyTuple::new(py, [(&p.0).into_pyobject(py)?, (&p.1).into_pyobject(py)?])?.into_any()),
        },
        "struct_eq" => Ok(py_bool(py, x == num2()?)),
        "hash_eq" => {
            let h = |n: &Num| {
                let mut s = std::collections::hash_map::DefaultHasher::new();
                n.hash(&mut s);
                s.finish()
            };
            Ok(py_bool(py, h(&x) == h(&num2()?)))
        }
        _ => Err(PyValueError::new_err(format!("no operation {name}"))),
    }
}

/// One of the polynomial functions, Python polynomials in and out.
#[pyfunction]
#[pyo3(signature = (name, a, b=None))]
pub fn cf_poly_op<'py>(
    name: &str,
    a: &Bound<'py, PyAny>,
    b: Option<&Bound<'py, PyAny>>,
) -> PyResult<Bound<'py, PyAny>> {
    let py = a.py();
    let x = poly_from_py(a)?;
    let poly2 = || -> PyResult<Poly> {
        poly_from_py(b.ok_or_else(|| PyValueError::new_err("a second polynomial is needed"))?)
    };
    let triple = |r: (Poly, Poly, Poly)| -> PyResult<Bound<'py, PyAny>> {
        Ok(PyTuple::new(py, [poly_to_py(py, &r.0)?, poly_to_py(py, &r.1)?, poly_to_py(py, &r.2)?])?.into_any())
    };
    match name {
        "add" => poly_to_py(py, &add(&x, &poly2()?)),
        "mul" => poly_to_py(py, &mul(&x, &poly2()?)),
        "add_bounded" => poly_to_py(py, &add_bounded(&x, &poly2()?)?),
        "mul_bounded" => poly_to_py(py, &mul_bounded(&x, &poly2()?)?),
        "mul_checked" => poly_to_py(py, &mul_checked(&x, &poly2()?)?),
        "pow_checked" => {
            let k: i64 = b.ok_or_else(|| PyValueError::new_err("an int is needed"))?.extract()?;
            poly_to_py(py, &pow_checked(&x, k)?)
        }
        "divexact" => poly_to_py(py, &divexact(&x, &poly2()?)?),
        "inner_gcd" => triple(inner_gcd(&x, &poly2()?)?),
        "gcd" => poly_to_py(py, &gcd(&x, &poly2()?)?),
        "psize" => Ok(psize(&x).into_pyobject(py)?.into_any()),
        _ => Err(PyValueError::new_err(format!("no polynomial operation {name}"))),
    }
}

/// The native enclosures, bypassing the registry: "pi", "E", or `(r, b)` for a radical.
#[pyfunction]
pub fn cf_native_enclose<'py>(which: &Bound<'py, PyAny>, prec: i64) -> PyResult<Bound<'py, PyAny>> {
    let py = which.py();
    let (lo, hi) = if let Ok(t) = which.cast::<PyTuple>() {
        let (p, q) = rat_parts(&rat_of(&t.get_item(0)?)?);
        root_enclose(&p, &q, t.get_item(1)?.extract()?, prec)
    } else {
        match which.extract::<String>()?.as_str() {
            "pi" => pi_enclose(prec),
            "E" => e_enclose(prec),
            s => return Err(PyValueError::new_err(format!("no native enclosure {s}"))),
        }
    };
    Ok(PyTuple::new(py, [lo.into_pyobject(py)?, hi.into_pyobject(py)?])?.into_any())
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(pyo3::wrap_pyfunction!(cf_inner_gcd, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(cf_gcd_counts, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(cf_gcd_guard_count, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(cf_refresh_limits, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(cf_op, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(cf_num, m)?)?;
    m.add_class::<PyElem>()?;
    m.add_function(pyo3::wrap_pyfunction!(cf_poly_op, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(cf_native_enclose, m)?)?;
    Ok(())
}

// ---------------------------------------------------------------------------------------------------------------------
// Element._new step (issue 323, planner's C2 ruling (b)): the Rust `Element` pyclass
// ---------------------------------------------------------------------------------------------------------------------

/// A number of the field as it crosses to Python: the Rust `Elem` itself, where `Element._new(n, d)` built a Python Element.
/// It has Python Element's `==`, `hash` and `repr` in Rust, for the readers Python still has (model values, the state dump,
/// payloads read back by a Python theory). Every other read (arithmetic, order, an attribute such as `_n` or `to_sympy`) is a
/// named callback: it builds the Python Element once per `Elem` and asks it, counted `cf:elem_py_read`.
#[pyclass(name = "Element", module = "sa_solver", unsendable, weakref)]
pub struct PyElem {
    pub e: Rc<Elem>,
    hash: Cell<Option<isize>>,
}

impl PyElem {
    /// The object for `e`: the live one from its last crossing, else a new one.
    pub fn of<'py>(py: Python<'py>, e: &Rc<Elem>) -> PyResult<Bound<'py, PyAny>> {
        if let Some(w) = &*e.pyw.borrow() {
            if let Some(o) = w.bind(py).cast::<pyo3::types::PyWeakrefReference>()?.upgrade() {
                return Ok(o);
            }
        }
        crate::session::tick(crate::session::CF_ELEM_NEW);
        let o = Bound::new(py, PyElem { e: e.clone(), hash: Cell::new(None) })?.into_any();
        let w = pyo3::types::PyWeakrefReference::new(&o)?;
        *e.pyw.borrow_mut() = Some(w.into_any().unbind());
        Ok(o)
    }

    /// The Python Element for a read only Python answers: counted, built once per `Elem`.
    fn element<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        crate::session::tick(crate::session::CF_ELEM_PY_READ);
        Num::E(self.e.clone()).to_py_element(py)
    }

    fn delegate<'py>(&self, py: Python<'py>, name: &str, other: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        let o = match other.cast::<PyElem>() {
            Ok(pe) => pe.borrow().element(py)?,
            Err(_) => other.clone(),
        };
        self.element(py)?.call_method1(name, (o,))
    }
}

fn poly_repr(py: Python<'_>, p: &Poly) -> PyResult<String> {
    match p {
        PQ(r) => {
            let (n, d) = rat_parts(r);
            Ok(if d.is_one() { n.to_string() } else { format!("{n}/{d}") })
        }
        PT(v, cs) => {
            let name: String = module(py)?.getattr("_CONSTANTS")?.get_item(*v)?.getattr("name")?.extract()?;
            let mut parts = Vec::new();
            for (k, c) in cs.iter().enumerate() {
                if is_zero(c) {
                    continue;
                }
                let t = match k {
                    0 => String::new(),
                    1 => name.clone(),
                    _ => format!("{name}**{k}"),
                };
                let s = poly_repr(py, c)?;
                if t.is_empty() {
                    parts.push(s);
                } else if s == "1" {
                    parts.push(t);
                } else if matches!(c, PT(..)) || s.contains('/') || s.starts_with('-') {
                    parts.push(format!("({s})*{t}"));
                } else {
                    parts.push(format!("{s}*{t}"));
                }
            }
            parts.reverse();
            Ok(parts.join(" + "))
        }
    }
}

#[pymethods]
impl PyElem {
    fn __richcmp__<'py>(&self, py: Python<'py>, other: &Bound<'py, PyAny>, op: pyo3::basic::CompareOp) -> PyResult<Bound<'py, PyAny>> {
        use pyo3::basic::CompareOp::*;
        match op {
            Eq | Ne => {
                crate::session::tick(crate::session::CF_ELEM_EQ);
                let o = if other.is_instance_of::<pyo3::types::PyBool>() { None } else { Num::from_py(other).ok() };
                let Some(o) = o else {
                    // A SymPy number, or not a number: Python Element's own `__eq__`/`__ne__` (`_coerce_foreign`).
                    return self.delegate(py, if matches!(op, Eq) { "__eq__" } else { "__ne__" }, other);
                };
                let mut r = Num::E(self.e.clone()).py_eq(&o)?;
                if crate::relations_core::planted(crate::relations_core::ELEM_EQ_FLIP) {
                    r = !r;
                }
                Ok(py_bool(py, if matches!(op, Eq) { r } else { !r }))
            }
            Lt => self.delegate(py, "__lt__", other),
            Le => self.delegate(py, "__le__", other),
            Gt => self.delegate(py, "__gt__", other),
            Ge => self.delegate(py, "__ge__", other),
        }
    }

    /// Python Element's `hash(("constfield", n, d))`, on the Python polynomials.
    fn __hash__(&self, py: Python<'_>) -> PyResult<isize> {
        crate::session::tick(crate::session::CF_ELEM_HASH);
        let h = match self.hash.get() {
            Some(h) => h,
            None => {
                let t = PyTuple::new(py, [pyo3::types::PyString::new(py, "constfield").into_any(), poly_to_py(py, &self.e.n)?, poly_to_py(py, &self.e.d)?])?;
                let h = t.hash()?;
                self.hash.set(Some(h));
                h
            }
        };
        Ok(if crate::relations_core::planted(crate::relations_core::ELEM_HASH_SKEW) { h.wrapping_add(1) } else { h })
    }

    /// Python Element's `__repr__` (constfield.py:1293), reading the constants' names from Python's registry.
    fn __repr__(&self, py: Python<'_>) -> PyResult<String> {
        crate::session::tick(crate::session::CF_ELEM_REPR);
        let n = poly_repr(py, &self.e.n)?;
        let s = if matches!(self.e.d, PQ(_)) { format!("Element({n})") } else { format!("Element(({n})/({}))", poly_repr(py, &self.e.d)?) };
        Ok(if crate::relations_core::planted(crate::relations_core::ELEM_REPR_BRACKET) { s.replace("Element(", "Element[") } else { s })
    }

    /// `_nonzero` (Python's `__bool__`), on Rust.
    fn __bool__(&self) -> PyResult<bool> {
        crate::session::tick(crate::session::CF_ELEM_EQ);
        Ok(Num::E(self.e.clone()).nonzero()?)
    }

    /// Python Element's `sign()` (:1443 in Rust), for `constfield.sign`: -1, 0 or 1, or Undecided as Python raises it.
    fn sign(&self) -> PyResult<i32> {
        crate::session::tick(crate::session::CF_ELEM_SIGN);
        Ok(Num::E(self.e.clone()).sign()?)
    }

    /// An immutable value: a copy is itself, as for Python's Element (which has no `__copy__` but copies to an equal one).
    fn __copy__(slf: Bound<'_, Self>) -> Bound<'_, Self> {
        slf
    }

    fn __deepcopy__<'py>(slf: Bound<'py, Self>, _memo: &Bound<'py, PyAny>) -> Bound<'py, Self> {
        slf
    }

    /// The Python Element, for a caller that needs one (`lra_live._same_num`, the comparisons). Counted as a read.
    fn to_python<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        self.element(py)
    }

    fn __getattr__<'py>(&self, py: Python<'py>, name: &str) -> PyResult<Bound<'py, PyAny>> {
        self.element(py)?.getattr(name)
    }

    fn __neg__<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        self.element(py)?.call_method0("__neg__")
    }
    fn __pos__<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        self.element(py)?.call_method0("__pos__")
    }
    fn __abs__<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        self.element(py)?.call_method0("__abs__")
    }
    fn __floor__<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        self.element(py)?.call_method0("__floor__")
    }
    fn __ceil__<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        self.element(py)?.call_method0("__ceil__")
    }
    fn __add__<'py>(&self, py: Python<'py>, o: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        self.delegate(py, "__add__", o)
    }
    fn __radd__<'py>(&self, py: Python<'py>, o: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        self.delegate(py, "__radd__", o)
    }
    fn __sub__<'py>(&self, py: Python<'py>, o: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        self.delegate(py, "__sub__", o)
    }
    fn __rsub__<'py>(&self, py: Python<'py>, o: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        self.delegate(py, "__rsub__", o)
    }
    fn __mul__<'py>(&self, py: Python<'py>, o: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        self.delegate(py, "__mul__", o)
    }
    fn __rmul__<'py>(&self, py: Python<'py>, o: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        self.delegate(py, "__rmul__", o)
    }
    fn __truediv__<'py>(&self, py: Python<'py>, o: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        self.delegate(py, "__truediv__", o)
    }
    fn __rtruediv__<'py>(&self, py: Python<'py>, o: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        self.delegate(py, "__rtruediv__", o)
    }
    fn __pow__<'py>(&self, py: Python<'py>, o: &Bound<'py, PyAny>, _m: Option<&Bound<'py, PyAny>>) -> PyResult<Bound<'py, PyAny>> {
        self.delegate(py, "__pow__", o)
    }
}
