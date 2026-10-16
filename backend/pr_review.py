"""Review the changes between two commits, for pull requests (CI) or locally.

    uv run python -m backend.pr_review --base <sha> --head <sha> [--out comment.md]

Both commits are checked out into temporary worktrees (the current checkout is left alone) and run
through the static analysis. Only findings that are new in the changed files are reported; an
existing problem in an untouched file does not show up on every pull request. Secrets are looked
for in the added lines only, and never printed. The exit code is 1 when the change adds a
high-severity security finding or a secret, so the check can block a merge.

The model review is not part of this: CI runners have no model server. It stays a local feature.
"""

import argparse
import shutil
import sys
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from backend.analysis import analyze
from security.commands import run as run_command
from security.secrets import redact, scan_text


@dataclass
class Review:
    changed: list[str]
    new_findings: list[dict] = field(default_factory=list)
    secrets: list[str] = field(default_factory=list)
    blocking: bool = False
    markdown: str = ""


def _git(repo: Path, *args: str) -> str:
    return run_command(["git", "-C", str(repo), *args], check=True).stdout


def _findings(repo: Path, commit: str, files: set[str]) -> list[dict]:
    tmp = Path(tempfile.mkdtemp(prefix="locali-pr-"))
    try:
        _git(repo, "worktree", "add", "--detach", str(tmp / "wt"), commit)
        return [{**asdict(f), "message": redact(f.message)} for f in analyze(tmp / "wt")
                if f.path in files and f.tool != "secrets"]
    finally:
        run_command(["git", "-C", str(repo), "worktree", "remove", "--force", str(tmp / "wt")])
        shutil.rmtree(tmp, ignore_errors=True)


def _added_secrets(repo: Path, base: str, head: str, files: list[str]) -> list[str]:
    found = []
    for f in files:
        diff = _git(repo, "diff", base, head, "--", f)
        added = "\n".join(line[1:] for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++"))
        found += sorted({f"{f}: {s.rule}" for s in scan_text(added)})
    return found


def _markdown(r: Review) -> str:
    lines = ["### Locali review", ""]
    if not r.new_findings and not r.secrets:
        lines.append(f"No new findings in the {len(r.changed)} changed file(s).")
    else:
        verdict = "Blocking: this change adds a high-severity security issue or a secret." if r.blocking else \
            "Nothing blocking, but have a look."
        lines += [verdict, ""]
        if r.secrets:
            lines += ["**Secrets in added lines** (values not shown):", ""] + [f"- `{s}`" for s in r.secrets] + [""]
        if r.new_findings:
            lines += ["| Severity | Location | Rule | Message |", "|---|---|---|---|"]
            for f in r.new_findings:
                message = f["message"].replace("|", "\\|")
                lines.append(f"| {f['severity']} | `{f['path']}:{f['line']}` | {f['tool']} {f['rule']} | {message} |")
    lines += ["", ("<sub>Static analysis (Ruff, Bandit, Radon, Semgrep) and secret scan of the changed files. "
                   "The model review runs locally, not in CI.</sub>")]
    return "\n".join(lines) + "\n"


def review_range(repo: str | Path, base: str, head: str) -> Review:
    repo = Path(repo).resolve()
    changed = [f for f in _git(repo, "diff", "--name-only", "--diff-filter=ACMR", base, head).splitlines() if f]
    review = Review(changed=changed)
    if changed:
        files = set(changed)
        before = Counter((f["path"], f["tool"], f["rule"]) for f in _findings(repo, base, files))
        after = _findings(repo, head, files)
        counts = Counter((f["path"], f["tool"], f["rule"]) for f in after)
        new_keys = {k for k, n in counts.items() if n > before[k]}
        review.new_findings = [f for f in after if (f["path"], f["tool"], f["rule"]) in new_keys]
        review.secrets = _added_secrets(repo, base, head, changed)
    review.blocking = bool(review.secrets) or any(
        f["category"] == "security" and f["severity"] == "high" for f in review.new_findings)
    review.markdown = _markdown(review)
    return review


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    review = review_range(args.repo, args.base, args.head)
    if args.out:
        args.out.write_text(review.markdown)
    print(review.markdown)
    sys.exit(1 if review.blocking else 0)


if __name__ == "__main__":
    main()
