"""MCP server for static analysis (Ruff, Bandit, Radon, Semgrep, secret scan) of one repository.

    python -m mcp_servers.analysis_server --root /path/to/repo
"""

import argparse
from dataclasses import asdict
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from backend.analysis import analyze
from security.secrets import redact


def analyze_path(root: Path, path: str = ".") -> list[dict]:
    base = root.resolve()
    target = (base / path).resolve()
    if not target.is_relative_to(base):
        raise PermissionError(f"path is outside the repository root: {path}")
    prefix = target.relative_to(base).as_posix()
    findings = []
    for f in analyze(target):
        item = asdict(f)
        item["path"] = f.path if prefix == "." else f"{prefix}/{f.path}"
        item["message"] = redact(f.message)
        findings.append(item)
    return findings


def build_server(root: Path) -> FastMCP:
    server = FastMCP("locali-analysis")

    @server.tool(name="analyze", description="Static analysis of a folder (relative to the repository root): "
                                              "bugs, security issues, complexity and hardcoded secrets.")
    def analyze_tool(path: str = ".") -> list[dict]:
        return analyze_path(root, path)

    return server


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    build_server(args.root).run(transport="stdio")


if __name__ == "__main__":
    main()
