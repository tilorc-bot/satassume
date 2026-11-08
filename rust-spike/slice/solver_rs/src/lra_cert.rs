//! Port of satassume/theories/lra/lra_cert.py. Line numbers below are that file's.
//!
//! What `certify` needs of the theory (all of it plain data, the module doesn't know the theory):
//! - `atoms`: `LRATheory._atoms.values()` in registration order, as `(kind is "=" or "!=", bound)`.
//! - `ints`: `_ints.values()` in registration order, as `(m, k)` of the atom `m*v + k`.
//! - `forms`: the keys of `_slack_of` in registration order, each form's `(var, coefficient)`.
//! - `nt`: `len(_key) - len(_rows)`, the nonbasic variables.
//! - `values`: `None`, or `(top, den)` from `rational_values`, over the nonbasic variables' values.
//! - `g`: the theory's `CertAtoms` (`_cagg`), kept between calls: only what's new (from the end of each sequence) is
//!   read. Python's order is newest first, which `DoubleEndedIterator` gives.
//! `_certificate`'s memo and its `except Exception -> (False, None)` are the caller's: this returns `Result`. The memo
//! key takes `limits()`; call `constfield::refresh_limits()` before it.
//!
//! `pi_laurent` of an Element bound is constfield.rs's `pi_laurent_elem` (adapters step, part C2); it was a callback here.
#![allow(dead_code)]

use crate::constfield::{lim, pi_laurent_elem, CfErr, rat_of, rat_parts, refresh_limits, Num, R};
use crate::relations_core::{planted, unplant, CF_LAURENT_RAISE, CF_LAURENT_REFUSE, CF_LAURENT_RATIONAL};
use crate::session::{self, tick};
use crate::rat::Rat;
use num_bigint::BigInt;
use num_integer::Integer;
use num_traits::{One, Signed, Zero};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyTuple};
use std::collections::BTreeSet;

const GROWTH: usize = 16;
const CERT_DEGREE: i64 = 3;

fn ceil_abs(c: &Rat) -> BigInt {
    let (n, d) = rat_parts(c);
    -((-n.abs()).div_floor(&d))
}

fn magnitude(lx: &[(i64, Rat)]) -> BigInt {
    let mut s = BigInt::zero();
    for (j, c) in lx {
        s += ceil_abs(c) << (if *j > 0 { 2 * *j as usize } else { 0 });
    }
    s
}

/// `within` (:41): `|q| <= bound` shown by an enclosure at the first precision. Python's docstring says it never
/// raises, but a callback's exception in `enclosure` does get through, so this is a `Result`.
pub fn within(q: &Num, bound: &Rat) -> R<bool> {
    match q {
        Num::Q(r) => Ok(if r.is_neg() { r.neg() } else { r.clone() } <= *bound),
        Num::E(_) => {
            let start = lim().prec_start;
            let Some(e) = q.enclosure(start)? else { return Ok(false) };
            let s = bound.mul(&Rat::norm_big(BigInt::one() << start as usize, BigInt::one()));
            let as_rat = |x: &BigInt| Rat::norm_big(x.clone(), BigInt::one());
            Ok(s.neg() <= as_rat(&e.0) && as_rat(&e.1) <= s)
        }
    }
}

fn window(exps: &BTreeSet<i64>) -> bool {
    exps.iter().all(|j| *j == 0 || *j == 1) || exps.iter().all(|j| *j == -1 || *j == 0)
}

/// `_decided` (:60).
pub fn decided(den: &BigInt, height: &BigInt) -> bool {
    let h3: BigInt = BigInt::from(3) * height;
    let h2: BigInt = &h3 + BigInt::from(2) * den;
    let h8: BigInt = &h3 + 8;
    let total = den.bits() as i128 + 41 * h2.bits() as i128 + h8.bits() as i128 + 8;
    total <= lim().prec_cap as i128
}

