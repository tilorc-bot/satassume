"""gen_offline_data.py [--check] [OUT]: writes section 9's offline data file (PORT-INVENTORY.md, component D).

Offline, and not ported: Tilo, 7 Nov, "None of the offline stuff should be ported". Rust reads the output once at load
(`solver_rs/src/term/offline.rs`) and refuses a file whose hashes don't match.

The file is two lines of JSON: a header, then the body. No timestamp, no path and no hash order reaches it: a set is
written sorted, and a mapping in its insertion order, so if some insertion order did come from a hash, the byte
comparison across hash seeds (`--check`, `tests_offline.py`) shows it. Anything this script can't write exactly stops
it; there is no fallback to `repr`.

Tagged values, since JSON has only strings, ints, bools, null, lists and objects:
  {"$num": "1/2"}     a SymPy number, as the text its class gives; {"$class": "sin"} a class by name
  {"$set": [...]}     a set, sorted by its JSON;                    {"$map": [[k, v], ...]} a mapping with non-text keys
  {"$fn": "name"}     a function, by name;                          {"$row": "Row", ...} a dataclass or namedtuple
  {"$int": "123"}     an int outside i64
"""
import dataclasses
import hashlib
import importlib
import json
import os
import sys
import types

import sympy
from sympy.core.basic import Basic
from sympy.core.numbers import Number, NumberSymbol, ImaginaryUnit

FORMAT = 1
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DEFAULT_OUT = os.path.join(HERE, "offline_data.json")

#: every source whose content reaches the body; a change to any of them makes Rust refuse the file
SOURCES = tuple(f"satassume/knowledge/{p}" for p in (
    "rules.py", "domain.py", "templates/__init__.py", "templates/_common.py", "templates/_compiled_rows.py",
    "templates/_rows_runtime.py", "templates/atoms.py", "templates/core.py", "templates/functions.py",
    "templates/table.py", "templates/wiring.py", "templates/power.py", "templates/mul.py", "templates/add.py",
    "templates/selection.py",
))


def _table_row():
    from satassume.knowledge.templates.table import Row
    return Row


def canon(x):
    """``x`` as JSON values, exactly, or an error."""
    if x is None or isinstance(x, (bool, str)):
        return x
    if isinstance(x, int):
        return x if -2**63 <= x < 2**63 else {"$int": str(x)}
    if isinstance(x, (tuple, list)) and not hasattr(x, "_fields"):
        return [canon(a) for a in x]
    if isinstance(x, (frozenset, set)):
        items = [canon(a) for a in x]
        return {"$set": sorted(items, key=lambda a: json.dumps(a, sort_keys=True))}
    if isinstance(x, (dict, types.MappingProxyType)):
        if all(isinstance(k, str) and not k.startswith("$") for k in x):
            return {k: canon(v) for k, v in x.items()}
        return {"$map": [[canon(k), canon(v)] for k, v in x.items()]}
    if isinstance(x, (Number, NumberSymbol, ImaginaryUnit)):
        return {"$num": str(x)}
    if isinstance(x, type):
        return {"$class": x.__name__}
    if isinstance(x, (types.FunctionType, types.BuiltinFunctionType)):
        if x.__name__ == "<lambda>":
            raise TypeError("a lambda has no name Rust could bind")
        return {"$fn": x.__name__}
    if isinstance(x, _table_row()):
        # the public fields; `_prem`, `_concl` and `_ge2` are a cache of them
        return {"$row": "Row", **{f: canon(getattr(x, f)) for f in ("name", "prem", "concl", "when", "preds", "kind")}}
    if hasattr(x, "_fields"):
        return {"$row": type(x).__name__, **{f: canon(getattr(x, f)) for f in x._fields}}
    if dataclasses.is_dataclass(x):
        return {"$row": type(x).__name__, **{f.name: canon(getattr(x, f.name)) for f in dataclasses.fields(x)}}
    if isinstance(x, Basic):
        raise TypeError(f"a SymPy term in the offline data: {x!r}")
    raise TypeError(f"no exact form for {type(x).__name__}: {x!r}")


def rules_section():
    from satassume.knowledge import rules as r
    return {name: canon(getattr(r, name)) for name in (
        "PREDICATES", "PRED_INDEX", "BASIS", "BASIS_INDEX", "NPRED", "DEFINITIONS", "RULES", "RULE_CLAUSES", "DEF_LITS",
        "_CNF_POS", "_CNF_NEG", "BASIS_OF", "RULE_INSTANTIATED", "RULE_INTERNAL", "RULE_FREE")}


def template_kinds():
    """Function name to template kind: `wiring.load` and `template` as one offline step, resolved against classes by
    conversion. The kind is the qualname of what the real `wiring.template` returns, so this can't drift from it."""
    from satassume.knowledge.templates import ROW_FAMILIES, wiring
    from satassume.knowledge.templates._compiled_rows import FAMILIES
    from satassume.knowledge.templates._rows_runtime import generator
    out = []
    for family, fns in ROW_FAMILIES:
        by_name = {f.__name__: f for f in map(wiring._declared, fns) if f is not None}
        for fn_name, arity, terms, specs, *schemas in dict(FAMILIES)[family]:
            fn = by_name.get(fn_name)
            if fn is None:
                out.append([fn_name, family, None, None])     # declared by name, and this SymPy lacks it
                continue
            t = wiring.template(fn, generator(fn_name, arity, terms, specs, "offline", *schemas))
            out.append([fn_name, family, t.__qualname__, f"{fn.__module__}:{fn.__qualname__}"])
    return out


