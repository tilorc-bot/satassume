//! `knowledge/templates/_rows_runtime.py`: the readers of the texts of the compiled rows, over Rust's numbers, and the
//! data reader `generator` becomes. `templates/_rows.py`, the language and its compiler, is offline and stays Python.
//!
//! Python stays the owner of what Rust can't read exactly. A text or value is either read here to the value SymPy's
//! arithmetic gives, or not read at all (`None`), and the caller goes to Python's reader. Not read: `I` (the constant
//! field is real), a `number` that is no `Rational` (`Float`, `oo`, `-oo`, `nan`), a value that isn't a rational times
//! a power of `E` or `pi` (`zoo`, `sqrt(2)`, `E + 1`), and every text outside the strict grammar below.
//!
//! `wiring.py` is still Python and takes SymPy objects, so what `RowsGen` hands out is built from the Rust value at
//! this boundary. Nothing here approximates: the only numbers are `Rat` and the constant field's `Element`.
use crate::constfield::{module, rat_parts, Num, Poly};
use crate::rat::Rat;
use num_bigint::BigInt;
use num_traits::{One, Signed, ToPrimitive};
use pyo3::exceptions::PyTypeError;
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyDict, PyInt, PyList, PyString, PyTuple};

/// A longer literal or a deeper text goes to Python, whose own limits (int digits, recursion) then apply as they are.
const MAX_LITERAL: usize = 4000;
const MAX_DEPTH: usize = 64;
/// A larger exponent goes to Python, so a text can't make this reader the one that runs out of memory.
const MAX_POW: i64 = 4096;

#[derive(Clone, Copy)]
enum Op {
    Add,
    Sub,
    Mul,
    Div,
    Pow,
}

enum Ast {
    Int(BigInt),
    Name(String),
    Neg(Box<Ast>),
    Bin(Op, Box<Ast>, Box<Ast>),
    Call(String, Box<Ast>),
}

/// The part of Python's expression grammar `_read` reads, with Python's precedence. Stricter than `ast.parse`: whatever
/// it refuses goes to Python, so refusing is always safe and accepting must mean what Python means.
struct Parser<'a> {
    b: &'a [u8],
    i: usize,
    depth: usize,
}

impl Parser<'_> {
    fn spaces(&mut self) {
        while self.b.get(self.i) == Some(&b' ') {
            self.i += 1;
        }
    }

    fn peek(&self) -> Option<u8> {
        self.b.get(self.i).copied()
    }

    fn enter(&mut self) -> Option<()> {
        self.depth += 1;
        (self.depth <= MAX_DEPTH).then_some(())
    }

    fn expr(&mut self) -> Option<Ast> {
        self.enter()?;
        let mut a = self.term()?;
        loop {
            self.spaces();
            let op = match self.peek() {
                Some(b'+') => Op::Add,
                Some(b'-') => Op::Sub,
                _ => break,
            };
            self.i += 1;
            a = Ast::Bin(op, Box::new(a), Box::new(self.term()?));
        }
        self.depth -= 1;
        Some(a)
    }

    fn term(&mut self) -> Option<Ast> {
        let mut a = self.unary()?;
        loop {
            self.spaces();
            let op = match (self.peek(), self.b.get(self.i + 1)) {
                (Some(b'*'), Some(b'*')) | (Some(b'/'), Some(b'/')) => return None,
                (Some(b'*'), _) => Op::Mul,
                (Some(b'/'), _) => Op::Div,
                _ => break,
            };
            self.i += 1;
            a = Ast::Bin(op, Box::new(a), Box::new(self.unary()?));
        }
        Some(a)
    }

    fn unary(&mut self) -> Option<Ast> {
        self.enter()?;
        self.spaces();
        let a = if self.peek() == Some(b'-') {
            self.i += 1;
            Ast::Neg(Box::new(self.unary()?))
        } else {
            self.power()?
        };
        self.depth -= 1;
        Some(a)
    }

    fn power(&mut self) -> Option<Ast> {
        let base = self.atom()?;
        self.spaces();
        if self.peek() == Some(b'*') && self.b.get(self.i + 1) == Some(&b'*') {
            self.i += 2;
            return Some(Ast::Bin(Op::Pow, Box::new(base), Box::new(self.unary()?)));
        }
        Some(base)
    }

    fn atom(&mut self) -> Option<Ast> {
        self.spaces();
        let c = self.peek()?;
        let start = self.i;
        if c.is_ascii_digit() {
            while self.peek().is_some_and(|c| c.is_ascii_digit()) {
                self.i += 1;
            }
            let digits = &self.b[start..self.i];
            // `007`, `1_000`, `1.5`, `1e3`, `0x10`, `2j`, `2x`: Python's to read, or to refuse.
            if (digits[0] == b'0' && digits.len() > 1) || digits.len() > MAX_LITERAL {
                return None;
            }
            if self.peek().is_some_and(|c| c.is_ascii_alphanumeric() || c == b'_' || c == b'.') {
                return None;
            }
            return Some(Ast::Int(BigInt::parse_bytes(digits, 10)?));
        }
        if c.is_ascii_alphabetic() || c == b'_' {
            while self.peek().is_some_and(|c| c.is_ascii_alphanumeric() || c == b'_') {
                self.i += 1;
            }
            let name = std::str::from_utf8(&self.b[start..self.i]).ok()?.to_owned();
            self.spaces();
            if self.peek() != Some(b'(') {
                return Some(Ast::Name(name));
            }
            self.i += 1;
            let arg = self.expr()?;
            self.spaces();
            if self.peek()? != b')' {
                return None;        // no second argument, keyword or star here
            }
            self.i += 1;
            return Some(Ast::Call(name, Box::new(arg)));
        }
        if c == b'(' {
            self.i += 1;
            let a = self.expr()?;
            self.spaces();
            if self.peek()? != b')' {
                return None;
            }
            self.i += 1;
            return Some(a);
        }
        None
    }
}

