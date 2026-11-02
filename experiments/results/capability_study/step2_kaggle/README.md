# Capability study, step 2: prompt shape, sampling and log-probabilities

Step 1 left two questions. Does the prompt shape (code in the prompt vs English) pick the
fine-tuned models' answer style, and with it the HumanEval+ loss? And is the knowledge behind the
10 lost problems gone, or still in the model but no longer chosen by greedy decoding?

Models: base Qwen2.5-Coder-3B, run D (mix v3b-diag, deployed) and run E (mix v3s, self-distilled
replay). One Kaggle job, 2×T4, vLLM 0.29.0, FP16 + LoRA, 2026-11-02
(`training/kaggle/capability/kaggle_capability.py`, notebook commit c043d93, 2 h 4 min).
Tables: `uv run python experiments/scripts/capability_step2.py experiments/results/capability_study/step2_kaggle`
(output in `tables.md`).

Three parts:

1. **Prompt-shape swap, greedy.** HumanEval+ asked in English: signature plus docstring, no code
   stub (`humaneval_plus_english`). MBPP+ asked as a code stub: the English task written as the
   docstring of the reference solution's signature (`mbpp_plus_stub`). Both are in
   `evaluation/tasks/codegen.py`. Scored in the sandbox as usual.
2. **Sampling.** 20 answers per HumanEval+ problem at T = 0.8, top-p 0.95 (seed 3407), scored with
   the HumanEval+ tests. Unbiased pass@k.
3. **Log-probabilities.** Each model scores each model's greedy HumanEval+ answer (teacher
   forcing, `prompt_logprobs`).

## 1. The prompt shape changes the style, but explains only a third of the gap

| Model | HumanEval+ code (standard) | HumanEval+ English | MBPP+ English (standard) | MBPP+ code stub |
|---|---|---|---|---|
| Base | 81.0 | 79.8 | 64.5 | 69.5 |
| D | 71.8 | 73.6 | 64.2 | 68.2 |
| E | 74.2 | 76.1 | 64.2 | 68.2 |

Paired against the base on the same prompts:

| | HumanEval+ code | HumanEval+ English | MBPP+ English | MBPP+ code stub |
|---|---|---|---|---|
| D | −9.2 (22/7, p 0.008) | −6.1 (21/11, p 0.11) | −0.3 (p 1) | −1.3 (p 0.58) |
| E | −6.7 (19/8, p 0.05) | −3.7 (15/9, p 0.31) | −0.3 (p 1) | −1.3 (p 0.56) |

(Brackets: problems only the base solves / only the fine-tuned model solves, exact McNemar.)

- Asking HumanEval+ in English narrows the gap by about 3 points for both runs. The base loses
  1.2 points and the fine-tuned runs gain about 2. The remaining 6.1 and 3.7 points are no longer
  significant, but the direction is the same.
- MBPP+ as a code stub is easier for every model (4 to 5 points, base p 0.02). The fine-tuned runs
  stay level with the base in both shapes, so on MBPP+ the shape does not open a gap.
- Style follows the prompt shape for E, not for D:

| Answers with comments / output tokens | HumanEval+ code | HumanEval+ English | MBPP+ English | MBPP+ code stub |
|---|---|---|---|---|
| Base | 0.36 / 242 | 0.63 / 172 | 0.98 / 123 | 0.31 / 147 |
| D | 0.01 / 96 | 0.00 / 66 | 0.00 / 47 | 0.00 / 65 |
| E | 0.07 / 160 | 0.18 / 88 | 0.94 / 123 | 0.03 / 103 |

  E comments 94 % of its MBPP+ answers in the English shape and 3 % in the stub shape, so the
  step 1 hypothesis holds for E. D writes terse code with no comments whatever the prompt. The
  base also comments less when given a stub, so part of the effect is the base's own behaviour.
- On the 10 lost problems, the English prompt brings back 5 for E (0 with the code prompt) and 1
  for D. The base itself passes only 7 of them in English.

## 2. Sampling: nothing is forgotten, the probability moved

