"""Guard for `_forms`, whose order and key objects the state comparison leaves out (planner's rule, 7 Nov, issue 323): that's
allowed only if a whole-tree search shows nothing reads it that way, a guard test holds that true, and the report names the
exception. Passing answers don't qualify a field. Needs no Rust, so it runs on any tree."""
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
LRA = os.path.join("satassume", "theories", "lra", "lra.py")
# `_forms` is only hashed into: `.get` and an assignment. Its order and its keys' objects can't be told apart that way.
FORMS = {"self._forms: dict[frozenset, tuple[int, Fraction]] = {}   # _var_of_form", "r = self._forms.get(key)", "self._forms[key] = r"}


def py_files(root):
    for d, _, names in os.walk(os.path.join(root, "satassume")):
        for n in names:
            if n.endswith(".py"):
                yield os.path.join(d, n)


def lines_with(root, pattern):
    """Every line of satassume/ matching, code, strings and comments alike, so a `getattr` by name counts too."""
    out = []
    for path in py_files(root):
        with open(path, encoding="utf-8") as f:
            for line in f:
                if re.search(pattern, line):
                    out.append((os.path.relpath(path, root), line.strip()))
    return out


def extra_forms(root):
    return [x for x in lines_with(root, r"\b_forms\b") if x != (LRA, x[1]) or x[1] not in FORMS]


def test_forms_is_only_hashed_into():
    assert extra_forms(ROOT) == [], "a new use of _forms: its order and objects aren't compared, see the planner's rule"
    assert {x[1] for x in lines_with(ROOT, r"\b_forms\b")} == FORMS


def test_the_forms_guard_can_fire(tmp_path):
    d = tmp_path / "satassume"
    d.mkdir()
    (d / "m.py").write_text("for k in t._forms:\n    pass\n")
    assert extra_forms(str(tmp_path)) == [(os.path.join("satassume", "m.py"), "for k in t._forms:")]
