import json

import pytest

from evaluation.tasks.condefects import DefectItem, candidates
from evaluation.tests.test_codegen import needs_docker
from training.data.real_bugs import check, collect, messages, older_contests

CORRECT = "a, b = map(int, input().split())\nprint(a + b)\n"
FAULTY = "a, b = map(int, input().split())\nprint(a - b)\n"


@pytest.fixture
def condefects(tmp_path):
    """Two tasks, one before the evaluation's cut-off (2024-02-01) and one after."""
    code = tmp_path / "Code"
    for task, date in (("abc300_a", "2023-05-01"), ("abc999_a", "2024-03-01")):
        sub = code / task / "Python" / "1"
        sub.mkdir(parents=True)
        (sub / "faultyVersion.py").write_text(FAULTY)
        (sub / "correctVersion.py").write_text(CORRECT)
        tests = tmp_path / "Test" / task.split("_")[0] / "A"
        for name, given, want in [("01.txt", "1 1", "2"), ("00_zero.txt", "0 0", "0")]:
            for kind, text in (("in", given), ("out", want)):
                (tests / kind).mkdir(parents=True, exist_ok=True)
                (tests / kind / name).write_text(text + "\n")
    (tmp_path / "date.txt").write_text("abc300_a 2023-05-01\nabc999_a 2024-03-01\n")
    return code


def test_only_tasks_before_the_cut_off_are_candidates(condefects):
    root = condefects.parent / "Test"
    assert older_contests(condefects) == {"abc300"}
    assert [i.task_id for i in candidates(condefects, root, since="0000", before="2024-02-01")] == ["abc300_a/1"]
    assert [i.task_id for i in candidates(condefects, root)] == ["abc999_a/1"]


def test_row_is_the_evaluation_prompt_answered_with_the_accepted_program():
    item = DefectItem("abc300_a/1", "2023-05-01", FAULTY, CORRECT, "abc300/A", "1 1", "2", "0")
    user, answer = messages(item)
    assert user["content"].startswith("Fix the bug in this program.") and "Actual output:\n0" in user["content"]
    assert answer == {"role": "assistant", "content": f"```python\n{CORRECT}\n```"}


@needs_docker
def test_collect_keeps_a_bug_whose_failing_test_the_accepted_program_passes(condefects, monkeypatch, tmp_path):
    root = condefects.parent / "Test"
    monkeypatch.setenv("CONDEFECTS_TESTS", str(root))
    same = DefectItem("abc300_a/2", "2023-05-01", CORRECT, CORRECT, "abc300/A")
    assert check(same, root) == "faulty version passes every test"
    out = tmp_path / "out" / "bugs.jsonl"
    collect(condefects, out, workers=1)
    collect(condefects, out, workers=1)  # the second run finds everything done
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert [(r["task_id"], r["verdict"], r["shown_input"], r["shown_actual"]) for r in rows] == [
        ("abc300_a/1", "kept", "1 1", "0")]


def test_mix_rows_drop_what_was_not_kept_or_is_dated_in_the_evaluation_period():
    from training.data.build_mix_v3r import real_rows

    def bug(task_id, date, verdict="kept", faulty=FAULTY):
        return {"task_id": task_id, "date": date, "faulty": faulty, "correct": CORRECT, "tests": "x/A",
                "shown_input": "1 1", "shown_expected": "2", "shown_actual": "0", "verdict": verdict}

    bugs = [bug("abc300_a/1", "2023-05-01"), bug("abc300_a/2", "2023-05-01", verdict="faulty version passes every test"),
            bug("abc999_a/1", "2024-03-01"), bug("abc301_a/1", "2023-06-01", faulty="LEAKED\n" + FAULTY)]
    rows, dropped = real_rows(bugs, lambda text: ["humaneval_plus"] if "LEAKED" in text else [])
    assert [(r["id"], r["task"], r["group"]) for r in rows] == [("t1c-abc300_a-1", "T1C", "condefects:abc300_a")]
    assert rows[0]["split"] in ("train", "val", "test") and len(rows[0]["messages"]) == 2
    assert dropped == {"not kept by the check": 1, "dated in the evaluation period": 1, "overlaps humaneval_plus": 1}
