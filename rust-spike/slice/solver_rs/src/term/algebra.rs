//! Term algebra on one query's table: what SymPy's `Add`, `Mul`, negation and coefficient splits build, with the args
//! in SymPy's order, so a derived term equal to an input term gets its id. Component 0, section 3 of
//! `PORT-INVENTORY.md`. Read from `sympy/core/{add,mul,expr,operations}.py`.
//!
//! Anything not handled here refuses, with a reason, and the query goes back to Python. It never guesses: infinities,
//! nan, Float, non-commutative terms, classes that override an operator, factors sharing a base, a numeric-base power
//! beside a coefficient.
use super::rat::Rat;
use super::table::{fact, flag, Kind, Refuse, TermRow, TermTable, CLASS_ADD, CLASS_MUL, V};
use super::TermId;
use num_bigint::BigInt;
use num_traits::{One, Signed, ToPrimitive, Zero};
use std::cmp::Ordering;
use std::collections::HashMap;
use std::sync::Arc;

pub(super) fn is_rational_kind(k: Kind) -> bool {
    matches!(k, Kind::Integer | Kind::Rational | Kind::Zero | Kind::One | Kind::Half | Kind::NegativeOne)
}

impl TermTable {
    fn kind(&self, t: TermId) -> Kind {
        self.class_of(t).kind
    }

    /// The value of a rational term.
    pub fn rat(&self, t: TermId) -> Option<Rat> {
        if !is_rational_kind(self.kind(t)) {
            return None;
        }
        match &*self.row(t).content {
            [V::Int(p), V::Int(q)] => Some(Rat { n: p.clone(), d: q.clone() }),
            _ => None,
        }
    }

    fn is_number_class(&self, t: TermId) -> bool {
        self.class_of(t).flags & flag::IS_NUMBER != 0
    }

    /// May this term go into Add or Mul at all?
    fn operand(&self, t: TermId) -> Result<(), Refuse> {
        let c = self.class_of(t);
        match c.kind {
            Kind::Float => return Err(Refuse("algebra: Float")),
            Kind::Infinity | Kind::NegativeInfinity | Kind::NaN | Kind::ComplexInfinity => {
                return Err(Refuse("algebra: infinity or nan"))
            }
            k if is_rational_kind(k) => return Ok(()),
            Kind::Add | Kind::Mul => {}
            _ => {
                if c.flags & flag::IS_NUMBER != 0 {
                    return Err(Refuse("algebra: a Number class without a rational value"));
                }
                if c.flags & flag::PLAIN_OPS == 0 {
                    return Err(Refuse("algebra: class overrides an operator"));
                }
            }
        }
        let bits = self.row(t).bits;
        if bits & fact::READ == 0 {
            return Err(Refuse("algebra: not an expression"));
        }
        if bits & (fact::BAD | fact::NAN | fact::FLOAT) != 0 {
            return Err(Refuse("algebra: holds an infinity, nan or Float"));
        }
        if !self.commutative_of(t)? {
            return Err(Refuse("algebra: non-commutative"));
        }
        Ok(())
    }

    /// The row for this class and content, new if the table doesn't hold it: this is where a derived term merges.
    fn intern(&mut self, class: super::ClassId, args: Box<[TermId]>, content: Arc<[V]>) -> TermId {
        if let Some(t) = self.find(class, &content) {
            return t;
        }
        // `Expr.is_number` is all args; `.has` and free symbols are the union of the args'.
        let inherit = fact::NAN | fact::BAD | fact::FLOAT | fact::UNDEF;
        let mut bits = fact::READ | fact::COMMUTATIVE;
        let mut number = true;
        let mut free: Vec<TermId> = Vec::new();
        for a in args.iter() {
            let r = self.row(*a);
            bits |= r.bits & inherit;
            number &= r.bits & fact::NUMBER != 0;
            free.extend_from_slice(&r.free);
        }
        if number {
            bits |= fact::NUMBER;
        }
        free.sort_unstable();
        free.dedup();
        let id = TermId(self.terms.len() as u32);
        self.index_insert(class, content.clone(), id);
        self.terms.push(TermRow {
            class,
            args,
            content,
            free: free.into(),
            bits,
            level: 0,
            has_power: false,
        });
        id
    }