fn parse(text: &str) -> Option<Ast> {
    // A leading space, a tab, a newline or a comment: Python's to read.
    if !text.is_ascii() || text.starts_with(' ') {
        return None;
    }
    let mut p = Parser { b: text.as_bytes(), i: 0, depth: 0 };
    let a = p.expr()?;
    p.spaces();
    (p.i == p.b.len()).then_some(a)
}

/// The integer `n`, if it is one small enough for an exponent.
fn small_exponent(n: &Num) -> Option<i64> {
    let Num::Q(r) = n else { return None };
    if !r.is_int() {
        return None;
    }
    let k = rat_parts(r).0.to_i64()?;
    (k.abs() <= MAX_POW).then_some(k)
}

/// `isqrt` of `n` when `n` is a perfect square.
fn exact_sqrt(n: &BigInt) -> Option<BigInt> {
    let r = n.sqrt();
    (&r * &r == *n).then_some(r)
}

/// `sqrt(x)` for a rational square. SymPy gives the same; everything else is Python's.
fn rational_sqrt(x: &Num) -> Option<Num> {
    let Num::Q(r) = x else { return None };
    let (n, d) = rat_parts(r);
    if n.is_negative() {
        return None;
    }
    Some(Num::Q(Rat::norm_big(exact_sqrt(&n)?, exact_sqrt(&d)?)))
}

fn constant_named(py: Python<'_>, name: &str) -> Option<Num> {
    Num::from_py(&module(py).ok()?.getattr(name).ok()?).ok()
}

/// `_read`, over Rust's numbers. `number` is `constant_value`'s `c`. `None`: not read here.
fn eval(py: Python<'_>, a: &Ast, number: Option<&Num>) -> Option<Num> {
    Some(match a {
        Ast::Int(n) => Num::Q(Rat::norm_big(n.clone(), BigInt::one())),
        Ast::Name(name) => match (name.as_str(), number) {
            ("E", _) => constant_named(py, "E")?,
            ("pi", _) => constant_named(py, "PI")?,
            ("number" | "coefficient", Some(c)) => c.clone(),
            _ => return None,       // `I`, and any other name
        },
        Ast::Neg(x) => eval(py, x, number)?.neg(),
        Ast::Bin(op, x, y) => {
            let (x, y) = (eval(py, x, number)?, eval(py, y, number)?);
            match op {
                Op::Add => x.add(&y).ok()?,
                Op::Sub => x.sub(&y).ok()?,
                Op::Mul => x.mul(&y).ok()?,
                Op::Div => x.div(&y).ok()?,   // by zero: SymPy's `zoo`, not a number here
                Op::Pow => x.pow(small_exponent(&y)?).ok()?,
            }
        }
        Ast::Call(f, x) => {
            let x = eval(py, x, number)?;
            match f.as_str() {
                "Abs" => x.abs().ok()?,
                "exp" => constant_named(py, "E")?.pow(small_exponent(&x)?).ok()?,
                "sqrt" => rational_sqrt(&x)?,
                _ => return None,
            }
        }
    })
}

