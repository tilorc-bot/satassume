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
//!
//! `term_row` leaves bit 32 of a row's flags 0: it was F_MAYBE_NAN (`templates._may_be_nan` of the term), which no
//! reader of a row used. The position stays reserved.
use pyo3::exceptions::{PyException, PyKeyError, PyOverflowError, PyRecursionError, PyTypeError, PyValueError};
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyComplex, PyDict, PyFunction, PyInt, PyList, PyString, PyTuple, PyType};
use std::cell::Cell;
use std::collections::HashMap;
use std::sync::atomic::{AtomicU8, Ordering};


// The items, as bits of `Walk.mask`: `convert.RUST_ITEMS`, same order.
pub const ENC: u16 = 1;
pub const KLASS: u16 = 2;
pub const TERM_ROW: u16 = 4;
pub const WALK: u16 = 8;
pub const ENC_INT: u16 = 16;
/// `_template_name` and `_structural_class`, the per-class calls of `klass`.
pub const KLASS_CALLS: u16 = 32;
pub const POWER_ROWS: u16 = 64;
/// `_Walk.read` and the `_read_*` it dispatches to. Python decides it: the bit says `read` is this walk's method.
#[allow(dead_code)]
pub const READ: u16 = 128;
/// `convert`, `default_engine_settings`, `formula` and the walk's state (`_Walk.__init__`): `WalkEntry`. Python
/// decides it (`convert` asks the walker class for its ENTRY).
#[allow(dead_code)]
pub const ENTRY: u16 = 256;
const ALL: u16 = 511;

/// `formula` nested deeper than this is answered by Python's `formula`, whose own limit is the interpreter's.
const DEPTH: u32 = 100;

/// Counters 740-745 (`sa_solver.walk_counts()`), per thread like the witness check's.
const NAMES: [&str; 7] = [
    "cv:entry",          // 740: conversions entered natively (`convert`'s body here)
    "cv:formula",        // 741: `formula` calls (the scope check) answered natively
    "cv:read",           // 742: lazy reads dispatched natively
    "cv:fallback:depth", // 743: to Python's `formula`: nesting past DEPTH
    "cv:fallback:name",  // 744: to Python's `_template_name`: a template whose class has a metaclass of its own
    "cv:py:own_base",    // 745: `own_base` reads, whose `Mul(2, t)` stays the Python input layer's (ruling 5)
    "cv:patched",        // 746: conversions with an item off because its Python definition was replaced (P1)
];
const C_ENTRY: usize = 0;
const C_FORMULA: usize = 1;
const C_READ: usize = 2;
const C_DEPTH: usize = 3;
const C_NAME: usize = 4;
const C_OWN_BASE: usize = 5;
const C_PATCHED: usize = 6;

thread_local! {
    static COUNTS: [Cell<u64>; 7] = const { [const { Cell::new(0) }; 7] };
}

fn count(i: usize) {
    COUNTS.with(|c| c[i].set(c[i].get() + 1));
}

#[pyfunction]
fn walk_counts<'py>(py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
    let d = PyDict::new(py);
    COUNTS.with(|c| NAMES.iter().zip(c).try_for_each(|(n, x)| d.set_item(n, x.get())))?;
    Ok(d)
}

#[pyfunction]
fn walk_counts_reset() {
    COUNTS.with(|c| c.iter().for_each(|x| x.set(0)));
}

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
const T_MISS: i64 = 10;

// Term fact bits and class flags past FLAGS: `convert.py`'s `F_*` and `_PLAIN_*`/`_IS_*`.
const F_NUMBER: i64 = 1;
const F_NAN: i64 = 2;
const F_BAD: i64 = 4;
const F_FLOAT: i64 = 8;
const F_UNDEF: i64 = 16;
// 32 is reserved (the old F_MAYBE_NAN) and always 0.
const F_READ: i64 = 64;
const PLAIN_OPS: i64 = 1 << 14;
const PLAIN_BASE: i64 = 1 << 15;
const IS_EXPR: i64 = 1 << 16;
const IS_MATRIX: i64 = 1 << 17;
const IS_EXP: i64 = 1 << 18;
const PLAIN_ATOMS: i64 = 1 << 19;