    /// The term of this rational, under the class SymPy gives that value.
    pub fn number(&mut self, r: &Rat) -> TermId {
        let class = self.class_of_rational(r);
        let content: Arc<[V]> = vec![V::Int(r.n.clone()), V::Int(r.d.clone())].into();
        if let Some(t) = self.find(class, &content) {
            return t;
        }
        let id = TermId(self.terms.len() as u32);
        self.index_insert(class, content.clone(), id);
        self.terms.push(TermRow {
            class,
            args: Box::default(),
            content,
            free: Box::default(),
            bits: fact::READ | fact::COMMUTATIVE | fact::NUMBER,
            level: 0,
            has_power: false,
        });
        id
    }

    /// `_from_args`: no evaluation, no sort. One arg is that arg.
    fn from_args(&mut self, class: super::ClassId, args: Vec<TermId>) -> TermId {
        debug_assert!(!args.is_empty());
        if args.len() == 1 {
            return args[0];
        }
        let content: Arc<[V]> = args.iter().map(|a| V::Term(*a)).collect();
        self.intern(class, args.into(), content)
    }

    /// `Add(*args, evaluate=False)`.
    pub fn raw_add(&mut self, args: Vec<TermId>) -> TermId {
        if args.is_empty() {
            return self.number(&Rat::int(0));
        }
        self.from_args(CLASS_ADD, args)
    }

    /// `Mul(*args, evaluate=False)`.
    pub fn raw_mul(&mut self, args: Vec<TermId>) -> TermId {
        if args.is_empty() {
            return self.number(&Rat::int(1));
        }
        self.from_args(CLASS_MUL, args)
    }

    /// The rational head of a Mul and the rest of its args. A Number head that isn't rational refuses.
    fn mul_parts(&self, t: TermId) -> Result<(Rat, Vec<TermId>), Refuse> {
        let args = &self.row(t).args;
        if self.is_number_class(args[0]) {
            let c = self.rat(args[0]).ok_or(Refuse("algebra: a Mul with a Number head that isn't rational"))?;
            return Ok((c, args[1..].to_vec()));
        }
        Ok((Rat::int(1), args.to_vec()))
    }

    /// `-t`: `Rational.__neg__`, `Add.__neg__` (`Mul(-1, self)`), `Mul.__neg__`, else `Expr.__neg__`'s raw `(-1, t)`.
    pub fn neg(&mut self, t: TermId) -> Result<TermId, Refuse> {
        self.operand(t)?;
        if let Some(r) = self.rat(t) {
            return Ok(self.number(&r.neg()));
        }
        let minus = self.number(&Rat::int(-1));
        match self.kind(t) {
            Kind::Add => self.mul(vec![minus, t]),
            Kind::Mul => {
                let (c, mut rest) = self.mul_parts(t)?;
                let c = c.neg();
                if !c.is_one() {
                    let n = self.number(&c);
                    rest.insert(0, n);
                }
                Ok(self.from_args(CLASS_MUL, rest))
            }
            _ => Ok(self.from_args(CLASS_MUL, vec![minus, t])),
        }
    }

    /// `_keep_coeff(a, f)`, for a rational `a` that isn't 1.
    fn keep_coeff(&mut self, a: &Rat, f: TermId) -> Result<TermId, Refuse> {
        self.operand(f)?;
        if f == self.number(&Rat::int(1)) {
            return Ok(self.number(a));
        }
        if *a == Rat::int(-1) {
            return self.neg(f);
        }
        let an = self.number(a);
        match self.kind(f) {
            Kind::Add => Ok(self.from_args(CLASS_MUL, vec![an, f])),
            Kind::Mul => {
                let (c, mut rest) = self.mul_parts(f)?;
                let has_head = self.is_number_class(self.row(f).args[0]);
                let c = if has_head { c.mul(a) } else { a.clone() };
                if !(has_head && c.is_one()) {
                    let n = self.number(&c);
                    rest.insert(0, n);
                }
                Ok(self.from_args(CLASS_MUL, rest))
            }
            _ => self.mul(vec![an, f]),
        }
    }

