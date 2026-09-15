import asyncio
import os
import sys

import pytest

from mcp_servers.repo_server import list_files, read_file


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "calc.py").write_text("def add(a, b):\n    return a + b\n")
    (root / "README.md").write_text("# demo\n")
    (tmp_path / "secret.txt").write_text("API_KEY=sk-not-real\n")
    return root


# ---- path confinement (unit) ----

def test_read_file_returns_content_inside_root(repo):
    assert read_file(repo, "pkg/calc.py").startswith("def add")


@pytest.mark.parametrize("path", ["../secret.txt", "pkg/../../secret.txt"])
def test_read_file_rejects_parent_traversal(repo, path):
    with pytest.raises(PermissionError):
        read_file(repo, path)


def test_read_file_rejects_absolute_path_outside_root(repo):
    with pytest.raises(PermissionError):
        read_file(repo, str(repo.parent / "secret.txt"))


def test_read_file_rejects_symlink_escaping_root(repo):
    os.symlink(repo.parent / "secret.txt", repo / "link.txt")
    with pytest.raises(PermissionError):
        read_file(repo, "link.txt")


def test_list_files_returns_relative_paths(repo):
    assert list_files(repo) == ["README.md", "pkg/calc.py"]


# ---- over MCP stdio ----

def mcp_client(repo):
    from langchain_mcp_adapters.client import MultiServerMCPClient

    return MultiServerMCPClient({
        "repo": {
            "transport": "stdio",
            "command": sys.executable,
            "args": ["-m", "mcp_servers.repo_server", "--root", str(repo)],
            "cwd": os.getcwd(),
        }
    })


def test_mcp_server_exposes_only_allow_listed_tools(repo):
    tools = asyncio.run(mcp_client(repo).get_tools())

    assert sorted(t.name for t in tools) == ["list_files", "read_file"]


def test_mcp_read_file_tool_returns_content(repo):
    async def call():
        tools = {t.name: t for t in await mcp_client(repo).get_tools()}
        return await tools["read_file"].ainvoke({"path": "pkg/calc.py"})

    assert "def add" in str(asyncio.run(call()))


def test_mcp_read_file_tool_refuses_traversal(repo):
    async def call():
        tools = {t.name: t for t in await mcp_client(repo).get_tools()}
        return await tools["read_file"].ainvoke({"path": "../secret.txt"})

    result = str(asyncio.run(call()))
    assert "sk-not-real" not in result
    assert "outside" in result.lower()


# ---- from a LangGraph node ----

def test_langgraph_node_reads_file_through_mcp(repo):
    from typing import TypedDict

    from langgraph.graph import END, START, StateGraph

    class State(TypedDict, total=False):
        path: str
        code: str

    async def load_code(state: State) -> State:
        tools = {t.name: t for t in await mcp_client(repo).get_tools()}
        return {"code": str(await tools["read_file"].ainvoke({"path": state["path"]}))}

    graph = StateGraph(State)
    graph.add_node("load_code", load_code)
    graph.add_edge(START, "load_code")
    graph.add_edge("load_code", END)

    final = asyncio.run(graph.compile().ainvoke({"path": "pkg/calc.py"}))

    assert "def add" in final["code"]
