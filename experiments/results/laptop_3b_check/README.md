# Can the 3B run on the laptop?

Qwen2.5-Coder-3B-Instruct, official Q4_K_M GGUF @f74adce, llama.cpp 987498f, 4 threads, one request
at a time, greedy, on the first 20 problems of HumanEvalFix and HumanEval+ (2026-10-24,
`check3b.sh`). No energy: the RAPL counter was not readable. The 1.5B rows are the same 20
problems from `../speculative_laptop` (fine-tuned v2, Q4_K_M, 2026-10-19).

| 20 problems | Passed | Output tokens | Decode tok/s | Seconds per answer |
|---|---|---|---|---|
| **HumanEvalFix** | | | | |
| 3B base | 11 | 123 | 8.1 | 21.1 |
| 3B base + n-gram | 13 | | 11.5 | 17.0 |
| 1.5B fine-tuned | 10 | 68 | 15.9 | 7.3 |
| 1.5B fine-tuned + n-gram | 10 | 68 | 22.7 | 6.0 |
| **HumanEval+** | | | | |
| 3B base | 19 | 161 | 8.2 | 22.6 |
| 3B base + n-gram | 19 | | 11.8 | 16.6 |
| 1.5B fine-tuned | 18 | 122 | 15.8 | 9.3 |

Peak RAM of the 3B server: 2.35 GB (2.39 GB with n-gram lookup).

The 3B decodes at half the speed of the 1.5B, and the untrained 3B writes almost twice as many
tokens on repair (it explains its fix), so an answer takes about three times as long. N-gram lookup
makes it 1.4x faster per token. Twenty problems are too few to compare accuracy; the full-set
comparison is in `../kaggle_coder_baselines_20261024`. With n-gram lookup, 5 of the 20 repair
answers and 2 of the 20 HumanEval+ answers differ from plain decoding.
