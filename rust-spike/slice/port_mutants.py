"""Planted bugs in what 1a added: payload conversion, term ids, model rendering. Through `ask()`, fresh, against Python.

  port_mutants.py list
  port_mutants.py build WORK                 one .so per Rust mutant, WORK/NAME/sa_solver.so
  port_mutants.py run NAME WL OUT [live.py flags]    Python mutants patch lra_backend's source; Rust ones want --so
  port_mutants.py score REF DIR              caught by what, per file DIR/NAME-WL.jsonl

Each entry is (file, old, new); `old` has to occur exactly once. Test-only.
"""
import json
import os
import shutil
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

PY = {
    "payload:negated_parity": ("negated = not negated", "negated = negated"),
    "payload:strict_lost": ("lt = False if eq else (True if strict else False)", "lt = False"),
    "payload:equality_lost": ("eq = True if equality else False", "eq = False"),
    "payload:coefficient_sign": ("out.append((i, c))", "out.append((i, -c))"),
    "payload:pair_order": ("        return out\n", "        return out[::-1]\n"),
    "payload:constant_plus_one": ("core.register_plain(literal, negated, lt, eq, k, ids)",
                                  "core.register_plain(literal, negated, lt, eq, k + 1, ids)"),
    "payload:offset_sign": ("core.register_integral(literal, k, ids)", "core.register_integral(literal, -k, ids)"),
    "payload:touch_skipped": ("k = num(constant)\n        except Exception:\n            if not core.touch(ids):\n                return\n",
                              "k = num(constant)\n        except Exception:\n"),
    "payload:budget_plus_one": ("core.check(_lra.BRANCH_BUDGET, self._terms)", "core.check(_lra.BRANCH_BUDGET + 1, self._terms)"),
    "term:forget_skipped": ("except BaseException:\n            self._forget(n0)\n            raise\n        return out",
                            "except BaseException:\n            raise\n        return out"),
    "term:always_new": ("i = tid.get(t)", "i = None"),
    "term:last_object": ("                out.append((i, c))",
                         "                objs[i] = t\n                out.append((i, c))"),
    "model:terms_reversed": ("core.check(_lra.BRANCH_BUDGET, self._terms)", "core.check(_lra.BRANCH_BUDGET, self._terms[::-1])"),
}
RS = {
    "model:order_reversed": ("for (id, q) in &m {", "for (id, q) in m.iter().rev() {"),
    "model:first_dropped": ("for (id, q) in &m {", "for (id, q) in m.iter().skip(1) {"),
    "model:value_negated": ("d.set_item(terms.get_item(*id as usize)?, self.frac(p, q)?)?;",
                            "d.set_item(terms.get_item(*id as usize)?, self.frac(p, &q.neg())?)?;"),
    "payload:rat_small_negated": ("return Ok(Rat::S(a, b));", "return Ok(Rat::S(-a, b));"),
    "payload:pairs_reversed_rs": ("    Ok(out)\n}\n\nfn kind_text", "    out.reverse();\n    Ok(out)\n}\n\nfn kind_text"),
}


def build(work):
    from mutate_slice import build as cargo
    src = os.path.join(HERE, "solver_rs")
    crate = os.path.join(work, "crate")
    shutil.copytree(src, crate, dirs_exist_ok=True, ignore=shutil.ignore_patterns("target"))
    path = os.path.join(crate, "src", "lra_py.rs")
    text = open(path).read()
    for name, (old, new) in RS.items():
        assert text.count(old) == 1, name
        open(path, "w").write(text.replace(old, new))
        cargo(crate, os.path.join(work, name.replace(":", "_")))
    open(path, "w").write(text)


def run(name, argv):
    if name in PY:
        old, new = PY[name]
        path = os.path.join(HERE, "lra_backend.py")
        text = open(path).read()
        assert text.count(old) == 1, name
        m = types.ModuleType("lra_backend")
        m.__file__ = path
        sys.modules["lra_backend"] = m
        exec(compile(text.replace(old, new), path, "exec"), m.__dict__)
    import live
    sys.argv = ["live.py", *argv]
    live.main()


def score(ref, d):
    py = {r["q"]: r for r in map(json.loads, open(ref)) if "q" in r}
    res = {}
    for name in [*PY, *RS]:
        f = os.path.join(d, name.replace(":", "_") + ".jsonl")
        if not os.path.exists(f):
            continue
        rows = {r["q"]: r for r in map(json.loads, open(f)) if "q" in r}
        kinds, first = {}, None
        for q, p in py.items():
            r = rows.get(q)
            hit = set()
            if r is None:
                hit.add("died")
            else:
                if r["ans"] != p["ans"]:
                    hit.add("raise" if str(r["ans"]).startswith("raise") else "ans")
                if len(r["sessions"]) != len(p["sessions"]):
                    hit.add("sessions")
                for a, b in zip(p["sessions"], r["sessions"]):
                    hit |= {k for k in ("end", "stream", "lra") if a[k] != b[k]}
                if r.get("caught"):
                    hit.add("quiet")
            for h in hit:
                kinds[h] = kinds.get(h, 0) + 1
            if hit and first is None:
                first = (q, sorted(hit))
        res[name] = dict(rows=len(rows), of=len(py), kinds=kinds, first=first)
        print(f"{name:32} {'CAUGHT' if kinds else 'not caught':11} {kinds} first={first}")
    json.dump(res, open(os.path.join(d, "score.json"), "w"), indent=0)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "list":
        print("\n".join([*PY, *RS]))
    elif a[0] == "build":
        build(a[1])
    elif a[0] == "run":
        run(a[1], a[2:])
    else:
        score(a[1], a[2])
