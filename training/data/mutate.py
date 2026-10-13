"""Single-fault mutation operators for building bug-repair training data (T1).

Each mutant changes one operator, constant or condition on one line by editing the original
text in place (no re-rendering), so quotes, spacing and comments stay identical and the diff
between buggy and fixed code is only the injected fault.

Operators (classic mutation-testing operators):
    comparison_flip   <  <=  >  >=  ==  != swapped with their boundary/negated partner
    boolean_swap      and <-> or
    arithmetic_swap   + <-> - (binary and augmented assignment)
    off_by_one        integer constant n -> n + 1
    negate_condition  if/while condition c -> not (c), or not c -> c

Family v2 (added after the format-transfer check showed the v1 adapter only improved on
HumanEvalFix bug types that resemble v1 faults; closer to human-made bugs):
    variable_misuse   a variable read replaced by another parameter / local of the function
    missing_condition `a and b` / `a or b` -> `a` or `b`
    missing_term      `a + b` -> `a` or `b`; `a - b`, `a * b` -> `a`
    missing_call      abs/int/str/float/round/sorted/reversed/list/set/tuple(x) -> x
    function_swap     min<->max, any<->all, upper<->lower, startswith<->endswith, ...
"""

import ast
import re
from dataclasses import dataclass
from typing import NamedTuple

COMPARISON_FLIP = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt, ast.Eq: ast.NotEq, ast.NotEq: ast.Eq}
ARITHMETIC_SWAP = {ast.Add: ast.Sub, ast.Sub: ast.Add}


@dataclass
class Mutant:
    operator: str
    line: int
    code: str
    original: str  # source text of the replaced node
    replacement: str


def _splice(lines: list[str], node: ast.AST, replacement: str) -> str:
    line = lines[node.lineno - 1].encode()
    new = line[: node.col_offset] + replacement.encode() + line[node.end_col_offset :]
    out = list(lines)
    out[node.lineno - 1] = new.decode()
    return "".join(out)


def _segment(lines: list[str], node: ast.AST) -> str:
    return lines[node.lineno - 1].encode()[node.col_offset : node.end_col_offset].decode()


def _replace_between(lines: list[str], node: ast.AST, left: ast.AST, right: ast.AST, old: str, new: str) -> str | None:
    """Node text with the first `old` token in the gap between `left` and `right` replaced.

    Only the operator token changes; operands keep their exact original text (quotes,
    spacing, parentheses).
    """
    if left.end_lineno != node.lineno or right.lineno != node.lineno:
        return None
    line = lines[node.lineno - 1].encode()
    head = line[node.col_offset : left.end_col_offset]
    gap = line[left.end_col_offset : right.col_offset].decode()
    tail = line[right.col_offset : node.end_col_offset]
    pattern = rf"\b{old}\b" if old.isalpha() else re.escape(old)
    if not re.search(pattern, gap):
        return None
    return head.decode() + re.sub(pattern, new, gap, count=1) + tail.decode()


_COMPARE_TEXT = {ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">=", ast.Eq: "==", ast.NotEq: "!="}