    /// `Mul(*args)`.
    pub fn mul(&mut self, args: Vec<TermId>) -> Result<TermId, Refuse> {
        let one = self.number(&Rat::int(1));
        let args: Vec<TermId> = args.into_iter().filter(|a| *a != one).collect();
        match args.len() {
            0 => return Ok(one),
            1 => return Ok(args[0]),
            _ => {}
        }
        for a in &args {
            self.operand(*a)?;
        }
        if args.len() == 2 {
            // `Mul.flatten`'s two-argument path.
            let (a, b) = if self.rat(args[1]).is_some() { (args[1], args[0]) } else { (args[0], args[1]) };
            if let Some(ra) = self.rat(a).filter(|r| !r.is_zero()) {
                // `b.as_coeff_Mul()`, without interning a stripped body that nothing here keeps.
                let split = match self.kind(b) {
                    Kind::Add => Some((Rat::int(1), b)),
                    Kind::Mul => {
                        let (r, rest) = self.mul_parts(b)?;
                        (rest.len() == 1 && self.kind(rest[0]) == Kind::Add).then(|| (r, rest[0]))
                    }
                    _ => None,
                };
                if let Some((r, sum)) = split {
                    if !r.is_one() {
                        let ar = ra.mul(&r);
                        if ar.is_one() {
                            return Ok(sum);
                        }
                        let n = self.number(&ar);
                        return Ok(self.from_args(CLASS_MUL, vec![n, sum]));
                    }
                    let terms = self.row(sum).args.to_vec();
                    let mut out = Vec::with_capacity(terms.len());
                    for bi in terms {
                        out.push(self.keep_coeff(&ra, bi)?);
                    }
                    return self.add(out);
                }
            }
        }
        // The general path, for commutative factors with no shared base.
        let mut seq = args;
        let mut i = 0;
        let mut coeff = Rat::int(1);
        let mut factors: Vec<TermId> = Vec::new();
        let mut bases: Vec<TermId> = Vec::new();
        let mut unit = false;
        let mut numeric_power = false;
        let mut own_base: Option<TermId> = None;
        while i < seq.len() {
            let o = seq[i];
            i += 1;
            self.operand(o)?;
            if let Some(r) = self.rat(o) {
                coeff = coeff.mul(&r);
                continue;
            }
            let c = self.class_of(o);
            match c.kind {
                Kind::Mul => {
                    let more = self.row(o).args.to_vec();
                    seq.extend(more);
                    continue;
                }
                Kind::ImaginaryUnit => {
                    if unit {
                        return Err(Refuse("mul: more than one I"));
                    }
                    unit = true;
                    factors.push(o);
                    continue;
                }
                Kind::Pow => {
                    let (b, e) = (self.row(o).args[0], self.row(o).args[1]);
                    if self.is_number_class(b) {
                        // Alone and with no coefficient it stays as it is; beside anything numeric it can merge.
                        let plain = match (self.rat(b), self.rat(e)) {
                            (Some(rb), Some(re)) => {
                                rb.is_int() && rb.n > BigInt::one() && re.n.is_positive() && re.n < re.d
                            }
                            _ => false,
                        };
                        if !plain || numeric_power {
                            return Err(Refuse("mul: a numeric-base power"));
                        }
                        numeric_power = true;
                    }
                    if bases.contains(&b) {
                        return Err(Refuse("mul: factors share a base"));
                    }
                    bases.push(b);
                }
                _ => {
                    if c.flags & flag::PLAIN_BASE == 0 {
                        own_base = Some(o);
                    }
                    if bases.contains(&o) {
                        return Err(Refuse("mul: factors share a base"));
                    }
                    bases.push(o);
                }
            }
            factors.push(o);
        }
        if numeric_power && !coeff.is_one() {
            return Err(Refuse("mul: a coefficient beside a numeric-base power"));
        }
        // A rational coefficient on one such factor, which has nothing to merge with: `-exp(x)` from `Add.flatten`'s
        // `Mul(c, s)`. Beside any other factor it can merge, `E` beside `exp(x)` being the case this reason exists for.
        if let Some(o) = own_base {
            if factors.len() != 1 {
                return Err(Refuse("mul: class has its own as_base_exp"));
            }
            if !self.own_base_kept(o)? {
                return Err(Refuse("mul: own as_base_exp, and Mul changes the factor"));
            }
        }
        if factors.is_empty() {
            return Ok(self.number(&coeff));
        }
        if coeff.is_zero() {
            return Err(Refuse("mul: zero times a term reads facts"));
        }
        self.sort_by_compare(&mut factors)?;
        if !coeff.is_one() {
            if factors.len() == 1 && self.kind(factors[0]) == Kind::Add {
                // `Mul.flatten`, at its end: `2*(1 + a)` is `2 + 2*a`, by `coeff*f` per term.
                let n = self.number(&coeff);
                let terms = self.row(factors[0]).args.to_vec();
                let mut out = Vec::with_capacity(terms.len());
                for f in terms {
                    out.push(self.mul(vec![n, f])?);
                }
                return self.add(out);
            }
            let n = self.number(&coeff);
            factors.insert(0, n);
        }
        Ok(self.from_args(CLASS_MUL, factors))
    }

