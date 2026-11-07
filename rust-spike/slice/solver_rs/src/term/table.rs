//! One top-level query's term table, read from `convert.py`'s token streams. Section 9 of `PORT-INVENTORY.md`.
//!
//! Nothing here is kept across queries. The hash-cons index is only ever looked up, never iterated, so no hash order
//! can reach a result. `Refuse` means the query goes back to Python; it propagates and is never caught to carry on.
use super::rat::Rat;
use super::{ClassId, TermId};
use num_bigint::BigInt;
use std::cmp::Ordering;
use std::collections::HashMap;
use std::sync::Arc;

/// Why Rust won't go on with this query.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Refuse(pub &'static str);

/// A value of a content or a key. Tokens: `T_*` in `convert.py`, same order.
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub enum V {
    None,
    Bool(bool),
    Int(BigInt),
    Str(u32),
    Tuple(Arc<[V]>),
    Term(TermId),
    Rat(Rat),
    Opaque(u32),
}

/// Exact class only; `KINDS` in `convert.py`, same order.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
#[repr(u8)]
pub enum Kind {
    Add, Mul, Pow, Symbol, Dummy, Wild, Integer, Rational, Float, Zero, One, Half, NegativeOne, Infinity,
    NegativeInfinity, NaN, ComplexInfinity, ImaginaryUnit, Pi, Exp1, GoldenRatio, TribonacciConstant, EulerGamma,
    Catalan, AppliedUndef, Function, Other,
}

const KINDS: [Kind; 27] = {
    use Kind::*;
    [
        Add, Mul, Pow, Symbol, Dummy, Wild, Integer, Rational, Float, Zero, One, Half, NegativeOne, Infinity,
        NegativeInfinity, NaN, ComplexInfinity, ImaginaryUnit, Pi, Exp1, GoldenRatio, TribonacciConstant, EulerGamma,
        Catalan, AppliedUndef, Function, Other,
    ]
};

pub mod fact {
    pub const NUMBER: u8 = 1;
    pub const NAN: u8 = 2;
    pub const BAD: u8 = 4;
    pub const FLOAT: u8 = 8;
    pub const UNDEF: u8 = 16;
    pub const MAYBE_NAN: u8 = 32;
    /// Facts were read for this term: not a node of the formula's skeleton.
    pub const READ: u8 = 64;
    /// `is_commutative` is True.
    pub const COMMUTATIVE: u8 = 128;
}

/// Bits of `ClassRow::flags`: `FLAGS` in `convert.py`, same order.
pub mod flag {
    pub const IS_NUMBER: u32 = 1 << 4;
    pub const IS_NUMBER_SYMBOL: u32 = 1 << 12;
    /// The operators and coefficient splits are `Expr`'s own, at `Expr`'s priority.
    pub const PLAIN_OPS: u32 = 1 << 14;
    /// `as_base_exp` is `Expr`'s own: `(self, 1)`.
    pub const PLAIN_BASE: u32 = 1 << 15;
}

/// `_PREFIX` in `convert.py`: rows always sent first, since Rust can build these with none in the input.
pub const CLASS_ADD: ClassId = ClassId(0);
pub const CLASS_MUL: ClassId = ClassId(1);
pub const CLASS_INTEGER: ClassId = ClassId(3);
pub const CLASS_RATIONAL: ClassId = ClassId(4);
pub const CLASS_ZERO: ClassId = ClassId(5);
pub const CLASS_ONE: ClassId = ClassId(6);
pub const CLASS_NEGATIVE_ONE: ClassId = ClassId(7);
pub const CLASS_HALF: ClassId = ClassId(8);
const PREFIX_KINDS: [Kind; 9] = [
    Kind::Add, Kind::Mul, Kind::Pow, Kind::Integer, Kind::Rational, Kind::Zero, Kind::One, Kind::NegativeOne, Kind::Half,
];

pub struct ClassRow {
    pub name: u32,
    pub kind: Kind,
    /// Index in `ordering_of_classes`, or None if it isn't there.
    pub rank: Option<u32>,
    pub flags: u32,
    pub class_key: V,
    pub templates: V,
    pub structural: bool,
    pub custom_content: bool,
}

pub struct Closed {
    /// `is_finite`: None when SymPy doesn't know.
    pub is_finite: Option<bool>,
    /// `complex()` as exact f64s, when it converts.
    pub complex: Option<(f64, f64)>,
}

pub struct TermRow {
    pub class: ClassId,
    pub args: Box<[TermId]>,
    /// `_hashable_content`.
    pub content: Arc<[V]>,
    pub key: Option<V>,
    pub free: Box<[TermId]>,
    pub bits: u8,
    pub level: u8,
    pub closed: Option<Closed>,
    /// `decompose_power`: base (None if not an input term, which refuses when a key needs it) and exponent.
    pub power: Option<(Option<TermId>, BigInt)>,
}

