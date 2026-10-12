from training.data.teacher import accept_explanation, teacher_messages
from training.data.tests.test_format import EXAMPLE


def test_teacher_prompt_gives_both_lines_test_and_error():
    content = teacher_messages(EXAMPLE)[-1]["content"]

    assert "x >= hi" in content and "x > hi" in content
    assert "AssertionError: 10 != 9" in content
    assert "def test_edges" in content


def test_accepts_explanation_that_references_the_code():
    assert accept_explanation(EXAMPLE, "Using `>=` returns `hi` too early, so clamp(10, 0, 10) gives 9 instead of 10; it should be `x > hi`.")


def test_rejects_explanations_that_leak_the_construction_or_miss_the_code():
    assert not accept_explanation(EXAMPLE, "This mutation flipped the operator x >= hi.")
    assert not accept_explanation(EXAMPLE, "The function has a logic error in a condition somewhere.")
    assert not accept_explanation(EXAMPLE, "x > hi")  # too short
    assert not accept_explanation(EXAMPLE, "Because x >= hi. " * 40)  # too long
