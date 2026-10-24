# Larger bases: Qwen2.5-Coder-3B and 7B

Question from the retrospective (`docs/retrospective.md`, item 3): is a larger model of the same
family a better starting point than more data for the 1.5B?

Generation: 2026-10-24, Kaggle 2 x T4, vLLM 0.29.0, eager mode, 16 concurrent requests, greedy,
768 tokens, same job and tasks as `../kaggle_baselines_20261012` (`QUEUES=coder`).
Qwen2.5-Coder-3B-Instruct@488639f in FP16 on GPU 0; Qwen2.5-Coder-7B-Instruct-AWQ@8e8ed24 (4-bit
AWQ, since the FP16 7B does not fit a T4) on GPU 1. Scored on the laptop in the Docker sandbox.
Licences: the 3B is under the Qwen research licence (non-commercial), the 7B under Apache-2.0.

## Untrained 3B and 7B against our fine-tuned 1.5B

| Task | 1.5B base | **1.5B fine-tuned (v2)** | 3B base | 7B base (AWQ) | 9B reference |
|---|---|---|---|---|---|
| HumanEvalFix | 25.0 | 36.0 | **46.3** | **59.2** | 65.8 |
| HumanEval+ | 65.0 | 62.0 | **81.0** | **80.4** | 84.0 |
| MBPP+ | 56.2 | 62.1 | 64.7 | **67.6** | 62.1 |
| CRUXEval-O | 30.1 | 28.7 | **42.2** | **51.7** | 54.5 |
| Completion | 35.6 | 36.8 | **56.4** | **59.5** | 62.0 |
| Test generation: bugs caught | 46.3 | **82.3** | 62.2 | 88.4 | 95.7 |
| Refactoring: behaviour preserved | 69.9 | **93.9** | 86.5 | 77.3 | 92.6 |
| Bug detection accuracy | 53.0 | (seed-dependent) | 61.6 | 65.5 | 72.0 |
| GPU energy per correct HumanEval+ solution (J) | 54 | | 64 | 57 | 421 |

Paired exact McNemar tests, fine-tuned 1.5B vs each base (problems only the fine-tune solved /
only the base solved):

| Task | vs 3B | vs 7B |
|---|---|---|
| HumanEvalFix | 59 vs 76 (18 / 35), p = 0.027 | 59 vs 97 (8 / 46), p = 1e-7 |
| HumanEval+ | 101 vs 132 (7 / 38), p = 3e-6 | 101 vs 131 (5 / 35), p = 1e-6 |
| MBPP+ | 234 vs 244 (31 / 41), p = 0.29 | 234 vs 255 (30 / 51), p = 0.026 |
| CRUXEval-O | 230 vs 338, p = 3e-17 | 230 vs 414, p = 6e-37 |
| Completion | 60 vs 92, p = 2e-6 | 60 vs 97, p = 4e-7 |

HumanEvalFix by bug type (problems fixed):

| Bug type | n | 1.5B fine-tuned | 3B base | 7B base |
|---|---|---|---|---|
| Operator misuse | 25 | 16 | 15 | 15 |
| Value misuse | 44 | 18 | 21 | 31 |
| Excess logic | 31 | 8 | 11 | 17 |
| Missing logic | 33 | 7 | 12 | 14 |
| Variable misuse | 23 | 6 | 13 | 15 |
| Function misuse | 8 | 4 | 4 | 5 |

## What it says

- **The untrained 3B repairs more bugs than our fine-tuned 1.5B** (46.3 vs 36.0 %, p = 0.027) and is
  far ahead on generation, reasoning and completion. Our fine-tune only matches it on operator
  bugs, the kind it was trained on.
- **The fine-tune keeps two real wins**: test generation (82.3 vs 62.2 % of bugs caught) and
  behaviour-preserving refactoring (93.9 vs 86.5 %), where the 3B is still weak. Those are the
  skills our data taught.
- **The 7B in 4-bit is close to the 9B on repair** (59.2 vs 65.8 %) at a seventh of its energy per
  correct answer on the T4.
- **Cost on a T4 is similar**: 54-64 J per correct HumanEval+ solution for 1.5B, 3B and 7B AWQ under
  batching. On the laptop CPU the 3B at Q4 needs about 2 GB of RAM and should decode at roughly half
  the 1.5B's speed; that has to be measured before it is chosen for deployment.

Proposal for v3: train the 3B (QLoRA fits a T4 easily) with the v2 test and refactoring data plus
the new realistic-bug data, and compare it with the 3B base and with v2 on the same tasks.