/// `limits()` (:83): `(PREC_START, PREC_CAP, MAX_DEGREE, MAX_TERMS, MAX_BITS, MAX_WORK)` as last refreshed.
pub fn limits() -> [i64; 6] {
    let l = lim();
    [l.prec_start, l.prec_cap, l.max_degree, l.max_terms, l.max_bits, l.max_work]
}

fn limits_suffice() -> bool {
    let t = CERT_DEGREE + 1;
    let l = lim();
    l.max_degree >= 2 * CERT_DEGREE && l.max_terms >= 2 * t - 1 && l.max_work >= t * t && l.prec_start <= l.prec_cap
}

/// `pi_laurent` of a number, `{j: c}` as pairs in the dict's order. For an Element, constfield.rs's port of it
/// (adapters step, part C2): no Python call and no `Element._new` at this boundary.
pub(crate) fn laurent(x: &Num) -> R<Option<Vec<(i64, Rat)>>> {
    match x {
        Num::Q(q) => Ok(Some(if q.is_zero() { vec![] } else { vec![(0, q.clone())] })),
        Num::E(e) => {
            tick(session::CF_PI_LAURENT);
            if planted(CF_LAURENT_REFUSE) {
                unplant();
                return Err(CfErr::Py(crate::term::py::TermRefuse::new_err("planted")));
            }
            if planted(CF_LAURENT_RAISE) {
                return Err(CfErr::Py(pyo3::exceptions::PyValueError::new_err("planted")));
            }
            let mut r = Python::attach(|py| pi_laurent_elem(py, e))?;
            if planted(CF_LAURENT_RATIONAL) {
                if let Some(v) = r.as_mut() {
                    v.retain(|p| p.0 == 0);
                }
            }
            Ok(r)
        }
    }
}

/// One integrality atom's row of `CertAtoms.ints` (:118).
#[derive(Clone, Debug)]
pub struct CertInt {
    pub e: i64,
    pub mu: Rat,
    pub ek: BTreeSet<i64>,
    pub dk: BigInt,
    pub ck: BigInt,
    pub nk: BigInt,
    pub lkd: BigInt,
    pub kc: BigInt,
}

/// `CertAtoms` (:102): the registered atoms' aggregate, gathered incrementally. One per theory.
#[derive(Clone, Debug)]
pub struct CertAtoms {
    pub ok: bool,
    pub na: usize,
    pub ni: usize,
    pub nf: usize,
    pub exps: BTreeSet<i64>,
    pub den: BigInt,
    pub top: BigInt,
    pub x: BigInt,
    pub neq: u64,
    pub had: BigInt,
    pub ints: Vec<CertInt>,
}

impl Default for CertAtoms {
    fn default() -> Self {
        Self::new()
    }
}

impl CertAtoms {
    pub fn new() -> CertAtoms {
        CertAtoms {
            ok: true,
            na: 0,
            ni: 0,
            nf: 0,
            exps: BTreeSet::new(),
            den: BigInt::one(),
            top: BigInt::zero(),
            x: BigInt::zero(),
            neq: 0,
            had: BigInt::one(),
            ints: Vec::new(),
        }
    }

