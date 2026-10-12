from training.data.selfoss import replay_examples, review_items

ROWS = [
    {"id": 0, "instruction": "Write add.", "response": "Here:\n```python\ndef add(a, b):\n    return a + b\n```"},
    {"id": 1, "instruction": "Run a command.", "response": "```python\nimport subprocess\n\ndef run(c):\n    return subprocess.call(c, shell=True)\n```"},
    {"id": 2, "instruction": "Write mul.", "response": "```python\ndef mul(a, b):\n    return a * b\n```"},
    {"id": 3, "instruction": "Unused import.", "response": "```python\nimport os\n\ndef one():\n    return 1\n```"},
    {"id": 5, "instruction": "Sum.", "response": "```python\ndef total(xs):\n    return sum(xs)\n```"},
]


def test_replay_uses_even_ids_with_instruction_and_full_response():
    examples = replay_examples(ROWS, n=10)

    assert {e["group"] for e in examples} == {"self-oss:0", "self-oss:2"}
    add = next(e for e in examples if e["group"] == "self-oss:0")
    assert add["messages"][0] == {"role": "user", "content": "Write add."}
    assert add["messages"][1]["content"].startswith("Here:")


def test_review_items_use_odd_ids_and_balance_kinds():
    items = review_items(ROWS, n_security=1, n_quality=1, n_clean=1)
    by_group = {i["group"]: i for i in items}

    assert set(by_group) == {"self-oss:1", "self-oss:3", "self-oss:5"}
    assert {f["category"] for f in by_group["self-oss:1"]["findings"]} >= {"security"}
    assert {f["category"] for f in by_group["self-oss:3"]["findings"]} == {"quality"}
    assert by_group["self-oss:5"]["findings"] == []