pub struct TermTable {
    pub strings: Vec<String>,
    pub classes: Vec<ClassRow>,
    pub terms: Vec<TermRow>,
    pub settings: V,
    /// (proposition, assumptions or None): nested tuples headed by a tag string; relation atoms stay (name, lhs, rhs).
    pub formula: V,
    /// Rows from conversion; the ones after these are derived.
    pub n_input: usize,
    index: HashMap<(ClassId, Arc<[V]>), TermId>,
    /// Section 9's Symbols and Atomic numbers rows, by term: input terms only. Empty if conversion sent none.
    pub atoms: HashMap<TermId, AtomRow>,
}

/// What an atom template reads, from conversion.
#[derive(Clone, Debug)]
pub enum AtomRow {
    /// `assumptions0`, in dict order: name (a string id) and True, False or None.
    Symbol(Vec<(u32, Option<bool>)>),
    /// `const_value` over `_CONST_BASIS`, in that order.
    Constant(Vec<Option<bool>>),
}

struct Reader<'a> {
    t: &'a [i64],
    i: usize,
}

impl Reader<'_> {
    fn next(&mut self) -> Result<i64, String> {
        let v = *self.t.get(self.i).ok_or("tokens end early")?;
        self.i += 1;
        Ok(v)
    }

    fn value(&mut self, strings: &[String]) -> Result<V, String> {
        Ok(match self.next()? {
            0 => V::None,
            1 => V::Bool(false),
            2 => V::Bool(true),
            3 => V::Int(BigInt::from(self.next()?)),
            4 => {
                let s = strings.get(self.next()? as usize).ok_or("bad string index")?;
                V::Int(s.parse().map_err(|_| "bad big int")?)
            }
            5 => V::Str(self.next()? as u32),
            6 => {
                let n = self.next()? as usize;
                let mut v = Vec::with_capacity(n);
                for _ in 0..n {
                    v.push(self.value(strings)?);
                }
                V::Tuple(v.into())
            }
            7 => V::Term(TermId(self.next()? as u32)),
            8 => {
                let (p, q) = (self.value(strings)?, self.value(strings)?);
                match (p, q) {
                    (V::Int(p), V::Int(q)) => V::Rat(Rat::new(p, q)),
                    _ => return Err("bad rational".into()),
                }
            }
            9 => V::Opaque(self.next()? as u32),
            t => return Err(format!("bad token {t}")),
        })
    }

    fn tuple(&mut self, strings: &[String], want: usize) -> Result<Arc<[V]>, String> {
        match self.value(strings)? {
            V::Tuple(v) if v.len() == want => Ok(v),
            _ => Err(format!("wanted a row of {want}")),
        }
    }
}

fn int(v: &V) -> Result<i64, String> {
    match v {
        V::Int(n) => i64::try_from(n).map_err(|_| "int out of range".to_string()),
        _ => Err("wanted an int".into()),
    }
}

fn ids(v: &V) -> Result<Box<[TermId]>, String> {
    match v {
        V::Tuple(xs) => xs
            .iter()
            .map(|x| match x {
                V::Term(t) => Ok(*t),
                _ => Err("wanted a term".to_string()),
            })
            .collect(),
        _ => Err("wanted a tuple of terms".into()),
    }
}

fn bits_f64(v: &V) -> Result<f64, String> {
    Ok(f64::from_bits(int(v)? as u64))
}

fn tri(v: &V) -> Result<Option<bool>, String> {
    match v {
        V::None => Ok(None),
        V::Bool(b) => Ok(Some(*b)),
        _ => Err("wanted True, False or None".into()),
    }
}

impl TermTable {
    /// Reads the `atoms` tokens: `(term, 0, ((name, value), ...))` for a symbol, `(term, 1, (value, ...))` for a number.
    pub fn read_atoms(&mut self, tokens: &[i64], n: usize) -> Result<(), String> {
        let mut r = Reader { t: tokens, i: 0 };
        for _ in 0..n {
            let f = r.tuple(&self.strings, 3)?;
            let t = TermId(int(&f[0])? as u32);
            if t.index() >= self.n_input {
                return Err(format!("atom row: bad term {}", t.0));
            }
            let items = match &f[2] {
                V::Tuple(x) => x.clone(),
                _ => return Err("atom row: items".into()),
            };
            let row = match int(&f[1])? {
                0 => AtomRow::Symbol(
                    items
                        .iter()
                        .map(|kv| match kv {
                            V::Tuple(p) if p.len() == 2 => match p[0] {
                                V::Str(s) => Ok((s, tri(&p[1])?)),
                                _ => Err("atom row: fact name".to_string()),
                            },
                            _ => Err("atom row: fact".to_string()),
                        })
                        .collect::<Result<_, _>>()?,
                ),
                1 => AtomRow::Constant(items.iter().map(tri).collect::<Result<_, _>>()?),
                k => return Err(format!("atom row: tag {k}")),
            };
            if self.atoms.insert(t, row).is_some() {
                return Err(format!("atom row: two rows for term {}", t.0));
            }
        }
        Ok(())
    }