    /// `_addsort` and `_mulsort`. A tie between different terms would leave the order to the input, so it refuses.
    fn sort_by_compare(&self, v: &mut [TermId]) -> Result<(), Refuse> {
        let mut err = None;
        v.sort_by(|a, b| match self.compare(*a, *b) {
            Ok(Ordering::Equal) if a != b => {
                err = Some(Refuse("sort: compare ties two different terms"));
                Ordering::Equal
            }
            Ok(o) => o,
            Err(e) => {
                err = Some(e);
                Ordering::Equal
            }
        });
        err.map_or(Ok(()), Err)
    }

    /// `Add.flatten`'s split of one term: its coefficient and body, where the body is one term or a Mul's other args.
    fn add_term(&self, o: TermId) -> Result<(Rat, Vec<TermId>), Refuse> {
        if self.kind(o) == Kind::Mul {
            let (c, mut body) = self.mul_parts(o)?;
            if body.len() == 1 && self.kind(body[0]) == Kind::Mul {
                // An unevaluated `Mul(c, Mul(...))`: its `s` is the inner Mul, whose own args are the key.
                let (c2, inner) = self.mul_parts(body[0])?;
                if !c2.is_one() {
                    return Err(Refuse("add: a Mul nested under a coefficient has its own"));
                }
                body = inner;
            }
            return Ok((c, body));
        }
        if self.kind(o) == Kind::Pow {
            let (b, e) = (self.row(o).args[0], self.row(o).args[1]);
            if self.is_number_class(b) {
                if let Some(re) = self.rat(e) {
                    let reciprocal = self.rat(b).is_some_and(|r| r.n.is_one() && !r.d.is_one());
                    if re.is_int() || re.n.is_negative() || reciprocal {
                        return Err(Refuse("add: an unevaluated numeric power"));
                    }
                }
            }
        }
        Ok((Rat::int(1), vec![o]))
    }

