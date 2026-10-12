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


from training.data.teacher import condense

LONG = ("The condition `x >= hi` returns hi for x equal to hi, so clamp(10, 0, 10) gives 9 instead of 10. "
        "This happens because the boundary value is treated as out of range, which shifts every edge case "
        "and breaks the expected identity for values already inside the interval, as the failing test shows "
        "with its explicit check on the upper edge; the fix restores the strict comparison `x > hi` here, "
        "which keeps every value inside the interval unchanged and only clips values strictly above it.")


def test_condense_keeps_first_sentence_of_long_text():
    assert len(LONG) > 400
    assert condense(LONG, cut=False) == "The condition `x >= hi` returns hi for x equal to hi, so clamp(10, 0, 10) gives 9 instead of 10."


def test_condense_drops_unfinished_sentence_of_cut_text():
    cut = "The condition `x >= hi` returns hi too early. It should be `x > hi` so that the upper"
    assert condense(cut, cut=True) == "The condition `x >= hi` returns hi too early."


def test_condense_keeps_short_complete_text():
    text = "Using `x >= hi` treats 10 as out of range; it should be `x > hi`."
    assert condense(text, cut=False) == text
