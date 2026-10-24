from evaluation.isolated import run_isolated
from training.data.realistic_bugs import (
    BUG_KINDS,
    bug_messages,
    changed_lines,
    check_candidate,
    strip_comments,
    unittest_program,
)

ORIGINAL = '''def count_positive(xs):
    # count the strictly positive numbers
    n = 0
    for x in xs:
        if x > 0:
            n += 1
    return n
'''

TESTS = '''import unittest

class TestCount(unittest.TestCase):
    def test_mixed(self):
        self.assertEqual(count_positive([1, -2, 0, 3]), 2)

    def test_empty(self):
        self.assertEqual(count_positive([]), 0)
'''


def test_prompt_names_the_kind_and_shows_the_code():
    msgs = bug_messages("Count positives.", ORIGINAL, "off_by_one")
    text = msgs[-1]["content"]
    assert BUG_KINDS["off_by_one"] in text and "def count_positive" in text


def test_comments_are_stripped_so_they_cannot_give_the_bug_away():
    assert "#" not in strip_comments(ORIGINAL)
    assert "def count_positive(xs):" in strip_comments(ORIGINAL)


def test_a_realistic_edit_is_accepted():
    buggy = ORIGINAL.replace("x > 0", "x >= 0")
    assert check_candidate(ORIGINAL, buggy) == (True, "ok")


def test_an_unchanged_or_renamed_only_function_is_rejected():
    assert check_candidate(ORIGINAL, ORIGINAL)[0] is False
    assert check_candidate(ORIGINAL, ORIGINAL.replace("# count", "# tally"))[1] == "unchanged"


def test_a_rewrite_of_the_whole_function_is_rejected():
    rewrite = "def count_positive(xs):\n    return len([x for x in xs if x > 1])\n"
    ok, reason = check_candidate(ORIGINAL, rewrite)
    assert not ok and reason == "too many changed lines"


def test_a_changed_signature_is_rejected():
    ok, reason = check_candidate(ORIGINAL, ORIGINAL.replace("count_positive(xs)", "count_positive(xs, k=0)"))
    assert not ok and reason == "signature changed"


def test_unparseable_code_is_rejected():
    assert check_candidate(ORIGINAL, "def count_positive(xs)\n    return 0\n") == (False, "syntax error")


def test_changed_lines_counts_edited_lines_only():
    assert changed_lines(ORIGINAL, ORIGINAL.replace("x > 0", "x >= 0")) == 1


def test_the_test_program_passes_on_the_original_and_fails_on_a_bug():
    assert run_isolated(unittest_program(ORIGINAL, TESTS), isolate_network="none").passed
    buggy = run_isolated(unittest_program(ORIGINAL.replace("x > 0", "x >= 0"), TESTS), isolate_network="none")
    assert not buggy.passed and "AssertionError" in buggy.error


def test_missing_logic_must_remove_a_statement():
    dropped = ORIGINAL.replace("        if x > 0:\n            n += 1\n", "        n += 1\n")
    assert check_candidate(ORIGINAL, dropped, kind="missing_logic") == (True, "ok")
    edited = ORIGINAL.replace("x > 0", "x >= 0")
    assert check_candidate(ORIGINAL, edited, kind="missing_logic") == (False, "no statement removed")


def test_excess_logic_must_add_a_statement():
    added = ORIGINAL.replace("    return n\n", "    if n > 2:\n        n -= 1\n    return n\n")
    assert check_candidate(ORIGINAL, added, kind="excess_logic") == (True, "ok")
    edited = ORIGINAL.replace("return n", "return n + 0")
    assert check_candidate(ORIGINAL, edited, kind="excess_logic") == (False, "no statement added")


def test_the_reported_error_is_the_assertion_message_not_the_diff_tail():
    tests = TESTS.replace("count_positive([1, -2, 0, 3]), 2)", "[count_positive([1, -2, 0, 3])], [2])")
    r = run_isolated(unittest_program(ORIGINAL.replace("x > 0", "x >= 0"), tests), isolate_network="none")
    assert r.error.startswith("AssertionError: Lists differ: [3] != [2]"), r.error


def test_the_teacher_reply_gives_a_description_and_code():
    from training.data.realistic_bugs import parse_reply

    reply = "Bug: the loop forgets to skip zeros.\n```python\ndef f():\n    return 1\n```"
    assert parse_reply(reply) == ("the loop forgets to skip zeros.", "def f():\n    return 1")
    assert parse_reply("```python\ndef f():\n    return 1\n```")[0] == ""
