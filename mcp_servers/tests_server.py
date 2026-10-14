"""MCP server that runs a repository's tests in the Docker sandbox (no network, read-only, limits).

One tool. The repository root is fixed at start-up and selected tests must stay inside it.

    python -m mcp_servers.tests_server --root /path/to/repo
"""

import argparse
import re
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from security.sandbox import run_pytest
from security.secrets import redact

OUTPUT_TAIL = 3000
_FAILED = re.compile(r"^(?:FAILED|ERROR) (\S+?)(?: - |$)", re.MULTILINE)


def _check_selection(root: Path, select: list[str]) -> None:
    base = root.resolve()
    for node in select:
        if not (base / node.split("::")[0]).resolve().is_relative_to(base):
            raise PermissionError(f"test path is outside the repository root: {node}")


def run_tests(root: Path, select: list[str] | None = None, timeout_s: float = 120) -> dict:
    if select:
        _check_selection(root, select)
    result = run_pytest(root.resolve(), timeout_s=timeout_s, coverage=True, select=select or None)
    return {
        "passed": result.passed,
        "failed": sorted(set(_FAILED.findall(result.output))),
        "errors": result.errors,
        "timed_out": result.timed_out,
        "coverage_percent": result.coverage_percent,
        "output_tail": redact(result.output[-OUTPUT_TAIL:]),
    }


def build_server(root: Path) -> FastMCP:
    server = FastMCP("locali-tests")

    @server.tool(name="run_tests", description="Run the repository's pytest suite (or the given test ids) "
                                                "in an isolated sandbox; returns counts, failing tests and coverage.")
    def run_tests_tool(select: list[str] | None = None) -> dict:
        return run_tests(root, select)

    return server


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    build_server(args.root).run(transport="stdio")


if __name__ == "__main__":
    main()