/// Test plants (`SLICE_CONVERT_PLANT`): one per item (plants 670-674), each a wrong value at one site. Numbers 6 to 8
/// were plants 746-748 in the F_MAYBE_NAN bit and stay unused.
static PLANT: AtomicU8 = AtomicU8::new(0);
const PLANT_ENC: u8 = 1; // 670: True encodes as False
const PLANT_KLASS: u8 = 2; // 671: a class row without the IS_EXPR flag
const PLANT_TERM_ROW: u8 = 3; // 672: a term row without the is_number bit
const PLANT_WALK: u8 = 4; // 673: args pushed unreversed, so ids aren't by first sight
const PLANT_ENC_INT: u8 = 5; // 674: a negative int loses its sign
const PLANT_STRUCTURAL: u8 = 9; // 768: `_structural_class` says the opposite
const PLANT_POWER_ROWS: u8 = 10; // 769: the last power row is dropped
const PLANT_READ: u8 = 11; // 770: the `commutative` read says the opposite
const PLANT_ENTRY: u8 = 12; // 771: the assumptions aren't scope-checked (as if they were True)
// 13 was plant 772 (an `and` tagged `or` in the converted formula table), retired with the table.
const PLANT_REPLACED: u8 = 14; // 773: a replaced definition isn't looked for, so Rust's item answers in its place

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
    constructed_nc: Py<PyAny>,
    getattr: Py<PyAny>,
    reversed: Py<PyAny>,
    int_t: Py<PyAny>,
    i64_lo: Py<PyAny>,
    i64_hi: Py<PyAny>,
    // ---- the per-class calls
    structural: Py<PyAny>,
    integral_transform: Py<PyAny>,
    euf_basic: Py<PyAny>,
    py_template_name: Py<PyAny>,
    format: Py<PyAny>,
    // ---- power_rows, read
    py_read_own_base: Py<PyAny>,
    reads: Py<PyTuple>,
    default_sort_key: Py<PyAny>,
    decompose_power: Py<PyAny>,
    const_value: Py<PyAny>,
    const_basis: Py<PyAny>,
    complex_t: Py<PyAny>,
    // ---- the entry
    a: Py<PyAny>,
    b_true: Py<PyAny>,
    b_false: Py<PyAny>,
    applied: Py<PyAny>,
    relational: Py<PyAny>,
    connective: Vec<Py<PyAny>>,
    relation_predicates: Py<PyAny>,
    opaque_categories: Py<PyAny>,
    unsupported: Py<PyAny>,
    py_formula: Py<PyAny>,
    prefix: Py<PyAny>,
    kept: Py<PyAny>,
    converted: Py<PyAny>,
    // ---- replaced definitions (P1): each name of `_Walk` and of the module as defined, with the items it turns off
    module: Py<PyAny>,
    walk_cls: Py<PyAny>,
    original: Vec<(bool, Py<PyString>, Py<PyAny>, u16)>,
    py_convert: Py<PyAny>,
    walk_class: Py<PyAny>,
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
        let a = m.getattr("A")?;
        let original_of = m.getattr("_ORIGINAL")?;
        let mut original = Vec::new();
        for (name, f) in original_of.cast::<PyDict>()?.iter() {
            let name = name.cast_into::<PyString>()?;
            let (on_walk, off) = match name.to_cow()?.as_ref() {
                "enc" => (true, ENC),
                "enc_int" => (true, ENC_INT),
                "walk" => (true, WALK),
                "klass" => (true, KLASS),
                "term_row" => (true, TERM_ROW),
                "power_rows" => (true, POWER_ROWS),
                "formula" | "default_engine_settings" | "_rel" => (false, ENTRY),
                "_template_name" | "_structural_class" => (false, KLASS_CALLS),
                "convert" => continue,
                n if n == "read" || n.starts_with("_read_") => (true, READ),
                _ => (true, ALL), // `__init__`, `s`, `term`: every item stands on them
            };
            original.push((on_walk, name.unbind(), f.unbind(), off));
        }
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
            constructed_nc: g("constructed_noncommutative")?,
            getattr: builtins.getattr("getattr")?.unbind(),
            reversed: builtins.getattr("reversed")?.unbind(),
            int_t: builtins.getattr("int")?.unbind(),
            i64_lo: i64v.neg()?.unbind(),
            i64_hi: i64v.unbind(),
            structural: g("_STRUCTURAL")?,
            integral_transform: g("IntegralTransform")?,
            euf_basic: m.getattr("_inherits_from_basic")?.getattr("__globals__")?.get_item("Basic")?.unbind(),
            py_template_name: g("_template_name")?,
            format: builtins.getattr("format")?.unbind(),
            py_read_own_base: walk.getattr("_read_own_base")?.unbind(),
            reads: m.getattr("READS")?.cast_into::<PyTuple>()?.unbind(),
            default_sort_key: g("default_sort_key")?,
            decompose_power: g("decompose_power")?,
            const_value: g("const_value")?,
            const_basis: g("_CONST_BASIS")?,
            complex_t: builtins.getattr("complex")?.unbind(),
            b_true: a.getattr("_BTrue")?.unbind(),
            b_false: a.getattr("_BFalse")?.unbind(),
            applied: a.getattr("_Applied")?.unbind(),
            relational: a.getattr("_Relational")?.unbind(),
            connective: m.getattr("_CONNECTIVE")?.try_iter()?.map(|x| Ok(x?.unbind())).collect::<PyResult<_>>()?,
            relation_predicates: a.getattr("RELATION_PREDICATES")?.unbind(),
            opaque_categories: a.getattr("OPAQUE_CATEGORIES")?.unbind(),
            unsupported: a.getattr("Unsupported")?.unbind(),
            a: a.unbind(),
            py_formula: g("formula")?,
            prefix: g("_PREFIX")?,
            kept: g("Kept")?,
            converted: g("Converted")?,
            module: m.clone().unbind(),
            walk_cls: walk.clone().unbind(),
            original,
            py_convert: original_of.get_item("convert")?.unbind(),
            walk_class: g("_walk_class")?,
        })
    }
}

