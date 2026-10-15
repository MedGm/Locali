import json
from pathlib import Path

from backend.agents.single import review_files
from backend.tests.test_debug_agent import ScriptedModel

DEMO = Path(__file__).resolve().parents[2] / "demo_repo"


def test_single_agent_reviews_whole_files_and_locates_findings():
    model = ScriptedModel(json.dumps({"findings": [
        {"line": "    return round(total * (1 + percent / 100), 2)", "category": "bug", "severity": "high",
         "message": "adds the discount"},
        {"line": "not in the file", "category": "bug", "severity": "high", "message": "made up"},
    ]}))
    result = review_files(DEMO, model, ["tinyshop/pricing.py"])
    assert "def bulk_discount" in model.prompts[0] and "def apply_discount" in model.prompts[0]
    assert [(f["path"], f["line"], f["tool"]) for f in result.findings] == [("tinyshop/pricing.py", 16, "model")]
    assert result.dropped == 1
