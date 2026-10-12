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
"""

import ast
import re
from dataclasses import dataclass

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


def enumerate_mutants(source: str) -> list[Mutant]:
    """All single-fault mutants of `source`, in a deterministic order."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    lines = source.splitlines(keepends=True)
    mutants, seen = [], {source}
    sites = sorted(_candidates(tree, lines), key=lambda c: (c[1].lineno, c[1].col_offset, c[0], c[2]))
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
