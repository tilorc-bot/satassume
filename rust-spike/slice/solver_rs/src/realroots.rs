//! `satassume/knowledge/realroots.py`, all 16 functions: exact real-root counts by Sturm's theorem. Same steps in the same
//! order over the same values, so the answers are Python's by construction and the comparison in `realroots_cmp.py` checks
//! that. Exact throughout: big ints and rationals in lowest terms, no floats, no size limit Python doesn't have.
//!
//! Input is `int` or `fractions.Fraction`, the module's documented types. Its only caller outside the tests passes plain
//! ints (`templates/rootof.py:28`). Anything else `Fraction()` would accept (a float, a string, a SymPy number) is a
//! TypeError here, which `knowledge_live` turns into a loud fault, not a quiet "unknown".
use crate::term::rat::Rat;
use num_bigint::BigInt;
use num_integer::Integer;
use num_traits::{One, Signed, Zero};
use pyo3::exceptions::{PyIndexError, PyTypeError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyInt, PyList, PySequence};

type Poly = Vec<Rat>;

const MAX_DEGREE: usize = 120;
const MAX_BITS: u64 = 512;

fn sub(a: &Rat, b: &Rat) -> Rat {
    a.add(&b.neg())
}

/// `b` is a leading coefficient of a stripped polynomial, so it isn't zero.
fn div(a: &Rat, b: &Rat) -> Rat {
    Rat::new(&a.n * &b.d, &a.d * &b.n)
}

fn from_int(n: BigInt) -> Rat {
    Rat { n, d: BigInt::one() }
}

fn strip(p: &[Rat]) -> Poly {
    let i = p.iter().take_while(|c| c.is_zero()).count();
    p[i..].to_vec()
}

fn rem(a: &[Rat], b: &[Rat]) -> Poly {
    let mut a = a.to_vec();
    let lb = &b[0];
    let db = b.len() - 1;
    while !a.is_empty() && a.len() - 1 >= db {
        let q = div(&a[0], lb);
        for i in 0..b.len() {
            a[i] = sub(&a[i], &q.mul(&b[i]));
        }
        a = strip(&a);
    }
    a
}

fn monic(p: &[Rat]) -> Poly {
    p.iter().map(|c| div(c, &p[0])).collect()
}

/// Every caller's `p` is stripped, so it isn't all zeros and the gcd below isn't zero.
fn primitive(p: &[Rat]) -> Poly {
    if p.is_empty() {
        return Vec::new();
    }
    let m = p.iter().fold(BigInt::one(), |m, c| m.lcm(&c.d));
    let q: Vec<BigInt> = p.iter().map(|c| &c.n * (&m / &c.d)).collect();
    let g = q.iter().fold(BigInt::zero(), |g, c| g.gcd(c));
    q.into_iter().map(|c| from_int(c / &g)).collect()
}

fn gcd(a: &[Rat], b: &[Rat]) -> Poly {
    let (mut a, mut b) = (primitive(&strip(a)), primitive(&strip(b)));
    while !b.is_empty() {
        let r = primitive(&rem(&a, &b));
        a = std::mem::replace(&mut b, r);
    }
    if a.is_empty() {
        a
    } else {
        monic(&a)
    }
}

fn derivative(p: &[Rat]) -> Poly {
    let n = p.len();
    if n == 0 {
        return Vec::new();
    }
    let d = n - 1;
    let out: Poly = p[..d].iter().enumerate().map(|(i, c)| c.mul(&from_int(BigInt::from(d - i)))).collect();
    strip(&out)
}

fn exact_div(a: &[Rat], b: &[Rat]) -> Poly {
    let mut a = a.to_vec();
    let mut out = Vec::new();
    let lb = &b[0];
    while a.len() >= b.len() {
        let q = div(&a[0], lb);
        for i in 0..b.len() {
            a[i] = sub(&a[i], &q.mul(&b[i]));
        }
        out.push(q);
        a.remove(0);
    }
    out
}

fn squarefree(p: &[Rat]) -> bool {
    let p = strip(p);
    gcd(&p, &derivative(&p)).len() <= 1
}

fn chain(p: &[Rat]) -> Vec<Poly> {
    let mut out = vec![primitive(p), primitive(&derivative(p))];
    while out[out.len() - 1].len() > 1 {
        let r = primitive(&rem(&out[out.len() - 2], &out[out.len() - 1]));
        if r.is_empty() {
            break;
        }
        out.push(r.iter().map(Rat::neg).collect());
    }
    out
}

fn changes(signs: impl Iterator<Item = bool>) -> i64 {
    // `true` is positive; the zeros are already gone.
    let s: Vec<bool> = signs.collect();
    s.windows(2).filter(|w| w[0] != w[1]).count() as i64
}

fn at_inf(chain: &[Poly], neg: bool) -> i64 {
    changes(chain.iter().filter(|q| !q[0].is_zero()).map(|q| q[0].n.is_positive() != (neg && (q.len() - 1) % 2 == 1)))
}

fn at_zero(chain: &[Poly]) -> i64 {
    changes(chain.iter().map(|q| &q[q.len() - 1]).filter(|c| !c.is_zero()).map(|c| c.n.is_positive()))
}

/// `p` is stripped and not empty; Python's `p[-1]` raises on an empty one, and the binding raises that.
fn real_root_counts(p: &[Rat]) -> (i64, i64, i64) {
    let mut p = p;
    let mut zero = 0;
    if p[p.len() - 1].is_zero() {
        zero = 1;
        p = &p[..p.len() - 1];
    }
    if p.len() == 1 {
        return (0, zero, 0);
    }
    let c = chain(p);
    let v0 = at_zero(&c);
    (at_inf(&c, true) - v0, zero, v0 - at_inf(&c, false))
}

