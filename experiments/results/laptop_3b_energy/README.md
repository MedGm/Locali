# Energy per fixed bug: the fine-tuned 3B on the laptop

Run C (Qwen2.5-Coder-3B + QLoRA, mixture v3b), merged and exported to Q4_K_M (1.93 GB), llama.cpp
987498f with n-gram lookup (`--spec-type ngram-simple`), 4 threads, one request at a time, greedy,
all 164 HumanEvalFix problems, RAPL package energy per request (2026-10-26,
`../laptop_3b_check/check3b_param.sh` with `BENCHES=humanevalfix SETTINGS=ngram-simple`).

| HumanEvalFix, laptop CPU, Q4_K_M + n-gram | Fixed | J per problem | J per fixed bug | s per problem | Output tokens |
|---|---|---|---|---|---|
| 1.5B fine-tuned (v2), `../speculative_laptop`, 19 Oct | 49 (29.9 %) | 121 | 405 | 7.9 | 74 |
| **3B fine-tuned (run C)** | **100 (61.0 %)** | 272 | **446** | 14.9 | 68 |

Peak RAM 2.23 GB; n-gram acceptance 0.51.

- The 3B fixes twice as many bugs for 10 % more energy per fixed bug: per problem it costs 2.2x
  as much, but its answers are no longer, and it is right twice as often.
- On the laptop in Q4_K_M it solves exactly as many problems as in FP16 on the T4 (100 / 164).
- The two runs are a week apart; plain decoding of the same model on different days differed by
  up to 7 % in energy in this project, so the 10 % gap is within the range of day-to-day drift.
