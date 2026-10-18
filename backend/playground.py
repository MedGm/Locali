"""Playground: ask the model directly, with presets for the tasks it was trained on.

For Python, review, tests and fix use the exact prompt formats of the fine-tuning data (T3, T2, T1),
because that is where the model is measurably better. Other languages, explanations and free
prompts use plain instructions; the fine-tune was not trained or measured on them.
"""

import ast

from training.data.format import repair_prompt
from training.data.t3_review import review_prompt

LANGUAGES = {
    "python": ("Python", "pytest"),
    "javascript": ("JavaScript", "Jest"),
    "typescript": ("TypeScript", "Jest"),
    "java": ("Java", "JUnit 5"),
    "go": ("Go", "the testing package"),
    "csharp": ("C#", "xUnit"),
    "cpp": ("C++", "GoogleTest"),
    "rust": ("Rust", "#[test] functions"),
    "php": ("PHP", "PHPUnit"),
    "ruby": ("Ruby", "RSpec"),
    "other": ("", "the usual test framework for this language"),
}

TASKS = {
    "review": "Review code",
    "tests": "Write tests",
    "fix": "Fix a bug",
    "explain": "Explain code",
    "free": "Free prompt",
}


def _block(code: str, language: str) -> str:
    fence = language if language != "other" else ""
    return f"```{fence}\n{code.rstrip()}\n```"


def _first_function(code: str) -> str | None:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    return next((n.name for n in tree.body if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)), None)


def build_messages(task: str, language: str, *, code: str = "", prompt: str = "", test: str = "",
                   error: str = "") -> list[dict]:
    if task not in TASKS:
        raise ValueError(f"unknown task {task!r}")
    if language not in LANGUAGES:
        raise ValueError(f"unknown language {language!r}")
    name, framework = LANGUAGES[language]
    lang = f"{name} " if name else ""
    code, prompt = code.strip("\n"), prompt.strip()
    if task == "free":
        if not prompt:
            raise ValueError("write a prompt")
        content = prompt + (f"\n\n{_block(code, language)}" if code.strip() else "")
        return [{"role": "user", "content": content}]
    if not code.strip():
        raise ValueError("paste some code")

    python = language == "python"
    if task == "review":
        content = review_prompt(code) if python else (
            f"Review the following {lang}code for bugs, security issues and code-quality problems. For each "
            f"problem, quote the line, say what is wrong and how to fix it.\n\n{_block(code, language)}")
    elif task == "tests":
        entry = _first_function(code) if python else None
        if entry:
            from evaluation.tasks.testgen import testgen_prompt

            content = testgen_prompt(entry, code.rstrip() + "\n")
        else:
            content = (f"Write unit tests for the following {lang}code with {framework}. Cover normal cases and "
                       f"edge cases. Return a single test file in a code block.\n\n{_block(code, language)}")
    elif task == "fix":
        if python and test.strip() and error.strip():
            test_name = _first_function(test) or "test"
            content = repair_prompt(code, test_name, test, error)
        else:
            extra = f"\n\nA failing test:\n{_block(test, language)}" if test.strip() else ""
            extra += f"\n\nThe error:\n```\n{error.rstrip()}\n```" if error.strip() else ""
            content = (f"The following {lang}code has a bug. Find it, explain it in one or two sentences, and give "
                       f"the corrected code.\n\n{_block(code, language)}{extra}")
    else:
        content = (f"Explain what the following {lang}code does, step by step, for a developer who has not seen it "
                   f"before. Point out anything surprising or risky.\n\n{_block(code, language)}")
    if prompt and task != "free":
        content += f"\n\nAlso: {prompt}"
    return [{"role": "user", "content": content}]
