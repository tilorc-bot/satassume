//! Step 6f (issue 323): `knowledge/templates/{functions,special,rootof,nodes,physics,stats}.py` over one query's table.
//! The rule builders and unit facts are pure over small ints and rationals, in Python's order (`resolve` reads rules in
//! order). The splits (`_cosh_shift_split`, `shifted`, `_doubled`) read `TermRow.args` and build with `algebra.rs`'s
//! `add`/`mul`, which refuse what they can't do exactly. `facts`, `units`, `_CACHE` and the keys stay Python (6d's
//! `_common`); the rows' generators stay Python (6g); `knowledge_f6_live.py` builds the keys from the query's objects.
use super::rat::Rat;
use super::table::{flag, Refuse, TermTable};
use super::tcore::{Lit, Rest, Rule};
use super::TermId;
use num_bigint::BigInt;
use num_integer::Integer;
use num_traits::{One, Signed};

const X: usize = 0;
const N: usize = 1;
/// `functions.PS`: the slot of `s` in `sin(pi*c*s)` / `cos(pi*c*s)`.
const PS: usize = 2;
/// `functions.CR`, `functions.CS`: the slots of `r` and `s` in `cosh(r + I*pi*c*s)`.
const CR: usize = 2;
const CS: usize = 3;

fn r1(prem: Vec<Lit>, concl: Lit) -> Rule {
    (prem, vec![concl])
}

fn cmp_one(c: &Rat) -> std::cmp::Ordering {
    // d > 0 (Rat::new normalizes)
    c.n.cmp(&c.d)
}

/// `functions._pi_trig_rules(R, cos_, c, has_s)`, the rules it appends.
pub fn pi_trig_rules(cos_: bool, c: &Rat, has_s: bool) -> Vec<Rule> {
    let mut out = Vec::new();
    if !has_s {
        out.push(r1(vec![], (N, "algebraic", true)));
        let c = if cos_ { c.add(&Rat::new(BigInt::one(), BigInt::from(2))) } else { c.clone() };
        // `c % 2` on a Rational: floor modulo, in [0, 2)
        let two_d = &c.d * 2;
        let r = Rat::new(c.n.mod_floor(&two_d), c.d.clone());
        if r.is_int() {
            out.push(r1(vec![], (N, "zero", true)));
        } else {
            if r.d == BigInt::from(2) {
                out.push(r1(vec![], (N, "odd", true)));
            }
            let pos = cmp_one(&r) == std::cmp::Ordering::Less;
            out.push(r1(vec![], (N, if pos { "positive" } else { "negative" }, true)));
        }
        return out;
    }
    out.push(r1(vec![(PS, "rational", true)], (N, "algebraic", true)));
    let integer = c.is_int();
    let half = !integer && c.d == BigInt::from(2);
    if !cos_ {
        if integer {
            out.push(r1(vec![(PS, "integer", true)], (N, "zero", true)));
        } else if half {
            out.push(r1(vec![(PS, "even", true)], (N, "zero", true)));
            out.push(r1(vec![(PS, "odd", true)], (N, "odd", true)));
        }
        return out;
    }
    if integer {
        out.push(r1(vec![(PS, "integer", true)], (N, "odd", true)));
        if c.n.is_even() {
            out.push(r1(vec![(PS, "integer", true)], (N, "positive", true)));
        } else {
            out.push(r1(vec![(PS, "even", true)], (N, "positive", true)));
            out.push(r1(vec![(PS, "odd", true)], (N, "negative", true)));
        }
    } else if half {
        out.push(r1(vec![(PS, "odd", true)], (N, "zero", true)));
        out.push(r1(vec![(PS, "even", true)], (N, "odd", true)));
    }
    out
}

/// `functions._cosh_shift_rules(R, c, has_s)`, the rules it appends (`c` an integer: its numerator's parity).
pub fn cosh_shift_rules(c: &Rat, has_s: bool) -> Vec<Rule> {
    let even_c = c.n.is_even();
    let (integer, alts): (Vec<Lit>, Vec<(Vec<Lit>, bool)>) = if !has_s {
        (vec![], vec![(vec![], even_c)])
    } else {
        let integer = vec![(CS, "integer", true)];
        let alts = if even_c {
            vec![(integer.clone(), true)]
        } else {
            vec![(vec![(CS, "even", true)], true), (vec![(CS, "odd", true)], false)]
        };
        (integer, alts)
    };
    let mut out = Vec::new();
    for (cond, even) in alts {
        let mut p = cond;
        p.push((CR, "real", true));
        if even {
            out.push(r1(p, (N, "positive", true)));
        } else {
            p.push((X, "extended_real", false));
            out.push(r1(p, (N, "negative", true)));
        }
    }
    let mut p = integer;
    p.push((CR, "imaginary", true));
    out.push(r1(p, (N, "real", true)));
    out
}