/// One `_Walk`'s Rust half. `strings`, `string_ids` and `reading` live here because `_Walk.read` replaces them: the
/// Python object's attributes of those names are properties onto these.
// `weakref`: a kept test holds the walk behind `tables['reads']` weakly to see that it dies with its table (H2).
#[pyclass(name = "Walk", weakref)]
pub struct Walk {
    ctx: Py<WalkCtx>,
    mask: u16,
    ids: Option<Py<PyDict>>,
    objects: Option<Py<PyList>>,
    classes: Option<Py<PyDict>>,
    class_rows: Option<Py<PyList>>,
    opaque: Option<Py<PyList>>,
    counts: Option<Py<PyDict>>,
    /// `_Walk.raised`: only `read` writes it.
    raised: Option<Py<PyList>>,
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
    /// The `_Walk` whose Python methods answer the items that are off. None when every item is on.
    o: Option<Bound<'py, PyAny>>,
    mask: u16,
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

/// `Py_EnterRecursiveCall` around `enc`'s own recursion (and `may_be_nan`'s): a nesting Python's walker ends with
/// RecursionError ends so here.
pub(super) struct Depth;

impl Depth {
    pub(super) fn enter() -> PyResult<Depth> {
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
    fn new(slf: &Bound<'py, Walk>, o: Option<&Bound<'py, PyAny>>) -> PyResult<W<'py>> {
        let py = slf.py();
        let b = slf.borrow();
        Ok(W {
            py,
            slf: slf.clone(),
            cx: b.ctx.bind(py).clone(),
            o: o.filter(|x| !x.is_none()).cloned(),
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

    /// The owner, for an item that is off.
    fn owner(&self) -> PyResult<&Bound<'py, PyAny>> {
        self.o.as_ref().ok_or_else(|| PyValueError::new_err("Walk: an item is off and there is no Python walker"))
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
    // The owner's method is called by name: an item that is off is `_Walk`'s method as it is now, so a replaced one (P1,
    // `replaced`) is the one that runs, as under Python's walker.

    fn enc(&self, v: &Bound<'py, PyAny>, out: &Bound<'py, PyList>, key: bool) -> PyResult<()> {
        if self.mask & ENC != 0 { return self.enc_native(v, out, key); } //@call enc
        self.owner()?.call_method1(intern!(self.py, "enc"), (v, out, key)).map(drop)
    }

    fn enc_int(&self, n: &Bound<'py, PyAny>, out: &Bound<'py, PyList>) -> PyResult<()> {
        if self.mask & ENC_INT != 0 { return self.enc_int_native(n, out); } //@call enc_int
        self.owner()?.call_method1(intern!(self.py, "enc_int"), (n, out)).map(drop)
    }

    fn walk(&self, root: &Bound<'py, PyAny>) -> PyResult<()> {
        if self.mask & WALK != 0 { return self.walk_native(root); } //@call walk
        self.owner()?.call_method1(intern!(self.py, "walk"), (root,)).map(drop)
    }

    fn klass(&self, cls: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        if self.mask & KLASS != 0 { return self.klass_native(cls); } //@call klass
        self.owner()?.call_method1(intern!(self.py, "klass"), (cls,))
    }

    fn term_row(&self, t: &Bound<'py, PyAny>, out: &Bound<'py, PyList>) -> PyResult<()> {
        if self.mask & TERM_ROW != 0 { return self.term_row_native(t, out); } //@call term_row
        self.owner()?.call_method1(intern!(self.py, "term_row"), (t, out)).map(drop)
    }

    fn power_rows(&self, n: usize) -> PyResult<Bound<'py, PyAny>> {
        if self.mask & POWER_ROWS != 0 { return self.power_rows_native(n); } //@call power_rows
        self.owner()?.call_method1(intern!(self.py, "power_rows"), (n,))
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

    //@begin enc_int
    /// `_Walk.enc_int`.
    fn enc_int_native(&self, n: &Bound<'py, PyAny>, out: &Bound<'py, PyList>) -> PyResult<()> {
        let py = self.py;
        let cx = self.cx.get();
        // `-_I64 < n < _I64`: by value for an int that fits, by Python's own comparison for anything else.
        let small = match n.extract::<i64>() {
            Ok(x) if n.is_exact_instance_of::<PyInt>() => {
                if x != i64::MIN && x < 0 && planted(PLANT_ENC_INT) {
                    out.append(T_INT)?;
                    return out.append(-x);
                }
                x != i64::MIN
            }
            Err(e) if n.is_exact_instance_of::<PyInt>() && e.is_instance_of::<PyOverflowError>(py) => false,
            _ => cx.i64_lo.bind(py).lt(n)? && n.lt(cx.i64_hi.bind(py))?,
        };
        if small {
            out.append(T_INT)?;
            out.append(n)
        } else {
            let i = self.s(n.str()?.as_any())?;
            out.append(T_BIG)?;
            out.append(i)
        }
    }
    //@end enc_int

    //@begin walk
    /// `_Walk.walk`: preorder over `.args`, ids by first sight.
    fn walk_native(&self, root: &Bound<'py, PyAny>) -> PyResult<()> {
        let py = self.py;
        let cx = self.cx.get();
        let basic = cx.basic.bind(py);
        let setdefault = intern!(py, "setdefault");
        let mut stack = vec![root.clone()];
        while let Some(t) = stack.pop() {
            if !t.is_instance(basic)? {
                return self.keep("non-basic", type_name(&t)?);
            }
            // `if t in ids: continue; ids[t] = len(objects)`, as one lookup: an id already there is a smaller one.
            let n = self.objects.len().into_pyobject(py)?;
            if !self.ids.call_method1(setdefault, (&t, &n))?.is(&n) {
                continue;
            }
            self.objects.append(&t)?;
            if t.is_instance(cx.kept_classes.bind(py))? {
                return self.keep("sum-product-integral", type_name(&t)?);
            }
            self.klass(t.get_type().as_any())?;
            let args = t.getattr(intern!(py, "args"))?;
            let exact = args.cast_exact::<PyTuple>().ok();
            let len = match exact {
                Some(a) => a.len(),
                None => args.len()?,
            };
            if len > 1 {
                let seen = PyDict::new(py);
                let check = |a: &Bound<'py, PyAny>| -> PyResult<()> {
                    if !a.is_instance(basic)? {
                        return self.keep("non-basic", type_name(a)?);
                    }
                    if !seen.call_method1(setdefault, (a, a))?.is(a) {
                        return self.keep("args-eq-not-is", type_name(&t)?);
                    }
                    Ok(())
                };
                match exact {
                    Some(a) => {
                        for x in a.iter() {
                            check(&x)?;
                        }
                    }
                    None => {
                        for x in args.try_iter()? {
                            check(&x?)?;
                        }
                    }
                }
            }
            // `stack.extend(reversed(args))`
            match exact {
                Some(a) if planted(PLANT_WALK) => stack.extend(a.iter()),
                Some(a) => stack.extend(a.iter().rev()),
                None => {
                    for x in cx.reversed.bind(py).call1((&args,))?.try_iter()? {
                        stack.push(x?);
                    }
                }
            }
        }
        Ok(())
    }
    //@end walk

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
            names.append(self.template_name(&f?)?)?;
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
        self.enc(&self.structural_class(cls)?, out, false)?;
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
        let nc = cx.constructed_nc.bind(py).call1((t,))?;
        out.append(T_INT)?;
        out.append(bits)?;
        out.append(T_INT)?;
        out.append(nc)
    }
    //@end term_row

    //@begin klass_calls
    /// `_template_name`: `f'{getattr(f, "__module__", "?")}.{getattr(f, "__qualname__", repr(type(f)))}'`. Python makes
    /// `repr(type(f))` whether or not it is used; for a class whose metaclass is `type` that repr runs no code of the
    /// class, so it is made here only when used. Any other metaclass: Python's function, before anything is read.
    fn template_name(&self, f: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        let py = self.py;
        let cx = self.cx.get();
        if self.mask & KLASS_CALLS == 0 {
            return cx.module.bind(py).getattr(intern!(py, "_template_name"))?.call1((f,)); // by name: a replaced one runs (P1)
        }
        let ty = f.get_type();
        if !ty.get_type().is(&py.get_type::<PyType>()) {
            count(C_NAME);
            return cx.py_template_name.bind(py).call1((f,));
        }
        let m = self.getattr3(f, intern!(py, "__module__"), intern!(py, "?").as_any())?;
        let q = if f.is_exact_instance_of::<PyFunction>() {
            f.getattr(intern!(py, "__qualname__"))?
        } else {
            let d = ty.repr()?;
            self.getattr3(f, intern!(py, "__qualname__"), d.as_any())?
        };
        let text = |x: Bound<'py, PyAny>| -> PyResult<String> {
            match x.cast_exact::<PyString>() {
                Ok(s) => Ok(s.to_cow()?.into_owned()),
                Err(_) => cx.format.bind(py).call1((&x, intern!(py, "")))?.extract(),
            }
        };
        let m = text(m)?;
        let q = text(q)?;
        Ok(PyString::new(py, &format!("{m}.{q}")).into_any())
    }

