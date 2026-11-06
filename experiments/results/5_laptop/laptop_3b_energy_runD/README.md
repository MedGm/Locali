# Energy per fixed bug: run D on the laptop

Same measurement as `../laptop_3b_energy` (run C), on run D, the model Locali now deploys
(`../../3_finetune_3b/finetune_qwen25_3b_qlora_mixv3b_diag`): Q4_K_M GGUF (1.93 GB) built by `training/kaggle/deploy/gguf`
with `ADAPTER=mixv3b-diag`, llama.cpp 987498f with n-gram lookup, 4 threads, one request at a
time, greedy, all 164 HumanEvalFix problems, RAPL package energy per request (2026-11-02,
`../laptop_3b_check/check3b_param.sh` with `BENCHES=humanevalfix SETTINGS=ngram-simple`).

| HumanEvalFix, laptop CPU, Q4_K_M + n-gram | Fixed | J per problem | J per fixed bug | s per problem | Output tokens |
|---|---|---|---|---|---|
| 1.5B fine-tuned (v2), 19 Oct | 49 (29.9 %) | 121 | 405 | 7.9 | 74 |
| 3B run C, 26 Oct | 100 (61.0 %) | 272 | 446 | 14.9 | 68 |
| **3B run D, 2 Nov** | **100 (61.0 %)** | 278 | **456** | 15.2 | 69 |

Peak RAM 2.23 GB; n-gram acceptance 0.51 (C: 0.51).

Run D matches run C on the laptop as it did on the T4 (101 fixed there, 100 here). The 2 % energy
difference is within the day-to-day drift seen in this project (up to 7 %).
