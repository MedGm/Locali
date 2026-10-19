# Speculative decoding on a T4

Does a draft model or n-gram lookup make the 1.5B models cheaper per correct answer on a GPU, and
does fine-tuning change how well a stock draft model predicts the target?

Run on 2026-10-18/19 in a Kaggle notebook with 2 x T4 (`training/kaggle/speculative`), vLLM 0.29.0,
FP16, CUDA graphs, greedy, 768 tokens. GPU 0 served the fine-tune (QLoRA v2, merged), GPU 1 the
base model, at the same time; each setting got a fresh server. Draft model:
Qwen2.5-Coder-0.5B-Instruct@ea3f247 (the base 0.5B, not fine-tuned). Answers were scored on the VM
with `evaluation/isolated.py` (sockets disabled by the guard), through the normal task scoring.
Energy is the integral of `nvidia-smi` board power over each run's window, idle draw included.
Draft counts are vLLM's Prometheus counters before and after each run.

Settings: `none`; `draft-nK`, the draft model proposing K tokens; `ngram-n4`, prompt lookup of
2-4-grams proposing 4 tokens. Each at 1 concurrent request (one user) and 8.

## One request at a time

| Target | Benchmark | Setting | Passed | Speed-up | J per correct | Acceptance |
|---|---|---|---|---|---|---|
| Fine-tuned | HumanEval+ (163) | none | 99 | 1.00 | 325 | |
| | | draft-n2 | 100 | 1.88 | 172 (−47 %) | 0.94 |
| | | draft-n4 | 100 | 1.44 | 210 (−35 %) | 0.89 |
| | | draft-n8 | 99 | 1.33 | 240 (−26 %) | 0.79 |
| | | **ngram-n4** | 100 | **1.96** | **162 (−50 %)** | 0.64 |
| Fine-tuned | HumanEvalFix (164) | none | 59 | 1.00 | 332 | |
| | | draft-n2 | 59 | 1.47 | 223 (−33 %) | 0.87 |
| | | draft-n4 | 59 | 1.37 | 240 (−28 %) | 0.79 |
| | | draft-n8 | 59 | 0.96 | 334 (+1 %) | 0.63 |
| | | **ngram-n4** | 59 | **2.44** | **133 (−60 %)** | 0.82 |
| Base | HumanEval+ (163) | none | 106 | 1.00 | 439 | |
| | | draft-n2 | 106 | 1.60 | 269 (−39 %) | 0.95 |
| | | draft-n4 | 106 | 1.42 | 292 (−34 %) | 0.91 |
| | | draft-n8 | 106 | 1.24 | 332 (−24 %) | 0.84 |
| | | **ngram-n4** | 106 | **1.99** | **219 (−50 %)** | 0.59 |
| Base | HumanEvalFix (164) | none | 41 | 1.00 | 1007 | |
| | | draft-n2 | 41 | 1.40 | 680 (−32 %) | 0.96 |
| | | draft-n4 | 41 | 1.43 | 688 (−32 %) | 0.93 |
| | | draft-n8 | 41 | 1.47 | 676 (−33 %) | 0.87 |
| | | **ngram-n4** | 40 | **3.09** | **333 (−67 %)** | 0.77 |

Speed-up is wall time of plain decoding over wall time of the setting, for the same answers.

## Eight requests at a time

| Target | Benchmark | J per correct, none | best draft | ngram-n4 |
|---|---|---|---|---|
| Fine-tuned | HumanEval+ | 36.1 | 32.2 (n4, −11 %) | 30.3 (−16 %) |
| Fine-tuned | HumanEvalFix | 39.5 | 39.8 (n2, +1 %) | 27.6 (−30 %) |
| Base | HumanEval+ | 53.5 | 44.7 (n4, −16 %) | 46.1 (−14 %) |
| Base | HumanEvalFix | 141.7 | 115.2 (n8, −19 %) | 76.6 (−46 %) |

## What it says

- **Batching matters more than speculation.** Eight requests at a time cost 6-9x less energy per
  correct answer than one at a time, more than any speculative setting saves. Speculation is for
  the single-user case, which is how Locali runs.
- **For one user, n-gram lookup is the best setting everywhere:** half the energy per correct
  answer on HumanEval+, 60-67 % less on repair, where the answer mostly copies the buggy code in
  the prompt. It needs no second model. Under batching it is still the only setting that never
  costs more.
- **The draft model's best length is short (2 tokens) and longer drafts hurt the fine-tune most.**
  On repair with 8 drafted tokens the fine-tune is slower than plain decoding (0.96x, 0.63
  acceptance) while the base model still gains (1.47x, 0.87).
- **Fine-tuning moves the target away from the stock draft.** Acceptance is lower for the
  fine-tune than for the base model at every length on both benchmarks, the gap growing with
  length (repair: 0.87 vs 0.96 at 2 tokens, 0.63 vs 0.87 at 8). A draft distilled from, or
  fine-tuned with, the target is the obvious fix.
- **Correctness does not change.** Pass counts move by at most one problem. Answers are not
  bit-identical, though: 155-164 of 163/164 match plain decoding, because verifying several tokens
  at once changes FP16 rounding (as does batching: plain decoding at 1 and at 8 requests also
  differs on a few answers).

## Limits

One run per setting. Board energy over each run window includes idle draw, so it favours whatever
finishes sooner; that is the energy actually spent, but it is not the model's energy alone. The
base model writes longer answers (34.8k vs 22.3k tokens on HumanEval+), so compare the two models
per setting, not in absolute joules. Kaggle T4s are shared hardware.
