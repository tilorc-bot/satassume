//! Exact rationals: i64 over i64 in lowest terms, falling back to num-bigint when a value doesn't fit.
//! Canonical: `S` whenever both parts fit in i64 (den > 0, coprime), `B` only otherwise, so derived Eq and Hash are
//! value equality. i64::MIN is never stored in `S`, which keeps negation and abs simple. No floats anywhere.
use num_bigint::BigInt;
use num_integer::Integer;
use num_traits::{One, Signed, ToPrimitive};
use std::cmp::Ordering;
use std::hash::{Hash, Hasher};

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Rat {
    S(i64, i64),
    B(Box<(BigInt, BigInt)>),
}

#[cfg(feature = "prof")]
pub mod prof {
    use std::sync::atomic::{AtomicU64, Ordering::Relaxed};
    /// Results by width: both parts fit in i32, in i64, neither. Then the operations that used 128-bit
    /// intermediates beyond i64 but came back to fit, and the bits of the largest part.
    pub static W32: AtomicU64 = AtomicU64::new(0);
    pub static W64: AtomicU64 = AtomicU64::new(0);
    pub static WBIG: AtomicU64 = AtomicU64::new(0);
    pub static BIGOP: AtomicU64 = AtomicU64::new(0);
    pub static MAXBITS: AtomicU64 = AtomicU64::new(0);
    pub fn small(n: i64, d: i64) {
        if n.unsigned_abs() <= i32::MAX as u64 && d <= i32::MAX as i64 {
            W32.fetch_add(1, Relaxed);
        } else {
            W64.fetch_add(1, Relaxed);
        }
    }
    pub fn big(bits: u64) {
        WBIG.fetch_add(1, Relaxed);
        MAXBITS.fetch_max(bits, Relaxed);
    }
    pub fn bigop() {
        BIGOP.fetch_add(1, Relaxed);
    }
}

#[inline(always)]
fn count_small(_n: i64, _d: i64) {
    #[cfg(feature = "prof")]
    prof::small(_n, _d);
}

#[inline]
fn gcd64(mut a: u64, mut b: u64) -> u64 {
    while b != 0 {
        let t = a % b;
        a = b;
        b = t;
    }
    a
}

#[inline]
fn gcd128_64(a: u128, b: u64) -> u64 {
    // gcd of a 128-bit value with a 64-bit one: one wide remainder, then 64-bit.
    if b == 0 {
        return if a <= u64::MAX as u128 { a as u64 } else { 0 };
    }
    gcd64(b, (a % b as u128) as u64)
}

#[inline]
fn fits(x: i128) -> bool {
    x > i64::MIN as i128 && x <= i64::MAX as i128
}

impl Rat {
    pub const ZERO: Rat = Rat::S(0, 1);
    pub const ONE: Rat = Rat::S(1, 1);
    pub const MINUS_ONE: Rat = Rat::S(-1, 1);

    /// From lowest-terms 128-bit parts (den > 0).
    #[inline]
    fn from_128(n: i128, d: i128) -> Rat {
        if fits(n) && fits(d) {
            count_small(n as i64, d as i64);
            Rat::S(n as i64, d as i64)
        } else {
            Rat::norm_big(BigInt::from(n), BigInt::from(d))
        }
    }

    /// From lowest-terms BigInts (den > 0): back to `S` if it fits.
    fn norm_big(n: BigInt, d: BigInt) -> Rat {
        #[cfg(feature = "prof")]
        prof::bigop();
        if let (Some(a), Some(b)) = (n.to_i64(), d.to_i64()) {
            if a != i64::MIN {
                count_small(a, b);
                return Rat::S(a, b);
            }
        }
        #[cfg(feature = "prof")]
        prof::big(n.bits().max(d.bits()));
        Rat::B(Box::new((n, d)))
    }

    fn big_parts(&self) -> (BigInt, BigInt) {
        match self {
            Rat::S(n, d) => (BigInt::from(*n), BigInt::from(*d)),
            Rat::B(b) => (b.0.clone(), b.1.clone()),
        }
    }

    fn big_reduced(n: BigInt, d: BigInt) -> Rat {
        let g = n.gcd(&d);
        if g.is_one() {
            Rat::norm_big(n, d)
        } else {
            Rat::norm_big(&n / &g, &d / &g)
        }
    }

    pub fn parse(s: &str) -> Rat {
        let (n, d) = s.split_once('/').unwrap();
        if let (Ok(a), Ok(b)) = (n.parse::<i64>(), d.parse::<i64>()) {
            if a != i64::MIN {
                return Rat::S(a, b); // the trace holds Fractions: lowest terms already
            }
        }
        Rat::norm_big(n.parse().unwrap(), d.parse().unwrap())
    }

    pub fn text(&self) -> String {
        match self {
            Rat::S(n, d) => format!("{n}/{d}"),
            Rat::B(b) => format!("{}/{}", b.0, b.1),
        }
    }

    #[inline]
    pub fn is_zero(&self) -> bool {
        matches!(self, Rat::S(0, _))
    }

    #[inline]
    pub fn is_int(&self) -> bool {
        match self {
            Rat::S(_, d) => *d == 1,
            Rat::B(b) => b.1.is_one(),
        }
    }

    #[inline]
    pub fn is_neg(&self) -> bool {
        match self {
            Rat::S(n, _) => *n < 0,
            Rat::B(b) => b.0.is_negative(),
        }
    }

    #[inline]
    pub fn is_pos(&self) -> bool {
        match self {
            Rat::S(n, _) => *n > 0,
            Rat::B(b) => b.0.is_positive(),
        }
    }

