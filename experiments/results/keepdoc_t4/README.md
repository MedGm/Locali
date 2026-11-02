# Does keeping the docstring win back HumanEval+?

Second guess for the HumanEval+ loss (`../epoch1_t4`): the fine-tuned models drop the docstring and
its examples in most answers, and the answers that drop it fail more often. Test: ask for the
signature and docstring to be copied unchanged before the body (`humaneval_plus_keepdoc`,
evaluation/tasks/codegen.py). `training/kaggle/plan` with `TASKS=humaneval_plus_keepdoc`, vLLM
0.29.0, T4, FP16, run D adapter, greedy, 2026-11-02. Standard-prompt answers from `../plan_t4`
(same server setup).

| HumanEval+ (163) | Standard | Keep the docstring | only standard / only keepdoc | p | Docstring kept |
|---|---|---|---|---|---|
| 3B base | 132 (81.0 %) | **139 (85.3 %)** | 0 / 7 | **0.016** | 163 / 163 |
| 3B run D | 117 (71.8 %) | 121 (74.2 %) | 3 / 7 | 0.34 | 163 / 163 |

Base vs run D with the docstring kept: 85.3 vs 74.2 %, 22 lost / 4 gained (p = 5e-4).

## What it says

- **The guess is wrong.** Run D now keeps every docstring and still writes the same wrong
  programs: `HumanEval/97` still `(a % 10) * (b % 10)` without `abs`, `HumanEval/55` still plain
  recursion that times out. Dropping the docstring was a symptom, not the cause; the gap to the base
  even widens (11 points), because the instruction helps the base more.
- Side result: for the base model the instruction is a free +4.3 points (no problem lost).
- What is left: the fine-tuned models write terser code that handles fewer edge cases, on HumanEval+
  but not on MBPP+. Neither answer length (`../plan_t4`), the number of epochs (`../epoch1_t4`) nor
  the docstring explains it, so it lies in what the training answers look like. A candidate fix
  is to replace part of the replay data with the base model's own passing answers (self-distilled
  replay), so training keeps the base's coding style; that needs a new training run.
