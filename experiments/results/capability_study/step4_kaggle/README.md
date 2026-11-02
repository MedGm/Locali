# Capability study, step 4: does making the fine-tuned models spell out their code help?

Step 3 found that a fine-tuned model's wrong HumanEval+ answer is one or two tokens away from a
right one, and that those tokens are where the base writes a step comment, a setup variable or a
helper while the fine-tuned model writes a one-liner. Two earlier prompts did not close the gap:
- a prose plan before the code (`../../plan_t4`);
- keeping the docstring (`../../keepdoc_t4`).

This step tests comments inside the code, on all 163 problems. It also tests the repetition
penalty that vLLM had applied by default (step 3).

Job: `training/kaggle/scaffold/kaggle_scaffold.py` (Kaggle 2×T4, vLLM 0.29.0, FP16 + LoRA,
kernel version 2, 2026-11-02, 55 min of generation). Greedy decoding, max 1,024 tokens. Tables:
`uv run python experiments/scripts/capability_step4.py experiments/results/capability_study/step4_kaggle`
(output in `tables.md`).

Conditions:
- **standard**: the usual HumanEval+ prompt.
- **comments**: the prompt asks for a short comment before each step (`humaneval_plus_comments`,
  `evaluation/tasks/codegen.py`).
- **scaffold**: the usual prompt, and the answer is started for the model with its own code fence,
  the stub (signature and docstring) and `    #`. The body has to open with a comment
  (`scaffold_prefix`).

Each condition was run with repetition penalty 1.05 (the model's `generation_config`, as in steps 2
and 3) and with 1.0 (no penalty). The standard prompt at 1.05 reproduces step 2 exactly (132, 117
and 121 passed).

## Results

HumanEval+ pass@1, 163 problems:

| Model | penalty | standard | comments | scaffold |
|---|---|---|---|---|
| Base | 1.05 | 81.0 | 76.1 | 71.2 |
| Base | 1.0 | 79.8 | 81.6 | 73.0 |
| D | 1.05 | 71.8 | 73.6 | 66.9 |
| D | 1.0 | 71.8 | 74.8 | 70.6 |
| E | 1.05 | 74.2 | 75.5 | 74.2 |
| E | 1.0 | 77.9 | 77.3 | 73.0 |

Each model against its own standard prompt at 1.05 (problems only the standard solves / only the
other condition solves, exact McNemar):

| Model | comments, 1.05 | scaffold, 1.05 | standard, 1.0 | comments, 1.0 | scaffold, 1.0 |
|---|---|---|---|---|---|
| Base | 12/4, p 0.08 | **21/5, p 0.003** | 8/6, p 0.79 | 8/9, p 1 | **18/5, p 0.01** |
| D | 4/7, p 0.55 | 22/14, p 0.24 | 9/9, p 1 | 9/14, p 0.40 | 19/17, p 0.87 |
| E | 8/10, p 0.81 | 17/17, p 1 | 4/10, p 0.18 | 10/15, p 0.42 | 17/15, p 0.86 |

Gap to the base in the same condition:

| Model | standard, 1.05 | comments, 1.05 | scaffold, 1.05 | standard, 1.0 | comments, 1.0 | scaffold, 1.0 |
|---|---|---|---|---|---|---|
| D | −9.2 (p 0.008) | −2.5 (p 0.61) | −4.3 (p 0.26) | −8.0 (p 0.04) | −6.7 (p 0.07) | −2.5 (p 0.54) |
| E | −6.7 (p 0.05) | −0.6 (p 1) | +3.1 (p 0.36) | −1.8 (p 0.66) | −4.3 (p 0.14) | 0.0 (p 1) |

Style at penalty 1.05:

| Model | condition | answers with a `#` | comment lines in the body | output tokens | lost-10 passed |
|---|---|---|---|---|---|
| Base | standard | – | 1.0 | 242 | 10 |
| Base | comments | 149 / 163 | 3.9 | 252 | 8 |
| Base | scaffold | all | 3.4 | 154 | 6 |
| D | standard | – | 0.0 | 97 | 0 |
| D | comments | 5 / 163 | 0.0 | 172 | 2 |
| D | scaffold | all | 2.4 | 88 | 4 |
| E | standard | – | 0.2 | 159 | 0 |
| E | comments | 67 / 163 | 1.6 | 211 | 4 |
| E | scaffold | all | 4.0 | 138 | 7 |

## What it says

- **No condition makes D or E better than their own standard prompt.** Every paired difference
  for D and E is within noise (p ≥ 0.18). Spelling out does not win back HumanEval+.
- **Fixes on the lost problems are paid for elsewhere.** The comment scaffold brings back 4 (D)
  and 7 (E) of the 10 problems lost in step 1. But it breaks about as many others: D 22 lost / 14
  gained, E 17 / 17. This matches step 3: at 3B, greedy correctness turns on single tokens. A
  push that rights one answer wrongs another.
- **The scaffold hurts the base clearly** (−9.8 points, p 0.003). Forcing a comment as the first
  line of the body is not neutral; the base usually restates the docstring and writes code first.
- **The gap closes in some conditions, but by the base dropping.** With the comment prompt at
  1.05, D is 2.5 points and E 0.6 behind. The base loses 4.9 points there; D gains 1.8 and E 1.3,
  both within noise.
- **D ignores the comment instruction.** It writes a `#` in 5 of 163 answers (base 149, E 67). It
  copies the signature and docstring instead, which is why its answers get longer. Run D lost
  instruction following for answer style; run E, trained on the base's own replay answers, kept
  part of it.
- **Repetition penalty:** turning it off changes nothing for D (117 both ways) and the base (−2).
  E gains 6 problems (4 lost / 10 gained, p 0.18), which shrinks E's gap to the base to 1.8 points
  (p 0.66). This is the closest any condition comes, but E's own change is not significant. The
  laptop's llama.cpp runs decode without the penalty, so the gap there may be smaller than on Kaggle.
  That is worth checking before the paper quotes a gap.

Across steps 1 to 4:
- The fine-tuned 3B models have not lost the ability. pass@20 is equal (step 2), and a wrong answer
  is one or two likely tokens from a right one (step 3).
- What they lost is greedy reliability on HumanEval+, and neither a prompt nor a forced start
  brings it back (this step, `plan_t4`, `keepdoc_t4`).
- The loss is spread over many fragile decisions rather than one missing habit. Training on the
  base's own answers (run E) reduces it, and E without the repetition penalty is within noise of
  the base.

## Files

- `answers.jsonl`: one row per model, condition, penalty and problem (3 × 3 × 2 × 163 = 2,934),
  with the full answer text, extracted code, status and output tokens.
- `logs/`: vLLM and setup logs; `kaggle_kernel.log` is the notebook log.
- `tables.md`: output of the analysis script.

Code and text written with AI help (Claude); every figure above comes from the files listed here.
