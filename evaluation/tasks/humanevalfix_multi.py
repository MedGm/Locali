"""HumanEvalFix in JavaScript, Java, Go, C++ and Rust: does the Python fine-tune help or hurt there?

Same prompt as the Python task (evaluation/tasks/humanevalpack.py), with the language's code fence.
The answers are compiled and run with each language's own toolchain, following the conventions of
the HumanEvalPack harness:

- js: Node; console.assert only prints, so failed asserts are turned into errors
- java: one Main.java (imports moved to the top, the test's Main class, then Solution), run with the
  single-file launcher so compiling and running use the same JDK
- go: one main_test.go (package, test imports, the problem's imports, code, test) in a module with
  testify; the problem's import list is used, because Go rejects unused or repeated imports
- cpp: g++ with the problem's includes, the answer (any main() of its own removed) and the test,
  linked with OpenSSL (Boost headers needed for two problems). CPP/38's declaration already holds
  part of the body, so declaration + reference does not compile; answers are not affected, since
  only the declaration's #include lines are used
- rust: a library crate with rand, regex and md5, built and run with cargo test

This runs model-written code outside the Docker sandbox, which no other experiment does. It is meant
for a disposable Kaggle VM (training/kaggle/multilang), with a timeout per program.
"""

import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from evaluation.tasks.humanevalpack import HUMANEVALPACK

LANGUAGES = {"js": "javascript", "java": "java", "go": "go", "cpp": "cpp", "rust": "rust"}
FENCE = re.compile(r"```[\w+-]*[ \t]*\n(.*?)```", re.DOTALL)
JS_ASSERT = 'console.assert = (ok, ...msg) => { if (!ok) { throw new Error("Assertion failed: " + msg.join(" ")) } };\n'
RUST_DEPS = '[dependencies]\nrand = "0.8"\nregex = "1"\nmd5 = "0.7"\n'


@dataclass
class Item:
    task_id: str
    language: str
    declaration: str
    canonical_solution: str
    buggy_solution: str
    bug_type: str
    entry_point: str
    imports: str
    test_setup: str
    test: str


def load(language: str, limit: int | None = None) -> list[Item]:
    from datasets import load_dataset

    repo, revision = HUMANEVALPACK
    rows = load_dataset(repo, language, revision=revision, split="test")
    if limit:
        rows = rows.select(range(min(limit, len(rows))))
    return [Item(r["task_id"], language, r["declaration"], r["canonical_solution"], r["buggy_solution"],
                 r["bug_type"], r["entry_point"], r["import"], r["test_setup"], r["test"]) for r in rows]


def messages(item: Item) -> list[dict]:
    fence = LANGUAGES[item.language]
    content = (
        f"Fix bugs in {item.entry_point}.\n\n"
        f"```{fence}\n{item.imports}{item.declaration}{item.buggy_solution}```\n\n"
        f"These tests fail:\n```{fence}\n{item.test.strip()}\n```\n\n"
        "Return the complete fixed function in a markdown code block."
    )
    return [{"role": "user", "content": content}]


def extract(text: str) -> str:
    """The first fenced block of the answer, else the whole answer."""
    m = FENCE.search(text)
    return m.group(1) if m else text


def reference_answer(item: Item, solution: str) -> str:
    fence = LANGUAGES[item.language]
    return f"```{fence}\n{item.declaration}{solution}```"


def _without_main(code: str, pattern: str) -> str:
    m = re.search(pattern, code)
    return code[: m.start()] if m else code


