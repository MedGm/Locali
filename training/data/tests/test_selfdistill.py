from training.data.selfdistill import replace_replay, replay_prompts, runnable_code

REPLAY = {"id": "replay-4", "task": "replay", "group": "self-oss:4",
          "messages": [{"role": "user", "content": "Write add(a, b)."},
                       {"role": "assistant", "content": "Original answer."}]}
REPAIR = {"id": "t1-7", "task": "T1", "group": "mbpp:7",
          "messages": [{"role": "user", "content": "Fix it."}, {"role": "assistant", "content": "Fixed."}]}
ANSWER = "Here it is:\n```python\ndef add(a, b):\n    return a + b\n```\nIt adds."


def test_prompts_are_the_replay_rows_without_their_answer():
    assert replay_prompts([REPLAY, REPAIR]) == [("replay-4", [{"role": "user", "content": "Write add(a, b)."}])]


def test_finished_answer_with_parsing_code_gives_its_code():
    assert runnable_code({"text": ANSWER, "finish_reason": "stop"}) == "def add(a, b):\n    return a + b"


def test_cut_off_answer_is_rejected():
    assert runnable_code({"text": ANSWER, "finish_reason": "length"}) is None


def test_answer_without_python_block_is_rejected():
    assert runnable_code({"text": "Use a + b.", "finish_reason": "stop"}) is None


def test_code_that_does_not_parse_is_rejected():
    assert runnable_code({"text": "```python\ndef add(a, b)\n    return a + b\n```", "finish_reason": "stop"}) is None


def test_failed_request_is_rejected():
    assert runnable_code({"error": "timeout"}) is None


def test_accepted_answers_replace_only_replay_rows():
    rows, n = replace_replay([REPLAY, REPAIR], {"replay-4": ANSWER, "t1-7": "ignored"})

    assert rows[0]["messages"] == [REPLAY["messages"][0], {"role": "assistant", "content": ANSWER}]
    assert rows[1] == REPAIR
    assert n == 1
    assert REPLAY["messages"][1]["content"] == "Original answer."  # input rows unchanged


def test_replay_rows_without_an_accepted_answer_keep_the_original():
    rows, n = replace_replay([REPLAY], {})

    assert rows == [REPLAY]
    assert n == 0
