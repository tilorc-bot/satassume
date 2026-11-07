//! One top-level query's term table, read from `convert.py`'s token streams. Section 9 of `PORT-INVENTORY.md`.
//!
//! Nothing here is kept across queries. The hash-cons index is only ever looked up, never iterated, so no hash order
//! can reach a result. `Refuse` means the query goes back to Python; it propagates and is never caught to carry on.
use super::rat::Rat;
use super::{ClassId, TermId};
use num_bigint::BigInt;
use std::cmp::Ordering;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};

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
    /// Text from a lazy read: the table's strings are fixed by then, so it carries its own.
    Text(Arc<str>),
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
    /// `isinstance(e, Expr)`.
    pub const IS_EXPR: u32 = 1 << 16;
    /// `is_Matrix` or `is_MatrixExpr`.
    pub const IS_MATRIX: u32 = 1 << 17;
    /// A subclass of `exp`. `ExpMeta` also says yes to a `Pow` of `E`, but `_from_sympy` tests `Pow` first and the rest of its
    /// `exp` branch can't pass on one: its first arg is `E`, not an Integer.
    pub const IS_EXP: u32 = 1 << 18;
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

/// What Rust asks Python for when a key needs it. Read-only on the original input term, each at most once per table.
/// `READS` in `convert.py`, same order.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
#[repr(u8)]
pub enum Read {
    Key,
    Finite,
    Complex,
    Power,
    Commutative,
    Symbol,
    Constant,
    OwnBase,
}

/// The way back to Python. `Ok(None)`: the read raised an `Exception`, which each caller refuses on as it did when these
/// were read up front. `Err`: the callback itself failed, so the query can't go on.
pub trait Reads: Send + Sync {
    fn read(&self, kind: Read, t: TermId) -> Result<Option<(Vec<i64>, Vec<String>)>, Refuse>;
}

/// `Refuse` when a read raised something other than an `Exception`: `py.rs` raises that instead of `TermRefuse`.
pub const READ_RAISED: &str = "read: raised past Exception";
/// Tokens of a read whose value holds a term the table doesn't: `T_MISS` in `convert.py`.
const T_MISS: i64 = 10;

pub struct TermRow {
    pub class: ClassId,
    pub args: Box<[TermId]>,
    /// `_hashable_content`.
    pub content: Arc<[V]>,
    pub free: Box<[TermId]>,
    pub bits: u8,
    pub level: u8,
    /// `decompose_power` can split this term, so a key asks for its base and exponent.
    pub has_power: bool,
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
    reads: Box<dyn Reads>,
    /// Lazy reads so far, `None` where the read raised. Dies with the table. The lock is never held while Python runs:
    /// Python can drop the GIL during a read, and a thread holding the GIL while it waits for this lock would deadlock.
    memo: Mutex<HashMap<(Read, TermId), Option<V>>>,
}

