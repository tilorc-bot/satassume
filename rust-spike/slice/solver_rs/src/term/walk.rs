//! `convert.py`'s `_Walk` in Rust (issue 323, the convert step): the run-time converter of one query's SymPy input.
//!
//! The input stays SymPy objects and the state stays the Python walker's own: `Walk` works on the `ids` dict, the
//! `objects` list, the class and string tables and the token lists `_Walk.__init__` made, so what comes out is the
//! same objects Python's walker fills, and `_Walk.read`, `power_rows` and `convert` run on it unchanged. Each item
//! (`enc`, `klass`, `term_row`, `walk`, `enc_int`) is one function here that follows the Python method statement by
//! statement, in the same order of reads, and a mask says which run here: an item that is off is Python's method,
//! called on the owner. Python's `_Walk` is the reference and the default (`convert.WALK`).
//!
//! What is read of SymPy is what the method reads: `isinstance`, `hash`/`==` through the dicts, `.args`, class
//! attributes, `_hashable_content()`, `free_symbols`, `has`, `atoms`. Nothing is built: no SymPy expression is made
//! here. Nothing is kept across queries: a `Walk` dies with its `_Walk`. `WalkCtx` holds only names of `convert.py`'s
//! module (classes, constants, functions), read once.
use pyo3::exceptions::{PyException, PyKeyError, PyOverflowError, PyValueError};
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyDict, PyInt, PyList, PyString, PyTuple, PyType};
use std::collections::HashMap;
use std::sync::atomic::{AtomicU8, Ordering};

// The items, as bits of `Walk.mask`: `convert.RUST_ITEMS`, same order.
pub const ENC: u8 = 1;
pub const KLASS: u8 = 2;
#[allow(dead_code)] // never asked for from here: only `convert` calls term_row
pub const TERM_ROW: u8 = 4;
pub const WALK: u8 = 8;
pub const ENC_INT: u8 = 16;

// Tokens: `convert.py`'s `T_*`, and `V` in table.rs.
const T_NONE: i64 = 0;
const T_FALSE: i64 = 1;
const T_TRUE: i64 = 2;
const T_INT: i64 = 3;
const T_BIG: i64 = 4;
const T_STR: i64 = 5;
const T_TUPLE: i64 = 6;
const T_TERM: i64 = 7;
const T_RAT: i64 = 8;
const T_OPAQUE: i64 = 9;

// Term fact bits and class flags past FLAGS: `convert.py`'s `F_*` and `_PLAIN_*`/`_IS_*`.
const F_NUMBER: i64 = 1;
const F_NAN: i64 = 2;
const F_BAD: i64 = 4;
const F_FLOAT: i64 = 8;
const F_UNDEF: i64 = 16;
const F_MAYBE_NAN: i64 = 32;
const F_READ: i64 = 64;
const PLAIN_OPS: i64 = 1 << 14;
const PLAIN_BASE: i64 = 1 << 15;
const IS_EXPR: i64 = 1 << 16;
const IS_MATRIX: i64 = 1 << 17;
const IS_EXP: i64 = 1 << 18;
const PLAIN_ATOMS: i64 = 1 << 19;

/// Test plants, one per item (plants 670-674; `SLICE_CONVERT_PLANT`): each writes a wrong value at one site.
static PLANT: AtomicU8 = AtomicU8::new(0);
const PLANT_ENC: u8 = 1; // 670: True encodes as False
const PLANT_KLASS: u8 = 2; // 671: a class row without the IS_EXPR flag
const PLANT_TERM_ROW: u8 = 3; // 672: a term row without the is_number bit
const PLANT_WALK: u8 = 4; // 673: args pushed unreversed, so ids aren't by first sight
const PLANT_ENC_INT: u8 = 5; // 674: a negative int loses its sign

fn planted(p: u8) -> bool {
    PLANT.load(Ordering::Relaxed) == p
}

#[pyfunction]
fn walk_plant(p: u8) {
    PLANT.store(p, Ordering::Relaxed);
}

