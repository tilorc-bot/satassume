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

// ---- The Mul family: `_mul_factor_sets`, `_quotient_rules`, `_quotient_templates`.

/// `_mul_factor_sets`' derived sets before `kept_product`: the `c*t` set (`c`'s id and the rest's factors) and the
/// `I*pi*c*s` set (`c`, and `s` as one id that is a Mul, or factors for Python's `kept_product`).
pub type MulSets = (Option<(TermId, Vec<TermId>)>, Option<(Rat, Rest)>);

/// `_pi_split(arg, imag)` before `kept_product`: `(c, s)`, `s` None when there are no other factors.
pub type PiSplit = Option<(Rat, Option<Rest>)>;

impl TermTable {
    fn core_is_pow(&self, t: TermId) -> bool {
        self.class_of(t).flags & IS_POW != 0
    }

    fn core_two_args(&self, t: TermId) -> Result<(TermId, TermId), Refuse> {
        match *self.row(t).args {
            [a, b] => Ok((a, b)),
            _ => Err(Refuse("core: a binary node without two args")),
        }
    }

    /// `t.is_Integer and t.p < 0`.
    fn core_negative_integer(&self, t: TermId) -> Result<bool, Refuse> {
        Ok(matches!(self.core_rational(t)?, Some(r) if r.is_int() && r.n.is_negative()))
    }

    /// `_pi_split(arg, imag)`; a rest of more than one factor goes to Python's `kept_product`.
    pub fn core_pi_split(&self, arg: TermId, imag: bool) -> Result<PiSplit, Refuse> {
        if !self.core_is_mul(arg) {
            return Ok(None);
        }
        let mut c = Rat::int(1);
        let mut rest = Vec::new();
        let (mut seen_i, mut seen_pi) = (!imag, false);
        for &f in self.row(arg).args.iter() {
            let kind = self.class_of(f).kind;
            if kind == Kind::ImaginaryUnit && !seen_i {
                seen_i = true;
            } else if kind == Kind::Pi && !seen_pi {
                seen_pi = true;
            } else if let Some(r) = self.core_rational(f)? {
                c = c.mul(&r);
            } else {
                rest.push(f);
            }
        }
        if !(seen_i && seen_pi) {
            return Ok(None);
        }
        if rest.is_empty() {
            return Ok(Some((c, None)));
        }
        if c.is_zero() {
            return Ok(None); // Mul(I, pi, 0, x): nan at x = oo
        }
        Ok(Some((c, Some(if rest.len() == 1 { Rest::One(rest[0]) } else { Rest::Product(rest) }))))
    }

    /// `_mul_factor_sets(expr)` past its first set (the args): the derived sets, before `kept_product`.
    pub fn core_mul_factor_sets(&self, expr: TermId) -> Result<MulSets, Refuse> {
        let args = &self.row(expr).args;
        let mut ct = None;
        if args.len() >= 3 {
            if let Some(c) = self.core_rational(args[0])? {
                if !c.is_zero() {
                    ct = Some((args[0], args[1..].to_vec()));
                }
            }
        }
        let ipi = match self.core_pi_split(expr, true)? {
            Some((c, Some(Rest::One(s)))) if self.core_is_mul(s) => Some((c, Rest::One(s))),
            Some((c, Some(Rest::Product(fs)))) => Some((c, Rest::Product(fs))),
            _ => None,
        };
        Ok((ct, ipi))
    }

    /// `_quotient_templates`' shape test: `(a, v, v**k)` for `a*v**k`, `k` a negative integer and `v` no number.
    pub fn core_quotient_shape(&self, expr: TermId) -> Result<Option<(TermId, TermId, TermId)>, Refuse> {
        let args = &self.row(expr).args;
        if args.len() != 2 {
            return Ok(None);
        }
        let (mut a, mut t) = (args[0], args[1]);
        if !self.core_is_pow(t) {
            std::mem::swap(&mut a, &mut t);
        }
        if !self.core_is_pow(t) {
            return Ok(None);
        }
        let (v, k) = self.core_two_args(t)?;
        if self.core_is_number(v)? || !self.core_negative_integer(k)? {
            return Ok(None);
        }
        Ok(Some((a, v, t)))
    }

    // ---- The Pow family.