def wiring_section():
    from satassume.knowledge.templates import ROW_FAMILIES, wiring
    named = {}
    for name in ("PI_MULTIPLE", "I_PI_MULTIPLE", "I_PI_ROOT", "UNIT_INTERVAL", "VALUE_AT_INTEGER", "HALF_ARGUMENT",
                 "POWER", "AFTER_ROWS", "ARGUMENTS", "LEAVE_OUT_WIDE", "SOME_PER_ARGUMENT", "PRODUCT", "SUM"):
        named[name] = canon(getattr(wiring, name))
    named["ROW_FAMILIES"] = [[family, [f if isinstance(f, str) else f.__name__ for f in fns]]
                             for family, fns in ROW_FAMILIES]
    return named


def core_section():
    from satassume.knowledge.templates import core
    return {"MAX_ONEOUT": core.MAX_ONEOUT, "MAX_HALF_ODD": core.MAX_HALF_ODD, "_INT_BOUNDS": canon(core._INT_BOUNDS),
            "_RECIP_BOUNDS": canon(core._RECIP_BOUNDS),
            # guards are code: Rust binds them by these names, and the table's rows name them
            "IPI_GUARDS": sorted(core.IPI_GUARDS), "IPI_TABLE": canon(core.IPI_TABLE)}


def common_section():
    from satassume.knowledge.templates import _common, atoms, functions, table
    return {"VOCAB": canon(_common.VOCAB), "SIGN_FLIP": canon(_common.SIGN_FLIP),
            "_SIGNED_INFINITE": canon(_common._SIGNED_INFINITE), "MAX_EXPAND": _common.MAX_EXPAND,
            "MAX_CACHE": _common.MAX_CACHE, "GE2": table.GE2, "_CONST_BASIS": canon(atoms._CONST_BASIS),
            "functions": {k: canon(getattr(functions, k)) for k in ("X", "N", "M", "PS", "CR", "CS", "MAX_VALUE_ARG")}}


def domain_section():
    from satassume.knowledge import domain
    return {"noncommutative_false": canon(domain.noncommutative_false()), "SWEPT_UNARY": canon(domain.SWEPT_UNARY)}


def value_units_section():
    """`functions._value_units`, as a table: for each function of VALUE_AT_INTEGER and integer c, |c| <= MAX_VALUE_ARG,
    the facts of its value, or null where `_value_units` gives none. Only the facts are written, since only they are
    used. Fact sets are shared, as the same few recur. Keyed by exact class: a subclass isn't this table's."""
    from sympy import Integer, S
    from satassume.knowledge.templates import atoms, functions, wiring
    from satassume.knowledge.templates._common import const_value
    sets, index, rows = [], {}, {}
    for fn in wiring.VALUE_AT_INTEGER:
        row = []
        for n in range(-functions.MAX_VALUE_ARG, functions.MAX_VALUE_ARG + 1):
            try:
                v = fn(Integer(n))
            except (ValueError, TypeError, ArithmeticError):
                row.append(None)
                continue
            if not (v.is_Atom and v.is_number) or v is S.NaN:
                row.append(None)
                continue
            facts = tuple((p, bool(b)) for p, b in ((p, const_value(v, p)) for p in atoms._CONST_BASIS) if b is not None)
            row.append(index.setdefault(facts, len(index)))
            if index[facts] == len(sets):
                sets.append([list(f) for f in facts])
        rows[fn.__name__] = row
    return {"range": functions.MAX_VALUE_ARG, "fact_sets": sets, "rows": rows}


def body():
    from satassume.knowledge.templates._compiled_rows import FAMILIES
    return {"rules": rules_section(), "families": canon(FAMILIES), "template_kinds": template_kinds(),
            "wiring": wiring_section(), "core": core_section(), "common": common_section(),
            "domain": domain_section(), "value_units": value_units_section()}


def dumps(x):
    return json.dumps(x, separators=(",", ":"), ensure_ascii=True)


def sources():
    out = []
    for rel in SOURCES:
        with open(os.path.join(ROOT, rel), "rb") as f:
            out.append([rel, hashlib.sha256(f.read()).hexdigest()])
    return out


def generate() -> bytes:
    text = dumps(body())
    srcs = sources()
    header = {"format": FORMAT, "sympy": sympy.__version__, "sources": srcs,
              "sources_sha256": hashlib.sha256(dumps(srcs).encode()).hexdigest(),
              "body_sha256": hashlib.sha256(text.encode()).hexdigest()}
    return (dumps(header) + "\n" + text + "\n").encode()


def main(argv):
    check = "--check" in argv
    args = [a for a in argv if a != "--check"]
    out = args[0] if args else DEFAULT_OUT
    data = generate()
    if check:
        with open(out, "rb") as f:
            same = f.read() == data
        print("same" if same else "DIFFERS", hashlib.sha256(data).hexdigest())
        return 0 if same else 1
    with open(out, "wb") as f:
        f.write(data)
    print(out, len(data), hashlib.sha256(data).hexdigest())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