    /// `update` (:125): False when one is outside the certified kind of payload.
    pub fn update<'a, A, I, F>(&mut self, atoms: A, ints: I, forms: F) -> R<bool>
    where
        A: DoubleEndedIterator<Item = (bool, &'a Num)> + ExactSizeIterator,
        I: DoubleEndedIterator<Item = (&'a Num, &'a Num)> + ExactSizeIterator,
        F: DoubleEndedIterator<Item = &'a [(u32, Num)]> + ExactSizeIterator,
    {
        let la = atoms.len();
        if la > self.na {
            for (is_eq, b) in atoms.rev().take(la - self.na) {
                if is_eq {
                    self.neq += 1;
                }
                if let Num::Q(b) = b {
                    if !b.is_zero() {
                        let (n, d) = rat_parts(b);
                        self.exps.insert(0);
                        if !d.is_one() {
                            self.den = self.den.lcm(&d);
                        }
                        let n: BigInt = -((-n.abs()).div_floor(&d));
                        if n > self.top {
                            self.top = n.clone();
                        }
                        if n > self.x {
                            self.x = n;
                        }
                    }
                    continue;
                }
                let Some(lb) = laurent(b)? else { return Ok(false) };
                for (j, c) in &lb {
                    self.exps.insert(*j);
                    self.den = self.den.lcm(&rat_parts(c).1);
                    self.top = self.top.clone().max(ceil_abs(c));
                }
                self.x = self.x.clone().max(magnitude(&lb));
            }
            self.na = la;
        }
        let li = ints.len();
        if li > self.ni {
            for (m, k) in ints.rev().take(li - self.ni) {
                let (lm, lk) = (laurent(m)?, laurent(k)?);
                let (Some(lm), Some(lk)) = (lm, lk) else { return Ok(false) };
                if lm.len() != 1 {
                    return Ok(false);
                }
                let (e, mu) = &lm[0];
                let (mn, dm) = rat_parts(mu);
                let nm = mn.abs();
                let mut lkd = BigInt::one();
                for (_, c) in &lk {
                    lkd = lkd.lcm(&rat_parts(c).1);
                }
                let mut kc = BigInt::zero();
                for (_, c) in &lk {
                    let (cn, cd) = rat_parts(c);
                    kc = kc.max(cn.abs() * (&lkd / cd));
                }
                let k0 = lk.iter().find(|(j, _)| *j == 0);
                let big: BigInt = magnitude(&lk) + 1 + k0.map_or(BigInt::zero(), |(_, c)| ceil_abs(c));
                self.ints.push(CertInt {
                    e: *e,
                    mu: mu.clone(),
                    ek: lk.iter().map(|(j, _)| *j).collect(),
                    dk: nm.lcm(&(&lkd * &nm)),
                    ck: -((-&kc * &dm).div_floor(&(&nm * &lkd))),
                    nk: -(((-&big) * &dm).div_floor(&nm)),
                    lkd,
                    kc,
                });
            }
            self.ni = li;
        }
        let lf = forms.len();
        if lf > self.nf {
            for form in forms.rev().take(lf - self.nf) {
                let mut dl = BigInt::one();
                let mut parts = Vec::with_capacity(form.len());
                for (_, a) in form {
                    let Num::Q(a) = a else { return Ok(false) };
                    let (n, d) = rat_parts(a);
                    dl = dl.lcm(&d);
                    parts.push((n, d));
                }
                let mut n2 = &dl * &dl;
                for (n, d) in &parts {
                    let t = n * (&dl / d);
                    n2 += &t * &t;
                }
                let r = n2.sqrt();
                let rr: BigInt = &r * &r;
                let up = if rr < n2 { &r + 1 } else { r };
                self.had *= up;
            }
            self.nf = lf;
        }
        Ok(true)
    }
}

/// `certify` (:188): `(certified, Y)`, `Y` an integer as a Rat, for `within`.
pub fn certify<'a, A, I, F>(
    g: &mut CertAtoms,
    atoms: A,
    ints: I,
    forms: F,
    nt: usize,
    values: Option<&(Rat, BigInt)>,
) -> R<(bool, Option<Rat>)>
where
    A: DoubleEndedIterator<Item = (bool, &'a Num)> + ExactSizeIterator,
    I: DoubleEndedIterator<Item = (&'a Num, &'a Num)> + ExactSizeIterator,
    F: DoubleEndedIterator<Item = &'a [(u32, Num)]> + ExactSizeIterator,
{
    let no = (false, None);
    if !limits_suffice() {
        return Ok(no);
    }
    if !g.ok || !g.update(atoms, ints, forms)? {
        g.ok = false;
        return Ok(no);
    }
    let (mut exps, mut den, mut top, mut x) = (g.exps.clone(), g.den.clone(), g.top.clone(), g.x.clone());
    let had = &g.had;
    if let Some((vtop, vden)) = values {
        if !vtop.is_zero() {
            exps.insert(0);
        }
        let vt = rat_parts(&vtop.ceil()).0;
        top = top.max(vt.clone());
        x = x.max(vt);
        den = den.lcm(vden);
    }
    let nt1 = BigInt::from(nt) + 1;
    let growth = if crate::lra::mutant(106) { GROWTH - 1 } else { GROWTH };
    let y: BigInt = (&nt1 * had * (&x + 1)) << growth;
    for it in &g.ints {
        exps.insert(-it.e);
        for j in &it.ek {
            exps.insert(*j - it.e);
        }
        den = den.lcm(&it.dk);
        let four = if it.e > 0 { BigInt::from(4).pow(it.e as u32) } else { BigInt::one() };
        top = top.max(it.ck.clone()).max(four * &y + &it.nk);
    }
    if !window(&exps) {
        return Ok(no);
    }
    for it in &g.ints {
        let mut s: BTreeSet<i64> = exps.iter().map(|j| *j + it.e).collect();
        s.extend(it.ek.iter().copied());
        s.insert(0);
        if !window(&s) {
            return Ok(no);
        }
    }
    let hb = &top * &den;
    let (h1, d1) = (&nt1 * had * &hb, had * &den);
    let dc = &den * &nt1 * had;
    let (h3, d3): (BigInt, BigInt) = (BigInt::from(2) * &h1 * &dc, &dc * &dc);
    let mut checks: Vec<(BigInt, BigInt)> = vec![(d1, h1), (d3, h3)];
    for it in &g.ints {
        let (mn, dm) = rat_parts(&it.mu);
        let nm = mn.abs();
        checks.push((had * &den * &dm * &it.lkd, nm * &nt1 * had * &hb * &it.lkd + &it.kc * had * &den * &dm));
    }
    if !checks.iter().all(|(d, h)| decided(d, h)) {
        return Ok(no);
    }
    let l = lim();
    let most = checks.iter().map(|(d, h)| d.bits() as i128 + h.bits() as i128).max().unwrap();
    if 8 * most + 64 > l.max_bits as i128 {
        return Ok(no);
    }
    let neq = BigInt::from(g.neq);
    let w: BigInt = &neq * &neq + 2;
    let width = w.bits() as i128;
    if g.neq as i128 * width > l.max_bits.div_euclid(8) as i128 {
        return Ok(no);
    }
    Ok((true, Some(Rat::norm_big(y, BigInt::one()))))
}

/// `LRATheory.rational_values` (lra.py:434) over the values of the nonbasic variables, in variable order.
pub fn rational_values<'a>(nonbasic: impl Iterator<Item = &'a Num>) -> Option<(Rat, BigInt)> {
    let (mut top, mut den) = (Rat::ZERO, BigInt::one());
    for q in nonbasic {
        let Num::Q(q) = q else { return None };
        let a = if q.is_neg() { q.neg() } else { q.clone() };
        if a > top {
            top = a;
        }
        den = den.lcm(&rat_parts(q).1);
    }
    Some((top, den))
}

