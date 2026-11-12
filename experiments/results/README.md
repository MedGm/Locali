# Results

Every number in the main README comes from a folder here. Each folder holds the answers the
models gave (`samples.jsonl`), the scores (`summary.json`) and, for most, a README that says what
was run and what it shows. The folders are grouped in the order of the project.

`summary.json` (read by the web app's Results page) is built by
`experiments/scripts/report/export_results.py`; `REPRODUCTION.md` says which tables were rebuilt
from scratch and whether they matched.

## 1_baselines: the models before any training

| Folder | What it is |
|---|---|
| `harness_validation` | every benchmark scored with its official answers (all 100 %): the scoring works |
| `baselines` | four small models on the laptop CPU |
| `kaggle_baselines_20261012` | the same four models on Kaggle's GPU, all ten tasks |
| `kaggle_reference_20261012` | Qwen3.5-9B, the larger model to compare with |
| `kaggle_coder_baselines_20261024` | Qwen2.5-Coder-3B and 7B, the bigger bases |

## 2_finetune_1.5b: teaching the 1.5B model

| Folder | What it is |
|---|---|
| `data_mix_v1`, `data_mix_v2` | the training data, versions 1 and 2 |
| `finetune_qwen25_qlora_v1` | first fine-tune |
| `finetune_v2` | **the 1.5B result**: QLoRA, 16-bit LoRA and rsLoRA on data v2, compared |
| `finetune_qwen25_qlora_v2`, `finetune_qwen25_lora16_v2`, `finetune_qwen25_rslora_v2` | the three runs behind `finetune_v2` |
| `finetune_qwen25_qlora_v2_seed1234` | the same run with another seed |
| `finetune_phi4mini_qlora_v2`, `internal_eval_phi4mini_v2split` | Phi-4-mini on the same data (it got worse) |
| `internal_eval_qwen25_v1`, `internal_eval_v2split` | scores on my own held-out tasks |
| `format_transfer_qwen25_v1` | did it learn the format or the bugs? |
| `merge_qwen25_qlora_v2`, `merged_qwen25_qlora_v2_t4` | the merged model and its GGUF files, checked |
| `context_ablation_t4` | how much code and test the repair prompt needs |
| `feedback_t4` | repair with up to three tries and the test error |
| `multilang_t4`, `multilang_t4_rescore`, `multilang_t4_rescore2` | bug fixing in five other languages |

## 3_finetune_3b: teaching the 3B model

| Folder | What it is |
|---|---|
| `v3_bugs` | the 3,271 realistic bugs written by the teacher model |
| `finetune_qwen25_3b_qlora_mixv2` … `_mixv3b_diag`, `_mixv3s` | runs A, B, C, D and **E (the default)** |
| `finetune_qwen25_3b_qlora_mixv3f` | run F: the fix asked before the diagnosis (96 against 59 of 164 in the repair format) |
| `finetune_qwen25_3b_qlora_mixv3r` | run G: 1,441 real bugs added; 106 of 382 real bugs fixed against 54 for the base and 56 for run E |
| `multiple_comparisons` | **every base vs fine-tuned comparison**, with the correction for many tests |
| `capability_study` | why fine-tuning costs some code writing, in four steps |
| `epoch1_t4`, `keepdoc_t4`, `plan_t4` | three attempts to win the code writing back |
| `robust_3b_t4` | the repair gain with reworded prompts and with test feedback |
| `explain_t4` | explaining code (HumanEvalExplain) |

## 4_final_checks: the checks with rules written in advance

Protocol: `docs/preregistration-repair.md`.

| Folder | What it is |
|---|---|
| `condefects`, `quixbugs` | the two real-bug benchmarks, checked before use |
| `repair_prereg_t4` | **fixing real bugs**: the gain is not confirmed |
| `testgen2048_t4` | **writing tests with more room**: the gain holds |

## 5_laptop: running on the laptop

| Folder | What it is |
|---|---|
| `ladder_laptop` | 16, 8 and 4 bits: memory, speed, quality, energy (1.5B) |
| `laptop_3b_check` | can the 3B run on the laptop at all |
| `laptop_3b_energy`, `laptop_3b_energy_runD`, `laptop_3b_energy_runE` | energy per fixed bug, runs C, D and E |
| `speculative_laptop`, `speculative_3b_laptop` | guessing ahead (speculative decoding) |

## 6_gpu_serving: on a GPU, for comparison

| Folder | What it is |
|---|---|
| `serving_t4` | many requests at once, the KV cache, attention kernels |
| `speculative_t4` | guessing ahead on the GPU |

## 7_assistant: the whole assistant

| Folder | What it is |
|---|---|
| `agents_demo_repo` | the workflow on the demo project: one review vs the full workflow |
| `agents_api_tests` | integration and API tests on the demo project |
| `agents_runE` | **base vs run D vs run E on the demo project** |
| `repair_step_runE` | the repair step after 2026-11-11 on the laptop: 95, 102, 106 of 164 bugs within 1, 2, 3 attempts |
| `context_agents` | how much code the agents show the model |
| `feedback_repair` | the repair agent's runs with test feedback, laptop |
| `redteam` | my attack cases against the controls |

## 8_improve: what could still be gained without new data

Rules in `docs/preregistration-runs-fg.md`.

| Folder | What it is |
|---|---|
| `quant` | **run E at 16, 8, 5 and 4 bits**: the 4-bit laptop file loses 10 repair fixes, the 5-bit one keeps them |
| `scaling` | run E's adapter at lower strength and the D/E average: nothing to adopt |

## archive

Pilots, smoke tests and first attempts, kept because later results point to them:
`kaggle_pilot`, `finetune_smoke_run1`, `finetune_smoke_run2`, `speculative_*_pilot`,
`repair_prereg_t4_attempt1` (the run stopped by too-long prompts), `w1_spikes` and the `w0`/`w1`
files (the first week's checks).
