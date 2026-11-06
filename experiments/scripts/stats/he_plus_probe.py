"""HumanEval+ answers of several runs, probed input by input (step 1 of the capability study).

For every chosen problem and run: does the answer pass the original HumanEval tests
(bigcode/humanevalpack), and on which of the HumanEval+ inputs does it disagree with the reference
solution (wrong value, exception, or over 2 s)? Answers run in the evaluation sandbox.

    uv run python experiments/scripts/stats/he_plus_probe.py OUT.json HumanEval/97 ... -- name=samples.jsonl ...
"""

import ast
import json
import re
import sys
from pathlib import Path

from datasets import load_dataset

from evaluation.tasks.codegen import HUMANEVAL_PLUS, _prompt_imports, run_program

HUMANEVALPACK = ("bigcode/humanevalpack", "9a41762f73a8cb23bb5811b73d5aab164efcf378")
MARK = "PROBE-RESULT:"

HARNESS = r'''
import json, signal, sys

sys.set_int_max_str_digits(0)

def _alarm(*_):
    raise TimeoutError("over 2 s")

signal.signal(signal.SIGALRM, _alarm)
_ref = {}
exec(compile(REF, "reference.py", "exec"), _ref)
_report = {"n": len(INPUTS), "wrong": 0, "exception": 0, "timeout": 0, "examples": []}
for _args in INPUTS:
    _exp = _ref[ENTRY](*_args)
    signal.alarm(2)
    try:
        _out = globals()[ENTRY](*_args)
        _ok = _out == _exp or (isinstance(_exp, float) and isinstance(_out, (int, float)) and abs(_out - _exp) < 1e-6)
        _got, _kind = repr(_out)[:60], "wrong"
    except BaseException as _e:
        _ok, _got = False, type(_e).__name__
        _kind = "timeout" if isinstance(_e, TimeoutError) else "exception"
    finally:
        signal.alarm(0)
    if not _ok:
        _report[_kind] += 1
        if len(_report["examples"]) < 3:
            _report["examples"].append({"args": repr(_args)[:80], "expected": repr(_exp)[:40], "got": _got})
raise AssertionError("PROBE-RESULT:" + json.dumps(_report))
'''


def plus_inputs(test: str) -> str:
    for node in ast.walk(ast.parse(test)):
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == "inputs":
            return ast.get_source_segment(test, node.value)
    raise ValueError("no inputs list")


def main() -> None:
    out, rest = Path(sys.argv[1]), sys.argv[2:]
    split = rest.index("--")
    ids, runs = rest[:split], dict(a.split("=", 1) for a in rest[split + 1:])
    plus = {r["task_id"]: r for r in load_dataset(HUMANEVAL_PLUS[0], revision=HUMANEVAL_PLUS[1], split="test")}
    pack = {r["task_id"].replace("Python/", "HumanEval/"): r
            for r in load_dataset(*HUMANEVALPACK[:1], "python", revision=HUMANEVALPACK[1], split="test")}
    answers = {name: {json.loads(l)["task_id"]: json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()}
               for name, p in runs.items()}
    report = {}
    for tid in ids:
        p, entry = plus[tid], plus[tid]["entry_point"]
        imports = _prompt_imports(p["prompt"])
        report[tid] = {}
        for name, by_id in answers.items():
            code = by_id[tid]["code"]
            original = run_program(f"{imports}\n\n{code}\n\n{pack[tid]['test']}\n", timeout_s=30)
            program = (f"{imports}\n\n{code}\n\nREF = {(imports + chr(10) + p['prompt'] + p['canonical_solution'])!r}\n"
                       f"ENTRY = {entry!r}\nINPUTS = {plus_inputs(p['test'])}\n{HARNESS}")
            probe = run_program(program, timeout_s=120)
            found = re.search(re.escape(MARK) + r"(\{.*\})", probe.detail)
            result = json.loads(found.group(1)) if found else {"error": probe.status, "detail": probe.detail[-300:]}
            report[tid][name] = {"original_tests": original.status, "plus": result, "code": code}
            counts = f"{result['wrong']} wrong, {result['exception']} exc, {result['timeout']} slow" if "n" in result else "?"
            print(f"{tid:14} {name:5} original {original.status:7} plus {result.get('n', '?')} inputs: {counts}", flush=True)
    out.write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