// ---------------------------------------------------------------------------------------------------------------------
// bridges, for test_cf_diff.py: the Python signature over the theory's dicts
// ---------------------------------------------------------------------------------------------------------------------

#[pyclass(unsendable)]
pub struct CfCertAtoms {
    g: CertAtoms,
}

#[pymethods]
impl CfCertAtoms {
    #[new]
    fn new() -> Self {
        CfCertAtoms { g: CertAtoms::new() }
    }

    /// What `CertAtoms` holds: (ok, na, ni, nf, exps, den, top, X, neq, had, ints), comparable with Python's.
    fn state<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let g = &self.g;
        let ints: Vec<_> = g
            .ints
            .iter()
            .map(|i| {
                (
                    i.e,
                    crate::constfield::rat_to_py(py, &i.mu).unwrap(),
                    i.ek.iter().copied().collect::<Vec<_>>(),
                    i.dk.clone(),
                    i.ck.clone(),
                    i.nk.clone(),
                    i.lkd.clone(),
                    i.kc.clone(),
                )
            })
            .collect();
        let head = (g.ok, g.na, g.ni, g.nf, g.exps.iter().copied().collect::<Vec<_>>());
        let rest = (g.den.clone(), g.top.clone(), g.x.clone(), g.neq, g.had.clone(), ints);
        Ok(PyTuple::new(py, [head.into_pyobject(py)?.into_any(), rest.into_pyobject(py)?.into_any()])?.into_any())
    }
}