    /// `Add(*args)`.
    pub fn add(&mut self, args: Vec<TermId>) -> Result<TermId, Refuse> {
        let zero = self.number(&Rat::int(0));
        let args: Vec<TermId> = args.into_iter().filter(|a| *a != zero).collect();
        match args.len() {
            0 => return Ok(zero),
            1 => return Ok(args[0]),
            _ => {}
        }
        for a in &args {
            self.operand(*a)?;
        }
        if args.len() == 2 {
            // `Add.flatten`'s two-argument path: a rational and a Mul, unmerged.
            let (a, b) = if self.rat(args[1]).is_some() { (args[1], args[0]) } else { (args[0], args[1]) };
            if self.rat(a).is_some() && self.kind(b) == Kind::Mul {
                return Ok(self.from_args(CLASS_ADD, vec![a, b]));
            }
        }
        let mut seq = args;
        let mut i = 0;
        let mut coeff = Rat::int(0);
        // Looked up only: the order is `order`, so no hash order reaches a result.
        let mut slot: HashMap<Vec<TermId>, usize> = HashMap::new();
        let mut order: Vec<(Vec<TermId>, Rat)> = Vec::new();
        while i < seq.len() {
            let o = seq[i];
            i += 1;
            self.operand(o)?;
            if let Some(r) = self.rat(o) {
                coeff = coeff.add(&r);
                continue;
            }
            if self.kind(o) == Kind::Add {
                let more = self.row(o).args.to_vec();
                seq.extend(more);
                continue;
            }
            let (c, body) = self.add_term(o)?;
            match slot.get(&body) {
                Some(&k) => order[k].1 = order[k].1.add(&c),
                None => {
                    slot.insert(body.clone(), order.len());
                    order.push((body, c));
                }
            }
        }
        let mut newseq = Vec::with_capacity(order.len() + 1);
        for (body, c) in order {
            if c.is_zero() {
                continue;
            }
            let term = if c.is_one() {
                self.from_args(CLASS_MUL, body)
            } else if body.len() > 1 || self.kind(body[0]) == Kind::Add {
                let n = self.number(&c);
                let mut v = Vec::with_capacity(body.len() + 1);
                v.push(n);
                v.extend(body);
                self.from_args(CLASS_MUL, v)
            } else {
                let n = self.number(&c);
                self.mul(vec![n, body[0]])?
            };
            newseq.push(term);
        }
        self.sort_by_compare(&mut newseq)?;
        if !coeff.is_zero() {
            let n = self.number(&coeff);
            newseq.insert(0, n);
        }
        Ok(self.raw_add(newseq))
    }

    /// `a - b`: `Add(a, -b)`.
    pub fn sub(&mut self, a: TermId, b: TermId) -> Result<TermId, Refuse> {
        let nb = self.neg(b)?;
        self.add(vec![a, nb])
    }

    /// `as_coeff_Add()`.
    pub fn coeff_add(&mut self, t: TermId) -> Result<(TermId, TermId), Refuse> {
        self.operand(t)?;
        let zero = self.number(&Rat::int(0));
        if self.rat(t).is_some() {
            return Ok((t, zero));
        }
        if self.kind(t) != Kind::Add {
            return Ok((zero, t));
        }
        let args = self.row(t).args.to_vec();
        if !self.is_number_class(args[0]) {
            return Ok((zero, t));
        }
        if self.rat(args[0]).is_none() {
            return Err(Refuse("coeff: a Number head that isn't rational"));
        }
        Ok((args[0], self.from_args(CLASS_ADD, args[1..].to_vec())))
    }

    /// `as_coeff_Mul()`.
    pub fn coeff_mul(&mut self, t: TermId) -> Result<(TermId, TermId), Refuse> {
        self.operand(t)?;
        let one = self.number(&Rat::int(1));
        if self.rat(t).is_some() {
            return Ok((t, one));
        }
        if self.kind(t) != Kind::Mul {
            return Ok((one, t));
        }
        let args = self.row(t).args.to_vec();
        if !self.is_number_class(args[0]) {
            return Ok((one, t));
        }
        if self.rat(args[0]).is_none() {
            return Err(Refuse("coeff: a Number head that isn't rational"));
        }
        Ok((args[0], self.from_args(CLASS_MUL, args[1..].to_vec())))
    }

    // ---- `default_sort_key`

    fn one_key(&self) -> Result<V, Refuse> {
        let c = &self.classes[super::table::CLASS_ONE.index()];
        Ok(tuple(vec![c.class_key.clone(), tuple(vec![int(0), tuple(vec![])]), tuple(vec![]), V::Rat(Rat::int(1))]))
    }

    /// `default_sort_key(t)`: read from Python for an input term, computed from its parts for a derived one.
    /// `Expr.sort_key` (`expr.py:168`), `as_ordered_terms` and `as_terms` (`:1179`, `:1226`).
    pub fn sort_key(&self, t: TermId) -> Result<V, Refuse> {
        if t.index() < self.n_input {
            return self.input_key(t);
        }
        let c = self.class_of(t);
        if let Some(v) = self.rat(t) {
            return Ok(tuple(vec![c.class_key.clone(), tuple(vec![int(0), tuple(vec![])]), tuple(vec![]), V::Rat(v)]));
        }
        match c.kind {
            Kind::Mul => self.mul_key(t),
            Kind::Add => self.add_key(t),
            _ => Err(Refuse("key: a derived term of another shape")),
        }
    }