/// Names of `convert.py`'s module, read once: classes, constants and the functions that stay Python.
#[pyclass(name = "WalkCtx", frozen)]
pub struct WalkCtx {
    basic: Py<PyAny>,
    rational: Py<PyAny>,
    expr: Py<PyAny>,
    function: Py<PyAny>,
    applied_undef: Py<PyAny>,
    exp: Py<PyAny>,
    float: Py<PyAny>,
    nan: Py<PyAny>,
    neg_inf: Py<PyAny>,
    integral: Py<PyAny>,
    ordering: Py<PyAny>,
    kind_of: Py<PyDict>,
    k_undef: i64,
    k_function: i64,
    k_other: i64,
    flags: Vec<Py<PyString>>,
    ops: Vec<Py<PyString>>,
    kept_classes: Py<PyAny>,
    skeleton: Py<PyAny>,
    bad: Py<PyTuple>,
    keep: Py<PyAny>,
    not_in_table: Py<PyAny>,
    templates_for: Py<PyAny>,
    registry: Py<PyAny>,
    template_name: Py<PyAny>,
    structural_class: Py<PyAny>,
    may_be_nan: Py<PyAny>,
    constructed_nc: Py<PyAny>,
    py_enc: Py<PyAny>,
    py_enc_int: Py<PyAny>,
    py_walk: Py<PyAny>,
    py_klass: Py<PyAny>,
    getattr: Py<PyAny>,
    reversed: Py<PyAny>,
    int_t: Py<PyAny>,
    i64_lo: Py<PyAny>,
    i64_hi: Py<PyAny>,
}

#[pymethods]
impl WalkCtx {
    #[new]
    fn new(m: &Bound<'_, PyAny>) -> PyResult<Self> {
        let py = m.py();
        let g = |n: &str| -> PyResult<Py<PyAny>> { Ok(m.getattr(n)?.unbind()) };
        let names = |n: &str| -> PyResult<Vec<Py<PyString>>> {
            m.getattr(n)?.try_iter()?.map(|x| Ok(PyString::intern(py, x?.extract::<String>()?.as_str()).unbind())).collect()
        };
        let index = m.getattr("_KIND_INDEX")?;
        let kind = |n: &str| -> PyResult<i64> { index.get_item(n)?.extract() };
        let kind_of = PyDict::new(py);
        for (cls, name) in m.getattr("_KIND_OF")?.cast::<PyDict>()?.iter() {
            kind_of.set_item(cls, index.get_item(name)?)?;
        }
        let s = m.getattr("S")?;
        let walk = m.getattr("_Walk")?;
        let builtins = py.import("builtins")?;
        let i64v = m.getattr("_I64")?;
        Ok(WalkCtx {
            basic: g("Basic")?,
            rational: g("Rational")?,
            expr: g("Expr")?,
            function: g("Function")?,
            applied_undef: g("AppliedUndef")?,
            exp: g("exp")?,
            float: g("Float")?,
            nan: s.getattr("NaN")?.unbind(),
            neg_inf: s.getattr("NegativeInfinity")?.unbind(),
            integral: m.getattr("numbers")?.getattr("Integral")?.unbind(),
            ordering: g("ordering_of_classes")?,
            kind_of: kind_of.unbind(),
            k_undef: kind("AppliedUndef")?,
            k_function: kind("Function")?,
            k_other: kind("Other")?,
            flags: names("FLAGS")?,
            ops: names("_OPS")?,
            kept_classes: g("_KEPT_CLASSES")?,
            skeleton: g("_SKELETON")?,
            bad: PyTuple::new(py, m.getattr("_BAD")?.try_iter()?.collect::<PyResult<Vec<_>>>()?)?.unbind(),
            keep: g("_Keep")?,
            not_in_table: g("_NotInTable")?,
            templates_for: g("TEMPLATES_FOR")?,
            registry: g("registry")?,
            template_name: g("_template_name")?,
            structural_class: g("_structural_class")?,
            may_be_nan: g("_may_be_nan")?,
            constructed_nc: g("constructed_noncommutative")?,
            py_enc: walk.getattr("enc")?.unbind(),
            py_enc_int: walk.getattr("enc_int")?.unbind(),
            py_walk: walk.getattr("walk")?.unbind(),
            py_klass: walk.getattr("klass")?.unbind(),
            getattr: builtins.getattr("getattr")?.unbind(),
            reversed: builtins.getattr("reversed")?.unbind(),
            int_t: builtins.getattr("int")?.unbind(),
            i64_lo: i64v.neg()?.unbind(),
            i64_hi: i64v.unbind(),
        })
    }
}