    /// `euf_adapter._inherits_from_basic`.
    fn inherits_from_basic(&self, cls: &Bound<'py, PyAny>, name: &Bound<'py, PyString>) -> PyResult<bool> {
        let py = self.py;
        for c in cls.getattr(intern!(py, "__mro__"))?.try_iter()? {
            let c = c?;
            if c.getattr(intern!(py, "__dict__"))?.contains(name)? {
                return Ok(c.is(self.cx.get().euf_basic.bind(py)));
            }
        }
        Ok(true)
    }

    /// `_structural_class`.
    fn structural_class(&self, cls: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        let py = self.py;
        let cx = self.cx.get();
        if self.mask & KLASS_CALLS == 0 {
            return cx.module.bind(py).getattr(intern!(py, "_structural_class"))?.call1((cls,)); // by name, as above
        }
        let v = is_subclass(cls, &cx.structural)?
            && !is_subclass(cls, &cx.integral_transform)?
            && self.inherits_from_basic(cls, intern!(py, "free_symbols"))?
            && self.inherits_from_basic(cls, intern!(py, "bound_symbols"))?;
        Ok(PyBool::new(py, v != planted(PLANT_STRUCTURAL)).to_owned().into_any())
    }
    //@end klass_calls

    //@begin power_rows
    /// `_Walk.power_rows`.
    fn power_rows_native(&self, n: usize) -> PyResult<Bound<'py, PyAny>> {
        let py = self.py;
        let cx = self.cx.get();
        let expr = cx.expr.bind(py);
        let abe = intern!(py, "as_base_exp");
        let no = PyBool::new(py, false).to_owned();
        let out = PyList::empty(py);
        for i in 0..n {
            let t = self.objects.get_item(i)?;
            if !t.is_instance(expr)?
                || t.getattr(intern!(py, "is_Mul"))?.is_truthy()?
                || t.getattr(intern!(py, "is_Number"))?.is_truthy()?
                || t.get_type().getattr(abe)?.is(&expr.getattr(abe)?)
                || self.getattr3(&t, intern!(py, "is_number"), no.as_any())?.is_truthy()?
            {
                continue;
            }
            out.append(i)?;
        }
        if planted(PLANT_POWER_ROWS) && out.len() > 0 {
            out.del_item(out.len() - 1)?;
        }
        Ok(out.into_any())
    }
    //@end power_rows

    //@begin read
    fn bump(&self, key: &Bound<'py, PyString>) -> PyResult<()> {
        let n = self.counts.get_item(key)?.ok_or_else(|| PyKeyError::new_err((key.clone().unbind(),)))?;
        self.counts.set_item(key, n.add(1)?)
    }

