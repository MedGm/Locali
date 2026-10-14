import asyncio
import os
import sys
from pathlib import Path

import pytest

from evaluation.tests.test_codegen import needs_docker
from mcp_servers.analysis_server import analyze_path
from mcp_servers.repo_server import read_file
from mcp_servers.tests_server import run_tests

DEMO = Path(__file__).resolve().parents[2] / "demo_repo"


def client(module, root):
    from langchain_mcp_adapters.client import MultiServerMCPClient

    return MultiServerMCPClient({
        "s": {"transport": "stdio", "command": sys.executable, "args": ["-m", module, "--root", str(root)],
              "cwd": os.getcwd()}
    })


def call(module, root, tool, args):
    async def go():
        tools = {t.name: t for t in await client(module, root).get_tools()}
        return sorted(tools), str(await tools[tool].ainvoke(args))
    return asyncio.run(go())


def test_repo_server_redacts_secrets():
    text = read_file(DEMO, "tinyshop/settings.py")
    assert "AKIAIOSFODNN7EXAMPLE" not in text
    assert "[REDACTED:aws-access-key]" in text
    assert "VAT_RATE = 0.20" in text


@needs_docker
def test_run_tests_reports_the_failing_test_and_coverage():
    result = run_tests(DEMO)
    assert result["failed"] == ["tests/test_pricing.py::test_discount"]
    assert result["passed"] == 5
    assert 0 < result["coverage_percent"] < 100
    assert not result["timed_out"]


@needs_docker
def test_run_tests_can_select_tests():
    result = run_tests(DEMO, ["tests/test_inventory.py"])
    assert result["passed"] == 3 and result["failed"] == []


def test_run_tests_rejects_selection_outside_root():
    with pytest.raises(PermissionError):
        run_tests(DEMO, ["../evaluation/tests"])


def test_analyze_path_is_confined_and_returns_findings():
    findings = analyze_path(DEMO, "tinyshop")
    assert {"bandit", "semgrep", "secrets"} <= {f["tool"] for f in findings}
    assert all(not f["path"].startswith("/") for f in findings)
    with pytest.raises(PermissionError):
        analyze_path(DEMO, "..")


def test_mcp_servers_expose_only_their_tools():
    tools, _ = call("mcp_servers.analysis_server", DEMO, "analyze", {"path": "tinyshop"})
    assert tools == ["analyze"]
    tools, out = call("mcp_servers.tests_server", DEMO, "run_tests", {"select": ["../x"]})
    assert tools == ["run_tests"]
    assert "outside" in out.lower()
