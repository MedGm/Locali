"""Integration and API tests, next to the unit tests of backend.agents.testgen.

- Integration tests: a project function that calls functions of another project file (for example
  a report built from database queries) is tested together with them, with real collaborators and
  a temporary database or folder instead of mocks.
- API tests: each route of a FastAPI app is called through TestClient, against an app built by the
  module's factory on a temporary database. Only FastAPI is recognised.

Both use the same rules as the unit tests (testgen.keep_passing_tests): only passing tests are kept,
a failed assertion makes the target a suspect, a crash is only counted, and a target with a suspect
keeps no tests. Targets that are, or call, code the static tools flag as insecure get no tests.
"""

import ast
from dataclasses import dataclass
from pathlib import Path

from backend.agents.files import is_test_file, python_files
from backend.agents.testgen import Model, TestgenResult, keep_passing_tests, route_decorator
from evaluation.extract import extract_all_code, trim_to_parseable
from evaluation.tasks.testgen import split_asserts

MAX_INTEGRATION = 3


@dataclass
class Route:
    file: str
    function: str
    method: str
    path: str


def _modules(root: Path) -> dict[str, ast.Module]:
    return {p.relative_to(root).as_posix(): ast.parse(p.read_text()) for p in python_files(root)
            if not is_test_file(p.relative_to(root))}


