# QLoRA v2, second seed

The v2 fine-tune (`../finetune_qwen25_qlora_v2`, seed 3407) repeated with seed 1234: same data
(`locali-mix-v2`), recipe, Unsloth version (2026.10.4) and evaluation, on one Kaggle T4
(`training/kaggle/finetune-seed`, 2026-10-18). The seed sets the LoRA initialisation and the data
order (the recipe has no dropout). Answers were generated on Kaggle with the adapter in vLLM and scored on the laptop in
the Docker sandbox, as for v2.

Training: 14,151 examples, 2 epochs, 2.5 h; training loss 0.291 (v2: 0.291), validation loss 4.60
(v2: 4.75).

## The claims, with both seeds

Paired exact McNemar tests against the base model (Qwen2.5-Coder-1.5B-Instruct, same harness,
`../kaggle_baselines_20261012`):

| Benchmark | Base | Seed 3407 | p | Seed 1234 | p |
|---|---|---|---|---|---|
| MBPP+ (377) | 212 | 234 | 0.005 | 234 | 0.005 |
| HumanEvalFix (164) | 41 | 59 | 0.006 | 58 | 0.008 |
| HumanEval+ (163) | 106 | 101 | 0.51 | 105 | 1.0 |
| CRUXEval-O (800) | 241 | 230 | 0.31 | 244 | 0.84 |
| Completion (163) | 58 | 60 | 0.84 | 63 | 0.41 |

The two significant gains, code generation on MBPP+ and repair on HumanEvalFix, hold with the
second seed at the same size and significance. Neither seed changes HumanEval+, CRUXEval-O or
completion significantly.

## Seed 1234 against seed 3407

| Task | Seed 3407 | Seed 1234 |
|---|---|---|
| HumanEval+ pass@1 | 62.0 | 64.4 |
| MBPP+ pass@1 | 62.1 | 62.1 |
| HumanEvalFix pass@1 | 36.0 | 35.4 |
| CRUXEval-O pass@1 | 28.8 | 30.5 (16 / 30 problems differ, p = 0.05) |
| Bug detection (HumanEvalPack) accuracy | 65.6 | 54.6 |
| Bug detection, recall / precision | 0.64 / 0.66 | 0.95 / 0.53 |
| Bug detection in the trained format, accuracy | 65.9 | 65.6 |
| Internal repair (T1) pass@1 | 63.7 | 61.8 |
| Internal test generation, mutant kill rate | 0.33 | 0.37 |
| Internal review, clean specificity | 0.59 | 0.67 |
| Vulnerability detection accuracy | 51.5 | 53.5 |
| Refactoring, behaviour preserved | 93.9 | 93.3 |
| Secure code generation, insecure rate | 19.0 | 19.0 |

Most results agree within a few points. The exception is bug detection in the benchmark's own
format: seed 1234 answers "buggy" almost always (recall 0.95, precision 0.53), seed 3407 does not.
In the trained format both seeds give the same 66 %. So the yes/no answer in an unfamiliar format
depends on the seed and should not be reported from one run; the gains above should.

The adapter is not committed (82 MB); it is kept outside the repository.
