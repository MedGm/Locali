# Agent workflow on demo_repo

The full workflow (`backend/agents/workflow.py`) runs on `demo_repo/` and is scored against the
planted-flaw answer key (`security/demo_repo_flaws.json`) with `experiments/scripts/agent_eval.py`.

## Single agent vs multi-agent (deterministic runs, 2026-10-15)

Same model (fine-tuned Qwen2.5-Coder-1.5B, Q8_0, llama.cpp on the laptop CPU), same repository,
same scoring. The server ran with one slot and no prompt cache (`--parallel 1 --cache-ram 0`).
Two full-workflow runs (`det-multi-a`, `det-multi-b`) produced identical findings, suspects, fixes,
tests and a byte-identical patch, so these results reproduce.

| | Single agent | Multi-agent, no tools | Multi-agent + tools |
|---|---|---|---|
| What it does | one review call per file | review per function, test generation, debug loop | same, plus Ruff / Bandit / Radon / Semgrep / secret scan |
| Bugs fixed (of 5) | 0 | 1 | 1 |
| Bugs found on the right line | 0 | 1 (bulk boundary) | 2 (+ mutable default, by Ruff) |
| Real bug shown by generated tests | 0 | 1 (`total_units`) | 1 (`total_units`) |
| **Bugs caught in any way** | **0** | **3** | **4** |
| Vulnerabilities found (of 5) | 3 | 3 | **5** |
| Hardcoded secret found | no | no | **yes** |
| Model false positives | 3 | 17 | 17 |
| Tests after the patch | n/a | 6 (1 failing) → 17 (all passing), coverage 35 % → 78.5 % | same |
| Validated patch | none | yes | yes |
| Model calls / output tokens | 8 / 441 | 40 / 5,129 | 40 / 5,129 |
| Time | 85 s | 665 s | 669 s |

"Restock boundary" is left out of the bug counts even though the scorer marks it suspected: the
generated test behind it expected a wrong value.

- **Splitting the work is what finds and fixes bugs.** Reviewing a whole file in one call, the
  model mostly echoed lint-style remarks and found no bug at all. Working function by function, with
  tests and a sandboxed debug loop, it fixed one bug, found one more and exposed a third. The price is
  8× the time and 12× the output tokens, and 6× the false positives, because it reviews 17
  functions instead of 8 files.
- **Tools make security complete and add no noise.** The model alone found 3 of 5 vulnerabilities
  in both setups, a different 3 each time, and missed the SQL injection and the secret. The static
  tools found all of them, with no false positives, for 4 extra seconds.
- **The safety layer holds in every variant.** Both workflows ended in one validated patch, and
  `demo_repo/` was not modified.

An earlier set of runs (`ft-q8-run1`, `ft-q8-multi-notools`, `ft-q8-single`) used the server's
default settings (several slots, prompt cache), and the outputs changed between runs: the
no-tools run lost the bulk-boundary finding. Those runs are kept for the record, but the numbers
above come only from the deterministic runs.

## ft-q8-run1 (2026-10-15, default server settings)

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