/// `functions._parts_of_round_rules()`.
pub fn parts_of_round_rules() -> Vec<Rule> {
    vec![r1(vec![(0, "finite", true)], (2, "integer", true))]
}

/// `functions._genocchi_half_rules(R, h)`, the two rules it appends.
pub fn genocchi_half_rules(h: usize) -> Vec<Rule> {
    vec![
        r1(vec![(X, "even", true), (X, "positive", true), (h, "even", true)], (N, "positive", true)),
        r1(vec![(X, "even", true), (X, "positive", true), (h, "odd", true)], (N, "negative", true)),
    ]
}

/// `functions._unit_interval_units(kind, c, expr)` for a Rational `c`: `(predicate, value)`, `false` for `Not(P(..))`.
pub fn unit_interval_units(acos: bool, c: &Rat) -> Vec<(&'static str, bool)> {
    let mut out = vec![("finite", true), ("complex", true)];
    let lo = c.n >= -&c.d;
    let hi = c.n <= c.d;
    if lo && hi {
        out.push(("real", true));
        if acos {
            out.push((if c.n < c.d { "positive" } else { "zero" }, true));
        } else {
            out.push((
                if c.n.is_positive() {
                    "positive"
                } else if c.n.is_negative() {
                    "negative"
                } else {
                    "zero"
                },
                true,
            ));
        }
    } else {
        out.push(("extended_real", false));
        if acos && c.n > c.d {
            out.push(("imaginary", true));
        } else {
            out.push(("imaginary", false));
        }
    }
    out
}

/// `nodes._accum()`.
pub fn accum_rules() -> Vec<Rule> {
    let (a, b, n) = (0, 1, 2);
    vec![r1(vec![], (n, "extended_real", true)), r1(vec![(a, "real", true), (b, "real", true)], (n, "real", true))]
}

/// `special._multigamma_rules(p)`'s `build()`.
pub fn multigamma_rules(p: &BigInt) -> Vec<Rule> {
    let (x, node, y, d) = (0, 2, 3, 4);
    let mut out = vec![
        r1(vec![(x, "real", true), (y, "integer", false)], (node, "real", true)),
        r1(vec![(x, "real", true), (y, "integer", false)], (node, "zero", false)),
        r1(vec![(x, "real", true), (d, "positive", true)], (node, "positive", true)),
        r1(vec![(x, "complex", true), (x, "extended_real", false)], (node, "complex", true)),
        r1(vec![(x, "complex", true), (x, "extended_real", false)], (node, "zero", false)),
    ];
    if *p > BigInt::one() {
        for concl in [(node, "infinite", true), (node, "extended_real", false)] {
            out.push(r1(vec![(y, "integer", true), (d, "nonpositive", true)], concl));
        }
    } else {
        for concl in [(node, "infinite", true), (node, "extended_real", false)] {
            out.push(r1(vec![(x, "integer", true), (x, "nonpositive", true)], concl));
        }
        for concl in [(node, "real", true), (node, "zero", false)] {
            out.push(r1(vec![(x, "real", true), (x, "integer", false)], concl));
        }
    }
    out
}

/// `rootof._facts(coeffs, index)`, over realroots.rs's `root_facts`.
pub fn rootof_facts(coeffs: Option<&[BigInt]>, index: &BigInt) -> Vec<(&'static str, bool)> {
    let mut out = vec![("algebraic", true), ("finite", true)];
    let Some(cs) = coeffs else { return out };
    let poly: Vec<Rat> = cs.iter().map(|c| Rat::new(c.clone(), BigInt::one())).collect();
    let Some((real, sign, imaginary)) = crate::realroots::root_facts(&poly, index) else { return out };
    out.push(("extended_real", real));
    match sign {
        Some(-1) => out.push(("negative", true)),
        Some(0) => out.push(("zero", true)),
        Some(1) => out.push(("positive", true)),
        _ => {}
    }
    if let Some(v) = imaginary {
        out.push(("imaginary", v));
    }
    out
}

/// `stats._random_units(positive, integer, real)`: the declared facts, read by conversion, as unit facts.
pub fn randomsymbol_units(positive: Option<bool>, integer: Option<bool>, real: bool) -> Vec<(&'static str, bool)> {
    let mut out = vec![("finite", true)];
    if let Some(v) = positive {
        out.push(("positive", v));
    }
    if let Some(v) = integer {
        out.push(("integer", v));
    }
    if real {
        out.push(("real", true));
    }
    out
}