/// `certify(g, atoms, ints, forms, nt, values)` over the dicts of `LRATheory`.
#[pyfunction]
pub fn cert_check<'py>(
    g: &mut CfCertAtoms,
    atoms: &Bound<'py, PyDict>,
    ints: &Bound<'py, PyDict>,
    forms: &Bound<'py, PyDict>,
    nt: usize,
    values: Option<(Bound<'py, PyAny>, BigInt)>,
) -> PyResult<(bool, Option<BigInt>)> {
    let mut a = Vec::with_capacity(atoms.len());
    for v in atoms.values().iter() {
        let t = v.cast::<PyTuple>().map_err(PyErr::from)?;
        let kind: String = t.get_item(1)?.extract()?;
        a.push((kind == "=" || kind == "!=", Num::from_py(&t.get_item(2)?)?));
    }
    let mut i = Vec::with_capacity(ints.len());
    for v in ints.values().iter() {
        let t = v.cast::<PyTuple>().map_err(PyErr::from)?;
        i.push((Num::from_py(&t.get_item(1)?)?, Num::from_py(&t.get_item(2)?)?));
    }
    let mut f = Vec::with_capacity(forms.len());
    for form in forms.keys().iter() {
        let mut row = Vec::new();
        for item in form.try_iter()? {
            let item = item?;
            let t = item.cast::<PyTuple>().map_err(PyErr::from)?;
            row.push((t.get_item(0)?.extract::<u32>()?, Num::from_py(&t.get_item(1)?)?));
        }
        f.push(row);
    }
    let vals = match &values {
        None => None,
        Some((t, d)) => Some((rat_of(t)?, d.clone())),
    };
    let (ok, y) = certify(
        &mut g.g,
        a.iter().map(|(e, b)| (*e, b)),
        i.iter().map(|(m, k)| (m, k)),
        f.iter().map(|r| r.as_slice()),
        nt,
        vals.as_ref(),
    )?;
    Ok((ok, y.map(|y| rat_parts(&y).0)))
}

#[pyfunction]
pub fn cf_within(q: &Bound<'_, PyAny>, bound: &Bound<'_, PyAny>) -> PyResult<bool> {
    Ok(within(&Num::from_py(q)?, &rat_of(bound)?)?)
}

#[pyfunction]
pub fn cf_limits() -> PyResult<[i64; 6]> {
    refresh_limits()?;
    Ok(limits())
}

#[pyfunction]
pub fn cf_rational_values<'py>(
    py: Python<'py>,
    xs: &Bound<'py, PyAny>,
) -> PyResult<Option<(Bound<'py, PyAny>, BigInt)>> {
    let v: Vec<Num> = xs.try_iter()?.map(|x| Num::from_py(&x?)).collect::<PyResult<_>>()?;
    match rational_values(v.iter()) {
        None => Ok(None),
        Some((t, d)) => Ok(Some((crate::constfield::rat_to_py(py, &t)?, d))),
    }
}

#[pyfunction]
pub fn cf_decided(den: BigInt, height: BigInt) -> bool {
    decided(&den, &height)
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<CfCertAtoms>()?;
    m.add_function(pyo3::wrap_pyfunction!(cert_check, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(cf_within, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(cf_limits, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(cf_rational_values, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(cf_decided, m)?)?;
    Ok(())
}