    /// The `_read_*` of `name`, on the original object.
    fn read_value(&self, name: &str, t: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        let py = self.py;
        let cx = self.cx.get();
        Ok(match name {
            "key" => cx.default_sort_key.bind(py).call1((t,))?,
            "finite" => {
                if !t.is_instance(cx.expr.bind(py))? {
                    return Ok(py.None().into_bound(py));
                }
                t.getattr(intern!(py, "is_finite"))?
            }
            "complex" => {
                if !t.is_instance(cx.expr.bind(py))? {
                    return Err(PyTypeError::new_err((type_name(t)?.unbind(),)));
                }
                // The two doubles as their bit patterns (R17): `struct.unpack('<q', struct.pack('<d', x))`. No float is compared.
                let z = cx.complex_t.bind(py).call1((t,))?;
                let z = z.cast::<PyComplex>()?;
                PyTuple::new(py, [z.real().to_bits() as i64, z.imag().to_bits() as i64])?.into_any()
            }
            "power" => {
                let (base, e) = cx.decompose_power.bind(py).call1((t,))?.extract::<(Bound<'py, PyAny>, Bound<'py, PyAny>)>()?;
                let b = match self.ids.get_item(&base)? {
                    Some(b) => b,
                    None => (-1i64).into_pyobject(py)?.into_any(),
                };
                if b.lt(0)? {
                    self.bump(intern!(py, "pow_base_not_input"))?;
                }
                PyTuple::new(py, [b, e])?.into_any()
            }
            "commutative" => {
                let v = t.getattr(intern!(py, "is_commutative"))?.is(&PyBool::new(py, true).to_owned());
                PyBool::new(py, v != planted(PLANT_READ)).to_owned().into_any()
            }
            "symbol" => {
                let items = t.getattr(intern!(py, "assumptions0"))?.call_method0(intern!(py, "items"))?;
                PyTuple::new(py, items.try_iter()?.collect::<PyResult<Vec<_>>>()?)?.into_any()
            }
            "constant" => {
                let mut v = Vec::new();
                for p in cx.const_basis.bind(py).try_iter()? {
                    v.push(cx.const_value.bind(py).call1((t, p?))?);
                }
                PyTuple::new(py, v)?.into_any()
            }
            "own_base" => {
                // `Mul(2, t)`: a construction of the Python input layer (ruling 5), so Python's method makes it.
                count(C_OWN_BASE);
                let o = match &self.o {
                    Some(o) => o.clone(),
                    None => py.None().into_bound(py),
                };
                cx.py_read_own_base.bind(py).call1((o, t))?
            }
            _ => return Err(PyKeyError::new_err(format!("_read_{name}"))),
        })
    }

    /// `_Walk.read`.
    fn read_native(slf: &Bound<'py, Walk>, o: Option<&Bound<'py, PyAny>>, kind: &Bound<'py, PyAny>, i: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        let py = slf.py();
        count(C_READ);
        let name = slf.borrow().ctx.bind(py).get().reads.bind(py).as_any().get_item(kind)?;
        let name = name.cast_into::<PyString>()?;
        let key = PyString::new(py, &format!("read:{}", name.to_cow()?));
        {
            let w = W::new(slf, o)?;
            w.bump(&key)?;
        }
        let objects = slf.borrow().objects.as_ref().ok_or_else(unbound)?.bind(py).clone();
        let t = objects.as_any().get_item(i)?;
        {
            let mut b = slf.borrow_mut();
            b.reading = true;
            b.strings = PyList::empty(py).unbind();
            b.string_ids = PyDict::new(py).unbind();
        }
        let w = W::new(slf, o)?;
        let raised = slf.borrow().raised.as_ref().ok_or_else(unbound)?.bind(py).clone();
        let note = |e: &PyErr| -> PyResult<Bound<'py, PyAny>> {
            w.bump(intern!(py, "read_raised"))?;
            raised.append((&name, i, e.get_type(py).getattr(intern!(py, "__name__"))?))?;
            Ok(py.None().into_bound(py))
        };
        let v = match w.read_value(&name.to_cow()?, &t) {
            Ok(v) => v,
            Err(e) if e.is_instance_of::<PyException>(py) => return note(&e),
            Err(e) => return Err(e),
        };
        let out = PyList::empty(py);
        match w.enc(&v, &out, name.to_cow()? == "key") {
            Ok(()) => {}
            Err(e) if e.is_instance(py, w.cx.get().not_in_table.bind(py)) => {
                w.bump(intern!(py, "read_term_missing"))?;
                return Ok((PyList::new(py, [T_MISS])?, PyList::empty(py)).into_pyobject(py)?.into_any());
            }
            Err(e) if e.is_instance_of::<PyRecursionError>(py) => return note(&e),
            Err(e) => return Err(e),
        }
        Ok((out, &w.strings).into_pyobject(py)?.into_any())
    }
    //@end read

}

//@begin entry
/// `_rel`.
fn rel_parts<'py>(cx: &Bound<'py, WalkCtx>, parts: &Bound<'py, PyAny>, rel: bool) -> PyResult<()> {
    let py = cx.py();
    let cxb = cx;
    let cx = cxb.get();
    let (_name, lhs, rhs) = parts.extract::<(Bound<'py, PyAny>, Bound<'py, PyAny>, Bound<'py, PyAny>)>()?;
    let scalar = |x: &Bound<'py, PyAny>| -> PyResult<bool> {
        cx.a.bind(py).getattr(intern!(py, "_is_scalar"))?.call1((x,))?.is_truthy()
    };
    if !rel || !(scalar(&lhs)? && scalar(&rhs)?) {
        return Err(PyErr::from_value(cx.unsupported.bind(py).call1(("relation", "relation"))?));
    }
    Ok(())
}

