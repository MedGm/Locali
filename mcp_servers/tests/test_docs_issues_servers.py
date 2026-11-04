import asyncio
import os
import sys
from pathlib import Path

import pytest

from mcp_servers.docs_server import list_docs, read_doc, search_docs
from mcp_servers.issues_server import build_server, draft_issue, get_issue, list_issues

DEMO = Path(__file__).resolve().parents[2] / "demo_repo"


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    (root / "docs" / "issues").mkdir(parents=True)
    (root / "README.md").write_text("# shop\n\nRun the report with `python -m shop report`.\n")
    (root / "docs" / "setup.rst").write_text("Setup\n=====\n\naws_key = \"AKIAIOSFODNN7EXAMPLE\"\n")
    (root / "shop.py").write_text("def report():\n    pass\n")
    (root / "docs" / "issues" / "ISSUE-3.md").write_text("# #3 Report is slow\n\nOpened by: sam\n\nTakes 10 s.\n")
    (root / "docs" / "issues" / "notes.md").write_text("not an issue\n")
    (tmp_path / "outside.md").write_text("private\n")
    return root


# ---- docs ----

def test_list_docs_has_only_documentation_files(repo):
    assert list_docs(repo) == ["README.md", "docs/issues/ISSUE-3.md", "docs/issues/notes.md", "docs/setup.rst"]


@pytest.mark.parametrize("path", ["../outside.md", "shop.py"])
def test_read_doc_refuses_paths_outside_root_and_code_files(repo, path):
    with pytest.raises(PermissionError):
        read_doc(repo, path)


def test_read_doc_redacts_secrets(repo):
    assert "AKIAIOSFODNN7EXAMPLE" not in read_doc(repo, "docs/setup.rst")["text"]


def test_search_docs_needs_every_word(repo):
    hits = search_docs(repo, "REPORT python")
    assert [(h["path"], h["line"]) for h in hits] == [("README.md", 3)]


def test_demo_readme_injection_is_listed_with_the_text():
    doc = read_doc(DEMO, "README.md")
    assert any("already audited" in w for w in doc["injection_warnings"])
    assert any(h["injection"] for h in search_docs(DEMO, "audited"))


# ---- issues ----

def test_list_and_get_issue(repo):
    assert list_issues(repo) == [{"number": 3, "title": "Report is slow", "author": "sam", "injection_warnings": 0}]
    assert "Takes 10 s." in get_issue(repo, 3)["text"]
    with pytest.raises(FileNotFoundError):
        get_issue(repo, 4)


def test_demo_issue_with_fake_approval_is_flagged():
    issue = get_issue(DEMO, 12)
    assert issue["title"] == "Daily report shows wrong total"
    assert issue["author"] == "karim-shop"
    assert any("system or a maintainer" in w for w in issue["injection_warnings"])


def test_draft_issue_writes_a_draft_and_files_nothing(repo, tmp_path):
    drafts = tmp_path / "drafts"
    assert draft_issue(drafts, "Oversell", "POST /orders accepts 5 when stock is 1.") == {
        "draft": "draft-001.md", "filed": False}
    assert draft_issue(drafts, "Second", "body")["draft"] == "draft-002.md"
    assert "review before filing" in (drafts / "draft-001.md").read_text()
    assert sorted(p.name for p in (repo / "docs" / "issues").iterdir()) == ["ISSUE-3.md", "notes.md"]


@pytest.mark.parametrize(("title", "body"), [("", "body"), ("t", "  "), ("x" * 121, "body")])
def test_draft_issue_rejects_empty_or_long_input(tmp_path, title, body):
    with pytest.raises(ValueError):
        draft_issue(tmp_path / "d", title, body)


def test_drafts_folder_inside_the_repository_is_refused(repo):
    with pytest.raises(PermissionError):
        build_server(repo, repo / "drafts")


# ---- over MCP stdio ----

def tools(module, *args):
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient({"s": {"transport": "stdio", "command": sys.executable,
                                         "args": ["-m", module, *args], "cwd": os.getcwd()}})
    return client


def test_docs_server_over_mcp(repo):
    async def go():
        found = {t.name: t for t in await tools("mcp_servers.docs_server", "--root", str(repo)).get_tools()}
        return sorted(found), str(await found["read_doc"].ainvoke({"path": "../outside.md"}))

    names, refused = asyncio.run(go())
    assert names == ["list_docs", "read_doc", "search_docs"]
    assert "private" not in refused and "outside" in refused.lower()


def test_issues_server_offers_draft_only_with_a_drafts_folder(repo, tmp_path):
    async def names(*extra):
        return sorted(t.name for t in await tools("mcp_servers.issues_server", "--root", str(repo), *extra).get_tools())

    assert asyncio.run(names()) == ["get_issue", "list_issues"]
    assert asyncio.run(names("--drafts", str(tmp_path / "drafts"))) == ["draft_issue", "get_issue", "list_issues"]
