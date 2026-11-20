//! Exact rationals in lowest terms with a positive denominator: SymPy's `Rational` values. Plain big ints; nothing is
//! tuned yet. Component 1a's `Rat` (`rust-spike/lra/port/src/rat.rs`) is the fast one and can replace this when it is
//! in this crate; it can't be included from here today, since it reaches for `crate::lra`.
use num_bigint::BigInt;
use num_integer::Integer;
use num_traits::{One, Signed, Zero};
use std::cmp::Ordering;

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct Rat {
    pub n: BigInt,
    pub d: BigInt,
}

impl Rat {
    pub fn new(n: BigInt, d: BigInt) -> Rat {
        let g = n.gcd(&d);
        let (mut n, mut d) = (n / &g, d / &g);
        if d.is_negative() {
            n = -n;
            d = -d;
        }
        Rat { n, d }
    }

    pub fn int(n: i64) -> Rat {
        Rat { n: BigInt::from(n), d: BigInt::one() }
    }

    pub fn is_zero(&self) -> bool {
        self.n.is_zero()
    }

    pub fn is_one(&self) -> bool {
        self.n.is_one() && self.d.is_one()
    }

    pub fn is_int(&self) -> bool {
        self.d.is_one()
    }

    pub fn neg(&self) -> Rat {
        Rat { n: -&self.n, d: self.d.clone() }
    }

    pub fn add(&self, o: &Rat) -> Rat {
        Rat::new(&self.n * &o.d + &o.n * &self.d, &self.d * &o.d)
    }

    pub fn mul(&self, o: &Rat) -> Rat {
        Rat::new(&self.n * &o.n, &self.d * &o.d)
    }

    pub fn sub(&self, o: &Rat) -> Rat {
        Rat::new(&self.n * &o.d - &o.n * &self.d, &self.d * &o.d)
    }

    /// None for a division by 0.
    pub fn div(&self, o: &Rat) -> Option<Rat> {
        if o.n.is_zero() {
            return None;
        }
        Some(Rat::new(&self.n * &o.d, &self.d * &o.n))
    }

    /// `self ** n`. A negative power of 0 is the caller's to exclude.
    pub fn pow(&self, n: i32) -> Rat {
        let k = n.unsigned_abs();
        let (a, b) = (num_traits::Pow::pow(&self.n, k), num_traits::Pow::pow(&self.d, k));
        // lowest terms are kept by a power; `new` puts the sign back on the numerator of an inverse
        if n >= 0 { Rat { n: a, d: b } } else { Rat::new(b, a) }
    }

    /// Python's `abs(numerator).bit_length() + denominator.bit_length()`.
    pub fn bits(&self) -> u64 {
        self.n.bits() + self.d.bits()
    }

    /// 1, 0 or -1.
    pub fn sign(&self) -> i32 {
        if self.n.is_zero() { 0 } else if self.n.is_negative() { -1 } else { 1 }
    }
}

impl Ord for Rat {
    fn cmp(&self, o: &Rat) -> Ordering {
        (&self.n * &o.d).cmp(&(&o.n * &self.d))
    }
}

impl PartialOrd for Rat {
    fn partial_cmp(&self, o: &Rat) -> Option<Ordering> {
        Some(self.cmp(o))
    }
}