/// `q * v**k` of a polynomial, `k` possibly 0 (then `v` is 0).
fn monomial(p: &Poly) -> Option<(Rat, u32, i64)> {
    match p {
        Poly::Q(q) => Some((q.clone(), 0, 0)),
        Poly::T(v, cs) => {
            let mut found = None;
            for (k, c) in cs.iter().enumerate() {
                match c {
                    Poly::Q(q) if q.is_zero() => {}
                    Poly::Q(q) if found.is_none() => found = Some((q.clone(), *v, k as i64)),
                    _ => return None,
                }
            }
            found
        }
    }
}

fn sympy_rational<'py>(py: Python<'py>, r: &Rat) -> PyResult<Bound<'py, PyAny>> {
    let sympy = py.import("sympy")?;
    let (n, d) = rat_parts(r);
    if d.is_one() {
        return sympy.getattr("Integer")?.call1((n,));
    }
    sympy.getattr("Rational")?.call1((n, d))
}

/// The SymPy object of a value, by SymPy's own arithmetic on the same parts; `None` for anything but a rational times a
/// power of one constant, which is Python's.
fn to_sympy<'py>(py: Python<'py>, x: &Num) -> PyResult<Option<Bound<'py, PyAny>>> {
    let e = match x {
        Num::Q(r) => return sympy_rational(py, r).map(Some),
        Num::E(e) => e,
    };
    let (Some((a, va, ka)), Some((b, vb, kb))) = (monomial(e.numerator()), monomial(e.denominator())) else {
        return Ok(None);
    };
    if b.is_zero() || (ka != 0 && kb != 0 && va != vb) {
        return Ok(None);
    }
    let (v, k) = if ka != 0 { (va, ka - if vb == va { kb } else { 0 }) } else { (vb, -kb) };
    let q = sympy_rational(py, &a.mul(&b.inv()))?;
    if k == 0 {
        return Ok(Some(q));
    }
    let name: String = module(py)?.getattr("_CONSTANTS")?.get_item(v)?.getattr("name")?.extract()?;
    let s = py.import("sympy")?.getattr("S")?;
    let base = match name.as_str() {
        "E" => s.getattr("Exp1")?,
        "pi" => s.getattr("Pi")?,
        _ => return Ok(None),
    };
    q.mul(base.pow(sympy_rational(py, &Rat::norm_big(BigInt::from(k), BigInt::one()))?, py.None())?).map(Some)
}

fn rational_of(c: &Bound<'_, PyAny>) -> PyResult<Option<Num>> {
    if !c.getattr("is_Rational")?.is_truthy()? {
        return Ok(None);
    }
    let (p, q): (BigInt, BigInt) = (c.getattr("p")?.extract()?, c.getattr("q")?.extract()?);
    Ok(Some(Num::Q(Rat::norm_big(p, q))))
}

fn read_text(py: Python<'_>, text: &str, number: Option<&Num>) -> Option<Num> {
    eval(py, &parse(text)?, number)
}

/// `from_text`, with `_TEXT_NAMES`: its SymPy object, or `None` for Python's reader.
#[pyfunction]
fn rows_from_text<'py>(py: Python<'py>, text: &Bound<'py, PyAny>) -> PyResult<Option<Bound<'py, PyAny>>> {
    let n = if let Ok(s) = text.cast::<PyString>() {
        read_text(py, s.to_str()?, None)
    } else if text.is_exact_instance_of::<PyInt>() {
        Some(Num::Q(Rat::norm_big(text.extract()?, BigInt::one())))
    } else {
        None
    };
    n.map_or(Ok(None), |n| to_sympy(py, &n))
}