| Model | pass@1 | pass@5 | pass@20 | lost-10 solved at least once | lost-10 pass rate |
|---|---|---|---|---|---|
| Base | 76.6 | 88.8 | 92.0 | 9 / 10 | 56 % |
| D | 68.0 | 86.8 | 92.0 | 10 / 10 | 31 % |
| E | 72.9 | 87.0 | 92.0 | 9 / 10 | 30 % |

Samples passing out of 20 (base / D / E):

| Lost | 54 | 55 | 83 | 86 | 89 | 97 | 100 | 141 | 144 | 154 |
|---|---|---|---|---|---|---|---|---|---|---|
| | 16/12/15 | 17/6/0 | 0/3/4 | 3/3/4 | 14/5/10 | 16/9/5 | 12/13/11 | 9/2/2 | 20/6/6 | 4/3/2 |

| Gained | 59 | 64 | 99 | 160 |
|---|---|---|---|---|
| | 14/15/18 | 9/10/15 | 15/11/18 | 4/20/12 |

- pass@20 is identical (92.0 %, 150 of 163) for all three models. The fine-tuned models can still
  solve every problem the base can; the gap is in pass@1 and shrinks to 2 points at pass@5.
- On the lost 10 the pass rate halves (56 % → 31 %) but is not zero. Exceptions: E never solves
  55 (0 of 20), and the base never solves 83 under sampling (its greedy answer was lucky).
- The lost 10 were chosen because the base passed them greedily, so part of their drop is
  regression to the mean. The pass@1 gap under sampling (8.6 and 3.7 points) does not have this
  bias and is about the same size as the greedy gap.

## 3. Log-probabilities: a broad shift of style, not a few forgotten solutions

The base opens every answer with "```\npython\n" and the fine-tuned models with "```python\n". The
mismatched fence token costs about 10 nats on its own, so the first 3 answer tokens are left out
below.

Mean log-probability per token (in brackets: tokens below −2, i.e. probability under 14 %):

| Scored by \ answer of | Base | D | E |
|---|---|---|---|
| Base | −0.030 (0.0 %) | −0.105 (1.6 %) | −0.048 (0.5 %) |
| D | −0.107 (1.4 %) | −0.048 (0.0 %) | −0.050 (0.4 %) |
| E | −0.059 (0.8 %) | −0.056 (0.6 %) | −0.023 (0.0 %) |

- E stays about twice as close to the base as D does, in both directions, which matches its
  answer style (self-distilled replay).
- When D scores the base's greedy answer, the answer loses a median of 17.5 nats on problems both
  models solve (110), 25.0 nats on the problems D loses (22) and 22.7 on the rest. The shift is
  spread over all problems; the lost ones are only somewhat more affected.
- On the lost 10, the base's correct answer has 0 to 8 tokens below −2 under D (median 4.5) and 0
  to 6 under E. These are a handful of choice points per answer in 120 to 460 tokens (what they
  are is step 3). Everything else is still likely under D and E.

## What this says

- The fine-tuned 3B models have not lost the knowledge. Every problem the base solves is still
  solved by sampling (pass@20 equal), and the base's correct answers still get high probability
  apart from a few tokens.
- What fine-tuning changed is which answer greedy decoding picks: shorter answers without
  comments or a restated docstring, through a few changed decisions per answer. On HumanEval+
  these decisions go wrong more often than the base's. On MBPP+ they cost nothing.
- The prompt shape is part of the switch (E's style follows it; the English prompt narrows the gap
  by 3 points), but D's terse style does not depend on it.
- So this is not a dead end of the model; it is a change in the preferred answer. Next question
  (step 3): at the tokens where D and the base first diverge on the lost problems, what is chosen
  instead, and is the base's choice the first or second option for D?

## Files

- `results/<task>/<model>__fp16__kaggle-t4/`: greedy answers and scores, four tasks × three models.
- `samples/<model>.jsonl`: 20 samples per HumanEval+ problem (text, status, passed).
- `logprobs.jsonl`: per-token log-probabilities, 3 scorers × 3 answer sources × 163 problems.
- `logs/`: vLLM, setup and per-run logs; `kaggle_kernel.log` is the notebook log.
- `tables.md`: output of the analysis script.

Code and text written with AI help (Claude); every figure above comes from the files listed here.
