# Code explanation (HumanEvalExplain) on T4

The brief lists code explanation among the benchmark tasks. This is OctoPack's HumanEvalExplain
(Muennighoff et al., 2023), Python, all 164 problems of `bigcode/humanevalpack@9a41762`:

1. the model gets a function without its docstring and explains what it does, in at most as many
   characters as the original docstring;
2. the same model gets only its explanation and the function's signature, and writes the function;
3. that code runs against the problem's tests in the Docker sandbox.

An explanation counts as good when the code written from it passes. No model judges another.
Two checks the original leaves to the instruction are enforced here: code blocks are removed from
the explanation before step 2, and the explanation is cut at the length limit. Every result also
counts explanations that contain a line of the hidden solution (20 characters or more): 0 in all
runs. Harness check: the original docstring as the explanation and the canonical solution as the
code pass 164/164 (`../../1_baselines/harness_validation/humanevalexplain`).

Run: Kaggle, 2 x T4, vLLM 0.29 with the models' generation_config defaults (as in the other Kaggle
runs), greedy, 768 tokens per call, 2026-11-05 (`training/kaggle/evaluate/explain`). Answers were generated
on Kaggle and scored on the laptop with `evaluation.rescore`.

## Result

| Problems passed, of 164 | Same model explains and writes | Explains; the 3B base writes |
|---|---|---|
| Qwen2.5-Coder-3B (base) | 112 (68.3 %) | 112 (68.3 %) |
| Run D (default model) | *95 (57.9 %)* | 108 (65.9 %) |
| Run E | 112 (68.3 %) | 120 (73.2 %) |
| Qwen2.5-Coder-1.5B (base) | 93 (56.7 %) | 105 (64.0 %) |
| 1.5B QLoRA v2 | 87 (53.0 %) | 102 (62.2 %) |

Italic: significantly worse than the base (paired exact McNemar, p < 0.05).

| Fine-tune vs its base | Same model writes: base only / fine-tune only, p | 3B base writes: base only / fine-tune only, p |
|---|---|---|
| Run D | 27 / 10, p = 0.008 | 14 / 10, p = 0.54 |
| Run E | 15 / 15, p = 1.0 | 9 / 17, p = 0.17 |
| 1.5B QLoRA v2 | 22 / 16, p = 0.42 | 20 / 17, p = 0.74 |

## Reading

- With the benchmark's own protocol, run D scores 10 points below its base. The second column
  separates the two skills the protocol mixes: when the same writer (the 3B base) turns every
  model's explanation into code, D's explanations are as good as the base's (p = 0.54). D's loss
  comes from writing the code, the same loss it shows on HumanEval+ (81.0 → 72.4 % greedy), not
  from explaining.
- Fine-tuning did not make any model explain worse. None of the training data is an explanation
  task (repair, tests, reviews, execution traces), so no gain was expected either. Run E's
  explanations are the best (73.2 %), but not significantly.
- The 3B base as writer also lifts the 1.5B models' scores by 7 to 9 points: a 1.5B explanation is
  often good enough, its own code is not.
- The fine-tuned models write shorter explanations and code: 129 output tokens per problem for D
  and 142 for the 1.5B fine-tune, against 188 and 342 for their bases (both calls together).

## Limits

- One run per model, greedy. The control uses one writer; another writer could rank the
  explanations differently.
- "Good" means "enough to rebuild code that passes the tests". An explanation can be correct and
  still miss an edge case the tests check, and fluent text that a person would find clearer gets
  no credit.

## Files

- `results/<model>/`: the benchmark protocol (both calls by the same model); `samples.jsonl` holds
  the explanation and the code of each problem, joined by a marker line.
- `writer_3b/<model>/`: the control, the explanations of `results/<model>` and code by the 3B base.
- `logs/`, `writer_3b/logs/`, `*.log`: Kaggle and vLLM logs.

Code and text written with AI help (Claude); every figure above comes from the files listed here.
