from pathlib import Path

from backend.validation import validate_workspace
from backend.workspace import open_workspace
from evaluation.tests.test_codegen import needs_docker

DEMO = Path(__file__).resolve().parents[2] / "demo_repo"
FIXED_DISCOUNT = "    return round(total * (1 - percent / 100), 2)"
BUGGY_DISCOUNT = "    return round(total * (1 + percent / 100), 2)"


def change(ws, path, old, new):
    p = ws.path / path
    p.write_text(p.read_text().replace(old, new))


@needs_docker
def test_fixing_the_failing_test_validates():
    ws = open_workspace(DEMO)
    try:
        change(ws, "tinyshop/pricing.py", BUGGY_DISCOUNT, FIXED_DISCOUNT)
        result = validate_workspace(ws.path, ["tinyshop/pricing.py"], original=DEMO, diff=ws.diff())
    finally:
        ws.cleanup()
    assert result["ok"]
    assert result["tests"]["failed"] == [] and result["tests"]["passed"] == 6
    assert result["new_security_findings"] == [] and result["secrets_added"] == []


@needs_docker
def test_existing_failure_is_not_ok():
    ws = open_workspace(DEMO)
    try:
        change(ws, "tinyshop/pricing.py", "def with_vat", "# vat\ndef with_vat")
        result = validate_workspace(ws.path, ["tinyshop/pricing.py"], original=DEMO, diff=ws.diff())
    finally:
        ws.cleanup()
    assert not result["ok"]
    assert result["tests"]["failed"] == ["tests/test_pricing.py::test_discount"]


@needs_docker
def test_new_vulnerability_or_secret_blocks_the_patch():
    ws = open_workspace(DEMO)
    try:
        change(ws, "tinyshop/pricing.py", BUGGY_DISCOUNT, FIXED_DISCOUNT)
        change(ws, "tinyshop/pricing.py", "def with_vat(total):",
               'API_TOKEN = "' + "q8Zt4Lm" + 'Wp2Xc9Rv7Kd1Nf" \n\n\ndef with_vat(total):\n    eval("1")')
        result = validate_workspace(ws.path, ["tinyshop/pricing.py"], original=DEMO, diff=ws.diff())
    finally:
        ws.cleanup()
    assert not result["ok"]
    assert any(f["rule"] in ("eval-exec", "B307") for f in result["new_security_findings"])
    assert result["secrets_added"] == ["generic-secret"]


def test_existing_findings_in_a_touched_file_do_not_block(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / "m.py").write_text("def run(x):\n    return eval(x)\n\n\ndef add(a, b):\n    return a - b\n")
    ws = open_workspace(repo)
    try:
        change(ws, "m.py", "a - b", "a + b")
        result = validate_workspace(ws.path, ["m.py"], original=repo, diff=ws.diff(), run_tests=False)
    finally:
        ws.cleanup()
    assert result["new_security_findings"] == [] and result["ok"]