/// One `_Walk`'s Rust half. `strings`, `string_ids` and `reading` live here because `_Walk.read` replaces them: the
/// Python object's attributes of those names are properties onto these.
#[pyclass(name = "Walk")]
pub struct Walk {
    ctx: Py<WalkCtx>,
    mask: u8,
    ids: Option<Py<PyDict>>,
    objects: Option<Py<PyList>>,
    classes: Option<Py<PyDict>>,
    class_rows: Option<Py<PyList>>,
    opaque: Option<Py<PyList>>,
    counts: Option<Py<PyDict>>,
    #[pyo3(get, set)]
    strings: Py<PyList>,
    #[pyo3(get, set)]
    string_ids: Py<PyDict>,
    #[pyo3(get, set)]
    reading: bool,
    /// `isinstance(v, numbers.Integral)` by the value's class, for this walk: the ABC's answer is by class.
    integral: HashMap<usize, (Py<PyType>, bool)>,
    /// `Basic._hashable_content`, read once per walk.
    basic_content: Option<Py<PyAny>>,
}

/// One call's view of the walk: the handles, taken out so that no borrow of `Walk` is held across a Python call
/// (a Python method of the owner can come back in here).
struct W<'py> {
    py: Python<'py>,
    slf: Bound<'py, Walk>,
    cx: Bound<'py, WalkCtx>,
    o: Bound<'py, PyAny>,
    mask: u8,
    ids: Bound<'py, PyDict>,
    objects: Bound<'py, PyList>,
    classes: Bound<'py, PyDict>,
    class_rows: Bound<'py, PyList>,
    opaque: Bound<'py, PyList>,
    counts: Bound<'py, PyDict>,
    strings: Bound<'py, PyList>,
    string_ids: Bound<'py, PyDict>,
    reading: bool,
}

fn unbound() -> PyErr {
    PyValueError::new_err("Walk: bind() first")
}

fn type_name<'py>(t: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    t.get_type().getattr(intern!(t.py(), "__name__"))
}

fn is_subclass(cls: &Bound<'_, PyAny>, of: &Py<PyAny>) -> PyResult<bool> {
    cls.cast::<PyType>()?.is_subclass(of.bind(cls.py()))
}

/// `Py_EnterRecursiveCall` around `enc`'s own recursion: a nesting Python's walker ends with RecursionError ends so here.
struct Depth;

impl Depth {
    fn enter() -> PyResult<Depth> {
        if unsafe { pyo3::ffi::Py_EnterRecursiveCall(c" in convert's walk".as_ptr()) } != 0 {
            return Err(Python::attach(|py| PyErr::fetch(py)));
        }
        Ok(Depth)
    }
}

impl Drop for Depth {
    fn drop(&mut self) {
        unsafe { pyo3::ffi::Py_LeaveRecursiveCall() }
    }
}

