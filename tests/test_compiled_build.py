"""The optional compiled build (setup.py, docs/performance.md "Optional
compiled build"): its module list names real modules, and a compiled
module is never older than its source (a stale .so shadows the .py)."""
import ast
import importlib
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _compiled():
    tree = ast.parse(open(os.path.join(ROOT, "setup.py")).read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and node.targets[0].id == "COMPILED":
            return ast.literal_eval(node.value)
    raise AssertionError("setup.py has no COMPILED list")


def test_compiled_list_names_package_modules():
    paths = _compiled()
    assert len(set(paths)) == len(paths)
    for path in paths:
        assert path.startswith("satassume/") and path.endswith(".py")
        assert not path.endswith("__init__.py")
        assert os.path.isfile(os.path.join(ROOT, path)), path


def test_no_compiled_module_older_than_its_source():
    for path in _compiled():
        module = importlib.import_module(path[:-3].replace("/", "."))
        if module.__file__.endswith(".py"):
            continue                        # pure Python: nothing to check
        source = os.path.join(ROOT, path)
        assert os.path.getmtime(module.__file__) >= os.path.getmtime(source), \
            f"{module.__file__} is older than {path}: rebuild (setup.py)"
