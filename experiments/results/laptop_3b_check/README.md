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

## The fine-tuned 3B (run C, mixture v3b)

Merged on Kaggle (`training/kaggle/gguf`; merged vs base + adapter max logit difference 4e-5, FP16
top-1 agreement 100 %, report in `qwen2.5-coder-3b-locali-mixv3b.merge_report.json`), exported to
Q4_K_M with llama.cpp 987498f (1.93 GB), run with `check3b_param.sh` on the same 20 + 20 problems
(2026-10-25).

| 20 problems | Passed | Output tokens | Decode tok/s | Seconds per answer |
|---|---|---|---|---|
| **HumanEvalFix** | | | | |
| 3B base | 11 | 123 | 8.1 | 21.1 |
| 3B fine-tuned | **16** | **65** | 8.0 | **14.6** |
| 3B fine-tuned + n-gram | 16 | 64 | 9.5 | **14.0** |
| **HumanEval+** | | | | |
| 3B base | 19 | 161 | 8.2 | 22.6 |
| 3B fine-tuned | 18 | 144 | 7.8 | 21.9 |
| 3B fine-tuned + n-gram | 18 | 143 | 11.0 | 16.5 |

Peak RAM 2.18 GB (2.22 GB with n-gram lookup). Fine-tuning halves the repair answers (65 vs 123
tokens), which brings a fix down to 14-15 s. N-gram lookup helps little on these short answers:
much of the 14 s is reading the prompt (prefill on four CPU cores), which speculation does not
speed up. The 1.5B fine-tune takes 6-7 s per fix; the 3B fixes far more bugs (61 vs 36 % on the
full benchmark).