impl<'py> W<'py> {
    fn new(slf: &Bound<'py, Walk>, o: &Bound<'py, PyAny>) -> PyResult<W<'py>> {
        let py = slf.py();
        let b = slf.borrow();
        Ok(W {
            py,
            slf: slf.clone(),
            cx: b.ctx.bind(py).clone(),
            o: o.clone(),
            mask: b.mask,
            ids: b.ids.as_ref().ok_or_else(unbound)?.bind(py).clone(),
            objects: b.objects.as_ref().ok_or_else(unbound)?.bind(py).clone(),
            classes: b.classes.as_ref().ok_or_else(unbound)?.bind(py).clone(),
            class_rows: b.class_rows.as_ref().ok_or_else(unbound)?.bind(py).clone(),
            opaque: b.opaque.as_ref().ok_or_else(unbound)?.bind(py).clone(),
            counts: b.counts.as_ref().ok_or_else(unbound)?.bind(py).clone(),
            strings: b.strings.bind(py).clone(),
            string_ids: b.string_ids.bind(py).clone(),
            reading: b.reading,
        })
    }

    fn keep<T>(&self, reason: &str, detail: Bound<'py, PyAny>) -> PyResult<T> {
        Err(PyErr::from_value(self.cx.get().keep.bind(self.py).call1((reason, detail))?))
    }

    /// `getattr(o, name, default)`, by the builtin: a missing attribute costs no exception.
    fn getattr3(&self, o: &Bound<'py, PyAny>, name: &Bound<'py, PyString>, default: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        self.cx.get().getattr.bind(self.py).call1((o, name, default))
    }

    /// `_Walk.s`.
    fn s(&self, text: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        if let Some(i) = self.string_ids.get_item(text)? {
            if !i.is_none() {
                return Ok(i);
            }
        }
        let i = self.strings.len().into_pyobject(self.py)?.into_any();
        self.string_ids.set_item(text, &i)?;
        self.strings.append(text)?;
        Ok(i)
    }

    /// `_Walk.term`.
    fn term(&self, t: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        if let Some(i) = self.ids.get_item(t)? {
            if !i.is_none() {
                return Ok(i);
            }
        }
        if self.reading {
            return Err(PyErr::from_value(self.cx.get().not_in_table.bind(self.py).call0()?));
        }
        self.walk(t)?;
        self.ids.get_item(t)?.ok_or_else(|| PyKeyError::new_err((t.clone().unbind(),)))
    }

    // ---- the items: Rust's if the mask says so, else Python's method on the owner

    fn enc(&self, v: &Bound<'py, PyAny>, out: &Bound<'py, PyList>, key: bool) -> PyResult<()> {
        if self.mask & ENC != 0 { return self.enc_native(v, out, key); } //@call enc
        self.cx.get().py_enc.bind(self.py).call1((&self.o, v, out, key)).map(drop)
    }

    fn enc_int(&self, n: &Bound<'py, PyAny>, out: &Bound<'py, PyList>) -> PyResult<()> {
        self.cx.get().py_enc_int.bind(self.py).call1((&self.o, n, out)).map(drop)
    }

    fn walk(&self, root: &Bound<'py, PyAny>) -> PyResult<()> {
        self.cx.get().py_walk.bind(self.py).call1((&self.o, root)).map(drop)
    }

    fn klass(&self, cls: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        if self.mask & KLASS != 0 { return self.klass_native(cls); } //@call klass
        self.cx.get().py_klass.bind(self.py).call1((&self.o, cls))
    }

    //@begin enc
    /// `isinstance(v, numbers.Integral)`: an exact int is one; any other class is asked of the ABC once per walk.
    fn is_integral(&self, v: &Bound<'py, PyAny>) -> PyResult<bool> {
        if v.is_exact_instance_of::<PyInt>() {
            return Ok(true);
        }
        let t = v.get_type();
        let k = t.as_ptr() as usize;
        if let Some(b) = self.slf.borrow().integral.get(&k) {
            return Ok(b.1);
        }
        let b = v.is_instance(self.cx.get().integral.bind(self.py))?;
        self.slf.borrow_mut().integral.insert(k, (t.unbind(), b));
        Ok(b)
    }

    /// `_Walk.enc`.
    fn enc_native(&self, v: &Bound<'py, PyAny>, out: &Bound<'py, PyList>, key: bool) -> PyResult<()> {
        let py = self.py;
        let cx = self.cx.get();
        if v.is_instance(cx.basic.bind(py))? {
            if key && v.is_instance(cx.rational.bind(py))? {
                out.append(T_RAT)?;
                self.enc_int(&v.getattr(intern!(py, "p"))?, out)?;
                self.enc_int(&v.getattr(intern!(py, "q"))?, out)?;
            } else {
                let i = self.term(v)?;
                out.append(T_TERM)?;
                out.append(i)?;
            }
        } else if v.is_none() {
            out.append(T_NONE)?;
        } else if v.is(&PyBool::new(py, true).to_owned()) {
            out.append(if planted(PLANT_ENC) { T_FALSE } else { T_TRUE })?;
        } else if v.is(&PyBool::new(py, false).to_owned()) {
            out.append(T_FALSE)?;
        } else if self.is_integral(v)? {
            if v.is_exact_instance_of::<PyInt>() {
                self.enc_int(v, out)?;
            } else {
                self.enc_int(&cx.int_t.bind(py).call1((v,))?, out)?;
            }
        } else if v.is_instance_of::<PyString>() {
            let i = self.s(v)?;
            out.append(T_STR)?;
            out.append(i)?;
        } else if v.is_instance_of::<PyTuple>() {
            let n = v.len()?;
            out.append(T_TUPLE)?;
            out.append(n)?;
            let _d = Depth::enter()?;
            if let Ok(t) = v.cast_exact::<PyTuple>() {
                for x in t.iter() {
                    self.enc(&x, out, key)?;
                }
            } else {
                for x in v.try_iter()? {
                    self.enc(&x?, out, key)?;
                }
            }
        } else {
            let k = intern!(py, "opaque");
            let n = self.counts.get_item(k)?.ok_or_else(|| PyKeyError::new_err("opaque"))?;
            self.counts.set_item(k, n.add(1)?)?;
            let i = self.opaque.len();
            out.append(T_OPAQUE)?;
            out.append(i)?;
            self.opaque.append(v)?;
        }
        Ok(())
    }
    //@end enc

    //@begin klass
    /// `_Walk.klass`: the class's row, once per class under `==`.
    fn klass_native(&self, cls: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        let py = self.py;
        let cx = self.cx.get();
        if let Some(c) = self.classes.get_item(cls)? {
            if !c.is_none() {
                return Ok(c);
            }
        }
        let c = self.classes.len().into_pyobject(py)?.into_any();
        self.classes.set_item(cls, &c)?;
        let name = cls.getattr(intern!(py, "__name__"))?;
        let rank = match cx.ordering.bind(py).call_method1(intern!(py, "index"), (&name,)) {
            Ok(r) => r,
            Err(e) if e.is_instance_of::<PyValueError>(py) => (-1i64).into_pyobject(py)?.into_any(),
            Err(e) => return Err(e),
        };
        let kind = if is_subclass(cls, &cx.applied_undef)? {
            cx.k_undef.into_pyobject(py)?.into_any()
        } else {
            match cx.kind_of.bind(py).get_item(cls)? {
                Some(k) => k,
                None if is_subclass(cls, &cx.function)? => cx.k_function.into_pyobject(py)?.into_any(),
                None => cx.k_other.into_pyobject(py)?.into_any(),
            }
        };
        let no = PyBool::new(py, false).to_owned();
        let yes = PyBool::new(py, true).to_owned();
        let mut flags = 0i64;
        for (bit, f) in cx.flags.iter().enumerate() {
            if self.getattr3(cls, f.bind(py), no.as_any())?.is(&yes) {
                flags |= 1 << bit;
            }
        }
        let expr = cx.expr.bind(py);
        let is_expr = is_subclass(cls, &cx.expr)?;
        if is_expr && !self.getattr3(cls, intern!(py, "is_Order"), no.as_any())?.is_truthy()? {
            let op = intern!(py, "_op_priority");
            if cls.getattr(op)?.eq(expr.getattr(op)?)? {
                let mut plain = true;
                for f in &cx.ops {
                    if !cls.getattr(f.bind(py))?.is(&expr.getattr(f.bind(py))?) {
                        plain = false;
                        break;
                    }
                }
                if plain {
                    flags |= PLAIN_OPS;
                }
            }
        }
        let abe = intern!(py, "as_base_exp");
        if is_subclass(cls, &cx.expr)? && cls.getattr(abe)?.is(&expr.getattr(abe)?) {
            flags |= PLAIN_BASE;
        }
        if is_subclass(cls, &cx.expr)? && !planted(PLANT_KLASS) {
            flags |= IS_EXPR;
        }
        if self.getattr3(cls, intern!(py, "is_Matrix"), no.as_any())?.is_truthy()?
            || self.getattr3(cls, intern!(py, "is_MatrixExpr"), no.as_any())?.is_truthy()?
        {
            flags |= IS_MATRIX;
        }
        if is_subclass(cls, &cx.exp)? {
            flags |= IS_EXP;
        }
        let basic = cx.basic.bind(py);
        let atoms = intern!(py, "atoms");
        if is_subclass(cls, &cx.basic)? && cls.getattr(atoms)?.is(&basic.getattr(atoms)?) {
            flags |= PLAIN_ATOMS;
        }
        // try: ckey = cls.class_key(); found = (TEMPLATES_FOR[0] or registry.templates_for)(cls); except Exception
        let row = (|| -> PyResult<(Bound<'py, PyAny>, Bound<'py, PyAny>)> {
            let ckey = cls.call_method0(intern!(py, "class_key"))?;
            let mut tf = cx.templates_for.bind(py).get_item(0)?;
            if !tf.is_truthy()? {
                tf = cx.registry.bind(py).getattr(intern!(py, "templates_for"))?;
            }
            Ok((ckey, tf.call1((cls,))?))
        })();
        let (ckey, found) = match row {
            Ok(x) => x,
            Err(e) if e.is_instance_of::<PyException>(py) => {
                let detail = format!("{}: {}", name.str()?.to_cow()?, e.get_type(py).getattr(intern!(py, "__name__"))?.str()?.to_cow()?);
                return self.keep("class-no-row", detail.into_pyobject(py)?.into_any());
            }
            Err(e) => return Err(e),
        };
        // names = tuple(sorted(_template_name(f) for f in found))
        let names = PyList::empty(py);
        for f in found.try_iter()? {
            names.append(cx.template_name.bind(py).call1((f?,))?)?;
        }
        names.sort()?;
        let names = names.to_tuple();
        // any(not getattr(f, '__module__', '').startswith('satassume.') for f in found)
        let empty = intern!(py, "");
        for f in found.try_iter()? {
            let m = self.getattr3(&f?, intern!(py, "__module__"), empty.as_any())?;
            let ours = match m.cast_exact::<PyString>() {
                Ok(s) => s.to_cow()?.starts_with("satassume."),
                Err(_) => m.call_method1(intern!(py, "startswith"), ("satassume.",))?.is_truthy()?,
            };
            if !ours {
                return self.keep("non-default-registry", name);
            }
        }
        let out = &self.class_rows;
        out.append(T_TUPLE)?;
        out.append(8)?;
        let si = self.s(&name)?;
        out.append(T_STR)?;
        out.append(si)?;
        out.append(T_INT)?;
        out.append(kind)?;
        out.append(T_INT)?;
        out.append(rank)?;
        out.append(T_INT)?;
        out.append(flags)?;
        self.enc(&ckey, out, false)?;
        self.enc(names.as_any(), out, false)?;
        self.enc(&cx.structural_class.bind(py).call1((cls,))?, out, false)?;
        let hc = intern!(py, "_hashable_content");
        let own = !cls.getattr(hc)?.is(&basic.getattr(hc)?);
        self.enc(PyBool::new(py, own).as_any(), out, false)?;
        Ok(c)
    }
    //@end klass

    //@begin term_row
    /// `_Walk.term_row`: one term's row.
    fn term_row_native(&self, t: &Bound<'py, PyAny>, out: &Bound<'py, PyList>) -> PyResult<()> {
        let py = self.py;
        let cx = self.cx.get();
        let ty = t.get_type();
        let c = self.classes.get_item(&ty)?.ok_or_else(|| PyKeyError::new_err((ty.clone().unbind(),)))?;
        let args = t.getattr(intern!(py, "args"))?;
        let n = args.len()?;
        out.append(T_TUPLE)?;
        out.append(6)?;
        out.append(T_INT)?;
        out.append(c)?;
        out.append(T_TUPLE)?;
        out.append(n)?;
        for a in args.try_iter()? {
            let a = a?;
            let i = self.ids.get_item(&a)?.ok_or_else(|| PyKeyError::new_err((a.clone().unbind(),)))?;
            out.append(T_TERM)?;
            out.append(i)?;
        }
        let hc = intern!(py, "_hashable_content");
        let base = self.slf.borrow().basic_content.as_ref().map(|x| x.bind(py).clone());
        let base = match base {
            Some(b) => b,
            None => {
                let b = cx.basic.bind(py).getattr(hc)?;
                self.slf.borrow_mut().basic_content = Some(b.clone().unbind());
                b
            }
        };
        if ty.getattr(hc)?.is(&base) {
            out.append(T_NONE)?;
        } else {
            let content = t.call_method0(hc)?;
            let content = match content.cast_exact::<PyTuple>() {
                Ok(x) => x.clone(),
                Err(_) => PyTuple::new(py, content.try_iter()?.collect::<PyResult<Vec<_>>>()?)?,
            };
            self.enc(content.as_any(), out, false)?;
        }
        if t.is_instance(cx.skeleton.bind(py))? {
            for x in [T_NONE, T_INT, 0, T_INT, 0] {
                out.append(x)?;
            }
            return Ok(());
        }
        if t.is(cx.nan.bind(py)) {
            self.term(cx.neg_inf.bind(py))?;
        }
        let free = t.getattr(intern!(py, "free_symbols"))?;
        let mut fid = Vec::new();
        for x in free.try_iter()? {
            fid.push(self.term(&x?)?.extract::<i64>()?);
        }
        fid.sort_unstable();
        out.append(T_TUPLE)?;
        out.append(fid.len())?;
        for i in fid {
            out.append(T_TERM)?;
            out.append(i)?;
        }
        let no = PyBool::new(py, false).to_owned();
        let number = self.getattr3(t, intern!(py, "is_number"), no.as_any())?.is(&PyBool::new(py, true).to_owned());
        let mut bits = F_READ;
        if number && !planted(PLANT_TERM_ROW) {
            bits |= F_NUMBER;
        }
        let has = intern!(py, "has");
        if t.call_method1(has, (cx.nan.bind(py),))?.is_truthy()? {
            bits |= F_NAN;
        }
        if t.call_method1(has, cx.bad.bind(py))?.is_truthy()? {
            bits |= F_BAD;
        }
        if t.call_method1(has, (cx.float.bind(py),))?.is_truthy()? {
            bits |= F_FLOAT;
        }
        if t.call_method1(intern!(py, "atoms"), (cx.applied_undef.bind(py),))?.is_truthy()? {
            bits |= F_UNDEF;
        }
        if cx.may_be_nan.bind(py).call1((t,))?.is_truthy()? {
            bits |= F_MAYBE_NAN;
        }
        let nc = cx.constructed_nc.bind(py).call1((t,))?;
        out.append(T_INT)?;
        out.append(bits)?;
        out.append(T_INT)?;
        out.append(nc)
    }
    //@end term_row
}

