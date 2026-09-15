"""Run pytest on untrusted code inside a locked-down Docker container."""

import hashlib
import json
import shutil
import subprocess
import tempfile
import time
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
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
    coverage: bool = True,
) -> SandboxResult:
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
        if coverage:
            cmd += ["--cov=.", "--cov-report=json:/out/coverage.json"]
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
        return SandboxResult(
            exit_code=exit_code,
            timed_out=timed_out,
            passed=passed,
            failed=failed,
            errors=errors,
            coverage_percent=_coverage_percent(out / "coverage.json"),
            output=output,
            duration_s=round(duration, 2),
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


def _coverage_percent(path: Path) -> float | None:
    if not path.exists():
        return None
    return round(json.loads(path.read_text())["totals"]["percent_covered"], 1)