    /// `_unit_angle(b)`: `theta/pi` for `I`, `-1`, `-I`.
    pub fn core_unit_angle(&self, b: TermId) -> Result<Option<Rat>, Refuse> {
        Ok(match self.class_of(b).kind {
            Kind::ImaginaryUnit => Some(Rat::new(BigInt::from(1), BigInt::from(2))),
            Kind::NegativeOne => Some(Rat::int(1)),
            _ if self.core_is_mul(b) => match *self.row(b).args {
                [m, i] if self.class_of(m).kind == Kind::NegativeOne && self.class_of(i).kind == Kind::ImaginaryUnit => {
                    Some(Rat::new(BigInt::from(-1), BigInt::from(2)))
                }
                _ => None,
            },
            _ => None,
        })
    }

    /// `_exp_arg(b)`: `u` of `E**u` or `exp(u)`.
    pub fn core_exp_arg(&self, b: TermId) -> Result<Option<TermId>, Refuse> {
        if self.core_is_pow(b) {
            let (base, u) = self.core_two_args(b)?;
            return Ok(if self.class_of(base).kind == Kind::Exp1 { Some(u) } else { None });
        }
        let c = self.class_of(b);
        if c.kind == Kind::Function && self.class_name(c) == "exp" {
            return self.core_first(b).map(Some);
        }
        Ok(None)
    }

    /// `irrational_root(b, e)` over the constants' ids.
    pub fn core_irrational_root(&self, b: TermId, e: TermId) -> Result<bool, Refuse> {
        let Some(e) = self.core_rational(e)? else { return Ok(false) };
        if e.is_int() {
            return Ok(false);
        }
        let Some(b) = self.core_rational(b)? else { return Ok(false) };
        if !b.n.is_positive() {
            return Ok(false);
        }
        Ok(!(exact_root(&b.n, &e.d) && exact_root(&b.d, &e.d)))
    }

    /// `_pow_bound_templates`' shape test: `(b, e)` for an Add `b` and an exponent that isn't a number other than a
    /// negative integer.
    pub fn core_pow_bound_shape(&self, expr: TermId) -> Result<Option<(TermId, TermId)>, Refuse> {
        let (b, e) = self.core_two_args(expr)?;
        self.core_pow_bound_parts(b, e)
    }

    /// 6i(c): the same test on a base and exponent (a Pow Python built, which has no id of its own).
    pub fn core_pow_bound_parts(&self, b: TermId, e: TermId) -> Result<Option<(TermId, TermId)>, Refuse> {
        if self.class_of(b).flags & flag::IS_ADD == 0 || self.core_is_number(e)? && !self.core_negative_integer(e)? {
            return Ok(None);
        }
        Ok(Some((b, e)))
    }

    /// `_unit_power_units(angle, e, expr)` for a Rational `e` (`as_real_imag` is `(e, 0)`): `(predicate, value)` facts
    /// of the node, or None for another exponent.
    pub fn core_unit_power_units(&self, angle: &Rat, e: TermId) -> Result<Option<Vec<(&'static str, bool)>>, Refuse> {
        let Some(a) = self.core_rational(e)? else { return Ok(None) };
        Ok(Some(unit_power_units(angle, &a)))
    }
}

/// `integer_nthroot(y, n)[1]` for `y >= 0`, `n >= 1`.
fn exact_root(y: &BigInt, n: &BigInt) -> bool {
    if y <= &BigInt::from(1) {
        return true;
    }
    match u32::try_from(n) {
        Ok(k) => num_traits::Pow::pow(y.nth_root(k), k) == *y,
        Err(_) => false, // y >= 2 has no exact root of degree past 2**32
    }
}

/// `_unit_power_units`' facts for a rational real part `a` (imaginary part 0).
pub fn unit_power_units(angle: &Rat, a: &Rat) -> Vec<(&'static str, bool)> {
    let mut out = vec![("zero", false), ("finite", true), ("complex", true)];
    let phi = a.mul(angle);
    if phi.is_int() {
        out.push((if phi.n.is_even() { "positive" } else { "negative" }, true));
    } else if phi.d == BigInt::from(2) {
        out.push(("imaginary", true));
    } else {
        out.push(("extended_real", false));
        out.push(("imaginary", false));
    }
    out
}

/// `_quotient_rules()`.
pub fn quotient_rules() -> Vec<Rule> {
    vec![(vec![(0, "odd", true), (1, "even", true)], vec![(3, "integer", false)])]
}