/// `constant_value`: its SymPy object, or `None` for Python's reader.
#[pyfunction]
fn rows_constant_value<'py>(py: Python<'py>, text: &str, c: &Bound<'py, PyAny>) -> PyResult<Option<Bound<'py, PyAny>>> {
    let Some(c) = rational_of(c)? else { return Ok(None) };
    read_text(py, text, Some(&c)).map_or(Ok(None), |n| to_sympy(py, &n))
}

/// The plain data of a row: what `specs` and `schemas` hold other than the numbers.
enum Data {
    None,
    Bool(bool),
    Int(i64),
    Str(String),
    Tuple(Vec<Data>),
}

impl Data {
    fn read(x: &Bound<'_, PyAny>) -> PyResult<Data> {
        if x.is_none() {
            Ok(Data::None)
        } else if let Ok(b) = x.cast_exact::<PyBool>() {
            Ok(Data::Bool(b.is_true()))
        } else if x.is_exact_instance_of::<PyInt>() {
            Ok(Data::Int(x.extract()?))
        } else if let Ok(s) = x.cast_exact::<PyString>() {
            Ok(Data::Str(s.to_str()?.to_owned()))
        } else if let Ok(t) = x.cast_exact::<PyTuple>() {
            Ok(Data::Tuple(t.iter().map(|y| Data::read(&y)).collect::<PyResult<_>>()?))
        } else {
            Err(PyTypeError::new_err(format!("not row data: {}", x.get_type().name()?)))
        }
    }

    fn to_py<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        Ok(match self {
            Data::None => py.None().into_bound(py),
            Data::Bool(b) => PyBool::new(py, *b).to_owned().into_any(),
            Data::Int(i) => i.into_pyobject(py)?.into_any(),
            Data::Str(s) => PyString::new(py, s).into_any(),
            Data::Tuple(t) => {
                let v = t.iter().map(|y| y.to_py(py)).collect::<PyResult<Vec<_>>>()?;
                PyTuple::new(py, v)?.into_any()
            }
        })
    }

    fn items(&self) -> PyResult<&[Data]> {
        match self {
            Data::Tuple(t) => Ok(t),
            _ => Err(PyTypeError::new_err("row data: a tuple was expected")),
        }
    }
}

/// A rule of `specs`: `prem` and `concl`, and its shape if it has one.
struct Rule {
    prem: Vec<Data>,
    concl: Vec<Data>,
}

/// `generator`'s `gen`: the rows read into Rust. The attributes are the SymPy objects `wiring.py` reads.
#[pyclass(unsendable)]
pub struct RowsGen {
    /// Rule indices in the order of `specs`, per key; a Python dict, so `c` is looked up as Python's `specs.get(c)` does.
    keys: Py<PyDict>,
    by_key: Vec<Vec<Rule>>,
    #[pyo3(get)]
    terms: Py<PyAny>,
    #[pyo3(get)]
    shifts: Py<PyAny>,
    #[pyo3(get)]
    specs: Py<PyAny>,
    #[pyo3(get)]
    plain: bool,
    #[pyo3(get)]
    schemas: Py<PyAny>,
    /// The values read: (text, Rust's number).
    read: Vec<(String, Num)>,
    /// The values left to Python's reader.
    #[pyo3(get)]
    python_values: Py<PyList>,
}

/// One text of a row: Rust's number as a SymPy object, or Python's `from_text` when Rust can't read it exactly.
struct Reader<'a, 'py> {
    py: Python<'py>,
    from_text: &'a Bound<'py, PyAny>,
    read: Vec<(String, Num)>,
    python: Vec<Bound<'py, PyAny>>,
}