#[pymethods]
impl Walk {
    #[new]
    fn new(py: Python<'_>, ctx: Py<WalkCtx>, mask: u8) -> Self {
        Walk {
            ctx,
            mask,
            ids: None,
            objects: None,
            classes: None,
            class_rows: None,
            opaque: None,
            counts: None,
            strings: PyList::empty(py).unbind(),
            string_ids: PyDict::new(py).unbind(),
            reading: false,
            integral: HashMap::new(),
            basic_content: None,
        }
    }

    /// The state `_Walk.__init__` made: Rust fills these same objects.
    fn bind(&mut self, ids: Py<PyDict>, objects: Py<PyList>, classes: Py<PyDict>, class_rows: Py<PyList>, opaque: Py<PyList>, counts: Py<PyDict>) {
        self.ids = Some(ids);
        self.objects = Some(objects);
        self.classes = Some(classes);
        self.class_rows = Some(class_rows);
        self.opaque = Some(opaque);
        self.counts = Some(counts);
    }

    // Each takes the owner first: the `_Walk` whose Python methods answer the items that are off.
    fn enc<'py>(slf: &Bound<'py, Self>, o: &Bound<'py, PyAny>, v: &Bound<'py, PyAny>, out: &Bound<'py, PyList>, key: bool) -> PyResult<()> { W::new(slf, o)?.enc_native(v, out, key) } //@call enc
    fn klass<'py>(slf: &Bound<'py, Self>, o: &Bound<'py, PyAny>, cls: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> { W::new(slf, o)?.klass_native(cls) } //@call klass
    fn term_row<'py>(slf: &Bound<'py, Self>, o: &Bound<'py, PyAny>, t: &Bound<'py, PyAny>, out: &Bound<'py, PyList>) -> PyResult<()> { W::new(slf, o)?.term_row_native(t, out) } //@call term_row
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<WalkCtx>()?;
    m.add_class::<Walk>()?;
    m.add_function(wrap_pyfunction!(walk_plant, m)?)?;
    Ok(())
}
