import json
from pathlib import Path

from backend.agents.review import review_functions
from backend.tests.test_debug_agent import ScriptedModel

DEMO = Path(__file__).resolve().parents[2] / "demo_repo"


def answer(*findings):
    return json.dumps({"findings": list(findings)})


def test_findings_are_located_in_the_file_and_hallucinated_lines_dropped():
    model = ScriptedModel(answer(
        {"line": "    return round(total * (1 + percent / 100), 2)", "category": "bug", "severity": "high",
         "message": "adds the discount"},
        {"line": "    total = total - discount", "category": "bug", "severity": "high", "message": "made up"},
    ))
    result = review_functions(DEMO, model, [("tinyshop/pricing.py", "apply_discount")])
    assert [(f["path"], f["line"], f["category"], f["tool"]) for f in result.findings] == [
        ("tinyshop/pricing.py", 16, "bug", "model")]
    assert result.dropped == 1
    assert "Review the following Python code" in model.prompts[0]


def test_unparseable_answer_is_counted_and_adds_nothing():
    result = review_functions(DEMO, ScriptedModel("looks fine to me"), [("tinyshop/pricing.py", "with_vat")])
    assert result.findings == [] and result.invalid == 1


def test_code_sent_to_the_model_is_redacted(tmp_path):
    (tmp_path / "m.py").write_text('def connect():\n    key = "AKIAIOSFODNN7EXAMPLE"\n    return key\n')
    model = ScriptedModel(answer())
    review_functions(tmp_path, model, [("m.py", "connect")])
    assert "AKIAIOSFODNN7EXAMPLE" not in model.prompts[0] and "[REDACTED" in model.prompts[0]