def _functions(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    return {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}


def _module_file(root: Path, dotted: str) -> str | None:
    rel = dotted.replace(".", "/") + ".py"
    return rel if (root / rel).is_file() else None


def api_routes(root: Path) -> list[Route]:
    """Module-level route handlers in modules that import fastapi."""
    root = Path(root)
    routes = []
    for rel, tree in _modules(root).items():
        imports = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        imports |= {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        if "fastapi" not in imports:
            continue
        for node in _functions(tree).values():
            if found := route_decorator(node):
                routes.append(Route(rel, node.name, *found))
    return routes


def app_factory(root: Path, rel: str) -> str | None:
    """The module-level function of `rel` that builds the app (its body calls FastAPI(...))."""
    tree = ast.parse((Path(root) / rel).read_text())
    for node in _functions(tree).values():
        for call in ast.walk(node):
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "FastAPI":
                return node.name
    return None


def called_project_functions(root: Path, rel: str, func: str) -> set[tuple[str, str]]:
    """(file, name) of the project functions that `func` in `rel` calls, followed through imports."""
    root = Path(root)
    tree = ast.parse((root / rel).read_text())
    names: dict[str, tuple[str, str]] = {}  # local name -> (file, function)
    modules: dict[str, str] = {}  # local module name -> file
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            for a in node.names:
                if sub := _module_file(root, f"{node.module}.{a.name}"):
                    modules[a.asname or a.name] = sub
                elif src := _module_file(root, node.module):
                    names[a.asname or a.name] = (src, a.name)
        elif isinstance(node, ast.Import):
            for a in node.names:
                if src := _module_file(root, a.name):
                    modules[a.asname or a.name] = src
    for name in _functions(tree):
        names.setdefault(name, (rel, name))
    target = _functions(tree)[func]
    found = set()
    for call in ast.walk(target):
        if not isinstance(call, ast.Call):
            continue
        if isinstance(call.func, ast.Name) and call.func.id in names:
            found.add(names[call.func.id])
        elif (isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name)
              and call.func.value.id in modules):
            found.add((modules[call.func.value.id], call.func.attr))
    return {(f, n) for f, n in found if n in _functions(ast.parse((root / f).read_text())) and (f, n) != (rel, func)}


def _touches(root: Path, rel: str, func: str, skip: set[tuple[str, str]]) -> bool:
    return (rel, func) in skip or bool(called_project_functions(root, rel, func) & skip)


def integration_targets(root: Path, skip: set[tuple[str, str]], limit: int = MAX_INTEGRATION) -> list[tuple[str, str]]:
    """Public module-level functions that call a function of another project file (not route
    handlers, not generators), in file and line order, at most `limit`."""
    root = Path(root)
    targets = []
    for rel, tree in sorted(_modules(root).items()):
        for node in sorted(_functions(tree).values(), key=lambda n: n.lineno):
            if node.name.startswith("_") or route_decorator(node) is not None:
                continue
            if any(isinstance(n, ast.Yield | ast.YieldFrom) for n in ast.walk(node)):
                continue  # generators here are fixtures or injected dependencies, not behaviour to test
            calls = called_project_functions(root, rel, node.name)
            if any(f != rel for f, _ in calls) and not _touches(root, rel, node.name, skip):
                targets.append((rel, node.name))
    return targets[:limit]


def _dotted(rel: str) -> str:
    return rel[:-3].replace("/", ".")


def integration_prompt(module: str, func: str, code: str) -> str:
    return (
        f"Write pytest integration tests for `{func}` in `{module}` together with the project functions "
        "it calls, shown below. Use the real functions, no mocks. Import from the real modules, for "
        f"example `from {module} import {func}`. If the code needs a database or files, create them "
        "with the project's own functions under pytest's `tmp_path` (take `tmp_path` as the test's "
        "argument); there are no other fixtures. Test the behaviour the docstrings and names describe. "
        "Return a single Python test file in a markdown code block.\n\n"
        f"```python\n{code}```"
    )


def api_fixture(module: str, factory: str) -> str:
    """The `client` fixture every API test uses: the app on a fresh temporary database."""
    return (
        "import pytest\nfrom fastapi.testclient import TestClient\n\n"
        f"from {module} import {factory}\n\n\n"
        "@pytest.fixture\ndef client(tmp_path):\n"
        f'    return TestClient({factory}(tmp_path / "test.db"))\n'
    )


def api_prompt(module: str, factory: str, route: Route, code: str) -> str:
    return (
        f"Write pytest tests for the HTTP endpoint `{route.method} {route.path}` of the FastAPI app in "
        f"`{module}` (code below). Start the test file with this fixture and take `client` as the "
        "argument of every test, for example `def test_something(client):`; it is the app on an empty "
        "temporary database, and nothing else may create the app.\n\n"
        f"```python\n{api_fixture(module, factory)}```\n\n"
        "Create the data you need through the API. Test the behaviour the endpoint's docstring "
        "describes, including its error responses. Return a single Python test file in a markdown "
        "code block.\n\n"
        f"```python\n{code}```"
    )


def _source(root: Path, rel: str, func: str) -> str:
    src = (root / rel).read_text()
    return ast.get_source_segment(src, _functions(ast.parse(src))[func])


def _ask(model: Model, prompt: str) -> str | None:
    tests = trim_to_parseable(extract_all_code(model([{"role": "user", "content": prompt}])))
    try:
        tests = split_asserts(tests)
        names = [n for n in ast.parse(tests).body if isinstance(n, ast.FunctionDef) and n.name.startswith("test")]
    except SyntaxError:
        return None
    return tests if names else None


def _test_dir(root: Path) -> str:
    return "tests/" if (root / "tests").is_dir() else ""


def generate_integration_tests(root: Path, model: Model, skip: set[tuple[str, str]]) -> TestgenResult:
    root = Path(root)
    result = TestgenResult()
    for rel, func in integration_targets(root, skip):
        parts = [f"# --- {rel}\n{_source(root, rel, func)}"]
        # the whole module of each callee, so the model also sees how to create what it needs
        parts += [f"# --- {f}\n{(root / f).read_text().rstrip()}"
                  for f in sorted({f for f, _ in called_project_functions(root, rel, func)} - {rel})]
        tests = _ask(model, integration_prompt(_dotted(rel), func, "\n\n".join(parts) + "\n"))
        if tests:
            keep_passing_tests(root, f"{_test_dir(root)}test_locali_integration_{func}.py", tests, rel, func, result)
    return result


def generate_api_tests(root: Path, model: Model, skip: set[tuple[str, str]]) -> TestgenResult:
    root = Path(root)
    result = TestgenResult()
    for route in api_routes(root):
        factory = app_factory(root, route.file)
        if factory is None or _touches(root, route.file, route.function, skip):
            continue
        code = (root / route.file).read_text().rstrip("\n") + "\n"
        tests = _ask(model, api_prompt(_dotted(route.file), factory, route, code))
        if tests and "def client(" not in tests:
            tests = api_fixture(_dotted(route.file), factory) + "\n\n" + tests
        if tests:
            out = f"{_test_dir(root)}test_locali_api_{route.function}.py"
            keep_passing_tests(root, out, tests, route.file, route.function, result)
    return result
