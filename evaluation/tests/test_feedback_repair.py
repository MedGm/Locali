from evaluation.feedback_repair import feedback_messages, repair_with_feedback
from evaluation.tasks.humanevalpack import PackItem

ITEM = PackItem(task_id="Python/0", prompt="", declaration="def add(a, b):\n", canonical_solution="    return a + b\n",
                buggy_solution="    return a - b\n", bug_type="operator", entry_point="add", imports="", test_setup="",
                test="def check(add):\n    assert add(1, 2) == 3\ncheck(add)\n")


def test_first_attempt_is_the_benchmark_prompt_and_retries_carry_the_error():
    first = feedback_messages(ITEM, None, None)[0]["content"]
    assert first.startswith("Fix bugs in add.") and "return a - b" in first and "Running the tests" not in first
    retry = feedback_messages(ITEM, "def add(a, b):\n    return a * b\n", "AssertionError: assert 2 == 3")[0]["content"]
    assert "return a * b" in retry and "return a - b" not in retry
    assert "Running the tests gives:" in retry and "assert 2 == 3" in retry


def answer(code):
    return f"```python\n{code}```"


def test_stops_at_the_first_passing_attempt_and_feeds_back_the_error():
    seen = []
    answers = iter([answer("def add(a, b):\n    return a * b\n"), answer("def add(a, b):\n    return a + b\n")])

    def model(messages):
        seen.append(messages[0]["content"])
        return next(answers)

    def run(code):
        ok = "a + b" in code
        return ok, None if ok else "AssertionError: assert 2 == 3"

    r = repair_with_feedback(ITEM, model, run, max_attempts=3)
    assert r["fixed_at"] == 2 and r["attempts"] == 2 and len(seen) == 2
    assert "assert 2 == 3" in seen[1] and "return a * b" in seen[1]


def test_gives_up_after_the_last_attempt():
    r = repair_with_feedback(ITEM, lambda m: answer("def add(a, b):\n    return 0\n"), lambda c: (False, "nope"), 3)
    assert r["fixed_at"] is None and r["attempts"] == 3 and len(r["errors"]) == 3
