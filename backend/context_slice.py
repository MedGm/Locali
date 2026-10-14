"""Context slicing: the code a model needs to work on one function, instead of whole files.

Starting from the target function, keep the module-level definitions it uses: functions and
classes from the same file (followed transitively), the import lines and constants it refers to,
and, for `from <repo module> import name`, that definition from the other file. Each file's part
keeps the original source order and is headed by a `# --- <path>` comment.

Not followed: calls through a module object (`import db; db.add_product(...)`), methods resolved
at runtime, and anything defined inside other functions. Their import lines are kept.
"""

import ast
from pathlib import Path

MAX_DEPTH = 3


class _Module:
    def __init__(self, root: Path, rel: str):
        self.rel = rel
        self.src = (root / rel).read_text()
        self.tree = ast.parse(self.src)
        self.defs: dict[str, ast.stmt] = {}
        self.imports: dict[str, ast.stmt] = {}
        for node in self.tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                self.defs[node.name] = node
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    self.imports[(alias.asname or alias.name).split(".")[0]] = node
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for t in targets:
                    if isinstance(t, ast.Name):
                        self.defs[t.id] = node

    def segment(self, node: ast.stmt) -> str:
        return ast.get_source_segment(self.src, node, padded=True)


def _names(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _repo_module(root: Path, module: str | None) -> str | None:
    if not module:
        return None
    rel = module.replace(".", "/") + ".py"
    return rel if (root / rel).is_file() else None


def slice_function(root: str | Path, path: str, name: str) -> str:
    root = Path(root).resolve()
    modules: dict[str, _Module] = {}
    keep: dict[str, set[int]] = {}  # file -> ids of kept top-level statements

    def module(rel: str) -> _Module:
        if rel not in modules:
            modules[rel] = _Module(root, rel)
        return modules[rel]

    def visit(rel: str, symbol: str, depth: int) -> None:
        mod = module(rel)
        node = mod.defs.get(symbol)
        if node is None or id(node) in keep.setdefault(rel, set()):
            return
        keep[rel].add(id(node))
        if depth >= MAX_DEPTH:
            return
        for used in _names(node) - {symbol}:
            if used in mod.defs:
                visit(rel, used, depth + 1)
            elif used in mod.imports:
                stmt = mod.imports[used]
                keep[rel].add(id(stmt))
                other = _repo_module(root, stmt.module) if isinstance(stmt, ast.ImportFrom) else None
                if other:
                    visit(other, used, depth + 1)

    if name not in module(path).defs:
        raise KeyError(f"{name} is not defined at the top level of {path}")
    visit(path, name, 0)

    parts = []
    for rel in [path, *sorted(r for r in keep if r != path)]:
        mod = modules[rel]
        kept = [n for n in mod.tree.body if id(n) in keep.get(rel, set())]
        if kept:
            parts.append(f"# --- {rel}\n" + "\n\n".join(mod.segment(n) for n in kept))
    return "\n\n".join(parts) + "\n"