impl<'py> Reader<'_, 'py> {
    fn value(&mut self, text: &Data) -> PyResult<Bound<'py, PyAny>> {
        let (shown, n) = match text {
            Data::Int(i) => (i.to_string(), Some(Num::Q(Rat::norm_big(BigInt::from(*i), BigInt::one())))),
            Data::Str(s) => (s.clone(), read_text(self.py, s, None)),
            _ => (String::new(), None),
        };
        if let Some(n) = n {
            if let Some(o) = to_sympy(self.py, &n)? {
                self.read.push((shown, n));
                return Ok(o);
            }
        }
        let t = text.to_py(self.py)?;
        self.python.push(t.clone());
        self.from_text.call1((t,))
    }

    /// `_shape_object`
    fn shape(&mut self, shape: &[Data]) -> PyResult<Bound<'py, PyTuple>> {
        let mut out = Vec::with_capacity(shape.len());
        for s in shape {
            if let Data::Tuple(t) = s {
                if matches!(t.first(), Some(Data::Str(k)) if k == "value") {
                    let v = self.value(&t[1])?;
                    out.push(PyTuple::new(self.py, [t[0].to_py(self.py)?, v])?.into_any());
                    continue;
                }
            }
            out.push(s.to_py(self.py)?);
        }
        PyTuple::new(self.py, out)
    }

    /// `_term_object`
    fn term(&mut self, t: &[Data]) -> PyResult<Bound<'py, PyAny>> {
        let py = self.py;
        match t.first() {
            Some(Data::Str(k)) if k == "times" => {
                let v = self.value(&t[2])?;
                Ok(PyTuple::new(py, [t[0].to_py(py)?, t[1].to_py(py)?, v])?.into_any())
            }
            Some(Data::Str(k)) if k == "of_constant" || k == "inner" => {
                let v = t.iter().map(|y| y.to_py(py)).collect::<PyResult<Vec<_>>>()?;
                Ok(PyTuple::new(py, v)?.into_any())
            }
            _ => {
                let v = self.value(&t[1])?;
                Ok(PyTuple::new(py, [t[0].to_py(py)?, v])?.into_any())
            }
        }
    }
}