    pub fn from_tokens(
        strings: Vec<String>,
        classes: &[i64],
        terms: &[i64],
        powers: &[i64],
        settings: &[i64],
        formula: &[i64],
        n_classes: usize,
        n_terms: usize,
        n_powers: usize,
    ) -> Result<TermTable, String> {
        let mut r = Reader { t: classes, i: 0 };
        let mut class_rows = Vec::with_capacity(n_classes);
        for _ in 0..n_classes {
            let f = r.tuple(&strings, 8)?;
            let name = match f[0] {
                V::Str(s) => s,
                _ => return Err("class name".into()),
            };
            let kind = *KINDS.get(int(&f[1])? as usize).ok_or("bad kind")?;
            let rank = int(&f[2])?;
            class_rows.push(ClassRow {
                name,
                kind,
                rank: (rank >= 0).then_some(rank as u32),
                flags: int(&f[3])? as u32,
                class_key: f[4].clone(),
                templates: f[5].clone(),
                structural: f[6] == V::Bool(true),
                custom_content: f[7] == V::Bool(true),
            });
        }
        for (i, k) in PREFIX_KINDS.iter().enumerate() {
            if class_rows.get(i).map(|c| c.kind) != Some(*k) {
                return Err(format!("class row {i}: not the prefix"));
            }
        }
        let mut r = Reader { t: terms, i: 0 };
        let mut rows = Vec::with_capacity(n_terms);
        let mut index = HashMap::with_capacity(n_terms);
        for i in 0..n_terms {
            let f = r.tuple(&strings, 8)?;
            let class = ClassId(int(&f[0])? as u32);
            let args = ids(&f[1])?;
            let content: Arc<[V]> = match &f[2] {
                V::None => args.iter().map(|a| V::Term(*a)).collect(),
                V::Tuple(c) => c.clone(),
                _ => return Err("content".into()),
            };
            let closed = match &f[7] {
                V::None => None,
                V::Tuple(c) if c.len() == 3 => Some(Closed {
                    is_finite: match c[0] {
                        V::Bool(b) => Some(b),
                        _ => None,
                    },
                    complex: match (&c[1], &c[2]) {
                        (V::None, _) | (_, V::None) => None,
                        (a, b) => Some((bits_f64(a)?, bits_f64(b)?)),
                    },
                }),
                _ => return Err("closed".into()),
            };
            let free = match &f[4] {
                V::None => Box::default(),
                v => ids(v)?,
            };
            let id = TermId(i as u32);
            if index.insert((class, content.clone()), id).is_some() {
                return Err(format!("term {i}: two input ids for one (class, content)"));
            }
            rows.push(TermRow {
                class,
                args,
                content,
                key: (f[3] != V::None).then(|| f[3].clone()),
                free,
                bits: int(&f[5])? as u8,
                level: int(&f[6])? as u8,
                closed,
                power: None,
            });
        }
        let mut r = Reader { t: powers, i: 0 };
        for _ in 0..n_powers {
            let f = r.tuple(&strings, 3)?;
            let t = int(&f[0])? as usize;
            let b = int(&f[1])?;
            let e = match &f[2] {
                V::Int(e) => e.clone(),
                _ => return Err("power exponent".into()),
            };
            rows.get_mut(t).ok_or("power row: bad term")?.power =
                Some(((b >= 0).then_some(TermId(b as u32)), e));
        }
        let settings = Reader { t: settings, i: 0 }.value(&strings)?;
        let formula = Reader { t: formula, i: 0 }.value(&strings)?;
        Ok(TermTable { strings, classes: class_rows, terms: rows, settings, formula, n_input: n_terms, index, atoms: HashMap::new() })
    }

    pub fn len(&self) -> usize {
        self.terms.len()
    }

    pub fn row(&self, t: TermId) -> &TermRow {
        &self.terms[t.index()]
    }

    pub fn class_of(&self, t: TermId) -> &ClassRow {
        &self.classes[self.row(t).class.index()]
    }

    pub fn class_name(&self, c: &ClassRow) -> &str {
        &self.strings[c.name as usize]
    }

    /// The term with this class and content, if the table holds it: how a derived term will merge with an input term.
    pub fn find(&self, class: ClassId, content: &Arc<[V]>) -> Option<TermId> {
        self.index.get(&(class, content.clone())).copied()
    }

    pub(super) fn index_insert(&mut self, class: ClassId, content: Arc<[V]>, t: TermId) {
        self.index.insert((class, content), t);
    }