/// `formula`, the scope check: it raises where Python's does and builds nothing. `deep` is set, and an error returned, when the nesting passes DEPTH: the caller asks Python's.
fn formula<'py>(cx: &Bound<'py, WalkCtx>, e: &Bound<'py, PyAny>, rel: bool, opq: bool, level: u32, deep: &Cell<bool>) -> PyResult<()> {
    let py = cx.py();
    let cxb = cx;
    let cx = cxb.get();
    if level > DEPTH {
        deep.set(true);
        return Err(PyRecursionError::new_err("formula: nesting past the native bound"));
    }
    let yes = PyBool::new(py, true).to_owned();
    let no = PyBool::new(py, false).to_owned();
    let is_true = |x: &Bound<'py, PyAny>| -> PyResult<bool> { Ok(x.is(&yes) || x.is_instance(cx.b_true.bind(py))?) };
    let is_false = |x: &Bound<'py, PyAny>| -> PyResult<bool> { Ok(x.is(&no) || x.is_instance(cx.b_false.bind(py))?) };
    if is_true(e)? || is_false(e)? {
        return Ok(());
    }
    let a = cx.a.bind(py);
    if e.is_instance(cx.applied.bind(py))? {
        let arguments = intern!(py, "arguments");
        let name = e.getattr(intern!(py, "function"))?.getattr(intern!(py, "name"))?.str()?;
        let named = |s: &str| -> PyResult<bool> {
            match name.cast_exact::<PyString>() {
                Ok(n) => Ok(n.to_cow()? == s),
                Err(_) => PyAnyMethods::eq(name.as_any(), s),
            }
        };
        let truth = named("is_true")?;
        if truth && e.getattr(arguments)?.len()? == 1 {
            let x = e.getattr(arguments)?.get_item(0)?;
            if is_true(&x)? || is_false(&x)? {
                return Ok(());
            }
        }
        if cx.relation_predicates.bind(py).contains(&name)? || named("is_true")? {
            let parts = a.getattr(intern!(py, "relation_parts"))?.call1((e,))?;
            if !parts.is_none() {
                return rel_parts(cxb, &parts, rel);
            }
        }
        let c = a.getattr(intern!(py, "_applied_category"))?.call1((e,))?;
        if !c.is_none() {
            if opq && cx.opaque_categories.bind(py).contains(&c)? {
                return Ok(());
            }
            return Err(PyErr::from_value(cx.unsupported.bind(py).call1((&c, &c))?));
        }
        return Ok(());
    }
    for cls in &cx.connective {
        if e.is_instance(cls.bind(py))? {
            for x in e.getattr(intern!(py, "args"))?.try_iter()? {
                formula(cxb, &x?, rel, opq, level + 1, deep)?;
            }
            return Ok(());
        }
    }
    if e.is_instance(cx.relational.bind(py))? {
        return rel_parts(cxb, &a.getattr(intern!(py, "relation_parts"))?.call1((e,))?, rel);
    }
    Err(PyErr::from_value(cx.unsupported.bind(py).call1(("other", "other"))?))
}
/// `formula`, natively up to DEPTH and by Python's past it (from the top: `formula` only reads).
/// The items a replaced definition turns off for this query: `_Walk`'s methods and the module's functions, by identity
/// against `convert._ORIGINAL`. A replacement (a test's plant, an instrument) is then called by name, as Python's walker
/// calls it (P1).
fn replaced(cx: &Bound<'_, WalkCtx>) -> PyResult<u16> {
    let py = cx.py();
    let c = cx.get();
    let mut off = 0;
    if planted(PLANT_REPLACED) {
        return Ok(off);
    }
    for (on_walk, name, f, bits) in &c.original {
        let now = if *on_walk { c.walk_cls.bind(py) } else { c.module.bind(py) }.getattr(name.bind(py))?;
        if !now.is(f.bind(py)) {
            off |= bits;
        }
    }
    Ok(off)
}

fn formula_top<'py>(cx: &Bound<'py, WalkCtx>, e: &Bound<'py, PyAny>, rel: bool, opq: bool) -> PyResult<()> {
    let py = cx.py();
    let deep = Cell::new(false);
    match formula(cx, e, rel, opq, 0, &deep) {
        Err(_) if deep.get() => {
            count(C_DEPTH);
            cx.get().py_formula.bind(py).call1((e, rel, opq))?;
            Ok(())
        }
        r => {
            count(C_FORMULA);
            r
        }
    }
}

/// `default_engine_settings`.
fn engine_settings<'py>(cx: &Bound<'py, WalkCtx>, eng: &Bound<'py, PyAny>) -> PyResult<Option<Bound<'py, PyAny>>> {
    let py = cx.py();
    let c = cx.get();
    let default_specs = py.import(intern!(py, "satassume.relations"))?.getattr(intern!(py, "default_specs"))?;
    if eng.getattr(intern!(py, "_templates"))?.ne(c.registry.bind(py).getattr(intern!(py, "facts_for"))?)? {
        return Ok(None);
    }
    let names = |specs: Bound<'py, PyAny>| -> PyResult<Bound<'py, PyTuple>> {
        let mut v = Vec::new();
        for r in specs.try_iter()? {
            v.push(r?.getattr(intern!(py, "name"))?);
        }
        PyTuple::new(py, v)
    };
    let ours = names(eng.getattr(intern!(py, "_relation_specs"))?)?;
    if ours.as_any().ne(names(default_specs.call0()?)?)? {
        return Ok(None);
    }
    Ok(Some(
        (
            eng.getattr(intern!(py, "discovery_budget"))?,
            eng.getattr(intern!(py, "_transfer"))?,
            eng.getattr(intern!(py, "_uninterpreted"))?,
            eng.getattr(intern!(py, "_relevance"))?,
        )
            .into_pyobject(py)?
            .into_any(),
    ))
}

