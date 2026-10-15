from backend.agents.scoring import score_run

KEY = {"flaws": [
    {"id": "bug-a", "kind": "bug", "file": "m.py", "line": 3},
    {"id": "bug-b", "kind": "bug", "file": "m.py", "line": 9},
    {"id": "bug-c", "kind": "bug", "file": "m.py", "line": 14},
    {"id": "vuln", "kind": "security", "file": "db.py", "line": 5},
    {"id": "key", "kind": "secret", "file": "settings.py", "line": 2},
]}
FUNCTIONS = {("m.py", 3): "a", ("m.py", 9): "b", ("m.py", 14): "c"}


def test_score_counts_hits_by_line_and_category_and_false_positives_by_source():
    state = {
        "findings": [
            {"tool": "model", "path": "m.py", "line": 3, "category": "bug"},
            {"tool": "model", "path": "m.py", "line": 9, "category": "quality"},  # right line, wrong reason
            {"tool": "bandit", "path": "db.py", "line": 5, "category": "security"},
            {"tool": "secrets", "path": "settings.py", "line": 3, "category": "security"},
            {"tool": "model", "path": "db.py", "line": 1, "category": "security"},
            {"tool": "ruff", "path": "m.py", "line": 20, "category": "quality"},
        ],
        "suspects": [{"file": "m.py", "function": "c"}],
        "fixes": [{"file": "m.py", "function": "b", "fixed": True}],
    }
    s = score_run(state, KEY, FUNCTIONS)
    assert s["bugs"] == {"bug-a": "found", "bug-b": "fixed", "bug-c": "suspected"}
    assert s["security"] == {"vuln": True} and s["secrets"] == {"key": True}
    assert s["false_positives"] == {"model": 2, "ruff": 1}
