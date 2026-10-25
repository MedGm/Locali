**Locali fine-tuning data, version 4 of 4.** Previous: [locali-mix-v3](https://www.kaggle.com/datasets/elgorrimmohamed/locali-mix-v3). First: [locali-mix-v1](https://www.kaggle.com/datasets/elgorrimmohamed/locali-mix-v1).

The mixture of the current Locali model (Qwen2.5-Coder-3B + QLoRA). Project: [github.com/MedGm/Locali](https://github.com/MedGm/Locali).

## What changed from v3, and why

v3 doubled the 3B model's gains on logic bugs but cost refactoring (86.5 → 78.5 %) and left HumanEval+ six points below the base. Two changes, everything else as v3:

- **half of v2's one-line mutation bugs** (T1: 2,125 instead of 4,323, chosen by problem), suspected of pulling the model towards one-token patches
- **twice the general replay data** (3,587 rows of self-oss-instruct instead of 1,794), against forgetting

| Task | Train / val / test |
|---|---|
| T1 repair (mutations) | 2,125 / 252 / 212 |
| T1R realistic bugs | 2,898 / 173 / 149 |
| T2 tests | 2,619 / 148 / 134 |
| T3 review | 3,641 / 185 / 229 |
| T4 execution traces | 1,775 / 81 / 96 |
| replay | 3,587 / 199 / 197 |

## What it gave

QLoRA on Qwen2.5-Coder-3B, paired against the base on the same problems:

| | 3B base | 3B + v3 | **3B + v3b** |
|---|---|---|---|
| HumanEvalFix | 46.3 | 64.6 | **61.0** (p = 0.001 vs base) |
| Refactoring, behaviour preserved | 86.5 | 78.5 | **88.3** |
| Test generation, bugs caught | 62.2 | 82.3 | **80.5** |
| Bug detection accuracy | 61.6 | 63.1 | **69.5** |
| HumanEval+ | 81.0 | 74.8 | 73.0 |

Refactoring is restored and repair keeps most of its gain (the difference to v3 is not significant). HumanEval+ did not recover, so the mutation bugs were not its cause. A likely reason is that the fine-tuned models answer with bare code (88 tokens) while the base explains before coding (242 tokens); that remains to be tested.

## Sources and licences

CodeRM-UnitTest (Apache-2.0; tests generated with Llama-3.1-70B-Instruct, Llama 3.1 licence), self-oss-instruct-sc2-exec-filter-50k (ODC-BY), bugs and explanations written by Qwen3.5-9B (Apache-2.0).
