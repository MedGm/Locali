# Context ablation: how much code and test context does repair need?

Run on 2026-10-15 on a Kaggle T4, vLLM FP16, greedy, 16 concurrent requests. Model: the merged
QLoRA v2 model from the Hub (`MedGm/Llama-Locali-Qwen2.5-Coder-1.5B@a1b0b11`). Commit `380995d`.
Items: the 212 held-out repair problems of the v2 test split (`internal_t1`). Same scoring for all
three: the fixed function must pass the problem's full test suite in the sandbox.

Prompt variants (`evaluation/tasks/context.py`):

- **standard**: the trained prompt, with the buggy function, the one failing test and its error.
- **full suite**: the problem's whole unit-test suite instead of the one failing test.
- **compressed**: the standard prompt with comments, docstrings and blank lines removed from the
  function and the test.

Parsing the trained prompt and rebuilding it reproduces all 212 prompts byte for byte, so each
variant differs from the standard only in the part it changes.

## Results

| Prompt | pass@1 | Input tokens | Output tokens | Mean request time | GPU energy (212 items) |
|---|---|---|---|---|---|
| standard | 63.7 | 364 | 241 | 8.4 s | 7.7 kJ |
| full suite | 62.3 | 806 | 243 | 10.4 s | 13.0 kJ |
| compressed | 61.3 | 315 | 213 | 7.2 s | 6.7 kJ |

Paired against standard (exact McNemar): full suite 10 / 7 items lost / gained, p = 0.63.
Compressed 13 / 8, p = 0.38.

Request times are under 16 concurrent requests, so they include queueing. They show the direction,
not a single-user latency.

## What it means

- **More context did not help.** The whole test suite more than doubles the prompt and uses 70 %
  more GPU energy, and the model fixes slightly fewer bugs. One failing test with its real error is
  enough for single-function repair. The agents will send that, not whole test files.
- **Compression is a cheap saving with a small, unconfirmed cost.** It trims 14 % of the input and
  11 % of the output (the model echoes the shorter function back) and 13 % of the energy, for 2.4
  points that are not significant with 212 items. I'll keep it as an option for long files rather
  than the default.
- The exact-fix rate drops for the compressed prompt (0.46 vs 0.60), but that is the metric, not the
  model. The fix is compared with the original function's AST, and the compressed answers come back
  without the docstring.

The merged model reproduces the adapter's answers on these items exactly: the same 135 of 212 pass
under the standard prompt in both runs.