    /// The class SymPy gives this rational's value.
    pub(super) fn class_of_rational(&self, r: &Rat) -> ClassId {
        if r.is_int() {
            if r.is_zero() {
                CLASS_ZERO
            } else if r.is_one() {
                CLASS_ONE
            } else if r.neg().is_one() {
                CLASS_NEGATIVE_ONE
            } else {
                CLASS_INTEGER
            }
        } else if *r == Rat::new(BigInt::from(1), BigInt::from(2)) {
            CLASS_HALF
        } else {
            CLASS_RATIONAL
        }
    }

    /// `_cmp_name`: the same name is equal, whichever classes hold it. Ranks first, and names only if neither has one.
    fn cmp_class(&self, a: &ClassRow, b: &ClassRow) -> Ordering {
        let (na, nb) = (self.class_name(a), self.class_name(b));
        if na == nb {
            return Ordering::Equal;
        }
        match (a.rank, b.rank) {
            (None, None) => na.cmp(nb),
            (None, Some(_)) => Ordering::Greater,
            (Some(_), None) => Ordering::Less,
            (Some(x), Some(y)) => x.cmp(&y),
        }
    }

    /// `Basic.compare`.
    pub fn compare(&self, a: TermId, b: TermId) -> Result<Ordering, Refuse> {
        if a == b {
            return Ok(Ordering::Equal);
        }
        let c = self.cmp_class(self.class_of(a), self.class_of(b));
        if c != Ordering::Equal {
            return Ok(c);
        }
        let (st, ot) = (&self.row(a).content, &self.row(b).content);
        let c = st.len().cmp(&ot.len());
        if c != Ordering::Equal {
            return Ok(c);
        }
        for (l, r) in st.iter().zip(ot.iter()) {
            let c = match (l, r) {
                (V::Term(x), V::Term(y)) => self.compare(*x, *y)?,
                (V::Term(_), _) | (_, V::Term(_)) => return Err(Refuse("compare: a term against a non-term")),
                _ => self.value_cmp(l, r)?,
            };
            if c != Ordering::Equal {
                return Ok(c);
            }
        }
        Ok(Ordering::Equal)
    }

    fn kind_of(&self, t: TermId) -> Kind {
        self.class_of(t).kind
    }

    /// Python's `<` on two values of a content or a key. Types Python would raise on, and anything opaque, refuse.
    pub fn value_cmp(&self, a: &V, b: &V) -> Result<Ordering, Refuse> {
        Ok(match (a, b) {
            (V::Int(x), V::Int(y)) => x.cmp(y),
            (V::Bool(x), V::Bool(y)) => x.cmp(y),
            (V::Bool(x), V::Int(y)) => BigInt::from(*x as u8).cmp(y),
            (V::Int(x), V::Bool(y)) => x.cmp(&BigInt::from(*y as u8)),
            (V::Str(x), V::Str(y)) => self.strings[*x as usize].cmp(&self.strings[*y as usize]),
            (V::Rat(x), V::Rat(y)) => x.cmp(y),
            (V::Tuple(x), V::Tuple(y)) => {
                // A tuple's `<`: the first pair that isn't `==` decides, else the shorter is first.
                for (l, r) in x.iter().zip(y.iter()) {
                    let c = self.value_cmp(l, r)?;
                    if c != Ordering::Equal {
                        return Ok(c);
                    }
                }
                x.len().cmp(&y.len())
            }
            (V::Term(x), V::Term(y)) if x == y => Ordering::Equal,
            // SymPy's `<` on a number slot: every finite rational lies between -oo and oo. Float and nan still refuse.
            (V::Rat(_), V::Term(t)) if self.kind_of(*t) == Kind::Infinity => Ordering::Less,
            (V::Rat(_), V::Term(t)) if self.kind_of(*t) == Kind::NegativeInfinity => Ordering::Greater,
            (V::Term(t), V::Rat(_)) if self.kind_of(*t) == Kind::Infinity => Ordering::Greater,
            (V::Term(t), V::Rat(_)) if self.kind_of(*t) == Kind::NegativeInfinity => Ordering::Less,
            (V::Term(x), V::Term(y)) if self.kind_of(*x) == Kind::NegativeInfinity && self.kind_of(*y) == Kind::Infinity => Ordering::Less,
            (V::Term(x), V::Term(y)) if self.kind_of(*x) == Kind::Infinity && self.kind_of(*y) == Kind::NegativeInfinity => Ordering::Greater,
            (V::None, V::None) => return Err(Refuse("compare: None against None")),
            _ => return Err(Refuse("compare: types Python's < doesn't order")),
        })
    }

    /// `default_sort_key(a) < default_sort_key(b)`, as an ordering.
    pub fn key_cmp(&self, a: TermId, b: TermId) -> Result<Ordering, Refuse> {
        self.value_cmp(&self.sort_key(a)?, &self.sort_key(b)?)
    }
}