/// `convert`, for a walker class whose items are `mask`. With every item on, the state is made here and no Python
/// walker exists for the query. With an item off, for the class or for this query (`replaced`), the Python walker's
/// class for the items that are on (`convert._walk_class`) is instantiated and its methods answer the rest; with the
/// entry itself off for this query, Python's `convert` runs with that class.
#[pyclass(name = "WalkEntry", frozen)]
pub struct WalkEntry {
    ctx: Py<WalkCtx>,
    mask: u16,
}

#[pymethods]
impl WalkEntry {
    #[new]
    fn new(ctx: Py<WalkCtx>, mask: u16) -> Self {
        WalkEntry { ctx, mask }
    }

    fn __call__<'py>(&self, py: Python<'py>, proposition: &Bound<'py, PyAny>, assumptions: &Bound<'py, PyAny>, eng: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        let cx = self.ctx.bind(py);
        let c = cx.get();
        let mask = self.mask & !replaced(cx)?;
        if mask != self.mask {
            count(C_PATCHED);
        }
        let owner = if mask == ALL { None } else { Some(c.walk_class.bind(py).call1((mask,))?) };
        if mask & ENTRY == 0 {
            return c.py_convert.bind(py).call1((proposition, assumptions, eng, owner));
        }
        count(C_ENTRY);
        let yes = PyBool::new(py, true).to_owned();
        let no = PyBool::new(py, false).to_owned();
        let kept = |args: Bound<'py, PyTuple>| c.kept.bind(py).call1(args);
        type Built<'py> = (Bound<'py, PyAny>, Bound<'py, Walk>, Option<Bound<'py, PyAny>>, Bound<'py, PyList>, Bound<'py, PyAny>);
        let body = || -> PyResult<Result<Built<'py>, Bound<'py, PyAny>>> {
            let settings = match engine_settings(cx, eng)? {
                Some(s) => s,
                None => return Ok(Err(kept(PyTuple::new(py, ["non-default-registry"])?)?)),
            };
            let rel = eng.getattr(intern!(py, "relation_specs"))?.is_truthy()?;
            let in_scope = (|| -> PyResult<()> {
                formula_top(cx, proposition, rel, false)?;
                if !(assumptions.is(&yes) || planted(PLANT_ENTRY)) {
                    formula_top(cx, assumptions, rel, true)?;
                }
                Ok(())
            })();
            match in_scope {
                Ok(()) => {}
                Err(e) if e.is_instance(py, c.unsupported.bind(py)) => return Ok(Err(kept(PyTuple::new(py, ["out-of-scope"])?)?)),
                Err(e) => return Err(e),
            }
            let (slf, o) = match &owner {
                Some(cls) => {
                    let o = cls.call0()?;
                    (o.getattr(intern!(py, "_rs"))?.cast_into::<Walk>()?, Some(o))
                }
                None => (Bound::new(py, Walk::fresh(py, cx, mask)?)?, None),
            };
            let w = W::new(&slf, o.as_ref())?;
            for cls in c.prefix.bind(py).try_iter()? {
                w.klass(&cls?)?;
            }
            for x in [proposition, assumptions] {
                if x.is(&yes) || x.is(&no) {
                    continue;
                }
                w.walk(x)?;
            }
            let rows = PyList::empty(py);
            let mut i = 0;
            while i < w.objects.len() {
                w.term_row(&w.objects.get_item(i)?, &rows)?;
                i += 1;
            }
            let powers = w.power_rows(w.objects.len())?;
            Ok(Ok((settings, slf, o, rows, powers)))
        };
        let (settings, slf, o, rows, powers) = match body() {
            Ok(Ok(x)) => x,
            Ok(Err(k)) => return Ok(k),
            Err(e) if e.is_instance(py, c.keep.bind(py)) => {
                let v = e.value(py);
                return kept(PyTuple::new(py, [v.getattr(intern!(py, "reason"))?, v.getattr(intern!(py, "detail"))?])?);
            }
            Err(e) if e.is_instance_of::<PyRecursionError>(py) => return kept(PyTuple::new(py, ["too-deep"])?),
            Err(e) => return Err(e),
        };
        let w = W::new(&slf, o.as_ref())?;
        let sets = PyList::empty(py);
        w.enc(&settings, &sets, false)?;
        // `w.enc` may have added strings; `w.strings` is the list Rust holds, as `_RustWalk.strings` reads it.
        let reads = match &o {
            Some(o) => o.getattr(intern!(py, "read"))?,
            None => slf.getattr(intern!(py, "read_own"))?,
        };
        let tables = PyDict::new(py);
        tables.set_item(intern!(py, "strings"), &w.strings)?;
        tables.set_item(intern!(py, "classes"), &w.class_rows)?;
        tables.set_item(intern!(py, "terms"), rows)?;
        tables.set_item(intern!(py, "powers"), powers)?;
        tables.set_item(intern!(py, "settings"), sets)?;
        tables.set_item(intern!(py, "n_classes"), w.classes.len())?;
        tables.set_item(intern!(py, "n_terms"), w.objects.len())?;
        tables.set_item(intern!(py, "n_opaque"), w.opaque.len())?;
        tables.set_item(intern!(py, "reads"), reads)?;
        let raised = match &o {
            Some(o) => o.getattr(intern!(py, "raised"))?,
            None => slf.borrow().raised.as_ref().ok_or_else(unbound)?.bind(py).clone().into_any(),
        };
        c.converted.bind(py).call1((tables, &w.ids, &w.objects, &w.counts, &w.classes, raised))
    }
}
//@end entry