struct Reader<'a> {
    t: &'a [i64],
    i: usize,
    /// A lazy read's strings are its own: text is carried, not indexed.
    local: bool,
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
            5 if self.local => {
                let s = strings.get(self.next()? as usize).ok_or("bad string index")?;
                V::Text(s.as_str().into())
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

fn decode_complex(v: &V) -> Result<(f64, f64), String> {
    match v {
        V::Tuple(x) if x.len() == 2 => Ok((bits_f64(&x[0])?, bits_f64(&x[1])?)),
        _ => Err("complex: wanted two bit patterns".into()),
    }
}

fn tri(v: &V) -> Result<Option<bool>, Refuse> {
    match v {
        V::None => Ok(None),
        V::Bool(b) => Ok(Some(*b)),
        _ => Err(Refuse("read: tokens Rust can't read")),
    }
}

fn decode_power(v: &V) -> Option<(Option<TermId>, BigInt)> {
    match v {
        V::Tuple(x) if x.len() == 2 => match (&x[0], &x[1]) {
            (V::Int(b), V::Int(e)) => {
                let b = i64::try_from(b).ok()?;
                Some(((b >= 0).then_some(TermId(b as u32)), e.clone()))
            }
            _ => None,
        },
        _ => None,
    }
}

impl TermTable {
    pub fn from_tokens(
        strings: Vec<String>,
        classes: &[i64],
        terms: &[i64],
        powers: &[i64],
        settings: &[i64],
        formula: &[i64],
        n_classes: usize,
        n_terms: usize,
        reads: Box<dyn Reads>,
    ) -> Result<TermTable, String> {
        let mut r = Reader { t: classes, i: 0, local: false };
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
        let mut r = Reader { t: terms, i: 0, local: false };
        let mut rows = Vec::with_capacity(n_terms);
        let mut index = HashMap::with_capacity(n_terms);
        for i in 0..n_terms {
            let f = r.tuple(&strings, 6)?;
            let class = ClassId(int(&f[0])? as u32);
            let args = ids(&f[1])?;
            let content: Arc<[V]> = match &f[2] {
                V::None => args.iter().map(|a| V::Term(*a)).collect(),
                V::Tuple(c) => c.clone(),
                _ => return Err("content".into()),
            };
            let free = match &f[3] {
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
                free,
                bits: int(&f[4])? as u8,
                level: int(&f[5])? as u8,
                has_power: false,
            });
        }
        for t in powers {
            rows.get_mut(*t as usize).ok_or("power row: bad term")?.has_power = true;
        }
        let settings = Reader { t: settings, i: 0, local: false }.value(&strings)?;
        let formula = Reader { t: formula, i: 0, local: false }.value(&strings)?;
        Ok(TermTable {
            strings,
            classes: class_rows,
            terms: rows,
            settings,
            formula,
            n_input: n_terms,
            index,
            reads,
            memo: Mutex::new(HashMap::new()),
        })
    }

    /// A lazy read of an input term: Python's value, once per table.
    fn read(&self, kind: Read, t: TermId) -> Result<Option<V>, Refuse> {
        if let Some(v) = self.memo.lock().unwrap().get(&(kind, t)) {
            return Ok(v.clone());
        }
        let v = match self.reads.read(kind, t)? {
            None => None,
            Some((tokens, _)) if tokens == [T_MISS] => return Err(Refuse("read: a value holds a term the table doesn't")),
            Some((tokens, strings)) => Some(
                Reader { t: &tokens, i: 0, local: true }
                    .value(&strings)
                    .map_err(|_| Refuse("read: tokens Rust can't read"))?,
            ),
        };
        self.memo.lock().unwrap().insert((kind, t), v.clone());
        Ok(v)
    }

    /// What's been read so far, forcing nothing: outer None if it hasn't been.
    pub fn peek(&self, kind: Read, t: TermId) -> Option<Option<V>> {
        self.memo.lock().unwrap().get(&(kind, t)).cloned()
    }

    /// (is_finite, complex) as read so far, forcing nothing: None if neither has been.
    pub fn peek_closed(&self, t: TermId) -> Option<(Option<bool>, Option<(f64, f64)>)> {
        let (f, z) = (self.peek(Read::Finite, t), self.peek(Read::Complex, t));
        if f.is_none() && z.is_none() {
            return None;
        }
        let finite = match f {
            Some(Some(V::Bool(b))) => Some(b),
            _ => None,
        };
        Some((finite, z.flatten().and_then(|v| decode_complex(&v).ok())))
    }

    /// The `decompose_power` split as read so far, forcing nothing.
    pub fn peek_power(&self, t: TermId) -> Option<(Option<TermId>, BigInt)> {
        self.peek(Read::Power, t).flatten().and_then(|v| decode_power(&v))
    }

    /// What `symbol_units` reads of input term `t`: `assumptions0`, in dict order. Read when the template visits the term.
    /// A read that raised refuses.
    pub fn symbol_facts(&self, t: TermId) -> Result<Vec<(Arc<str>, Option<bool>)>, Refuse> {
        const BAD: Refuse = Refuse("read: tokens Rust can't read");
        match self.input_read(Read::Symbol, t)? {
            V::Tuple(items) => items
                .iter()
                .map(|kv| match kv {
                    V::Tuple(p) if p.len() == 2 => match &p[0] {
                        V::Text(name) => Ok((name.clone(), tri(&p[1])?)),
                        _ => Err(BAD),
                    },
                    _ => Err(BAD),
                })
                .collect(),
            _ => Err(BAD),
        }
    }

    /// What `constant_units` reads of input term `t`: `const_value` over `_CONST_BASIS`, in that order. As `symbol_facts`.
    pub fn constant_facts(&self, t: TermId) -> Result<Vec<Option<bool>>, Refuse> {
        match self.input_read(Read::Constant, t)? {
            V::Tuple(items) => items.iter().map(tri).collect(),
            _ => Err(Refuse("read: tokens Rust can't read")),
        }
    }

    fn input_read(&self, kind: Read, t: TermId) -> Result<V, Refuse> {
        if t.index() >= self.n_input {
            return Err(Refuse("atom: not an input term"));
        }
        self.read(kind, t)?.ok_or(Refuse("atom: read raised"))
    }

    /// How many reads the memo holds.
    pub fn reads_held(&self) -> usize {
        self.memo.lock().unwrap().len()
    }

    /// An input term's key. A skeleton node has none, and a key that raised refuses.
    pub(super) fn input_key(&self, t: TermId) -> Result<V, Refuse> {
        if self.row(t).bits & fact::READ == 0 {
            return Err(Refuse("key: not supplied"));
        }
        self.read(Read::Key, t)?.ok_or(Refuse("key: not supplied"))
    }

    /// `is_finite` of a closed input term: None when SymPy doesn't know, when the read raised, or for a term with no
    /// read, which is a derived term or one that isn't a closed `Expr`.
    pub fn finite_of(&self, t: TermId) -> Result<Option<bool>, Refuse> {
        if t.index() >= self.n_input || self.row(t).bits & fact::NUMBER == 0 {
            return Ok(None);
        }
        Ok(match self.read(Read::Finite, t)? {
            Some(V::Bool(b)) => Some(b),
            _ => None,
        })
    }

    /// `complex()` of a closed input term as exact f64s: None when it raises, or for a term with no read, as `finite_of`.
    pub fn complex_of(&self, t: TermId) -> Result<Option<(f64, f64)>, Refuse> {
        if t.index() >= self.n_input || self.row(t).bits & fact::NUMBER == 0 {
            return Ok(None);
        }
        match self.read(Read::Complex, t)? {
            None => Ok(None),
            Some(v) => decode_complex(&v).map(Some).map_err(|_| Refuse("read: tokens Rust can't read")),
        }
    }

    /// `decompose_power`: base (None if not an input term, which refuses when a key needs it) and exponent. None if this
    /// term has no split to read. An exponent that isn't an integer, or a split that raised, refuses.
    pub fn power_of(&self, t: TermId) -> Result<Option<(Option<TermId>, BigInt)>, Refuse> {
        if !self.row(t).has_power {
            return Ok(None);
        }
        let v = self.read(Read::Power, t)?.ok_or(Refuse("key: decompose_power raised"))?;
        decode_power(&v).map(Some).ok_or(Refuse("key: a power exponent that isn't an integer"))
    }

    /// `is_commutative is True`. Read for an input term; a derived term holds the bit. A read that raised is not True.
    /// Whether `Mul.flatten` gives back an input term whose class has its own `as_base_exp`. It rebuilds the factor as
    /// `Pow(b, e)`, which evaluates, so `exp(log(x), evaluate=False)` wouldn't come back. Only Python can say. A read that
    /// raised, like a False, refuses.
    pub fn own_base_kept(&self, t: TermId) -> Result<bool, Refuse> {
        if t.index() >= self.n_input {
            return Err(Refuse("mul: a derived term with its own as_base_exp"));
        }
        Ok(matches!(self.read(Read::OwnBase, t)?, Some(V::Bool(true))))
    }

    pub fn commutative_of(&self, t: TermId) -> Result<bool, Refuse> {
        if t.index() >= self.n_input {
            return Ok(self.row(t).bits & fact::COMMUTATIVE != 0);
        }
        Ok(matches!(self.read(Read::Commutative, t)?, Some(V::Bool(true))))
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
            (V::Text(x), V::Text(y)) => x.as_ref().cmp(y.as_ref()),
            (V::Str(x), V::Text(y)) => self.strings[*x as usize].as_str().cmp(y.as_ref()),
            (V::Text(x), V::Str(y)) => x.as_ref().cmp(self.strings[*y as usize].as_str()),
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