/// The constant unit facts of `nodes.idx_units` and `physics.quantity_units`.
pub fn const_units(tag: &str) -> Option<Vec<(&'static str, bool)>> {
    match tag {
        "idx" => Some(vec![("integer", true)]),
        "quantity" => Some(vec![("positive", true)]),
        _ => None,
    }
}

fn same_terms(a: &[TermId], b: &[TermId]) -> bool {
    let (mut a, mut b) = (a.to_vec(), b.to_vec());
    a.sort_unstable_by_key(|t| t.0);
    b.sort_unstable_by_key(|t| t.0);
    a == b
}

impl TermTable {
    fn f6_is_add(&self, t: TermId) -> bool {
        self.class_of(t).flags & flag::IS_ADD != 0
    }

    /// `Add(*args)` is an Add of the same terms in any order (`Counter(t.args) == Counter(args)`).
    fn f6_rebuilds(&mut self, args: &[TermId]) -> Result<bool, Refuse> {
        let t = self.add(args.to_vec())?;
        Ok(self.f6_is_add(t) && same_terms(&self.row(t).args, args))
    }

    /// `functions._cosh_shift_split(arg)`: `(r, c, s)`, `s` as `core_pi_split` gives it.
    pub fn f6_cosh_shift_split(&mut self, arg: TermId) -> Result<Option<(TermId, Rat, Option<Rest>)>, Refuse> {
        if !self.f6_is_add(arg) {
            return Ok(None);
        }
        let terms: Vec<TermId> = self.row(arg).args.to_vec();
        for (i, &t) in terms.iter().enumerate() {
            let Some((c, s)) = self.core_pi_split(t, true)? else { continue };
            if !c.is_int() {
                continue;
            }
            let others: Vec<TermId> = terms.iter().enumerate().filter(|(j, _)| *j != i).map(|(_, x)| *x).collect();
            let r = if others.len() == 1 {
                others[0]
            } else {
                let r = self.add(others.clone())?;
                if !(self.f6_is_add(r) && same_terms(&self.row(r).args, &others)) {
                    return Ok(None);
                }
                r
            };
            return Ok(Some((r, c, s)));
        }
        Ok(None)
    }

    /// `functions.shifted(x, c)`: `x + c`, or `Add(x, c, evaluate=False)` for a sum whose terms don't rebuild (#184).
    pub fn f6_shifted(&mut self, x: TermId, c: &Rat) -> Result<TermId, Refuse> {
        let k = self.number(c);
        if self.f6_is_add(x) {
            let args: Vec<TermId> = self.row(x).args.to_vec();
            if !self.f6_rebuilds(&args)? {
                return Ok(self.raw_add(vec![x, k]));
            }
        }
        self.add(vec![x, k])
    }

    /// 6i(b): `a/2`, the slot `_genocchi_half` adds (`functions.wiring.template`): SymPy's `Mul(a, 1/2)`, which
    /// distributes over a sum as `mul` does.
    pub fn f6_halved(&mut self, x: TermId) -> Result<TermId, Refuse> {
        let h = self.number(&Rat::new(1.into(), 2.into()));
        self.mul(vec![h, x])
    }

    /// `special._doubled(x)`: `2*x`, or `Mul(2, x, evaluate=False)` for a sum whose terms don't rebuild.
    pub fn f6_doubled(&mut self, x: TermId) -> Result<TermId, Refuse> {
        let two = self.number(&Rat::int(2));
        if self.f6_is_add(x) {
            let args: Vec<TermId> = self.row(x).args.to_vec();
            if !self.f6_rebuilds(&args)? {
                return Ok(self.raw_mul(vec![two, x]));
            }
        }
        self.mul(vec![two, x])
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn q(n: i64, d: i64) -> Rat {
        Rat::new(BigInt::from(n), BigInt::from(d))
    }

    #[test]
    fn pi_trig_plain_signs() {
        // sin(-pi/2): r = 3/2 -> odd, negative
        let r = pi_trig_rules(false, &q(-1, 2), false);
        assert_eq!(r[1], (vec![], vec![(N, "odd", true)]));
        assert_eq!(r[2], (vec![], vec![(N, "negative", true)]));
        // cos(pi): r = 3/2
        assert_eq!(pi_trig_rules(true, &q(1, 1), false)[2].1, vec![(N, "negative", true)]);
        // sin(3*pi): zero
        assert_eq!(pi_trig_rules(false, &q(3, 1), false)[1].1, vec![(N, "zero", true)]);
    }

    #[test]
    fn unit_interval() {
        assert_eq!(unit_interval_units(true, &q(1, 1))[3], ("zero", true));
        assert_eq!(unit_interval_units(true, &q(3, 2))[3], ("imaginary", true));
        assert_eq!(unit_interval_units(false, &q(-3, 2))[3], ("imaginary", false));
    }
}
