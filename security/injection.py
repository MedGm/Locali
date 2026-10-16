"""Prompt-injection detector: text in a repository that talks to AI tools instead of people.

An extra layer, not the defence. The agents never act on what the model says beyond parsing it into
findings or code, every change is validated and needs a human approval, and README or issue text
is never sent to the model at all. This scan makes an attempt visible: it reports lines that
address an assistant, try to override its instructions, claim an approval that did not happen, ask
to skip review, pipe a download into a shell or ask for secrets.

Line based and deliberately narrow, so ordinary comments and docs stay quiet. Findings are medium
severity: they are reported, they do not block a pull request on their own.
"""

import re
from pathlib import Path

from backend.agents.files import SKIP_DIRS
from backend.analysis import Finding

SUFFIXES = {".py", ".md", ".txt", ".rst", ".html", ".cfg", ".toml", ".yml", ".yaml"}

RULES = {  # rule: (description, alternatives)
    "injection.addresses-ai": ("addresses an AI tool directly", [
        (r"\b(note|message|instructions?|attention)\s+(for|to)\s+(the\s+)?"
         r"(automated|ai\b|llms?\b|language models?|assistants?|code review|copilot)"),
        r"\b(ai|llm|assistant|copilot)(\s+(reviewer|tool|assistant))?s?\s*[,:]\s*(you|please|do|report|ignore|this)\b",
    ]),
    "injection.override": ("tries to override the model's instructions", [
        (r"\b(ignore|disregard|forget)\s+(all\s+|any\s+|the\s+)?(previous|prior|above|earlier|your)\s+"
         r"(instructions|rules|prompts?|guidelines)"),
        r"\byou are now\b",
        r"\b(developer|dan|jailbreak)\s+mode\b",
    ]),
    "injection.fake-authority": ("claims to come from the system or a maintainer", [
        r"^\W*(system|admin|administrator|developer|maintainer)(\s+(message|note|override))?\s*:",
        r"\b(maintainer|admin|owner)s?\s+(has\s+|have\s+)?(approved|authori[sz]ed)\s+(automatic|auto|the assistant|ai)\b",
    ]),
    "injection.skip-review": ("asks to skip review or to report nothing", [
        r"\b(skip|bypass)\s+(the\s+)?(human\s+)?(approval|review|tests?|validation)\b",
        r"\bwithout\s+(human\s+)?(approval|review)\b",
        r"\breport\s+(that\s+)?(no|zero)\s+(issues|findings|problems|vulnerabilities|bugs)\b",
        r"\b(already|was|been)\s+audited\b",
    ]),
    "injection.pipe-to-shell": ("pipes a download into a shell", [
        r"\b(curl|wget)\b[^\n|]*\|\s*(sudo\s+)?(ba|z)?sh\b",
        r"\brm\s+-rf\s+(/|~|\$HOME)",
    ]),
    "injection.exfiltration": ("asks for secrets or file contents to be sent or shown", [
        (r"\b(include|paste|send|post|upload|leak|reveal|exfiltrate|email)\b.{0,30}"
         r"(contents? of|secrets?|api[ _-]?keys?|credentials|passwords|private keys?|\.env\b|settings\.py)"),
    ]),
}
_COMPILED = {rule: (desc, re.compile("|".join(alts), re.IGNORECASE)) for rule, (desc, alts) in RULES.items()}


def _files(root: Path) -> list[Path]:
    return [p for p in sorted(root.rglob("*"))
            if p.is_file() and p.suffix.lower() in SUFFIXES and not SKIP_DIRS & set(p.relative_to(root).parts)]


def scan(root: str | Path) -> list[Finding]:
    root = Path(root).resolve()
    found = []
    for path in _files(root):
        try:
            lines = path.read_text().splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        rel = path.relative_to(root).as_posix()
        for n, line in enumerate(lines, start=1):
            for rule, (desc, pattern) in _COMPILED.items():
                if pattern.search(line):
                    excerpt = line.strip()[:100]
                    found.append(Finding("injection", rule, rel, n, "security", "medium", f"{desc}: {excerpt}"))
    return found