#[pymethods]
impl RowsGen {
    #[new]
    #[pyo3(signature = (terms, specs, from_text, schemas=None))]
    fn new<'py>(
        py: Python<'py>,
        terms: &Bound<'py, PyAny>,
        specs: &Bound<'py, PyAny>,
        from_text: &Bound<'py, PyAny>,
        schemas: Option<&Bound<'py, PyAny>>,
    ) -> PyResult<RowsGen> {
        let mut rd = Reader { py, from_text, read: Vec::new(), python: Vec::new() };

        // `terms = {n: tuple(_term_object(t) for t in ts) for n, ts in terms}`
        let term_objects = PyDict::new(py);
        let (mut plain, mut shifts) = (true, Vec::new());
        for pair in terms.try_iter()? {
            let pair = pair?;
            let (n, ts) = (pair.get_item(0)?, Data::read(&pair.get_item(1)?)?);
            let mut objects = Vec::new();
            let is_one = n.eq(1)?;
            for t in ts.items()? {
                let t = t.items()?;
                let o = rd.term(t)?;
                if matches!(t[0], Data::Int(_)) {
                    if is_one {
                        shifts.push(o.get_item(1)?);
                    }
                } else {
                    plain = false;
                }
                objects.push(o);
            }
            term_objects.set_item(n, PyTuple::new(py, objects)?)?;
        }

        // `specs = dict(specs)`, and `gen.specs`
        let keys = PyDict::new(py);
        let mut rows: Vec<Vec<Data>> = Vec::new();
        for pair in specs.try_iter()? {
            let pair = pair?;
            let (n, rs) = (pair.get_item(0)?, Data::read(&pair.get_item(1)?)?);
            let Data::Tuple(rs) = rs else {
                return Err(PyTypeError::new_err("rows: a tuple was expected"));
            };
            if let Some(i) = keys.get_item(&n)? {
                rows[i.extract::<usize>()?] = rs;       // a repeated key keeps its place and takes the new rows
            } else {
                keys.set_item(&n, rows.len())?;
                rows.push(rs);
            }
        }
        let spec_objects = PyDict::new(py);
        let mut by_key = Vec::with_capacity(rows.len());
        for (i, (n, _)) in keys.iter().map(|kv| (kv.0, kv.1)).enumerate() {
            let rs = std::mem::take(&mut rows[i]);
            let mut objects = Vec::with_capacity(rs.len());
            let mut rules = Vec::with_capacity(rs.len());
            for r in rs {
                let Data::Tuple(mut r) = r else {
                    return Err(PyTypeError::new_err("rule: a tuple was expected"));
                };
                if r.len() > 2 {
                    plain = false;
                    let shape = rd.shape(r[2].items()?)?;
                    objects.push(PyTuple::new(py, [r[0].to_py(py)?, r[1].to_py(py)?, shape.into_any()])?.into_any());
                } else {
                    objects.push(PyTuple::new(py, r.iter().map(|y| y.to_py(py)).collect::<PyResult<Vec<_>>>()?)?.into_any());
                }
                r.truncate(2);
                let concl = r.pop().ok_or_else(|| PyTypeError::new_err("rule: no conclusion"))?;
                let prem = r.pop().ok_or_else(|| PyTypeError::new_err("rule: no premise"))?;
                let (Data::Tuple(prem), Data::Tuple(concl)) = (prem, concl) else {
                    return Err(PyTypeError::new_err("rule: a tuple was expected"));
                };
                rules.push(Rule { prem, concl });
            }
            spec_objects.set_item(n, PyTuple::new(py, objects)?)?;
            by_key.push(rules);
        }

        // `gen.schemas`
        let mut schema_objects = Vec::new();
        if let Some(schemas) = schemas {
            for s in schemas.try_iter()? {
                let s = Data::read(&s?)?;
                let s = s.items()?;
                let picks = s[1].items()?;
                let kinds: Vec<&Data> = picks.iter().map(|p| Ok(&p.items()?[0])).collect::<PyResult<_>>()?;
                let mut pairs = Vec::with_capacity(picks.len());
                for (k, p) in kinds.iter().zip(picks) {
                    let shape = rd.shape(std::slice::from_ref(*k))?;
                    pairs.push(PyTuple::new(py, [shape.get_item(0)?, p.items()?[1].to_py(py)?])?.into_any());
                }
                schema_objects.push(PyTuple::new(py, [s[0].to_py(py)?, PyTuple::new(py, pairs)?.into_any(), s[2].to_py(py)?])?.into_any());
            }
        }

        Ok(RowsGen {
            keys: keys.unbind(),
            by_key,
            terms: term_objects.into_any().unbind(),
            shifts: PyTuple::new(py, shifts)?.into_any().unbind(),
            specs: spec_objects.into_any().unbind(),
            plain,
            schemas: PyTuple::new(py, schema_objects)?.into_any().unbind(),
            read: rd.read,
            python_values: PyList::new(py, rd.python)?.unbind(),
        })
    }

    /// `gen(R, c)`
    fn __call__(&self, py: Python<'_>, r: &Bound<'_, PyAny>, c: &Bound<'_, PyAny>) -> PyResult<()> {
        let add = |rule: &Rule| -> PyResult<()> {
            let prem = rule.prem.iter().map(|d| d.to_py(py)).collect::<PyResult<Vec<_>>>()?;
            let concl = rule.concl.iter().map(|d| d.to_py(py)).collect::<PyResult<Vec<_>>>()?;
            r.call_method1("rule", (PyList::new(py, prem)?, PyList::new(py, concl)?))?;
            Ok(())
        };
        if self.by_key.len() > 1 {
            if let Some(i) = self.keys.bind(py).get_item(c)? {
                self.by_key[i.extract::<usize>()?].iter().try_for_each(add)?;
            }
            return Ok(());
        }
        self.by_key.iter().flatten().try_for_each(add)
    }

    /// The values Rust read, (text, its Fraction or Element), for checks against the constant field.
    fn numbers<'py>(&self, py: Python<'py>) -> PyResult<Vec<(String, Bound<'py, PyAny>)>> {
        self.read.iter().map(|(t, n)| Ok((t.clone(), n.to_py(py)?))).collect()
    }
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(pyo3::wrap_pyfunction!(rows_from_text, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(rows_constant_value, m)?)?;
    m.add_class::<RowsGen>()
}