def _candidates(tree: ast.AST, lines: list[str]):
    """Yield (operator, node, replacement text) for every single-line mutation site."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.While)) and node.test.lineno == node.test.end_lineno:
            test = node.test
            if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
                yield "negate_condition", test, _segment(lines, test.operand)
            else:
                yield "negate_condition", test, f"not ({_segment(lines, test)})"
        if getattr(node, "lineno", None) is None or node.lineno != getattr(node, "end_lineno", None):
            continue
        if isinstance(node, ast.Compare):
            operands = [node.left, *node.comparators]
            for i, op in enumerate(node.ops):
                if type(op) in COMPARISON_FLIP:
                    text = _replace_between(lines, node, operands[i], operands[i + 1],
                                            _COMPARE_TEXT[type(op)], _COMPARE_TEXT[COMPARISON_FLIP[type(op)]])
                    if text:
                        yield "comparison_flip", node, text
        elif isinstance(node, ast.BoolOp):
            old, new = ("and", "or") if isinstance(node.op, ast.And) else ("or", "and")
            text = _replace_between(lines, node, node.values[0], node.values[1], old, new)
            if text:
                yield "boolean_swap", node, text
        elif isinstance(node, ast.BinOp) and type(node.op) in ARITHMETIC_SWAP:
            old, new = ("+", "-") if isinstance(node.op, ast.Add) else ("-", "+")
            text = _replace_between(lines, node, node.left, node.right, old, new)
            if text:
                yield "arithmetic_swap", node, text
        elif isinstance(node, ast.AugAssign) and type(node.op) in ARITHMETIC_SWAP:
            old, new = ("+=", "-=") if isinstance(node.op, ast.Add) else ("-=", "+=")
            text = _replace_between(lines, node, node.target, node.value, old, new)
            if text:
                yield "arithmetic_swap", node, text
        elif isinstance(node, ast.Constant) and type(node.value) is int:
            yield "off_by_one", node, str(node.value + 1)


FUNCTION_SWAP = {"min": "max", "max": "min", "any": "all", "all": "any"}
METHOD_SWAP = {"upper": "lower", "lower": "upper", "startswith": "endswith", "endswith": "startswith",
               "isupper": "islower", "islower": "isupper", "isdigit": "isalpha", "isalpha": "isdigit",
               "find": "rfind", "rfind": "find", "lstrip": "rstrip", "rstrip": "lstrip", "floor": "ceil", "ceil": "floor"}
UNWRAPPABLE_CALLS = {"abs", "int", "str", "float", "round", "sorted", "reversed", "list", "set", "tuple"}


class _Span(NamedTuple):
    """A source span on one line, shaped like an AST node position (byte offsets)."""

    lineno: int
    end_lineno: int
    col_offset: int
    end_col_offset: int


def _single_line(node: ast.AST) -> bool:
    return getattr(node, "lineno", None) is not None and node.lineno == node.end_lineno


def _local_names(func: ast.FunctionDef) -> set[str]:
    args = func.args
    names = {a.arg for a in [*args.posonlyargs, *args.args, *args.kwonlyargs]}
    for node in ast.walk(func):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
    return names


def _candidates_v2(tree: ast.AST, lines: list[str]):
    called = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    for func in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)):
        local = sorted(_local_names(func))
        for node in ast.walk(func):
            if (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in local
                    and id(node) not in called and _single_line(node)):
                others = [n for n in local if n != node.id]
                if others:  # the next local name in sorted order: one deterministic alternative per site
                    yield "variable_misuse", node, others[local.index(node.id) % len(others)]
    for node in ast.walk(tree):
        if not _single_line(node):
            continue
        if isinstance(node, ast.BoolOp) and len(node.values) == 2 and all(_single_line(v) for v in node.values):
            for value in node.values:
                yield "missing_condition", node, _segment(lines, value)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult)):
            if _single_line(node.left):
                yield "missing_term", node, _segment(lines, node.left)
            if isinstance(node.op, ast.Add) and _single_line(node.right):
                yield "missing_term", node, _segment(lines, node.right)
        elif isinstance(node, ast.Call):
            func = node.func
            if (isinstance(func, ast.Name) and func.id in UNWRAPPABLE_CALLS and len(node.args) == 1
                    and not node.keywords and _single_line(node.args[0])):
                yield "missing_call", node, _segment(lines, node.args[0])
            if isinstance(func, ast.Name) and func.id in FUNCTION_SWAP:
                yield "function_swap", func, FUNCTION_SWAP[func.id]
            elif isinstance(func, ast.Attribute) and func.attr in METHOD_SWAP and _single_line(func):
                span = _Span(func.lineno, func.lineno, func.end_col_offset - len(func.attr.encode()), func.end_col_offset)
                yield "function_swap", span, METHOD_SWAP[func.attr]


def enumerate_mutants(source: str, family: str = "v1") -> list[Mutant]:
    """All single-fault mutants of `source` from one operator family, in a deterministic order."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    lines = source.splitlines(keepends=True)
    mutants, seen = [], {source}
    candidates = {"v1": _candidates, "v2": _candidates_v2}[family]
    sites = sorted(candidates(tree, lines), key=lambda c: (c[1].lineno, c[1].col_offset, c[0], c[2]))
    for operator, node, replacement in sites:
        code = _splice(lines, node, replacement)
        if code in seen:
            continue
        try:
            ast.parse(code)
        except SyntaxError:
            continue
        seen.add(code)
        mutants.append(Mutant(operator, node.lineno, code, _segment(lines, node), replacement))
    return mutants