/// `_pow_bound_templates`' `gen()` over the premises' indices into `INT_BOUNDS`.
pub fn pow_bound_rules(prems: &[usize]) -> Vec<Rule> {
    prems
        .iter()
        .map(|&i| {
            let mut p = prem(0, INT_BOUNDS[i].0);
            p.extend([(1, "integer", true), (1, "negative", true), (2, "finite", true)]);
            (p, vec![(3, "integer", false)])
        })
        .collect()
}

/// `IPI_GUARDS`' conditions on `c`.
#[derive(Clone, Copy, PartialEq)]
enum CWhen {
    Any,
    Integer,
    Even,
    Odd,
    HalfOdd,
    Other,
}

/// A slot of `IPI_TABLE`: `'S'` the `s`, `'N'` the node.
#[derive(Clone, Copy, PartialEq)]
enum IpiSlot {
    S,
    N,
}

type IpiLit = (IpiSlot, &'static str, bool);

/// `_ipi_table_rows()`, same order: name, premises, conclusion, `has_s` (`'s'`, else `'no s'`) and the condition on `c`.
#[allow(clippy::type_complexity)]
const IPI_TABLE: [(&str, &[IpiLit], IpiLit, bool, CWhen); 20] = {
    use CWhen::*;
    use IpiSlot::{N, S};
    [
        ("ipi.int", &[], (N, "odd", true), false, Integer),
        ("ipi.int.even", &[], (N, "positive", true), false, Even),
        ("ipi.int.odd", &[], (N, "negative", true), false, Odd),
        ("ipi.half.imaginary", &[], (N, "imaginary", true), false, HalfOdd),
        ("ipi.half.algebraic", &[], (N, "algebraic", true), false, HalfOdd),
        ("ipi.other.algebraic", &[], (N, "algebraic", true), false, Other),
        ("ipi.other.not_real", &[], (N, "extended_real", false), false, Other),
        ("ipi.other.not_imaginary", &[], (N, "imaginary", false), false, Other),
        ("ipi.other.nonzero", &[], (N, "zero", false), false, Other),
        ("ipi.s.algebraic", &[(S, "integer", true)], (N, "algebraic", true), true, Any),
        ("ipi.s.complex", &[(S, "real", true)], (N, "complex", true), true, Any),
        ("ipi.s.nonzero", &[(S, "real", true)], (N, "zero", false), true, Any),
        ("ipi.s.int", &[(S, "integer", true)], (N, "odd", true), true, Integer),
        ("ipi.s.int.even", &[(S, "integer", true)], (N, "positive", true), true, Even),
        ("ipi.s.int.odd.even", &[(S, "even", true)], (N, "positive", true), true, Odd),
        ("ipi.s.int.odd.odd", &[(S, "odd", true)], (N, "negative", true), true, Odd),
        ("ipi.s.int.odd.back_even", &[(S, "integer", true), (N, "positive", true)], (S, "even", true), true, Odd),
        ("ipi.s.int.odd.back_odd", &[(S, "integer", true), (N, "negative", true)], (S, "odd", true), true, Odd),
        ("ipi.s.half.even", &[(S, "even", true)], (N, "odd", true), true, HalfOdd),
        ("ipi.s.half.odd", &[(S, "odd", true)], (N, "imaginary", true), true, HalfOdd),
    ]
};

/// `ipi_rules(rule, c, iS, N)`: the rules it feeds `rule`, in order. `s` is `iS`.
pub fn ipi_rules(c: &Rat, s: Option<usize>, n: usize) -> Vec<Rule> {
    let int = c.is_int();
    let holds = |w: CWhen| match w {
        CWhen::Any => true,
        CWhen::Integer => int,
        CWhen::Even => int && c.n.is_even(),
        CWhen::Odd => int && !c.n.is_even(),
        CWhen::HalfOdd => !int && c.d == BigInt::from(2),
        CWhen::Other => !int && c.d != BigInt::from(2),
    };
    let lit = |(k, p, v): IpiLit| -> Lit { (if k == IpiSlot::S { s.unwrap_or(0) } else { n }, p, v) };
    IPI_TABLE
        .iter()
        .filter(|(_, _, _, has_s, w)| *has_s == s.is_some() && holds(*w))
        .map(|(_, ps, c, _, _)| (ps.iter().map(|&l| lit(l)).collect(), vec![lit(*c)]))
        .collect()
}
