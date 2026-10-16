"""DevOps step: is the repository ready to merge, are its dependencies safe, does it have CI.

No model here, everything is deterministic and comes from the earlier steps plus two checks:

- dependencies: names in requirements*.txt and pyproject.toml that are one edit away from a popular
  package but are not that package (reqeusts, flsk). This is the typosquatting attack (S6); a
  real check would ask the package index, this one works offline.
- CI: which GitHub workflows the repository has. When there is none, or no Locali review job, the
  summary includes a workflow to start from.
"""

import re
import tomllib
from pathlib import Path

POPULAR = {
    "accelerate", "aiohttp", "arrow", "attrs", "beautifulsoup4", "black", "boto", "boto3", "botocore",
    "celery", "certifi", "charset-normalizer", "click", "colorama", "coverage", "cryptography", "dash", "dask",
    "datasets", "django", "docker", "fastapi", "flake8", "flask", "grpcio", "gunicorn", "httpx",
    "huggingface-hub", "idna", "isort", "jinja2", "jsonschema", "keras", "langchain", "lxml", "markupsafe",
    "matplotlib", "mock", "mypy", "networkx", "numpy", "openai", "opencv-python", "packaging", "pandas",
    "paramiko", "pillow", "pip", "plotly", "protobuf", "psycopg2", "pydantic", "pyjwt", "pylint",
    "polars", "pyarrow", "pymongo", "pyopenssl", "pyparsing", "pytest", "pytest-cov", "python-dateutil", "python-dotenv",
    "pytz", "pyyaml", "redis", "regex", "requests", "rich", "ruff", "scikit-learn", "scipy", "seaborn", "selenium",
    "setuptools", "simplejson", "six", "sqlalchemy", "streamlit", "sympy", "tensorflow", "tiktoken",
    "toml", "tomli", "torch", "tornado", "tox", "tqdm", "transformers", "typer", "urllib3", "uvicorn", "virtualenv",
    "websocket-client", "werkzeug", "wheel", "xmltodict",
}
_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")

SUGGESTED_WORKFLOW = """\
name: CI

on:
  push:
  pull_request:

jobs:
  tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt pytest-cov
      - run: pytest --cov --cov-report=term

  locali-review:
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: actions/checkout@v4
        with:
          repository: MedGm/Locali
          path: .locali
      - uses: astral-sh/setup-uv@v6
      - run: uv sync --frozen --project .locali
      - run: uv run --project .locali python -m backend.pr_review --repo . --base "${{ github.event.pull_request.base.sha }}" --head "${{ github.event.pull_request.head.sha }}" --out comment.md
"""


def _normal(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _distance(a: str, b: str) -> int:
    """Edit distance where swapping two neighbouring letters counts as one edit."""
    d = [[i + j if i * j == 0 else 0 for j in range(len(b) + 1)] for i in range(len(a) + 1)]
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] != b[j - 1]))
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[-1][-1]


def _declared(root: Path) -> list[tuple[str, str]]:
    """(file, package name) for every dependency the repository declares."""
    found = []
    for req in sorted(root.glob("requirements*.txt")):
        for line in req.read_text().splitlines():
            m = _NAME.match(line.split("#")[0])
            if m and not line.lstrip().startswith("-"):
                found.append((req.name, m.group(1)))
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            deps = tomllib.loads(pyproject.read_text()).get("project", {}).get("dependencies", [])
        except tomllib.TOMLDecodeError:
            deps = []
        found += [("pyproject.toml", m.group(1)) for d in deps if (m := _NAME.match(d))]
    return found


def dependency_risks(root: Path) -> list[dict]:
    risks = []
    for file, name in _declared(Path(root)):
        norm = _normal(name)
        if norm in POPULAR or len(norm) < 4:
            continue
        close = sorted(p for p in POPULAR if len(p) >= 4 and _distance(norm, p) == 1)
        if close:
            risks.append({"file": file, "name": name, "looks_like": close[0]})
    return risks


def ci_status(root: Path) -> dict:
    folder = Path(root) / ".github" / "workflows"
    files = sorted(p for p in folder.glob("*") if p.suffix in (".yml", ".yaml")) if folder.is_dir() else []
    return {"has_ci": bool(files), "has_locali_review": any("pr_review" in p.read_text() for p in files),
            "workflows": [p.name for p in files]}


def devops_summary(root: Path, state: dict, tests_before: dict | None) -> dict:
    findings = state.get("findings", [])
    tool_findings = [f for f in findings if f["tool"] != "model"]
    secrets = [f for f in tool_findings if f["tool"] == "secrets"]
    high = [f for f in tool_findings if f["category"] == "security" and f["severity"] == "high"
            and f["tool"] != "secrets"]
    risks = dependency_risks(root)
    ci = ci_status(root)

    blockers = []
    if secrets:
        blockers.append(f"{len(secrets)} hard-coded secret(s): " + ", ".join(f"{f['path']}:{f['line']}" for f in secrets))
    if high:
        blockers.append(f"{len(high)} high-severity security finding(s) from the static tools")
    blockers += [f"{r['file']}: {r['name']} looks like {r['looks_like']} (possible typosquat)" for r in risks]
    failed = (tests_before or {}).get("failed", [])
    if failed:
        blockers.append(f"{len(failed)} test(s) fail on the current code")

    warnings = []
    if state.get("suspects"):
        warnings.append(f"{len(state['suspects'])} suspected bug(s) from generated tests, not confirmed")
    bad = [p for p in state.get("patches", []) if not p["ok"]]
    if bad:
        warnings.append(f"{len(bad)} proposed patch(es) failed validation")
    coverage = (tests_before or {}).get("coverage_percent")
    if coverage is not None and coverage < 60:
        warnings.append(f"test coverage is {coverage:.0f}%")
    if not ci["has_ci"]:
        warnings.append("no CI workflow")
    elif not ci["has_locali_review"]:
        warnings.append("CI does not run a security review on pull requests")

    suggestion = None if ci["has_ci"] and ci["has_locali_review"] else SUGGESTED_WORKFLOW
    ready = not blockers
    lines = ["## DevOps summary", "", f"Merge readiness: {'ready' if ready else 'not ready'}", "",
             "Blockers:", ""] + ([f"- {b}" for b in blockers] or ["- none"])
    lines += ["", "Warnings:", ""] + ([f"- {w}" for w in warnings] or ["- none"])
    if tests_before:
        lines += ["", f"Tests on the current code: {tests_before.get('passed', 0)} passed, {len(failed)} failed"
                  + (f", coverage {coverage:.1f}%" if coverage is not None else "")]
    lines += ["", f"CI workflows: {', '.join(ci['workflows']) or 'none'}"]
    if suggestion:
        lines += ["", "Suggested workflow (.github/workflows/ci.yml):", "", "```yaml", suggestion.rstrip(), "```"]
    return {"ready_to_merge": ready, "blockers": blockers, "warnings": warnings, "dependencies": risks,
            "ci": ci, "suggested_workflow": suggestion, "markdown": "\n".join(lines) + "\n"}