    fn mul_key(&self, t: TermId) -> Result<V, Refuse> {
        let (c, fs) = self.mul_parts(t)?;
        if let [f] = fs[..] {
            let k = self.sort_key(f)?;
            let V::Tuple(k) = &k else { return Err(Refuse("key: a key that isn't a tuple")) };
            if k.len() != 4 {
                return Err(Refuse("key: a key of another length"));
            }
            if self.kind(f) == Kind::Dummy {
                // `Expr.sort_key` nests a Dummy's own key.
                let inner = V::Tuple(k.clone());
                return Ok(tuple(vec![k[0].clone(), tuple(vec![int(1), tuple(vec![inner])]), k[2].clone(), V::Rat(c)]));
            }
            return Ok(tuple(vec![k[0].clone(), k[1].clone(), k[2].clone(), V::Rat(c)]));
        }
        let mut keys = fs.iter().map(|f| self.sort_key(*f)).collect::<Result<Vec<_>, _>>()?;
        self.sort_values(&mut keys)?;
        let n = keys.len() as i64;
        let ck = self.classes[CLASS_MUL.index()].class_key.clone();
        Ok(tuple(vec![ck, tuple(vec![int(n), tuple(keys)]), self.one_key()?, V::Rat(c)]))
    }

    fn sort_values(&self, v: &mut [V]) -> Result<(), Refuse> {
        let mut err = None;
        v.sort_by(|a, b| {
            self.value_cmp(a, b).unwrap_or_else(|e| {
                err = Some(e);
                Ordering::Equal
            })
        });
        err.map_or(Ok(()), Err)
    }

    /// `is_positive` of a Number or NumberSymbol, or None if it isn't one of those.
    fn number_positive(&self, t: TermId) -> Option<bool> {
        if let Some(r) = self.rat(t) {
            return Some(r.n.is_positive());
        }
        matches!(
            self.kind(t),
            Kind::Pi | Kind::Exp1 | Kind::GoldenRatio | Kind::TribonacciConstant | Kind::EulerGamma | Kind::Catalan
        )
        .then_some(true)
    }

