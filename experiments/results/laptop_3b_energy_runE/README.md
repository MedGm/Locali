# Energy per fixed bug: run E on the laptop

Same measurement as `../laptop_3b_energy_runD`, on run E (`../finetune_qwen25_3b_qlora_mixv3s`):
Q4_K_M GGUF built by `training/kaggle/gguf` with `ADAPTER=mixv3s`, llama.cpp 987498f with n-gram
lookup, 4 threads, one request at a time, greedy, all 164 HumanEvalFix problems, RAPL package
energy per request (2026-11-05, `experiments/scripts/laptop_runE.sh`, step 1).

| HumanEvalFix, laptop CPU, Q4_K_M + n-gram | Fixed | J per problem | J per fixed bug | s per problem | Output tokens |
|---|---|---|---|---|---|
| 3B run D, 2 Nov | 100 (61.0 %) | 278 | 456 | 15.2 | 69 |
| **3B run E, 5 Nov** | **95 (57.9 %)** | 277 | **478** | 15.2 | 68 |

Peak RAM 2.23 GB (same as D); n-gram acceptance 0.50 (D: 0.51).

Run D vs run E, paired on the same 164 problems: 12 fixed only by D, 7 only by E, exact McNemar
p = 0.36. The 5-bug gap is within noise; on the T4 at full precision E was slightly ahead
(`../finetune_qwen25_3b_qlora_mixv3s`). Energy per fixed bug follows the number fixed: the
energy per problem is the same.

`qwen2.5-coder-3b-locali-mixv3s.merge_report.json`: the merged model matches the adapter on top of
the base (largest logit difference 5.6e-5, same top-1 token on every checked position).

Code and text written with AI help (Claude); every figure above comes from the files in this folder.
