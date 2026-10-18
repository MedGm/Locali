"""HumanEvalFix the way the platform repairs code: try, run the tests, show the error, try again.

The benchmark's pass@1 gives the model one answer and no feedback. The assistant's repair loop
(backend/agents/debug.py) instead runs the failing test after each attempt and, if it still fails,
asks again with the latest version of the function and the new error, up to three times. This
measures that setting: fixed after 1, 2 or 3 attempts.

Each attempt is a single prompt, as in the agent: the benchmark's repair prompt, with the code the
model wrote last time in place of the buggy function and the test error below it. The tests shown
in the prompt are the tests that decide the score, as in the real setting where the failing test is
what the agent has to make pass.
"""

import ast
from collections.abc import Callable

from evaluation.extract import extract_code, sanitize
from evaluation.tasks.humanevalpack import PackItem

Model = Callable[[list[dict]], str]
Run = Callable[[str], tuple[bool, str | None]]  # code -> (passed, error)


_SHOW = (
    "def _lc_show(v):\n"
    "    s = repr(v)\n"
    "    return s if len(s) <= 200 else s[:200] + '...'\n\n"
)


class _ExplainAsserts(ast.NodeTransformer):
    """assert a == b -> evaluate a and b once, fail with what a returned and what was expected."""

    def visit_Assert(self, node: ast.Assert):
        if node.msg is not None:
            return node
        test = node.test
        if isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq):
            left, right = ast.unparse(test.left), ast.unparse(test.comparators[0])
            code = (f"_lc_l = {left}\n_lc_r = {right}\n"
                    f"if not (_lc_l == _lc_r):\n"
                    f"    raise AssertionError({left!r} + ' returned ' + _lc_show(_lc_l) + ', expected ' + _lc_show(_lc_r))\n")
            return ast.parse(code).body
        node.msg = ast.Constant("failed: assert " + ast.unparse(test))
        return node


def explain_asserts(test: str) -> str:
    """The same test, but a failing assertion says what the code returned. It passes exactly when the
    original passes, so it can replace it; if the test does not parse, it is returned unchanged."""
    try:
        tree = _ExplainAsserts().visit(ast.parse(test))
    except SyntaxError:
        return test
    return _SHOW + ast.unparse(ast.fix_missing_locations(tree)) + "\n"


def feedback_messages(item: PackItem, code: str | None, error: str | None) -> list[dict]:
    shown = code if code is not None else f"{item.declaration}{item.buggy_solution}"
    content = (
        f"Fix bugs in {item.entry_point}.\n\n"
        f"```python\n{shown.rstrip()}\n```\n\n"
        f"These tests fail:\n```python\n{item.test.strip()}\n```\n\n"
    )
    if error is not None:
        content += f"Running the tests gives:\n```\n{error.strip()[:1500]}\n```\n\n"
    content += "Return the complete fixed function in a markdown code block."
    return [{"role": "user", "content": content}]


def repair_with_feedback(item: PackItem, model: Model, run: Run, max_attempts: int = 3,
                         retry_model: Model | None = None) -> dict:
    """retry_model, when given, answers attempts 2 and up (e.g. the same model at a small temperature)."""
    code: str | None = None
    error: str | None = None
    errors, answers = [], []
    for attempt in range(1, max_attempts + 1):
        ask = retry_model if retry_model is not None and attempt > 1 else model
        answer = ask(feedback_messages(item, code, error))
        answers.append(answer)
        code = sanitize(extract_code(answer, entry_point=item.entry_point)) or code
        passed, error = run(code or "")
        if passed:
            return {"task_id": item.task_id, "fixed_at": attempt, "attempts": attempt, "errors": errors,
                    "answers": answers, "code": code}
        errors.append(error or "the tests failed")
    return {"task_id": item.task_id, "fixed_at": None, "attempts": max_attempts, "errors": errors,
            "answers": answers, "code": code}
