import json

from training.data.build_mix_v3f import reorder
from training.data.format import (
    REPAIR_INSTRUCTION,
    REPAIR_INSTRUCTION_CODE_FIRST,
    parse_repair_answer,
)

DIAGNOSIS = {"bug_location": "    return a - b", "bug_type": "wrong arithmetic operator", "explanation": "Uses {-}."}
REPAIR = {"id": "t1-1", "task": "T1", "messages": [
    {"role": "user", "content": f"The following Python function has a bug.\n\n{REPAIR_INSTRUCTION}"},
    {"role": "assistant", "content": json.dumps(DIAGNOSIS) + "\n```python\ndef add(a, b):\n    return a + b\n```"}]}
BENCHMARK = {"id": "t1r-2", "task": "T1R", "messages": [
    {"role": "user", "content": "Fix bugs in add."}, {"role": "assistant", "content": "```python\ndef add(a, b):\n    return a + b\n```"}]}


def test_repair_rows_get_the_code_first_and_keep_code_and_diagnosis():
    rows, changed = reorder([REPAIR, BENCHMARK])
    user, answer = rows[0]["messages"]
    assert user["content"].endswith(REPAIR_INSTRUCTION_CODE_FIRST) and REPAIR_INSTRUCTION not in user["content"]
    assert answer["content"] == "```python\ndef add(a, b):\n    return a + b\n```\n" + json.dumps(DIAGNOSIS)
    assert parse_repair_answer(answer["content"]) == parse_repair_answer(REPAIR["messages"][1]["content"])
    assert changed == {"T1": 1}


def test_other_rows_and_the_input_are_left_alone():
    before = json.dumps([REPAIR, BENCHMARK])
    rows, _ = reorder([REPAIR, BENCHMARK])
    assert rows[1] is BENCHMARK and json.dumps([REPAIR, BENCHMARK]) == before
