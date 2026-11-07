//! `knowledge/templates/core.py` over one query's table (step 6e, issue 323): the splits that read SymPy structure, read
//! here from `TermRow.args`, the class flags and a Rational's p/q, and the rule builders, pure over small ints and
//! rationals, in Python's order (`resolve` reads rules in order). `facts`, `_CACHE` and the keys stay Python (6d's
//! `_common`); `py.rs` returns ids and `knowledge_live.py` builds the keys from the query's objects.
//!
//! A term the split needs that isn't in the table (`kept_product`'s rest, which SymPy builds) comes back as its factors,
//! and Python builds it: the scaffolding the planner's ruling allows, counted there and checked against `mul` here.
use super::rat::Rat;
use super::table::{fact, flag, Kind, Refuse, TermTable};
use super::TermId;
use num_bigint::BigInt;
use num_integer::Integer;
use num_traits::{Signed, Zero};

/// Bits of `ClassRow::flags` not named in `table::flag`: `FLAGS` in `convert.py`.
const IS_MUL: u32 = 1 << 1;
const IS_POW: u32 = 1 << 2;

/// `MAX_HALF_ODD` in core.py.
pub const MAX_HALF_ODD: usize = 4;

pub type Lit = (usize, &'static str, bool);
pub type Rule = (Vec<Lit>, Vec<Lit>);

/// `_coeff_term`'s `t`: one term, or the factors of the rest of a Mul, which Python's `kept_product` builds.
#[derive(Clone, Debug, PartialEq)]
pub enum Rest {
    One(TermId),
    Product(Vec<TermId>),
}

/// `(c, t)` of `_coeff_term`: `c` the Rational first factor's id, or None for `S.One`.
pub type CoeffTerm = (Option<TermId>, Rest);

/// `_INT_BOUNDS` in core.py, same order.
pub const INT_BOUNDS: [(&[&str], bool, i64); 9] = [
    (&["integer", "extended_positive"], true, 1),
    (&["prime"], true, 2),
    (&["composite"], true, 4),
    (&["composite", "odd"], true, 9),
    (&["even", "extended_positive"], true, 2),
    (&["integer", "extended_nonnegative"], true, 0),
    (&["integer", "extended_negative"], false, -1),
    (&["even", "extended_negative"], false, -2),
    (&["integer", "extended_nonpositive"], false, 0),
];

/// `_RECIP_BOUNDS` in core.py, same order: premises, then `(lo, lo_open, hi, hi_open)` with each bound as `(p, q)`.
#[allow(clippy::type_complexity)]
pub const RECIP_BOUNDS: [(&[&str], ((i64, i64), bool, (i64, i64), bool)); 6] = [
    (&["integer", "extended_positive"], ((0, 1), true, (1, 1), false)),
    (&["prime"], ((0, 1), true, (1, 2), false)),
    (&["composite"], ((0, 1), true, (1, 4), false)),
    (&["even", "extended_positive"], ((0, 1), true, (1, 2), false)),
    (&["integer", "extended_negative"], ((-1, 1), false, (0, 1), true)),
    (&["even", "extended_negative"], ((-1, 2), false, (0, 1), true)),
];

fn rat(p: (i64, i64)) -> Rat {
    Rat::new(BigInt::from(p.0), BigInt::from(p.1))
}

fn prem(slot: usize, ps: &[&'static str]) -> Vec<Lit> {
    ps.iter().map(|p| (slot, *p, true)).collect()
}

impl TermTable {
    /// `t.is_Rational`, with its value.
    fn core_rational(&self, t: TermId) -> Result<Option<Rat>, Refuse> {
        if self.class_of(t).flags & flag::IS_RATIONAL == 0 {
            return Ok(None);
        }
        self.rat(t).map(Some).ok_or(Refuse("core: a Rational class without a value"))
    }

    fn core_is_mul(&self, t: TermId) -> bool {
        self.class_of(t).flags & IS_MUL != 0
    }

    /// `t.args[0]`, which raises IndexError on Python for no args.
    fn core_first(&self, t: TermId) -> Result<TermId, Refuse> {
        self.row(t).args.first().copied().ok_or(Refuse("core: args[0] of a node with no args"))
    }

    /// `t.is_number`, as `convert.py` read it.
    pub fn core_is_number(&self, t: TermId) -> Result<bool, Refuse> {
        let b = self.row(t).bits;
        if b & fact::READ == 0 {
            return Err(Refuse("core: is_number of a skeleton node"));
        }
        Ok(b & fact::NUMBER != 0)
    }

    /// `_coeff_term(a)`, with the rest of the Mul as factors when it has more than one; Python's `kept_product` decides
    /// whether that rest is a product of its factors.
    pub fn core_coeff_term(&self, a: TermId) -> Result<CoeffTerm, Refuse> {
        if !self.core_is_mul(a) || self.core_rational(self.core_first(a)?)?.is_none() {
            return Ok((None, Rest::One(a)));
        }
        let args = &self.row(a).args;
        let rest = &args[1..];
        let t = if rest.len() == 1 { Rest::One(rest[0]) } else { Rest::Product(rest.to_vec()) };
        Ok((Some(args[0]), t))
    }

    /// `_half_split(args)`, before `kept_product`: `(a0, [(a_k % 2, (c_k, t_k))])`.
    pub fn core_half_split(&self, args: &[TermId]) -> Result<Option<(u8, Vec<(u8, CoeffTerm)>)>, Refuse> {
        let mut half = false;
        for &a in args {
            let c = match self.core_rational(a)? {
                Some(c) => Some(c),
                None if self.core_is_mul(a) => self.core_rational(self.core_first(a)?)?,
                None => None,
            };
            if let Some(c) = c {
                if c.d != BigInt::from(1) {
                    if c.d != BigInt::from(2) {
                        return Ok(None);
                    }
                    half = true;
                }
            }
        }
        if !half {
            return Ok(None);
        }
        let two = Rat::int(2);
        let parity = |r: &Rat| -> u8 { if two.mul(r).n.mod_floor(&BigInt::from(2)).is_zero() { 0 } else { 1 } };
        let (mut a0, mut terms) = (0u8, Vec::new());
        for &a in args {
            if let Some(r) = self.core_rational(a)? {
                a0 = (a0 + parity(&r)) % 2;
            } else {
                let ct = self.core_coeff_term(a)?;
                let c = match ct.0 {
                    Some(c) => self.rat(c).ok_or(Refuse("core: a Rational class without a value"))?,
                    None => Rat::int(1),
                };
                terms.push((parity(&c), ct));
            }
        }
        Ok(Some((a0, terms)))
    }

    /// `_bound_split(args)`, before `kept_product` and the derived rest's `is_number`: `(c0, c, t)`.
    pub fn core_bound_split(&self, args: &[TermId]) -> Result<Option<(TermId, CoeffTerm)>, Refuse> {
        if args.len() != 2 {
            return Ok(None);
        }
        let (mut c0, mut t) = (args[0], args[1]);
        if self.core_rational(c0)?.is_none() {
            std::mem::swap(&mut c0, &mut t);
        }
        if self.core_rational(c0)?.is_none() || self.core_rational(t)?.is_some() {
            return Ok(None);
        }
        let ct = self.core_coeff_term(t)?;
        if let Some(c) = ct.0 {
            if self.rat(c).ok_or(Refuse("core: a Rational class without a value"))?.is_zero() {
                return Ok(None);
            }
        }
        // `ct is None` (a rest that isn't kept) comes first on Python; it and `is_number` of a built rest are Python's.
        if let Rest::One(u) = ct.1 {
            if self.core_is_number(u)? {
                return Ok(None);
            }
        }
        Ok(Some((c0, ct)))
    }

    /// The `v` of `_recip_templates`' shape test: `u` is `v**-1` and `v` no number.
    pub fn core_recip_base(&self, u: TermId) -> Result<Option<TermId>, Refuse> {
        if self.class_of(u).flags & IS_POW == 0 {
            return Ok(None);
        }
        let args = &self.row(u).args;
        if args.len() < 2 {
            return Err(Refuse("core: a Pow without two args"));
        }
        if self.class_of(args[1]).kind != Kind::NegativeOne || self.core_is_number(args[0])? {
            return Ok(None);
        }
        Ok(Some(args[0]))
    }

    /// `_imag_term(a)`: `(c, x)` with `c` None for `S.One`.
    pub fn core_imag_term(&self, a: TermId) -> Result<Option<(Option<TermId>, Option<TermId>)>, Refuse> {
        if self.class_of(a).kind == Kind::ImaginaryUnit {
            return Ok(Some((None, None)));
        }
        if !self.core_is_mul(a) {
            return Ok(None);
        }
        let mut args: &[TermId] = &self.row(a).args;
        let mut c = None;
        let first = self.core_first(a)?;
        if let Some(r) = self.core_rational(first)? {
            if r.is_zero() {
                return Ok(None);    // `c == 0`, tested last on Python, with nothing read after it
            }
            c = Some(first);
            args = &args[1..];
        }
        let rest: Vec<TermId> = args.iter().copied().filter(|&f| self.class_of(f).kind != Kind::ImaginaryUnit).collect();
        if rest.len() + 1 != args.len() || rest.len() > 1 {
            return Ok(None);
        }
        Ok(Some((c, rest.first().copied())))
    }

    /// `_imag_split(args)`.
    #[allow(clippy::type_complexity)]
    pub fn core_imag_split(&self, args: &[TermId]) -> Result<Option<Vec<(Option<TermId>, Option<TermId>)>>, Refuse> {
        let mut out = Vec::with_capacity(args.len());
        let mut none = false;
        for &a in args {
            match self.core_imag_term(a)? {
                Some(t) => out.push(t),
                None => none = true,    // Python reads every term before it tests for None
            }
        }
        Ok(if none { None } else { Some(out) })
    }
}

/// `_half_rules(a0, odd, m)`.
pub fn half_rules(a0: u8, odd: &[bool], m: usize) -> Vec<Rule> {
    let ints: Vec<Lit> = (0..m).map(|k| (k, "integer", true)).collect();
    let mut out = vec![(ints.clone(), vec![(m, "rational", true)])];
    let o: Vec<usize> = (0..m).filter(|&k| odd[k]).collect();
    if o.len() > MAX_HALF_ODD {
        return out;
    }
    let n = o.len();
    for idx in 0..(1usize << n) {
        // itertools.product(('even', 'odd'), repeat=n): the first position varies slowest.
        let mut prem = ints.clone();
        let mut odds = 0u8;
        for (i, &k) in o.iter().enumerate() {
            let is_odd = (idx >> (n - 1 - i)) & 1 == 1;
            odds += is_odd as u8;
            prem.push((k, if is_odd { "odd" } else { "even" }, true));
        }
        let num_odd = (a0 + odds) % 2;
        out.push((prem, vec![(m, "integer", num_odd == 0)]));
    }
    out
}

/// `_bound_rules(c0, c1)`.
pub fn bound_rules(c0: &Rat, c1: &Rat) -> Vec<Rule> {
    let mut out = Vec::new();
    let pos = c1.n.is_positive();
    for (ps, lower, b) in INT_BOUNDS {
        let v = c0.add(&c1.mul(&Rat::int(b)));
        let concl = if lower == pos {
            if v.n.is_positive() { Some("extended_positive") } else if v.is_zero() { Some("extended_nonnegative") } else { None }
        } else if v.n.is_negative() {
            Some("extended_negative")
        } else if v.is_zero() {
            Some("extended_nonpositive")
        } else {
            None
        };
        if let Some(c) = concl {
            out.push((prem(0, ps), vec![(1, c, true)]));
        }
    }
    out
}

/// `_recip_rules(c0, c1)`.
pub fn recip_rules(c0: &Rat, c1: &Rat) -> Vec<Rule> {
    let mut out = Vec::new();
    for (ps, (lo, lo_open, hi, hi_open)) in RECIP_BOUNDS {
        let (mut a, mut a_open, mut b, mut b_open) = (c0.add(&c1.mul(&rat(lo))), lo_open, c0.add(&c1.mul(&rat(hi))), hi_open);
        if c1.n.is_negative() {
            std::mem::swap(&mut a, &mut b);
            std::mem::swap(&mut a_open, &mut b_open);
        }
        let concl = if a.n.is_positive() || a.is_zero() && a_open {
            "extended_positive"
        } else if a.is_zero() {
            "extended_nonnegative"
        } else if b.n.is_negative() || b.is_zero() && b_open {
            "extended_negative"
        } else if b.is_zero() {
            "extended_nonpositive"
        } else {
            continue;
        };
        out.push((prem(0, ps), vec![(1, concl, true)]));
    }
    out
}

/// `_imag_rules(signs, csign)`: `csign` as which of 1 and -1 it holds.
pub fn imag_rules(signs: &[i8], c_pos: bool, c_neg: bool) -> Vec<Rule> {
    let mut out = Vec::new();
    let m = signs.len();
    for d in [1i8, -1] {
        let (has_d, has_minus_d) = if d == 1 { (c_pos, c_neg) } else { (c_neg, c_pos) };
        if has_minus_d {
            continue;
        }
        let weak: Vec<&'static str> = signs.iter().map(|&s| if s * d > 0 { "nonnegative" } else { "nonpositive" }).collect();
        let strict: Vec<&'static str> = signs.iter().map(|&s| if s * d > 0 { "positive" } else { "negative" }).collect();
        if has_d {
            out.push(((0..m).map(|k| (k, weak[k], true)).collect(), vec![(m, "imaginary", true)]));
            continue;
        }
        for j in 0..m {
            out.push((
                (0..m).map(|k| (k, if k == j { strict[k] } else { weak[k] }, true)).collect(),
                vec![(m, "imaginary", true)],
            ));
        }
    }
    out
}

/// `_imag_number_rules()`.
pub fn imag_number_rules() -> Vec<Rule> {
    vec![
        (vec![(0, "real", true), (0, "zero", false)], vec![(1, "imaginary", true)]),
        (vec![(0, "zero", true)], vec![(1, "zero", true)]),
    ]
}

/// `_not_unit_premises(c0, c1)`, as indices into `INT_BOUNDS`.
pub fn not_unit_premises(c0: &Rat, c1: &Rat) -> Vec<usize> {
    let pos = c1.n.is_positive();
    let (two, minus_two) = (Rat::int(2), Rat::int(-2));
    INT_BOUNDS
        .iter()
        .enumerate()
        .filter(|(_, (_, lower, b))| {
            let v = c0.add(&c1.mul(&Rat::int(*b)));
            *lower == pos && v >= two || *lower != pos && v <= minus_two
        })
        .map(|(i, _)| i)
        .collect()
}
