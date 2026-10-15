"""Score a workflow run against the planted-flaw answer key (security/demo_repo_flaws.json).

A finding counts only on the planted line *and* in the matching category: a finding on the right
line for the wrong reason is a false positive. Bugs are graded fixed > found > suspected > missed;
secrets match by file, because a secret spans several lines.
"""

from collections import Counter

CATEGORY = {"bug": "bug", "security": "security"}


def score_run(state: dict, key: dict, functions: dict[tuple[str, int], str]) -> dict:
    """functions maps each planted bug's (file, line) to the function that contains it."""
    flaws = key["flaws"]
    secret_files = {f["file"] for f in flaws if f["kind"] == "secret"}
    hits = {(f["file"], f["line"], CATEGORY[f["kind"]]) for f in flaws if f["kind"] in CATEGORY}

    false_positives: Counter = Counter()
    found: set[tuple[str, int, str]] = set()
    for f in state["findings"]:
        k = (f["path"], f["line"], f["category"])
        if k in hits:
            found.add(k)
        elif not (f["tool"] == "secrets" and f["path"] in secret_files):
            false_positives[f["tool"]] += 1

    fixed = {(f["file"], f["function"]) for f in state.get("fixes", []) if f["fixed"]}
    suspected = {(s["file"], s["function"]) for s in state.get("suspects", [])}
    bugs = {}
    for f in (f for f in flaws if f["kind"] == "bug"):
        fn = (f["file"], functions.get((f["file"], f["line"])))
        bugs[f["id"]] = ("fixed" if fn in fixed else "found" if (f["file"], f["line"], "bug") in found
                         else "suspected" if fn in suspected else "missed")
    secret_hits = {f["path"] for f in state["findings"] if f["tool"] == "secrets"}
    return {
        "bugs": bugs,
        "security": {f["id"]: (f["file"], f["line"], "security") in found for f in flaws if f["kind"] == "security"},
        "secrets": {f["id"]: f["file"] in secret_hits for f in flaws if f["kind"] == "secret"},
        "false_positives": dict(false_positives),
    }