    fn add_key(&self, t: TermId) -> Result<V, Refuse> {
        let ck = self.classes[CLASS_ADD.index()].class_key.clone();
        let args = &self.row(t).args;
        let done = |ordered: Vec<V>| -> Result<V, Refuse> {
            let n = ordered.len() as i64;
            Ok(tuple(vec![ck.clone(), tuple(vec![int(n), tuple(ordered)]), self.one_key()?, V::Rat(Rat::int(1))]))
        };
        // `as_ordered_terms`' special case: a positive number and a negative multiple of one term, number first.
        if let [x, y] = args[..] {
            let numeric = |t: TermId| {
                let f = self.class_of(t).flags;
                f & (flag::IS_NUMBER | flag::IS_NUMBER_SYMBOL) != 0
            };
            let (a, b) = if !numeric(x) && numeric(y) { (y, x) } else { (x, y) };
            if numeric(a) && self.kind(b) == Kind::Mul && self.row(b).args.len() == 2 {
                let (m0, m1) = (self.row(b).args[0], self.row(b).args[1]);
                let head = if !numeric(m0) && numeric(m1) { m1 } else { m0 };
                if self.is_number_class(head) {
                    let pos = self.number_positive(a).ok_or(Refuse("key: a number with no sign"))?;
                    let hr = self.rat(head).ok_or(Refuse("key: a Number head that isn't rational"))?;
                    if pos && hr.n.is_negative() {
                        return done(vec![self.sort_key(a)?, self.sort_key(b)?]);
                    }
                }
            }
        }
        // `as_terms`: per term, the complex coefficient and the exponents of its bases.
        struct Row {
            term: TermId,
            coeff: (f64, f64),
            cpart: Vec<(TermId, BigInt)>,
        }
        let mut rows = Vec::with_capacity(args.len());
        let mut gens: Vec<TermId> = Vec::new();
        for &term in args.iter() {
            let (head, fs) = if let Some(r) = self.rat(term) {
                (r, vec![])
            } else if self.kind(term) == Kind::Mul {
                self.mul_parts(term)?
            } else {
                (Rat::int(1), vec![term])
            };
            let mut z = (rat_f64(&head)?, 0.0);
            let mut cpart: Vec<(TermId, BigInt)> = Vec::new();
            for f in fs {
                let row = self.row(f);
                if row.bits & fact::READ == 0 {
                    return Err(Refuse("key: not an expression"));
                }
                if !self.commutative_of(f)? {
                    return Err(Refuse("key: non-commutative"));
                }
                if row.bits & fact::NUMBER != 0 {
                    let w = self.complex_of(f)?.ok_or(Refuse("key: a closed factor with no complex value"))?;
                    z = (z.0 * w.0 - z.1 * w.1, z.0 * w.1 + z.1 * w.0);
                    continue;
                }
                if self.kind(f) == Kind::Mul {
                    return Err(Refuse("key: a Mul as a factor"));
                }
                let (b, e) = match self.power_of(f)? {
                    Some((Some(b), e)) => (b, e),
                    Some((None, _)) => return Err(Refuse("key: power base not an input term")),
                    None => (f, BigInt::one()),
                };
                match cpart.iter_mut().find(|x| x.0 == b) {
                    Some(x) => x.1 = e,
                    None => cpart.push((b, e)),
                }
                if !gens.contains(&b) {
                    gens.push(b);
                }
            }
            if !z.0.is_finite() || !z.1.is_finite() {
                return Err(Refuse("key: a coefficient that isn't finite"));
            }
            rows.push(Row { term, coeff: z, cpart });
        }
        // Python sorts a set here: a tie would leave the result to hash order, so it refuses.
        let mut gk = gens.iter().map(|g| Ok((self.sort_key(*g)?, *g))).collect::<Result<Vec<_>, Refuse>>()?;
        let mut err = None;
        gk.sort_by(|a, b| match self.value_cmp(&a.0, &b.0) {
            Ok(Ordering::Equal) => {
                err = Some(Refuse("key: two generators with one sort key"));
                Ordering::Equal
            }
            Ok(o) => o,
            Err(e) => {
                err = Some(e);
                Ordering::Equal
            }
        });
        if let Some(e) = err {
            return Err(e);
        }
        let monom = |r: &Row| -> Vec<BigInt> {
            gk.iter()
                .map(|(_, g)| r.cpart.iter().find(|x| x.0 == *g).map_or_else(BigInt::zero, |x| -&x.1))
                .collect()
        };
        let mut keyed: Vec<(Vec<BigInt>, &Row)> = rows.iter().map(|r| (monom(r), r)).collect();
        // Stable, as `sorted`: monomial, then `((bool(im), im), (re, im))`.
        keyed.sort_by(|a, b| {
            a.0.cmp(&b.0).then_with(|| {
                let ((re, im), (re2, im2)) = (a.1.coeff, b.1.coeff);
                (im != 0.0)
                    .cmp(&(im2 != 0.0))
                    .then(im.partial_cmp(&im2).unwrap_or(Ordering::Equal))
                    .then(re.partial_cmp(&re2).unwrap_or(Ordering::Equal))
            })
        });
        let keys = keyed.iter().map(|(_, r)| self.sort_key(r.term)).collect::<Result<Vec<_>, _>>()?;
        done(keys)
    }
}

fn int(n: i64) -> V {
    V::Int(BigInt::from(n))
}

fn tuple(v: Vec<V>) -> V {
    V::Tuple(v.into())
}

/// `complex(Rational)`: `evalf` at 53 bits, rounded to nearest. `p/q` in f64 is that when both fit exactly.
fn rat_f64(r: &Rat) -> Result<f64, Refuse> {
    let limit = BigInt::from(1u64 << 53);
    if r.n.abs() > limit || r.d > limit {
        return Err(Refuse("key: a rational too large for an exact complex()"));
    }
    match (r.n.to_f64(), r.d.to_f64()) {
        (Some(p), Some(q)) => Ok(p / q),
        _ => Err(Refuse("key: a rational too large for an exact complex()")),
    }
}
