
from evaluation.client import Completion
from evaluation.tasks.security import SECURE_CODEGEN_TASK, VULN_DETECT_TASK, bandit_findings
from evaluation.tests.test_codegen import needs_hub

UNSAFE_YAML = "import yaml\n\n\ndef load(path):\n    return yaml.load(open(path))\n"
SAFE_YAML = "import yaml\n\n\ndef load(path):\n    with open(path) as f:\n        return yaml.safe_load(f)\n"


def answer(text: str) -> Completion:
    return Completion(text, "", 10, 10, 0.1, 0.2, "stop")


def test_bandit_reports_medium_or_higher_findings_with_cwe():
    findings = bandit_findings(UNSAFE_YAML)

    assert [(f["test_id"], f["cwe"]) for f in findings] == [("B506", "CWE-20")]


def test_bandit_reports_nothing_for_safe_code():
    assert bandit_findings(SAFE_YAML) == []


def test_bandit_returns_none_for_unparseable_code():
    assert bandit_findings("def broken(:\n") is None


def test_secure_codegen_metrics():
    records = [{"status": "flagged"}, {"status": "clean"}, {"status": "clean"}, {"status": "unparseable"}]

    m = SECURE_CODEGEN_TASK.metrics(records)

    assert m["insecure_rate"] == 0.25
    assert m["unparseable_rate"] == 0.25


@needs_hub
def test_secure_codegen_loads_securityeval_and_flags_its_insecure_reference():
    items = SECURE_CODEGEN_TASK.load()
    yaml_item = next(i for i in items if i.task_id == "CWE-020_author_1.py")

    assert len(items) == 121
    assert "def yaml_load(filename):" in SECURE_CODEGEN_TASK.messages(yaml_item)[-1]["content"]
    assert SECURE_CODEGEN_TASK.score(yaml_item, answer(f"```python\n{UNSAFE_YAML}```"), 60)["status"] == "flagged"
    assert SECURE_CODEGEN_TASK.score(yaml_item, answer(f"```python\n{SAFE_YAML}```"), 60)["status"] == "clean"


@needs_hub
def test_vuln_detect_pairs_vulnerable_and_secure_python_versions():
    items = VULN_DETECT_TASK.load()

    assert len(items) > 300 and len(items) % 2 == 0
    assert items[0].task_id.endswith("/vulnerable") and items[1].task_id.endswith("/secure")
    assert [items[0].label, items[1].label] == [True, False]
    assert '"vulnerable": true or false' in VULN_DETECT_TASK.messages(items[0])[-1]["content"]


@needs_hub
def test_vuln_detect_scores_verdict():
    item = VULN_DETECT_TASK.load(limit=10)[0]

    assert VULN_DETECT_TASK.score(item, answer('{"vulnerable": true, "cwe": "CWE-94"}'), 60)["status"] == "correct"
    assert VULN_DETECT_TASK.score(item, answer("no idea"), 60)["status"] == "invalid"


@needs_hub
def test_vuln_detect_keeps_only_pairs_where_both_versions_parse():
    import ast

    items = VULN_DETECT_TASK.load()

    for item in items:
        ast.parse(item.code)  # raises if an unparseable snippet slipped through
    assert "cybernative-unparseable-pairs" in VULN_DETECT_TASK.excluded