def program(item: Item, code: str) -> dict[str, str]:
    """Files to write for one answer, by name."""
    lang = item.language
    if lang == "js":
        return {"main.js": JS_ASSERT + code + "\n\n" + item.test}
    if lang == "cpp":
        includes = "\n".join(line for line in item.declaration.splitlines() if line.startswith(("#include", "using ")))
        body = _without_main(code, r"\bint\s+main\s*\(")
        return {"main.cpp": f"{includes}\n{body}\n{item.test}"}
    if lang == "java":
        imports = {line.strip() for line in (item.declaration + "\n" + code).splitlines() if line.strip().startswith("import ")}
        body = "\n".join(line for line in code.splitlines() if not line.strip().startswith("import "))
        if not re.search(r"\bclass\s+Solution\b", body):
            body = f"class Solution {{\n{body}\n}}"
        body = re.sub(r"\bpublic\s+class\s+Solution\b", "class Solution", body)
        # the source launcher (java Main.java) runs the first class of the file, so the test's Main goes first
        return {"Main.java": "\n".join(sorted(imports)) + "\n\n" + item.test + "\n\n" + body}
    if lang == "go":
        body = "\n".join(line for line in code.splitlines() if not line.startswith("package "))
        body = re.sub(r"^import\s*\([^)]*\)\s*$|^import\s+\"[^\"]+\"\s*$", "", body, flags=re.MULTILINE)
        return {"main_test.go": f"{item.test_setup}\n{item.imports}\n{body}\n\n{item.test}"}
    if lang == "rust":
        uses = "\n".join(line for line in item.declaration.splitlines() if line.strip().startswith("use "))
        return {"src/lib.rs": f"#![allow(unused, deprecated)]\n{uses}\n\n{code}\n\n{item.test}"}
    raise ValueError(lang)


class Runner:
    """Compiles and runs programs for one language, in a scratch folder prepared once."""

    def __init__(self, language: str, timeout_s: float = 20):
        self.language, self.timeout_s = language, timeout_s
        self.base = Path(tempfile.mkdtemp(prefix=f"humanevalfix-{language}-"))
        if language == "js":  # one problem uses the js-md5 package
            self._sh(["npm", "install", "--silent", "--no-audit", "--no-fund", "js-md5@0.8.3"], self.base, timeout=600)
        if language == "go":
            self._sh(["go", "mod", "init", "humanevalfix"], self.base)
            self._sh(["go", "get", "github.com/stretchr/testify/assert@v1.9.0"], self.base, timeout=600)
        if language == "rust":
            (self.base / "Cargo.toml").write_text('[package]\nname = "humanevalfix"\nversion = "0.1.0"\nedition = "2021"\n\n'
                                                  + RUST_DEPS)
            (self.base / "src").mkdir()
            (self.base / "src" / "lib.rs").write_text("")
            self._sh(["cargo", "test", "--quiet", "--no-run"], self.base, timeout=1200)  # builds the crates once

    def _sh(self, cmd: list[str], cwd: Path, timeout: float | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout or self.timeout_s,
                              check=False)

    def run(self, files: dict[str, str]) -> dict:
        start = time.perf_counter()
        work = self.base if self.language in ("go", "rust") else Path(tempfile.mkdtemp(dir=self.base))
        for name, text in files.items():
            (work / name).parent.mkdir(parents=True, exist_ok=True)
            (work / name).write_text(text)
        try:
            steps = {
                "js": [["node", "main.js"]],
                "cpp": [["g++", "-std=c++17", "-O0", "-o", "main", "main.cpp", "-lcrypto"], ["./main"]],
                "java": [["java", "Main.java"]],  # compiles and runs with one JDK
                "go": [["go", "test", "-count=1", "./..."]],
                "rust": [["cargo", "test", "--quiet", "--offline"]],
            }[self.language]
            for i, cmd in enumerate(steps):
                timeout = self.timeout_s * (6 if self.language == "rust" or (len(steps) > 1 and i == 0) else 1)
                done = self._sh(cmd, work, timeout)
                if done.returncode != 0:
                    stage = "compile" if len(steps) > 1 and i == 0 or self.language in ("go", "rust") else "run"
                    return {"passed": False, "status": f"failed ({stage})", "stderr": done.stderr[-2000:],
                            "seconds": round(time.perf_counter() - start, 2)}
            return {"passed": True, "status": "passed", "stderr": "", "seconds": round(time.perf_counter() - start, 2)}
        except subprocess.TimeoutExpired:
            return {"passed": False, "status": "timeout", "stderr": "", "seconds": round(time.perf_counter() - start, 2)}
        finally:
            if work is not self.base:
                shutil.rmtree(work, ignore_errors=True)
            else:
                for name in files:
                    (work / name).unlink(missing_ok=True)

    def close(self) -> None:
        shutil.rmtree(self.base, ignore_errors=True)
