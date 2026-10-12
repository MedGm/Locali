from training.data.mix import assign_split, explanation_for, reserved_for_t3
from training.data.tests.test_format import EXAMPLE


def test_split_depends_only_on_group_and_has_expected_proportions():
    groups = [f"src:{i}" for i in range(20000)]
    splits = [assign_split(g) for g in groups]

    assert assign_split("src:42") == assign_split("src:42")
    assert abs(splits.count("train") / len(groups) - 0.90) < 0.01
    assert abs(splits.count("val") / len(groups) - 0.05) < 0.01
    assert abs(splits.count("test") / len(groups) - 0.05) < 0.01


def test_t3_reservation_is_a_quarter_of_groups_and_independent_of_split():
    groups = [f"src:{i}" for i in range(20000)]
    reserved = [g for g in groups if reserved_for_t3(g)]

    assert abs(len(reserved) / len(groups) - 0.25) < 0.01
    in_train = sum(assign_split(g) == "train" for g in reserved) / len(reserved)
    assert abs(in_train - 0.90) < 0.02


def test_explanation_prefers_accepted_teacher_text_and_falls_back_to_template():
    good = "Using `x >= hi` returns hi for x == hi, but the test expects 10; it should be `x > hi`."
    assert explanation_for(EXAMPLE, good) == (good, "teacher")
    text, origin = explanation_for(EXAMPLE, "The mutation is wrong.")
    assert origin == "template" and "x > hi" in text
    assert explanation_for(EXAMPLE, None)[1] == "template"
