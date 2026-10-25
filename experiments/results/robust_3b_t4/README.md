# Is the v3 repair gain real? Reworded prompts and execution feedback (3B, T4)

Run B (Qwen2.5-Coder-3B + mixture v3) fixed 64.6 % of HumanEvalFix against 46.3 % for the base, but
half of its new training examples use the benchmark's own phrasing ("Fix bugs in f" with the failing
tests). This job (`training/kaggle/robust`, 2026-10-25, vLLM 0.29 on a T4, base model and both
adapters served together, greedy) asks the same 164 problems in two other ways and runs the
repair-with-feedback loop. Code ran in `evaluation/isolated.py`.

- **reworded**: same code and tests, in wording no training prompt uses ("A colleague's Python
  function f does not behave as intended. Its unit tests are below ...")
- **no tests**: only the documented function ("I think there is a mistake in this function, it does
  not do what its docstring says ...")

## Prompt wording

| % fixed (of 164) | 3B base | A: + v2 | B: + v3 | B vs base (lost / gained, p) | B vs A (p) |
|---|---|---|---|---|---|
| Benchmark prompt (`../finetune_qwen25_3b_qlora_mixv3`) | 46.3 | 43.9 | **64.6** | 11 / 41, 4e-5 | 5e-9 |
| **Reworded, with tests** | 40.2 | 38.4 | **56.7** | 14 / 41, **4e-4** | 1e-4 |
| **No tests, docstring only** | 73.8 | 59.2 | 75.0 | 22 / 24, 0.88 | 2e-4 |

- **The gain survives rewording**: +16.5 points with a prompt no training example uses, against +18.3
  with the benchmark's. It is not prompt matching.
- **It is a gain in repair from failing tests.** Given the docstring instead of the tests, the base
  is already at 73.8 % and run B is level with it (75.0 %, p = 0.88). The tests describe the intended
  behaviour less directly than a docstring, and that is the situation the v3 data trains.
- **The v2 data hurts repair from a specification** (A: 59.2 vs 73.8 %, p = 0.002); the v3 bugs
  remove that damage.

## Repair with execution feedback (up to 3 attempts)

| % fixed after 1 / 2 / 3 attempts | Plain errors | Explained errors, retries at T = 0.6 |
|---|---|---|
| 3B base | 46.3 / 51.2 / 51.8 | 46.3 / 53.7 / 54.9 |
| A: + v2 | 43.9 / 50.0 / 50.0 | 43.9 / 51.8 / 52.4 |
| **B: + v3** | 64.0 / 67.7 / 68.3 | 64.0 / 69.5 / **71.3** |

Gains from feedback, 1 vs 3 attempts (exact McNemar): base +9 (p = 0.004) and +14 (p = 1e-4),
A +10 and +14, B +7 (p = 0.016) and +12 (p = 5e-4). With explained errors and three attempts, run B
fixes 117 problems against 90 for the base (9 / 36, p = 7e-5), above the single-answer score of the
9B teacher (65.8 %). Problems never fixed whose three answers were all identical: base 22 of 74,
A 44 of 78, B 12 of 47 (explained errors); with plain errors 40, 55 and 15.

Run B's first attempt here is 64.0 % (105) against 64.6 % (106) in the fine-tuning run: one answer
differs between the two vLLM setups.

## Verdict for v3

The realistic bugs give a real, robust gain in test-driven repair (+16 to +18 points, significant
under any wording), work better with feedback, and make the model repeat itself far less. They do
not help when a docstring is given, where the base was already strong. The costs found in run B
remain: refactoring 78.5 vs 86.5 % for the base, and HumanEval+ six points below the base (from
the v2 data).
