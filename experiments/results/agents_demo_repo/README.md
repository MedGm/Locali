# Agent workflow on demo_repo

The full workflow (`backend/agents/workflow.py`) runs on `demo_repo/` and is scored against the
planted-flaw answer key (`security/demo_repo_flaws.json`) with `experiments/scripts/agent_eval.py`.

## ft-q8-run1 (2026-10-15)

Model: the fine-tuned Qwen2.5-Coder-1.5B, Q8_0 GGUF, llama.cpp on the laptop CPU (4 threads),
greedy decoding. 40 model calls, 5,129 output tokens, 773 s in total, most of it review and test
generation.

| Planted flaw | Result | By |
|---|---|---|
| 5 vulnerabilities (SQL injection, MD5, pickle, shell, eval) | 5 / 5 found | Bandit + Semgrep (all five); the model also flagged MD5, pickle and shell |
| Hardcoded secrets | found | secret scanner |
| discount sign (the one bug a test caught) | **fixed** | debug agent, first attempt, one-line diff |
| mutable default argument | found | Ruff B006 |
| bulk discount boundary (`> 50` vs "from 50") | found | model review, with the right explanation |
| `total_units` skips the first product | suspected | three generated tests fail with e.g. `total_units([[1, 5]]) == 0` |
| restock boundary (`<` vs "at or below") | missed | the scorer marks it "suspected", but the failing generated test expected `needs_restock(6)` to be True, which is wrong. A lucky hit, not a find |

False positives: 17, all from the model's review (14 quality, mostly Ruff-style messages that don't
apply, and several SQL-injection warnings on queries that are already parameterised). The static
tools produced none on this repository.

The run ended with one patch: the discount fix plus 6 new regression-test files. It passed
validation (all tests pass in the sandbox, no new Bandit/Semgrep findings, no secrets) and is
waiting for review. `demo_repo/` itself was not modified.

Test generation in numbers: 17 untested functions. Tests were kept for 6 of them. 9 failed
assertions became suspects: 3 for `total_units` (a real bug), the other 6 wrong expectations,
such as made-up MD5 digests. 39 tests crashed in their own setup and were only counted. Most of
them passed `None` or a string as the database connection.

## What it says about the agents

- **Precise where there is a test:** with a failing test and its error, the fine-tuned model fixed
  the bug in one attempt. That is the format it was trained on.
- **Useful but noisy without one:** generated tests and the model's review each found one bug the
  tools missed, but came with many more wrong claims. A person has to sort them, which is why
  suspects and model findings are reported separately and never become code changes on their own.
- **Static tools carry security:** every planted vulnerability and the secret were found by Bandit,
  Semgrep and the secret scanner, with no false positives here. The model added nothing there.

Files: `state.json` (whole run), `score.json`, `report.md` (what the user sees), `patch.diff`, and
`data/` (the stored patch and its validation record).
