"""Read-only MCP server exposing one repository root.

Least privilege: two tools, no write access, and every path is resolved (following
symlinks) and must stay inside the root.

    python -m mcp_servers.repo_server --root /path/to/repo
"""

import argparse
from pathlib import Path

from mcp.server.fastmcp import FastMCP

MAX_BYTES = 200_000
SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules"}


def _confine(root: Path, path: str) -> Path:
    base = root.resolve()
    target = (base / path).resolve()
    if not target.is_relative_to(base):
        raise PermissionError(f"path is outside the repository root: {path}")
    return target


def list_files(root: Path) -> list[str]:
    base = root.resolve()
    files = []
    for p in base.rglob("*"):
        rel = p.relative_to(base)
        if any(part in SKIP_DIRS for part in rel.parts) or not p.is_file():
            continue
        if p.resolve().is_relative_to(base):
            files.append(rel.as_posix())
    return sorted(files)


def read_file(root: Path, path: str) -> str:
    target = _confine(root, path)
    if not target.is_file():
        raise FileNotFoundError(f"no such file in repository: {path}")
    if target.stat().st_size > MAX_BYTES:
        raise ValueError(f"file larger than {MAX_BYTES} bytes: {path}")
    return target.read_text(errors="replace")


def build_server(root: Path) -> FastMCP:
    server = FastMCP("locali-repo")

    @server.tool(name="list_files", description="List files in the repository (relative paths).")
    def list_files_tool() -> list[str]:
        return list_files(root)

    @server.tool(name="read_file", description="Read a text file by path relative to the repository root.")
    def read_file_tool(path: str) -> str:
        return read_file(root, path)

    return server


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    build_server(args.root).run(transport="stdio")


if __name__ == "__main__":
    main()
