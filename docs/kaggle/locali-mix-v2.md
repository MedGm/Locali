**Locali fine-tuning data, version 2 of 4.** Previous: [locali-mix-v1](https://www.kaggle.com/datasets/elgorrimmohamed/locali-mix-v1). Next: [locali-mix-v3](https://www.kaggle.com/datasets/elgorrimmohamed/locali-mix-v3).

Mixture used for the first deployed Locali model (Qwen2.5-Coder-1.5B + QLoRA, published as [MedGm/Llama-Locali-Qwen2.5-Coder-1.5B](https://huggingface.co/MedGm/Llama-Locali-Qwen2.5-Coder-1.5B)). Project: [github.com/MedGm/Locali](https://github.com/MedGm/Locali).

## What changed from v1, and why

Every v1 row is kept unchanged and in the same split. Three additions answer the three problems v1 showed:

| Problem in v1 | Addition in v2 |
|---|---|
| Code reasoning fell 30.1 → 25.5 % | **T4 execution traces** (1,775 train): predict the value a call returns; every label is confirmed twice, by running the call and by the problem's own test |
| Repair improved only on bug types like the injected faults | **five more mutation operators** for T1 and T3: wrong variable, missing condition, missing term, missing call, wrong function (1,381 new bugs) |
| 40.6 % false bug reports on clean code | **500 verified clean reviews**: correct code whose answer lists only the tool findings, no bug |

| Task | Train / val / test |
|---|---|
| T1 repair | 4,323 / 252 / 212 |
| T2 tests | 2,619 / 148 / 134 |
| T3 review | 3,641 / 185 / 229 |
| T4 execution traces | 1,775 / 81 / 96 |
| replay | 1,794 / 86 / 113 |

Same decontamination and split rules as v1.

## What it gave, and what went wrong

QLoRA on Qwen2.5-Coder-1.5B, paired against the base model; the two main gains were confirmed with a second training seed:

- HumanEvalFix 25.0 → 36.0 % (p = 0.006), MBPP+ 56.2 → 62.1 % (p = 0.005)
- test generation, bugs caught 46.3 → 82.3 %; refactoring 69.9 → 93.9 %
- the CRUXEval drop of v1 is gone (28.7 %, not significantly different from the base)

A retrospective found the limit of this data. Every bug in it is a **one-line mutation**, and the model learned that shape, not repair in general. On HumanEvalFix it fixed operator bugs better than the 9B teacher (16 vs 13 of 25) but barely moved on missing logic (4 → 7 of 33, teacher: 22). On a stronger base (Qwen2.5-Coder-3B), this data even made repair slightly worse (46.3 → 43.9 %), and that model handed the buggy code back unchanged in 50 of 164 problems.

[Version 3](https://www.kaggle.com/datasets/elgorrimmohamed/locali-mix-v3) adds realistic bugs.

## Sources and licences

As v1: CodeRM-UnitTest (Apache-2.0; tests generated with Llama-3.1-70B-Instruct, Llama 3.1 licence), self-oss-instruct-sc2-exec-filter-50k (ODC-BY), explanations by Qwen3.5-9B (Apache-2.0). Also on Hugging Face as [MedGm/locali-mix-v2](https://huggingface.co/datasets/MedGm/locali-mix-v2).
