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

from collections.abc import Callable

from evaluation.extract import extract_code, sanitize
from evaluation.tasks.humanevalpack import PackItem

Model = Callable[[list[dict]], str]
Run = Callable[[str], tuple[bool, str | None]]  # code -> (passed, error)


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


def repair_with_feedback(item: PackItem, model: Model, run: Run, max_attempts: int = 3) -> dict:
    code: str | None = None
    error: str | None = None
    errors, answers = [], []
    for attempt in range(1, max_attempts + 1):
        answer = model(feedback_messages(item, code, error))
        answers.append(answer)
        code = sanitize(extract_code(answer, entry_point=item.entry_point)) or code
        passed, error = run(code or "")
        if passed:
            return {"task_id": item.task_id, "fixed_at": attempt, "attempts": attempt, "errors": errors,
                    "answers": answers, "code": code}
        errors.append(error or "the tests failed")
    return {"task_id": item.task_id, "fixed_at": None, "attempts": max_attempts, "errors": errors,
            "answers": answers, "code": code}
