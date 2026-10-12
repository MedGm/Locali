"""Run pytest on untrusted code inside a locked-down Docker container."""

import hashlib
import json
import shutil
import subprocess
import tempfile
import time
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

DOCKERFILE = Path(__file__).with_name("sandbox.Dockerfile")
# Tag by Dockerfile content so any change to the image definition forces a rebuild.
IMAGE = f"locali-sandbox:{hashlib.sha256(DOCKERFILE.read_bytes()).hexdigest()[:12]}"


@dataclass
class SandboxResult:
    exit_code: int | None
    timed_out: bool
    passed: int
    failed: int
    errors: int
    coverage_percent: float | None
    output: str
    duration_s: float
    passed_tests: list[str] = field(default_factory=list)  # pytest node ids
    container: str = ""  # docker container name of this run


def ensure_image() -> None:
    exists = subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True, check=False)
    if exists.returncode != 0:
        subprocess.run(
            ["docker", "build", "-t", IMAGE, "-f", str(DOCKERFILE), str(DOCKERFILE.parent)],
            check=True, capture_output=True,
        )


def run_pytest(
    project: Path,
    *,
    timeout_s: float = 60,
    memory: str = "512m",
    pids: int = 128,
    cpus: str = "1",
    coverage: bool | str = True,
    select: list[str] | None = None,
) -> SandboxResult:
    """coverage: False, True (whole project, lines), or a module name (that module, lines + branches).
    select: pytest node ids to run instead of the whole project.
    """
    ensure_image()
    name = f"locali-sbx-{uuid.uuid4().hex[:12]}"
    with tempfile.TemporaryDirectory(prefix="locali-sbx-") as tmp:
        work = Path(tmp) / "work"
        out = Path(tmp) / "out"
        shutil.copytree(project, work)
        # Temp dirs are 0700; the container user (nobody) needs read access to the copy
        # (still mounted read-only) and write access to the report directory only.
        Path(tmp).chmod(0o755)
        for path in [work, *work.rglob("*")]:
            path.chmod(0o755 if path.is_dir() else 0o644)
        out.mkdir()
        out.chmod(0o777)
        cmd = [
            "docker", "run", "--rm", "--name", name, "--label", "locali.sandbox=1",
            "--network", "none",
            "--memory", memory, "--memory-swap", memory,
            "--pids-limit", str(pids), "--cpus", cpus,
            "--read-only", "--tmpfs", "/tmp:rw,size=64m",
            "--user", "65534:65534",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "-e", "COVERAGE_FILE=/tmp/.coverage",
            "-v", f"{work}:/work:ro",
            "-v", f"{out}:/out:rw",
            "-w", "/work",
            IMAGE,
            "python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "--junitxml=/out/junit.xml",
        ]
        if isinstance(coverage, str):
            cmd += [f"--cov={coverage}", "--cov-branch", "--cov-report=json:/out/coverage.json"]
        elif coverage:
            cmd += ["--cov=.", "--cov-report=json:/out/coverage.json"]
        cmd += select or []
        start = time.perf_counter()
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, check=False)
            exit_code, output, timed_out = proc.returncode, proc.stdout + proc.stderr, False
        except subprocess.TimeoutExpired as e:
            # Killing the docker CLI does not stop the container; remove it explicitly.
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, check=False)
            exit_code, timed_out = None, True
            output = _text(e.stdout) + _text(e.stderr)
        duration = time.perf_counter() - start
        passed, failed, errors = _junit_counts(out / "junit.xml")
        passed_tests = _junit_passed_node_ids(out / "junit.xml", work)
        return SandboxResult(
            exit_code=exit_code,
            timed_out=timed_out,
            passed=passed,
            failed=failed,
            errors=errors,
            coverage_percent=_coverage_percent(out / "coverage.json"),
            output=output,
            duration_s=round(duration, 2),
            passed_tests=passed_tests,
            container=name,
        )


def _text(data: bytes | str | None) -> str:
    if isinstance(data, bytes):
        return data.decode(errors="replace")
    return data or ""


def _junit_counts(path: Path) -> tuple[int, int, int]:
    if not path.exists():
        return 0, 0, 0
    root = ET.parse(path).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    tests, failures = int(suite.get("tests", 0)), int(suite.get("failures", 0))
    errors, skipped = int(suite.get("errors", 0)), int(suite.get("skipped", 0))
    return tests - failures - errors - skipped, failures, errors


def _junit_passed_node_ids(path: Path, work: Path) -> list[str]:
    """Rebuild pytest node ids (file.py::Class::test[param]) of passing test cases."""
    if not path.exists():
        return []
    ids = []
    for case in ET.parse(path).getroot().iter("testcase"):
        if any(case.find(tag) is not None for tag in ("failure", "error", "skipped")):
            continue
        parts = case.get("classname", "").split(".")
        for k in range(len(parts), 0, -1):
            module = Path(*parts[:k]).with_suffix(".py")
            if (work / module).exists():
                ids.append("::".join([module.as_posix(), *parts[k:], case.get("name", "")]))
                break
    return ids


def _coverage_percent(path: Path) -> float | None:
    if not path.exists():
        return None
    return round(json.loads(path.read_text())["totals"]["percent_covered"], 1)