    #[inline]
    pub fn neg(&self) -> Rat {
        match self {
            Rat::S(n, d) => Rat::S(-*n, *d),
            Rat::B(b) => Rat::norm_big(-&b.0, b.1.clone()),
        }
    }

    #[inline]
    pub fn add(&self, o: &Rat) -> Rat {
        if let (Rat::S(a, b), Rat::S(c, d)) = (self, o) {
            let (a, b, c, d) = (*a, *b, *c, *d);
            if b == 1 && d == 1 {
                return Rat::from_128(a as i128 + c as i128, 1);
            }
            let g = gcd64(b as u64, d as u64) as i64;
            if g == 1 {
                let n = a as i128 * d as i128 + c as i128 * b as i128;
                return Rat::from_128(n, b as i128 * d as i128);
            }
            let (bg, dg) = (b / g, d / g);
            let t = a as i128 * dg as i128 + c as i128 * bg as i128;
            let g2 = gcd128_64(t.unsigned_abs(), g as u64) as i128;
            let g2 = if g2 == 0 { 1 } else { g2 };
            return Rat::from_128(t / g2, bg as i128 * (d as i128 / g2));
        }
        let (a, b) = self.big_parts();
        let (c, d) = o.big_parts();
        Rat::big_reduced(a * &d + c * &b, b * d)
    }

    #[inline]
    pub fn sub(&self, o: &Rat) -> Rat {
        if let (Rat::S(a, b), Rat::S(c, d)) = (self, o) {
            let (a, b, c, d) = (*a, *b, *c, *d);
            if b == 1 && d == 1 {
                return Rat::from_128(a as i128 - c as i128, 1);
            }
            let g = gcd64(b as u64, d as u64) as i64;
            if g == 1 {
                let n = a as i128 * d as i128 - c as i128 * b as i128;
                return Rat::from_128(n, b as i128 * d as i128);
            }
            let (bg, dg) = (b / g, d / g);
            let t = a as i128 * dg as i128 - c as i128 * bg as i128;
            let g2 = gcd128_64(t.unsigned_abs(), g as u64) as i128;
            let g2 = if g2 == 0 { 1 } else { g2 };
            return Rat::from_128(t / g2, bg as i128 * (d as i128 / g2));
        }
        let (a, b) = self.big_parts();
        let (c, d) = o.big_parts();
        Rat::big_reduced(a * &d - c * &b, b * d)
    }

    #[inline]
    pub fn mul(&self, o: &Rat) -> Rat {
        if let (Rat::S(a, b), Rat::S(c, d)) = (self, o) {
            let (a, b, c, d) = (*a, *b, *c, *d);
            if a == 0 || c == 0 {
                return Rat::ZERO;
            }
            let g1 = gcd64(a.unsigned_abs(), d as u64) as i64;
            let g2 = gcd64(c.unsigned_abs(), b as u64) as i64;
            let n = (a / g1) as i128 * (c / g2) as i128;
            let den = (b / g2) as i128 * (d / g1) as i128;
            return Rat::from_128(n, den);
        }
        let (a, b) = self.big_parts();
        let (c, d) = o.big_parts();
        Rat::big_reduced(a * c, b * d)
    }

    /// self / o, o != 0.
    #[inline]
    pub fn div(&self, o: &Rat) -> Rat {
        self.mul(&o.inv())
    }

    /// 1 / self, self != 0. Lowest terms stay lowest terms.
    #[inline]
    pub fn inv(&self) -> Rat {
        match self {
            Rat::S(n, d) => {
                if *n > 0 {
                    Rat::S(*d, *n)
                } else {
                    Rat::S(-*d, -*n)
                }
            }
            Rat::B(b) => {
                if b.0.is_negative() {
                    Rat::norm_big(-&b.1, -&b.0)
                } else {
                    Rat::norm_big(b.1.clone(), b.0.clone())
                }
            }
        }
    }

    /// The largest integer <= self (Python's Fraction.__floor__).
    pub fn floor(&self) -> Rat {
        match self {
            Rat::S(n, d) => Rat::S(n.div_euclid(*d), 1),
            Rat::B(b) => Rat::norm_big(b.0.div_floor(&b.1), BigInt::one()),
        }
    }

    pub fn ceil(&self) -> Rat {
        match self {
            Rat::S(n, d) => Rat::S(-(-*n).div_euclid(*d), 1),
            Rat::B(b) => Rat::norm_big(-((-&b.0).div_floor(&b.1)), BigInt::one()),
        }
    }
}

impl Ord for Rat {
    #[inline]
    fn cmp(&self, o: &Rat) -> Ordering {
        if let (Rat::S(a, b), Rat::S(c, d)) = (self, o) {
            if b == d {
                return a.cmp(c);
            }
            return (*a as i128 * *d as i128).cmp(&(*c as i128 * *b as i128));
        }
        let (a, b) = self.big_parts();
        let (c, d) = o.big_parts();
        (a * d).cmp(&(c * b))
    }
}

impl PartialOrd for Rat {
    #[inline]
    fn partial_cmp(&self, o: &Rat) -> Option<Ordering> {
        Some(self.cmp(o))
    }
}

impl Hash for Rat {
    #[inline]
    fn hash<H: Hasher>(&self, h: &mut H) {
        match self {
            Rat::S(n, d) => {
                n.hash(h);
                d.hash(h);
            }
            Rat::B(b) => {
                b.0.hash(h);
                b.1.hash(h);
            }
        }
    }
}