#[pymethods]
impl Walk {
    #[new]
    fn new(py: Python<'_>, ctx: Py<WalkCtx>, mask: u16) -> Self {
        Walk::bare(py, ctx, mask)
    }

    /// The state `_Walk.__init__` made: Rust fills these same objects.
    #[pyo3(signature = (ids, objects, classes, class_rows, opaque, counts, raised=None))]
    #[allow(clippy::too_many_arguments)]
    fn bind(&mut self, ids: Py<PyDict>, objects: Py<PyList>, classes: Py<PyDict>, class_rows: Py<PyList>, opaque: Py<PyList>, counts: Py<PyDict>, raised: Option<Py<PyList>>) {
        self.ids = Some(ids);
        self.objects = Some(objects);
        self.classes = Some(classes);
        self.class_rows = Some(class_rows);
        self.opaque = Some(opaque);
        self.counts = Some(counts);
        self.raised = raised;
    }

    // Each takes the owner first: the `_Walk` whose Python methods answer the items that are off.
    fn enc<'py>(slf: &Bound<'py, Self>, o: &Bound<'py, PyAny>, v: &Bound<'py, PyAny>, out: &Bound<'py, PyList>, key: bool) -> PyResult<()> { W::new(slf, Some(o))?.enc_native(v, out, key) } //@call enc
    fn enc_int<'py>(slf: &Bound<'py, Self>, o: &Bound<'py, PyAny>, n: &Bound<'py, PyAny>, out: &Bound<'py, PyList>) -> PyResult<()> { W::new(slf, Some(o))?.enc_int_native(n, out) } //@call enc_int
    fn walk<'py>(slf: &Bound<'py, Self>, o: &Bound<'py, PyAny>, root: &Bound<'py, PyAny>) -> PyResult<()> { W::new(slf, Some(o))?.walk_native(root) } //@call walk
    fn klass<'py>(slf: &Bound<'py, Self>, o: &Bound<'py, PyAny>, cls: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> { W::new(slf, Some(o))?.klass_native(cls) } //@call klass
    fn term_row<'py>(slf: &Bound<'py, Self>, o: &Bound<'py, PyAny>, t: &Bound<'py, PyAny>, out: &Bound<'py, PyList>) -> PyResult<()> { W::new(slf, Some(o))?.term_row_native(t, out) } //@call term_row
    fn power_rows<'py>(slf: &Bound<'py, Self>, o: &Bound<'py, PyAny>, n: usize) -> PyResult<Bound<'py, PyAny>> { W::new(slf, Some(o))?.power_rows_native(n) } //@call power_rows
    fn read<'py>(slf: &Bound<'py, Self>, o: &Bound<'py, PyAny>, kind: &Bound<'py, PyAny>, i: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> { W::read_native(slf, Some(o), kind, i) } //@call read
    /// `_Walk.raised`: with every item on this object is `tables['reads'].__self__`, where kept tests and term_shadow.py
    /// read what the reads raised.
    #[getter]
    fn raised(&self, py: Python<'_>) -> PyResult<Py<PyList>> {
        self.raised.as_ref().map(|r| r.clone_ref(py)).ok_or_else(unbound)
    }

    /// `read` of a walk with every item on: `tables['reads']` itself, so no Python runs between the table and here.
    fn read_own<'py>(slf: &Bound<'py, Self>, kind: &Bound<'py, PyAny>, i: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> { W::read_native(slf, None, kind, i) } //@call read
}

impl Walk {
    fn bare(py: Python<'_>, ctx: Py<WalkCtx>, mask: u16) -> Self {
        Walk {
            ctx,
            mask,
            ids: None,
            objects: None,
            classes: None,
            class_rows: None,
            opaque: None,
            counts: None,
            raised: None,
            strings: PyList::empty(py).unbind(),
            string_ids: PyDict::new(py).unbind(),
            reading: false,
            integral: HashMap::new(),
            basic_content: None,
        }
    }

    /// `_Walk.__init__`: the state of one query's walk, made here when no Python walker is.
    fn fresh<'py>(py: Python<'py>, cx: &Bound<'py, WalkCtx>, mask: u16) -> PyResult<Self> {
        let mut w = Walk::bare(py, cx.clone().unbind(), mask);
        let counts = PyDict::new(py);
        for k in ["pow_base_not_input", "opaque", "read_term_missing", "read_raised"] {
            counts.set_item(k, 0)?;
        }
        for name in cx.get().reads.bind(py).iter() {
            counts.set_item(format!("read:{}", name.cast::<PyString>()?.to_cow()?), 0)?;
        }
        w.ids = Some(PyDict::new(py).unbind());
        w.objects = Some(PyList::empty(py).unbind());
        w.classes = Some(PyDict::new(py).unbind());
        w.class_rows = Some(PyList::empty(py).unbind());
        w.opaque = Some(PyList::empty(py).unbind());
        w.counts = Some(counts.unbind());
        w.raised = Some(PyList::empty(py).unbind());
        Ok(w)
    }
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<WalkCtx>()?;
    m.add_class::<Walk>()?;
    m.add_class::<WalkEntry>()?;
    m.add_function(wrap_pyfunction!(walk_plant, m)?)?;
    m.add_function(wrap_pyfunction!(walk_counts, m)?)?;
    m.add_function(wrap_pyfunction!(walk_counts_reset, m)?)?;
    Ok(())
}
