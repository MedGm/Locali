# Run E at 16, 8, 5 and 4 bits on one llama.cpp build

Kaggle T4, llama.cpp 987498f built with CUDA, 2026-11-11/12, commit f28df7d
(`training/kaggle/evaluate/quant`). Run E's adapter is merged into the base, exported as an f16 GGUF
and quantized in the job; every file answers HumanEvalFix and HumanEval+ on the same server
settings, greedy. The importance matrix is computed from 200 training rows. Registered as
descriptive in `docs/preregistration-runs-fg.md`, with one rule for the laptop default.

## Results

Fixed or passed, then problems won / lost against f16 and against Q4_K_M (exact McNemar, not corrected).

| File | Size | HumanEvalFix (164) | vs f16 | vs Q4_K_M | HumanEval+ (163) | vs f16 |
|---|---|---|---|---|---|---|
| f16 | 6.17 GB | 103 (62.8 %) | | 12 / 2, p = 0.013 | 124 (76.1 %) | |
| Q8_0 | 3.29 GB | 103 (62.8 %) | 1 / 1 | 13 / 3, p = 0.021 | 125 (76.7 %) | 2 / 1 |
| Q5_K_M | 2.22 GB | 102 (62.2 %) | 1 / 2 | 12 / 3, p = 0.035 | 125 (76.7 %) | 5 / 4 |
| Q4_K_M, importance matrix | 1.93 GB | 96 (58.5 %) | 2 / 9, p = 0.065 | 6 / 3, p = 0.51 | 123 (75.5 %) | 5 / 6 |
| Q4_K_M (the laptop file) | 1.93 GB | 93 (56.7 %) | 2 / 12, p = 0.013 | | 121 (74.2 %) | 3 / 6, p = 0.51 |

## What it shows

- The gap between Kaggle (104 of 164 with vLLM at 16 bits) and the laptop (95 with Q4_K_M) is the
  4-bit file, not the server: llama.cpp at 16 bits fixes 103, and the same build with the 4-bit file
  fixes 93. Ten fixes of the fine-tuning gain (base 82, run E 104) are lost at 4 bits.
- 5 bits is enough: Q5_K_M fixes 102, with 0.3 GB more than Q4_K_M. Q8_0 adds nothing over it.
- The importance matrix gives back 3 of the 10 (not significant); it does not replace the fifth bit.
- Code writing does not show the loss (121 to 125 of 163, no difference significant).
- Rule for the laptop default: a file of at most 2.6 GB better than Q4_K_M on HumanEvalFix with
  p < 0.05. Q5_K_M meets it (12 won, 3 lost, p = 0.035). Two files were candidates; corrected for
  two tests (Holm) the p-value is 0.07, so the rule as written is met and a stricter reading is not.
  The laptop numbers for speed and energy were all measured at 4 bits and have to be measured again
  for the 5-bit file before the default changes.
- Run D against run E on the laptop (both at 4 bits) is therefore a comparison of two damaged files;
  their order there says little about the adapters.

The GGUF files are not kept (the job deletes them). `training/kaggle/deploy/gguf` builds the 5-bit
file with `QUANT=Q5_K_M ADAPTER=mixv3s`.

Code and text written with AI help (Claude).