fn distinct_nonzero_real_roots(g: &[Rat]) -> i64 {
    let mut g = g;
    while !g.is_empty() && g[g.len() - 1].is_zero() {
        g = &g[..g.len() - 1];
    }
    if g.len() <= 1 {
        return 0;
    }
    let h = gcd(g, &derivative(g));
    let s = if h.len() > 1 { exact_div(g, &h) } else { g.to_vec() };
    let (n, _z, pos) = real_root_counts(&strip(&s));
    n + pos
}

fn imaginary_root_count(p: &[Rat]) -> i64 {
    let p = strip(p);
    let n = p.len();
    let mut re = vec![Rat::int(0); n];
    let mut im = vec![Rat::int(0); n];
    for (i, c) in p.iter().enumerate() {
        let k = n - 1 - i; // c*x**k at x = i*y: i**k * c * y**k
        let value = if k % 4 < 2 { c.clone() } else { c.neg() };
        if k % 2 == 0 {
            re[i] = value;
        } else {
            im[i] = value;
        }
    }
    distinct_nonzero_real_roots(&gcd(&re, &im))
}

/// `(real, sign, imaginary)`, or None as `root_facts` says.
pub(crate) fn root_facts(coeffs: &[Rat], index: &BigInt) -> Option<(bool, Option<i64>, Option<bool>)> {
    let p = strip(coeffs);
    let n = p.len();
    if n < 2 {
        return None;
    }
    let d = n - 1;
    if d > MAX_DEGREE
        || index.is_negative()
        || *index >= BigInt::from(d)
        || p.iter().map(|c| (c.n.abs() / &c.d).bits()).max().unwrap_or(0) > MAX_BITS
        || !squarefree(&p)
    {
        return None;
    }
    let (neg, zero, pos) = real_root_counts(&p);
    let nreal = neg + zero + pos;
    if *index < BigInt::from(nreal) {
        let sign = if *index < BigInt::from(neg) {
            -1
        } else if *index < BigInt::from(neg + zero) {
            0
        } else {
            1
        };
        return Some((true, Some(sign), Some(false)));
    }
    let m = imaginary_root_count(&p);
    let imaginary = if m == 0 {
        Some(false)
    } else if m == d as i64 - nreal {
        Some(true)
    } else {
        None
    };
    Some((false, None, imaginary))
}

fn read_poly(p: &Bound<'_, PyAny>) -> PyResult<Poly> {
    let py = p.py();
    let fraction = py.import("fractions")?.getattr("Fraction")?;
    let seq = p.cast::<PySequence>().map_err(|_| PyTypeError::new_err("realroots: a polynomial is a sequence"))?;
    let mut out = Vec::with_capacity(seq.len()?);
    for c in seq.try_iter()? {
        let c = c?;
        if c.is_instance_of::<PyInt>() {
            out.push(from_int(c.extract::<BigInt>()?));
        } else if c.is_instance(&fraction)? {
            // Already in lowest terms with a positive denominator.
            out.push(Rat { n: c.getattr("numerator")?.extract()?, d: c.getattr("denominator")?.extract()? });
        } else {
            return Err(PyTypeError::new_err(format!(
                "realroots: a coefficient is an int or a Fraction, not {}",
                c.get_type().name()?
            )));
        }
    }
    Ok(out)
}

#[pyfunction]
fn realroots_limits() -> (usize, u64) {
    (MAX_DEGREE, MAX_BITS)
}

#[pyfunction]
fn realroots_gcd<'py>(a: &Bound<'py, PyAny>, b: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyList>> {
    let py = a.py();
    let g = gcd(&read_poly(a)?, &read_poly(b)?);
    let fraction = py.import("fractions")?.getattr("Fraction")?;
    let out = PyList::empty(py);
    for c in g {
        out.append(fraction.call1((c.n, c.d))?)?;
    }
    Ok(out)
}

#[pyfunction]
fn realroots_squarefree(p: &Bound<'_, PyAny>) -> PyResult<bool> {
    Ok(squarefree(&read_poly(p)?))
}

#[pyfunction]
fn realroots_real_root_counts(p: &Bound<'_, PyAny>) -> PyResult<(i64, i64, i64)> {
    let p = strip(&read_poly(p)?);
    if p.is_empty() {
        return Err(PyIndexError::new_err("list index out of range"));
    }
    Ok(real_root_counts(&p))
}

#[pyfunction]
fn realroots_imaginary_root_count(p: &Bound<'_, PyAny>) -> PyResult<i64> {
    Ok(imaginary_root_count(&read_poly(p)?))
}

#[pyfunction]
fn realroots_root_facts<'py>(coeffs: &Bound<'py, PyAny>, index: BigInt) -> PyResult<Option<Bound<'py, PyDict>>> {
    let py = coeffs.py();
    let Some((real, sign, imaginary)) = root_facts(&read_poly(coeffs)?, &index) else {
        return Ok(None);
    };
    let out = PyDict::new(py);
    out.set_item("real", real)?;
    out.set_item("sign", sign)?;
    out.set_item("imaginary", imaginary)?;
    Ok(Some(out))
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(realroots_limits, m)?)?;
    m.add_function(wrap_pyfunction!(realroots_gcd, m)?)?;
    m.add_function(wrap_pyfunction!(realroots_squarefree, m)?)?;
    m.add_function(wrap_pyfunction!(realroots_real_root_counts, m)?)?;
    m.add_function(wrap_pyfunction!(realroots_imaginary_root_count, m)?)?;
    m.add_function(wrap_pyfunction!(realroots_root_facts, m)?)
}
