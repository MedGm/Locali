"""Examples from bigcode/self-oss-instruct-sc2-exec-filter-50k (ODC-BY; written by StarCoder2-15B,
responses execution-validated by its authors).

Rows with an even id feed the replay set (general instruction following, against forgetting);
odd ids feed T3 review items labelled by Bandit/Ruff. The two never share a row.
"""

import ast
import random
from concurrent.futures import ThreadPoolExecutor

from evaluation.extract import extract_code
from training.data.t3_review import tool_findings

SELF_OSS = ("bigcode/self-oss-instruct-sc2-exec-filter-50k", "356bb069eee815daa6e23e9a282eeefe1490ad44")
LICENSE = "ODC-BY"
MAX_LINES = 60


def _rows(rows, parity: int, seed: int):
    selected = [r for r in rows if int(r["id"]) % 2 == parity]  # by row id: stable across subsets
    random.Random(f"{seed}-{parity}").shuffle(selected)
    return selected


def replay_examples(rows, n: int, seed: int = 3407) -> list[dict]:
    out = []
    for r in _rows(rows, 0, seed)[:n]:
        out.append({
            "id": f"replay-{r['id']}", "task": "replay", "group": f"self-oss:{r['id']}",
            "source": f"{SELF_OSS[0]}:{r['id']}", "license": LICENSE,
            "messages": [{"role": "user", "content": r["instruction"]},
                         {"role": "assistant", "content": r["response"]}],
        })
    return out


def _candidate(row):
    code = extract_code(row["response"])
    if code.count("\n") + 1 > MAX_LINES:
        return None
    try:
        ast.parse(code)
    except SyntaxError:
        return None
    return row, code, tool_findings(code)


def review_items(rows, n_security: int, n_quality: int, n_clean: int, seed: int = 3407, workers: int = 4) -> list[dict]:
    """Balanced T3 items: code with security findings, with only quality findings, with none."""
    quota = {"security": n_security, "quality": n_quality, "clean": n_clean}
    items: list[dict] = []
    candidates = _rows(rows, 1, seed)
    batch = max(64, 4 * sum(quota.values()))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for start in range(0, len(candidates), batch):
            for result in pool.map(_candidate, candidates[start : start + batch]):
                if result is None:
                    continue
                row, code, findings = result
                categories = {f["category"] for f in findings}
                kind = "security" if "security" in categories else "quality" if findings else "clean"
                if quota[kind] > 0:
                    quota[kind] -= 1
                    items.append({
                        "id": f"t3-self-oss-{row['id']}", "task": "T3", "kind": kind,
                        "group": f"self-oss:{row['id']}", "source": f"{SELF_OSS[0]}:{row['id']}",
                        "license": LICENSE, "code": code, "findings": findings,
                    })
            if not any(quota.values()):
                break
    return items
